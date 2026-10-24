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
    for action in ("check", "generate"):
        cmd = subs.add_parser(action, help="check C2 against a model" if action == "check" else "make a C2 trace from Spike")
        cmd.add_argument("--elf", required=True, type=Path)
        cmd.add_argument("--core", help="bundled platform name, or a label with --platform")
        cmd.add_argument("--platform", type=Path, help="per-core platform JSON")
        cmd.add_argument("--json", action="store_true")
        if action == "check":
            cmd.add_argument("--trace", required=True, type=Path)
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
                    result = check(args.trace, model, platform, args.history, sync=sync)
                finally:
                    model.close()
                    model = None
            inputs.capture.verify_tools()
            result["reproduction"] = inputs.metadata()
            code = 1 if result["status"] == "mismatch" else 0
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
        print(f"cosim error: {result['message']}", file=sys.stderr)
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
