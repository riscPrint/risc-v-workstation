"""Register `rvw cosim` without changing the platform CLI."""
import json
import os
from pathlib import Path
import subprocess
import struct
import sys
import tempfile
import math
from rvw.common.capture import CaptureError
from .inputs import Inputs
from .checker import SYNC_KINDS, check
from .spike import Spike, probe
from .generate import generate


def register(subparsers):
    parser = subparsers.add_parser("cosim", help="trace-driven architectural comparison")
    subs = parser.add_subparsers(dest="cosim_action", required=True)
    from .doctor import register as register_doctor
    register_doctor(subs)
    from .dii_cli import register as register_dii
    register_dii(subs)
    from .exchange_cli import register as register_exchange
    register_exchange(subs)
    from .vector_source import register as register_vector_source
    register_vector_source(subs)
    from .adjudicate import register as register_adjudicate
    register_adjudicate(subs)
    from .qemu import register as register_qemu
    register_qemu(subs)
    for action in ("check", "generate", "live"):
        cmd = subs.add_parser(action, help={"check": "check C2 against a model", "generate": "make a C2 trace from Spike",
                                          "live": "launch an adapter and check C2 during simulation"}[action])
        cmd.add_argument("--elf", required=True, type=Path)
        cmd.add_argument("--core", help="bundled platform name, or a label with --platform")
        cmd.add_argument("--platform", type=Path, help="per-core platform JSON")
        cmd.add_argument("--json", action="store_true")
        if action in ("check", "live"):
            if action == "check":
                cmd.add_argument("--trace", required=True, type=Path)
            else:
                import argparse
                cmd.add_argument("--lockstep", action="store_true", help="block the simulator until each C2 record is checked")
                cmd.add_argument("--out", required=True, type=Path, help="new simulator output directory")
                cmd.add_argument("--simulator", nargs=argparse.REMAINDER, required=True,
                                 help="adapter command; use {elf} and {out} placeholders")
            cmd.add_argument("--model", choices=("spike", "sail"), default="spike")
            cmd.add_argument("--history", type=int, default=10)
            cmd.add_argument("--strict", action="store_true", help="disable all synchronization (" + ", ".join(SYNC_KINDS) + ")")
            cmd.add_argument("--strict-sync", type=sync_kinds, default=(), metavar="KINDS",
                             help="comma-separated synchronization kinds to disable: " + ", ".join(SYNC_KINDS))
            cmd.add_argument("--sail", default=os.environ.get("RVW_SAIL", "sail_riscv_sim"))
            cmd.add_argument("--sail-config", type=Path, help="Sail model config matching the platform")
            cmd.add_argument("--timeout", type=float, default=120)
        else:
            cmd.add_argument("--out", required=True, type=Path)
            cmd.add_argument("--max-instructions", type=int, default=1000000)
        cmd.set_defaults(func=run)


def sync_kinds(text):
    kinds = tuple(k for k in str(text).split(",") if k)
    unknown = set(kinds) - set(SYNC_KINDS)
    if unknown:
        raise ValueError(f"unknown synchronization kinds {sorted(unknown)}; choose from {', '.join(SYNC_KINDS)}")
    return kinds


