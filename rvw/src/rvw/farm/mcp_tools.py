from rvw.mcp.aliases import with_aliases
from dataclasses import replace
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import handler


def execute_json(hosts=None, manifest=None, adapter=None, identity_command=None, identity=None, out=None, jobs=1, timeout=600, action=None, root=None, core=None, suite=None, config=None, gate=None, run=None, reports=None):
    from .dashboard import dashboard
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
    manage = _lazy_manage
    budget = _lazy_budget
    triage = _lazy_triage
    select = _lazy_select
    workflow = _lazy_workflow
    plan = _lazy_plan
    tools = [ToolSpec("farm_plan", "Build one local/Kubernetes shard plan from a C1 manifest with hashed ELF inputs and expected cells.",
                 schema({"manifest": string, "adapter": array, "root": string, "image": string, "claim": string,
                         "shards": {"type": "integer", "minimum": 1}, "jobs": {"type": "integer", "minimum": 1},
                         "persistent": {"type": "boolean"}, "python": string,
                         "identity": {"type": "object"}, "resources": {"type": "object"}, "timeout": {"type": "number", "exclusiveMinimum": 0}},
                        ["manifest", "adapter", "root", "image", "claim"]), plan, long=True,
        side_effects='long-running; writes shard plan files under root', native_tools=(),
        ), ToolSpec("farm_live", "Read owner-scoped runs, trends, test history and failure clusters.",
                 schema({"root": string, "owner": string, "out": string}, ["root", "owner"]), live_json, long=True,
        side_effects='long-running; reads run evidence; creates queue database under root if absent; writes optional static export under out', native_tools=(),
        ), ToolSpec("farm_workflow", "Create, resume or inspect a command dependency plan. Completion is execution state, not verification.",
                 schema({"root": string, "action": string, "plan": {"type": "object"}, "workflow_id": string, "owner": string}, ["root"]),
                 workflow, long=True,
        side_effects='long-running; writes workflow and queue database under root; may submit configured commands', native_tools=(),
        ), ToolSpec("farm_select", "Advisory source-impact selection within a time budget. Unknown impacts keep tests mandatory.",
                 schema({"db": string, "changed": array, "catalogue": {"type": "object"}, "seconds": {"type": "number", "exclusiveMinimum": 0}},
                        ["db", "changed", "catalogue"]), select, long=True,
        side_effects='read-only; long-running', native_tools=(),
        ), ToolSpec("farm_triage", "Cluster recorded failures, compare regressions and bundle one representative. Never waive failures.",
                 schema({"root": string, "baseline": string, "known": string, "bundles": string, "core_env": string}, ["root"]), triage, long=True,
        side_effects='long-running; writes representative failure bundles under bundles', native_tools=(),
        ), ToolSpec("farm_budget", "Set cumulative queue budgets or report costs. CPU charge is declared cores times wall time.",
                 schema({"root": string, "scope": string, "limits": {"type": "object"},
                         "rate_per_core_hour": {"type": "number", "minimum": 0}}, ["root", "scope"]), budget,
        side_effects='writes budget and queue database under root', native_tools=(),
        ), ToolSpec("farm_batch", "Render, submit, inspect, cancel or collect explicit local/Kubernetes shards.",
                 schema({"plan": {"type": "object"}, "action": string, "executor": string, "root": string,
                         "ids": {"type": "array"}, "openapi": string}, ["plan"]), batch_json, long=True,
        side_effects='long-running; launches local commands or kubectl; writes shard artifacts under root; may cancel jobs; kubectl has no inventory ID', native_tools=None,
        ), ToolSpec("farm_queue", "Manage persistent local jobs. Completion is not DUT pass.",
                 schema({"root": string, "operation": string, "options": {"type": "object"}}, ["root"]),
                 queue_json, long=True,
        side_effects='long-running; writes queue database under root; may launch or cancel configured commands', native_tools=(),
        ), ToolSpec("farm_run", "Run native SSH shards. Complete is transport completeness, not a gate verdict.",
        schema({"hosts": {"type": "array", "items": {"type": "object"}, "minItems": 1},
                "manifest": string, "adapter": array, "identity_command": array,
                "identity": {"type": "object"}, "out": string,
                "jobs": {"type": "integer", "minimum": 1}, "timeout": {"type": "number", "exclusiveMinimum": 0}},
               ["hosts", "manifest", "adapter", "identity_command", "identity", "out"]),
        handler("rvw.farm.mcp_tools"), long=True,
        side_effects='long-running; launches SSH and configured remote native adapters; writes shard evidence under out', native_tools=(),
        ),
        ToolSpec("farm_notifications", "Export notification events. No external delivery is attempted.",
                 schema({"out": string}, ["out"]), handler("rvw.farm.mcp_tools", "notifications"), long=True,
        side_effects='long-running; reads notification events under out', native_tools=(),
        ),
        ToolSpec("farm_classify", "Classify identity-bound recorded repeats. Retain every DUT failure.",
                 schema({"reports": array}, ["reports"]), handler("rvw.farm.mcp_tools", "classify"), long=True,
        side_effects='read-only; long-running', native_tools=(),
        ),
        with_aliases(ToolSpec("farm_dashboard", "Write filtered C3/C4 history. Missing evidence remains visible.",
                 schema({"root": string, "out": string, **{k: string for k in ("core", "suite", "config", "gate", "run")}},
                        ["root", "out"]), handler("rvw.farm.mcp_tools", "dashboard"), long=True,
        side_effects='long-running; writes history dashboard under out', native_tools=(),
        ), run_id='run'),
        ToolSpec("farm_recover", "Read crash checkpoints. Missing final collection stays inconclusive.",
                 schema({"out": string}, ["out"]), handler("rvw.farm.mcp_tools", "recover"),
        side_effects='read-only; reads crash checkpoints under out', native_tools=(),
        ),
        ToolSpec("farm_cancel", "Cancel shards and confirm host process-group cleanup.",
                 schema({"out": string}, ["out"]), handler("rvw.farm.mcp_tools", "cancel"), long=True,
        side_effects='long-running; launches SSH; cancels remote process groups; writes cleanup state under out', native_tools=(),
        )]

    return [replace(t, handler=handler(t.handler.__module__, function=t.handler.__name__))
            if t.long and not t.wants_job else t for t in tools]


