"""Run an explicit generic timing experiment."""
import json
from .core import run


def register(subparsers):
    parser = subparsers.add_parser("ooo", help="run a trace-driven OoO timing experiment")
    parser.add_argument("config")
    parser.add_argument("trace")
    parser.add_argument("--max-cycles", type=int, default=1_000_000)
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(func=command)


def command(args):
    try:
        result = run(args.config, args.trace, args.max_cycles)
    except (ValueError, OSError, KeyError, UnicodeError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(result, indent=None if args.json else 2))
    return 0
