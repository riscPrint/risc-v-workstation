"""Bug-pattern memory MCP tools (C7)."""
from rvw.mcp.spec import ToolSpec, schema

from .memory import Store

S = {"type": "string"}
STORE = {"store": {**S, "description": "JSON-lines store; default RVW_BUGMEM or ~/.local/share/rvw/bugmem.jsonl"}}
REPORT = {"report": {**S, "description": "bundle summary.json, bundle dir, C1 result.json or run dir"}}


def _add(report, cause, fix=None, scope=None, label=None, store=None):
    return Store(store).add(report, cause, fix, scope, label)


def _match(report, top=5, min_score=0.2, store=None):
    return Store(store).match(report, top, min_score)


def _list(store=None):
    s = Store(store)
    return {"store": str(s.path), "entries": s.entries()}


def _evaluate(top=3, store=None):
    return Store(store).evaluate(top)


def mcp_tools():
    return [
        ToolSpec("bugmem_add", "Store a failure report (bundle summary or C1 result) with its root cause, fix and "
                 "verified scope in the bug-pattern memory.",
                 schema({**REPORT, "cause": S, "fix": S, "scope": S, "label": S, **STORE}, ["report", "cause"]), _add),
        ToolSpec("bugmem_match", "Rank stored failures by signature similarity to a new failure report; returns "
                 "shared features and the stored cause/fix. A candidate is a lead, not a diagnosis.",
                 schema({**REPORT, "top": {"type": "integer", "minimum": 1, "default": 5},
                         "min_score": {"type": "number", "minimum": 0, "default": 0.2}, **STORE}, ["report"]),
                 _match, annotations={"readOnlyHint": True}),
        ToolSpec("bugmem_list", "List the stored failure signatures and causes.", schema({**STORE}, []), _list,
                 annotations={"readOnlyHint": True}),
        ToolSpec("bugmem_evaluate", "Leave-one-out matching accuracy over labelled stored failures.",
                 schema({"top": {"type": "integer", "minimum": 1, "default": 3}, **STORE}, []), _evaluate,
                 annotations={"readOnlyHint": True}),
    ]
