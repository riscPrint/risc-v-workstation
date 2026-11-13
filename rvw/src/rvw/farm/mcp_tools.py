from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import handler
from .dashboard import dashboard


def execute_json(hosts=None, manifest=None, adapter=None, identity_command=None, identity=None, out=None, jobs=1, timeout=600, action=None, root=None, core=None, suite=None, config=None, gate=None, run=None, reports=None):
    if action == "notifications":
        from .notifications import notifications
        return notifications(out)
    if action == "classify":
        from .classify import classify
        return classify(reports)
    if action == "dashboard":
        return dashboard(root, out, core=core, suite=suite, config=config, gate=gate, run=run)
    if action == "recover":
        from .executor import recover
        return recover(out)
    if action == "cancel":
        return cancel_json(out)
    from .executor import execute
    return execute(hosts, manifest, adapter, identity_command, identity, out, jobs=jobs, timeout=timeout)


def cancel_json(out):
    from .executor import cancel
    return cancel(out)


def mcp_tools():
    string = {"type": "string"}
    array = {"type": "array", "items": string, "minItems": 1}
    from .service import manage
    return [ToolSpec("farm_queue", "Manage persistent local jobs. Completion is not DUT pass.",
                 schema({"root": string, "operation": string, "options": {"type": "object"}}, ["root"]),
                 queue_json, long=True), ToolSpec("farm_run", "Run native SSH shards. Complete is transport completeness, not a gate verdict.",
        schema({"hosts": {"type": "array", "items": {"type": "object"}, "minItems": 1},
                "manifest": string, "adapter": array, "identity_command": array,
                "identity": {"type": "object"}, "out": string,
                "jobs": {"type": "integer", "minimum": 1}, "timeout": {"type": "number", "exclusiveMinimum": 0}},
               ["hosts", "manifest", "adapter", "identity_command", "identity", "out"]),
        handler("rvw.farm.mcp_tools"), long=True),
        ToolSpec("farm_notifications", "Export notification events. No external delivery is attempted.",
                 schema({"out": string}, ["out"]), handler("rvw.farm.mcp_tools", "notifications"), long=True),
        ToolSpec("farm_classify", "Classify identity-bound recorded repeats. Retain every DUT failure.",
                 schema({"reports": array}, ["reports"]), handler("rvw.farm.mcp_tools", "classify"), long=True),
        ToolSpec("farm_dashboard", "Write filtered C3/C4 history. Missing evidence remains visible.",
                 schema({"root": string, "out": string, **{k: string for k in ("core", "suite", "config", "gate", "run")}},
                        ["root", "out"]), handler("rvw.farm.mcp_tools", "dashboard"), long=True),
        ToolSpec("farm_recover", "Read crash checkpoints. Missing final collection stays inconclusive.",
                 schema({"out": string}, ["out"]), handler("rvw.farm.mcp_tools", "recover")),
        ToolSpec("farm_cancel", "Cancel shards and confirm host process-group cleanup.",
                 schema({"out": string}, ["out"]), handler("rvw.farm.mcp_tools", "cancel"), long=True)]


def queue_json(root, operation="list", options=None):
    from .service import manage
    return manage(root, operation, **(options or {}))
