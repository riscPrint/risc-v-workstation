"""Workload CLI. No core is selected implicitly."""
import json
from . import core


def _run(args):
    try:
        if args.action == "list":
            value = core.load(core.recipe(args.recipe) if args.recipe else args.manifest)
        elif args.action == "build":
            value = core.build(core.recipe(args.recipe) if args.recipe else args.manifest, args.source, args.out, args.cc, args.bench)
        else:
            value = core.verify(args.build, args.out, args.oracle, args.timeout, args.trace)
        print(json.dumps(value, indent=2))
        return 0 if value.get("status") != "fail" else 2
    except (ValueError, OSError, KeyError, TypeError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}))
        return 2


def register(subparsers):
    p = subparsers.add_parser("workloads", help="pinned workloads and local SPEC hook")
    sub = p.add_subparsers(dest="action", required=True)
    for action in ("list", "build", "verify"):
        p = sub.add_parser(action)
        p.set_defaults(func=_run)
        p.add_argument("--json", action="store_true", help="output is always JSON")
        if action != "verify":
            choice = p.add_mutually_exclusive_group()
            choice.add_argument("--manifest", help="local manifest; default: Embench smoke set")
            choice.add_argument("--recipe", choices=("embench", "riscv-tests", "coremark", "zstd"))
        if action == "build":
            p.add_argument("--source")
            p.add_argument("--out", required=True)
            p.add_argument("--cc", default="riscv64-unknown-elf-gcc")
            p.add_argument("--bench", help="comma-separated workload IDs")
        if action == "verify":
            p.add_argument("--build", required=True, help="build.json")
            p.add_argument("--out", required=True, help="fresh reference result directory")
            p.add_argument("--oracle", default="spike", help="Spike or qemu-riscv64 executable")
            p.add_argument("--trace", action="store_true", help="capture Spike instruction categories")
            p.add_argument("--timeout", type=int, default=120)

    from rvw.common.subcommands import register_commands
    register_commands("rvw.workloads", sub)
