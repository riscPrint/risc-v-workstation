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
    live = commands.add_parser("live")
    live.add_argument("--root", required=True)
    live.add_argument("--owner", required=True)
    live.set_defaults(func=live_command)
    workflow = commands.add_parser("workflow")
    workflow.add_argument("--root", required=True)
    workflow.add_argument("--action", choices=("create", "status", "advance", "capabilities"), default="status")
    workflow.add_argument("--plan")
    workflow.add_argument("--workflow-id")
    workflow.add_argument("--owner", default="local")
    workflow.set_defaults(func=workflow_command)
    selection = commands.add_parser("select")
    selection.add_argument("--db", required=True)
    selection.add_argument("--changed", required=True, help="JSON array of changed source paths")
    selection.add_argument("--catalogue", required=True)
    selection.add_argument("--seconds", type=float, default=600)
    selection.set_defaults(func=selection_command)
    triage = commands.add_parser("triage")
    triage.add_argument("--root", required=True)
    triage.add_argument("--baseline")
    triage.add_argument("--known")
    triage.add_argument("--bundles")
    triage.set_defaults(func=triage_command)
    costs = commands.add_parser("budget")
    costs.add_argument("--root", required=True)
    costs.add_argument("--scope", required=True)
    costs.add_argument("--limits", help="JSON core_hours, wall_seconds and jobs limits")
    costs.add_argument("--rate-per-core-hour", type=float)
    costs.set_defaults(func=budget_command)
    batch = commands.add_parser("batch")
    batch.add_argument("--plan", required=True)
    batch.add_argument("--action", choices=("render", "submit", "status", "cancel", "collect"), default="render")
    batch.add_argument("--executor", choices=("local", "k8s"), default="local")
    batch.add_argument("--root", default=".")
    batch.add_argument("--ids", default="[]")
    batch.set_defaults(func=batch_command)
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


def batch_command(args):
    from .batch import batch
    print(json.dumps(batch(json.loads(Path(args.plan).read_text()), args.action, args.executor, args.root, json.loads(args.ids))))


def budget_command(args):
    from .costs import budget
    print(json.dumps(budget(args.root, args.scope, json.loads(args.limits) if args.limits else None, args.rate_per_core_hour)))


def triage_command(args):
    from .triage import triage
    print(json.dumps(triage(args.root, args.baseline, args.known, args.bundles), default=str))


def selection_command(args):
    from .selection import select
    print(json.dumps(select(args.db, json.loads(args.changed), json.loads(Path(args.catalogue).read_text()), args.seconds)))


def workflow_command(args):
    from .workflows import workflow
    print(json.dumps(workflow(args.root, args.action, json.loads(Path(args.plan).read_text()) if args.plan else None, args.workflow_id, args.owner)))


def live_command(args):
    from .live import snapshot
    from .service import Queue
    print(json.dumps(snapshot(Queue(args.root), args.owner)))
