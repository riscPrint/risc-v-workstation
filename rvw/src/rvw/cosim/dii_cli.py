"""CLI for v1 socket replay and a core-owned Python hook."""
import hashlib
import importlib
import json
from pathlib import Path
import socket
import struct
from .dii import Token, compare, deadline, serve_connection


def endpoint(text):
    host, port = text.rsplit(":", 1)
    port = int(port)
    if not host or not 0 < port < 65536:
        raise ValueError("expected HOST:PORT")
    return host, port


def register(subs):
    cmd = subs.add_parser("dii", help="bounded TestRIG v1 socket transport")
    modes = cmd.add_subparsers(dest="dii_mode", required=True)
    replay = modes.add_parser("replay", help="compare a DII stream with a Sail DII server")
    replay.add_argument("--tokens", required=True, type=Path)
    replay.add_argument("--core-endpoint", required=True)
    replay.add_argument("--sail-endpoint", required=True)
    server = modes.add_parser("serve", help="connect a core-owned hook to a vengine")
    server.add_argument("--listen", default="127.0.0.1:5001")
    server.add_argument("--hook", required=True, help="Python MODULE:FACTORY implementing Hook")
    server.add_argument("--max-streams", type=int, default=1000)
    for mode in (replay, server):
        mode.add_argument("--timeout", type=float, default=30)
        mode.add_argument("--json", action="store_true")
        mode.set_defaults(func=run)


def run(args):
    result = {"schema": "rvw.dii/1", "protocol": "rvfi-dii-v1"}
    try:
        deadline(args.timeout)
        if args.dii_mode == "serve":
            if args.max_streams < 1:
                raise ValueError("max-streams must be positive")
            module, factory = args.hook.split(":")
            hook = getattr(importlib.import_module(module), factory)()
            with socket.socket() as listener:
                listener.bind(endpoint(args.listen))
                listener.listen(1)
                listener.settimeout(args.timeout)
                connection, _ = listener.accept()
                with connection:
                    serve_connection(connection, hook, timeout=args.timeout,
                                     max_streams=args.max_streams)
            result.update(status="served", streams_limit=args.max_streams)
        else:
            # Bound the input before allocating or opening either endpoint.
            with args.tokens.open("rb") as source:
                raw = source.read(8 * 65537 + 1)
            if not raw or len(raw) % 8 or len(raw) > 8 * 65537:
                raise ValueError("invalid or oversized token file")
            tokens = [Token.decode(raw[i:i+8]) for i in range(0, len(raw), 8)]
            if tokens[-1].cmd != 0 or tokens[-1].insn != 0:
                raise ValueError("token file must end with EndOfTrace")
            if not tokens[:-1] or any(t.cmd != 1 for t in tokens[:-1]):
                raise ValueError("expected one nonempty instruction stream")
            core_endpoint = endpoint(args.core_endpoint)
            sail_endpoint = endpoint(args.sail_endpoint)
            if core_endpoint == sail_endpoint:
                raise ValueError("core and Sail endpoints must differ")
            with socket.create_connection(core_endpoint, args.timeout) as core:
                with socket.create_connection(sail_endpoint, args.timeout) as sail:
                    result.update(compare(core, sail, tokens[:-1], timeout=args.timeout))
            result.update(tokens_sha256=hashlib.sha256(raw).hexdigest(),
                          core_endpoint=args.core_endpoint, sail_endpoint=args.sail_endpoint)
        code = {"match": 0, "served": 0, "mismatch": 1, "inconclusive": 3}[result["status"]]
    except (TimeoutError, EOFError) as exc:
        result.update(status="inconclusive", message=str(exc))
        code = 3
    except (OSError, ValueError, TypeError, AttributeError, ImportError, struct.error) as exc:
        result.update(status="error", message=str(exc))
        code = 2
    print(json.dumps(result))
    return code
