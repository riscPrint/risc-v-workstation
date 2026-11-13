"""Compare measured and predicted structure changes."""
import json
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function


def register(sub):
    parser = sub.add_parser("ooo-delta", help="score paired RTL IPC changes with one base calibration")
    parser.add_argument("plan")
    parser.add_argument("--out", required=True)
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(func=command)


def command(args):
    from rvw.ooo.delta import delta
    try:
        print(json.dumps(delta(args.plan, args.out), indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2


def mcp_tools():
    def handler(job, **kw):
        return run_function(job, "rvw.ooo.delta", "delta", kw)
    return [ToolSpec("arch_ooo_delta", "Score paired RTL IPC changes using a fixed base calibration.",
                     schema({k: {"type": "string"} for k in ("plan", "out")}, ["plan", "out"]),
                     handler, long=True, side_effects="writes model configs and report under out",
                     native_tools=("native OoO", "native csim"))]