def calculate(args):
    """Return the exact result and exit status used by CLI and MCP."""
    model = None
    try:
        with tempfile.TemporaryDirectory(prefix="rvw-cosim-") as directory:
            inputs = Inputs(args, directory)
            args, platform = inputs.args, inputs.platform
            if args.cosim_action == "generate":
                if args.max_instructions < 1:
                    raise ValueError("--max-instructions must be positive")
                probe(platform, args.elf, shim=inputs.shim, executable=inputs.tool.path,
                      env=inputs.child_env, pythonpath=inputs.pythonpath)
                result = generate(args.elf, args.out, platform, args.max_instructions,
                                  shim=inputs.shim, verify=inputs.capture.verify_tools,
                                  elf_source=inputs.identity("elf")["resolved"])
            else:
                if args.history < 0 or not math.isfinite(args.timeout) or args.timeout <= 0:
                    raise ValueError("history must be nonnegative and timeout must be finite and positive")
                if args.cosim_action == "live" and args.model != "spike":
                    raise ValueError("live checking requires Spike; Sail is offline only")
                if args.model == "spike":
                    probe(platform, args.elf, shim=inputs.shim, executable=inputs.tool.path,
                          env=inputs.child_env, pythonpath=inputs.pythonpath)
                    model = Spike(platform, args.elf, shim=inputs.shim)
                else:
                    from .sail import Sail
                    model = Sail(platform, args.elf, args.trace, args.sail,
                                 args.sail_config, args.timeout, env=inputs.child_env,
                                 default_config=inputs.default_sail_config)
                sync = () if args.strict else tuple(k for k in SYNC_KINDS if k not in args.strict_sync)
                try:
                    if args.cosim_action == "live":
                        from .online import launch_online
                        command = [part.replace("{elf}", str(args.elf)).replace("{out}", str(args.out))
                                   for part in args.simulator]
                        result = launch_online(command, model, platform, lockstep=getattr(args, "lockstep", False), out=args.out,
                                               reproduction=inputs.metadata(), timeout=args.timeout,
                                               env=inputs.child_env, history=args.history, sync=sync)
                    else:
                        result = check(args.trace, model, platform, args.history, sync=sync)
                        # Same rule as live and lockstep: a matching prefix of a run that did not
                        # end is not a match (exit 3). `scope` still names the compared prefix.
                        if result["status"] == "match" and result.get("trace_complete") is not True:
                            result.update(status="inconclusive", cause="trace_incomplete")
                finally:
                    model.close()
                    model = None
            inputs.capture.verify_tools()
            result["reproduction"] = inputs.metadata()
            code = 2 if result["status"] == "error" else 3 if result["status"] == "inconclusive" else 1 if result["status"] == "mismatch" else 0
    except CaptureError as exc:
        result = {"schema": "rvw.cosim/1", "status": "inconclusive", "cause": exc.cause,
                  "message": str(exc)}
        code = 3
    except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration, subprocess.SubprocessError, struct.error) as exc:
        result = {"schema": "rvw.cosim/1", "status": "error", "message": str(exc) or type(exc).__name__}
        code = 2
    finally:
        if model is not None:
            model.close()
    return result, code


def run(args):
    result, code = calculate(args)
    if args.json:
        print(json.dumps(result))
    elif result["status"] == "mismatch":
        m = result["mismatch"]
        print(f"mismatch at index {m['instruction_index']}, order {m['order']}, cycle {m['cycle']}, pc {m['pc']}: {m['disassembly']}")
        for key, values in m["differences"].items():
            def display(value):
                return hex(value) if type(value) is int and key not in ("rd", "mode") else repr(value)
            print(f"  {key}: expected {display(values['expected'])}, actual {display(values['actual'])}")
        print("last matching instructions:")
        for e in m["last_matching"]:
            print(f"  {e['order']} {e['pc']} {e['disassembly']}")
        print("register diff: " + json.dumps(m["register_diff"]))
    elif result["status"] in ("error", "inconclusive"):
        print(f"cosim error: {result.get('message', result.get('cause', 'unknown'))}", file=sys.stderr)
    else:
        print(f"{result['status']}: {result['instructions']} instructions" +
              (f", {result['synchronized']} synchronizations ({result['scope']})" if "synchronized" in result else ""))
    return code


def execute_json(action: str, **options) -> dict:
    """MCP entry point. The Sail executable comes only from RVW_SAIL (or sail_riscv_sim on
    PATH), never from a tool argument, so a caller cannot make the server run another program."""
    from argparse import Namespace
    defaults = dict(elf=None, core=None, project=None, platform=None, trace=None, model="spike", history=10,
                    strict=False, strict_sync=(), sail_config=None, timeout=120, out=None,
                    max_instructions=1000000)
    unknown = options.keys() - defaults.keys()
    if unknown:
        raise TypeError(f"unknown options: {sorted(unknown)}")
    defaults.update(options)
    defaults["sail"] = os.environ.get("RVW_SAIL", "sail_riscv_sim")
    defaults["strict_sync"] = sync_kinds(",".join(defaults["strict_sync"]))
    for key in ("elf", "platform", "trace", "sail_config", "out"):
        if defaults[key] is not None:
            defaults[key] = Path(defaults[key])
    if action == "generate":
        defaults.pop("trace")  # metadata distinguishes generation by presence of trace
    result, _ = calculate(Namespace(cosim_action=action, **defaults))
    return result
