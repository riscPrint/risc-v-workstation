import json
from pathlib import Path
from .executor import execute, cancel, recover
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
    stop = commands.add_parser("cancel")
    stop.add_argument("--out", required=True)
    stop.set_defaults(func=cancel_command)
    notify = commands.add_parser("notifications")
    notify.add_argument("--out", required=True)
    notify.set_defaults(func=notifications_command)
    classification = commands.add_parser("classify")
    classification.add_argument("reports", nargs='+')
    classification.set_defaults(func=classify_command)
    recovery = commands.add_parser("recover")
    recovery.add_argument("--out", required=True)
    recovery.set_defaults(func=recover_command)
    queue = commands.add_parser("queue")
    queue.add_argument("--root", required=True)
    queue.add_argument("--operation", choices=("submit", "list", "work", "recover", "cancel", "events"), default="list")
    queue.add_argument("--options", default="{}", help="JSON operation arguments")
    queue.set_defaults(func=queue_command)
    serve = commands.add_parser("serve")
    serve.add_argument("--root", required=True)
    serve.add_argument("--tokens", required=True, help="JSON file mapping tokens to owners")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.set_defaults(func=serve_command)
    report = commands.add_parser("dashboard")
    report.add_argument("--root", required=True)
    report.add_argument("--out", required=True)
    for name in ("core", "suite", "config", "gate", "run"):
        report.add_argument("--" + name)
    report.set_defaults(func=dashboard_command)


def run_command(args):
    report = execute(json.loads(Path(args.hosts).read_text()), args.manifest,
                     json.loads(args.adapter), json.loads(args.identity_command),
                     json.loads(Path(args.identity).read_text()), args.out,
                     jobs=args.jobs, timeout=args.timeout)
    print(json.dumps(report))
    return 0 if report["status"] == "complete" else 3


def dashboard_command(args):
    print(json.dumps(dashboard(args.root, args.out, **{k: getattr(args, k) for k in ("core", "suite", "config", "gate", "run")})))


def cancel_command(args):
    report = cancel(args.out)
    print(json.dumps(report))
    return 0 if report["status"] == "cancelled" else 3


def recover_command(args):
    report = recover(args.out)
    print(json.dumps(report))
    return 0 if report['status'] == 'complete' else 3


def classify_command(args):
    from .classify import classify
    print(json.dumps(classify(args.reports)))


def notifications_command(args):
    from .notifications import notifications
    print(json.dumps(notifications(args.out)))


def queue_command(args):
    from .service import manage
    print(json.dumps(manage(args.root, args.operation, **json.loads(args.options))))


def serve_command(args):
    from .http import server
    with server(args.root, json.loads(Path(args.tokens).read_text()), args.host, args.port) as http:
        http.serve_forever()