def queue_json(root, operation="list", options=None):
    from .service import manage
    return manage(root, operation, **(options or {}))


def batch_json(**options):
    from .batch import batch
    return batch(**options)


def live_json(root, owner, out=None):
    from .live import snapshot
    from .service import Queue
    if out:
        from .live_export import export
        return export(Queue(root), owner, out)
    return snapshot(Queue(root), owner)



def _lazy_manage(root, operation='list', **options):
    """Load the handler on first use."""
    from rvw.farm.service import manage as implementation
    return implementation(root, operation, **options)

def _lazy_budget(root, scope, limits=None, rate_per_core_hour=None):
    """Load the handler on first use."""
    from rvw.farm.costs import budget as implementation
    return implementation(root, scope, limits, rate_per_core_hour)

def _lazy_triage(root, baseline=None, known=None, bundles=None, core_env=None):
    """Load the handler on first use."""
    from rvw.farm.triage import triage as implementation
    return implementation(root, baseline, known, bundles, core_env)

def _lazy_select(db, changed, catalogue, seconds=600):
    """Load the handler on first use."""
    from rvw.farm.selection import select as implementation
    return implementation(db, changed, catalogue, seconds)

def _lazy_workflow(root, action='status', plan=None, workflow_id=None, owner='local'):
    """Load the handler on first use."""
    from rvw.farm.workflows import workflow as implementation
    return implementation(root, action, plan, workflow_id, owner)

def _lazy_plan(manifest, adapter, root, image, claim, shards=1, jobs=1, identity=None, resources=None, timeout=600, persistent=False, python='python3'):
    """Load the handler on first use."""
    from rvw.farm.shard_plan import plan as implementation
    return implementation(manifest, adapter, root, image, claim, shards, jobs, identity, resources, timeout, persistent, python)
