import json
from pathlib import Path
from .executor import execute
from .dashboard import dashboard


def register(sub):
    parser = sub.add_parser("farm", help="native SSH shards and static history dashboard")
    commands = parser.add_subparsers(dest="farm_action", required=True)
    run = commands.add_parser("run")
    for name in ("hosts", "manifest", "adapter", "identity-command", "identity", "out"):
        run.add_argument("--" + name, required=True)
    run.add_argument("--jobs", type=int, default=1)
    run.add_argument("--timeout", type=float, default=600)
    run.set_defaults(func=run_command)
    report = commands.add_parser("dashboard")
    report.add_argument("--root", required=True)
    report.add_argument("--out", required=True)
    report.set_defaults(func=dashboard_command)


def run_command(args):
    report = execute(json.loads(Path(args.hosts).read_text()), args.manifest,
                     json.loads(args.adapter), json.loads(args.identity_command),
                     json.loads(Path(args.identity).read_text()), args.out,
                     jobs=args.jobs, timeout=args.timeout)
    print(json.dumps(report))
    return 0 if report["status"] == "complete" else 3


def dashboard_command(args):
    print(json.dumps(dashboard(args.root, args.out)))
