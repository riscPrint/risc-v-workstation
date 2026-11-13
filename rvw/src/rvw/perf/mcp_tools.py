"""Pipeline performance tools using the CLI's shared Python calculation."""
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function

S = {"type": "string"}
OPTIONS = {"window": {"type": "integer", "minimum": 1, "default": 1000},
           "isa": {**S, "enum": ["none", "riscv"], "default": "none"},
           "lane": {**S, "default": "0"}, "queue_stage": S, "issue_stage": S, "head_stage": S,
           "in_order_retirement": {"type": "boolean", "default": False}}


def _report(path: str, job, **options):
    return run_function(job, "rvw.perf.cli", "execute_json", {"paths": [path], **options})


def _compare(base: str, candidate: str, job, **options):
    return run_function(job, "rvw.perf.cli", "execute_json", {"paths": ["compare", base, candidate], **options})


def _topdown(events: str, job, c2: str | None = None, result: str | None = None, elf: str | None = None):
    return run_function(job, "rvw.perf.cli", "execute_json", {"paths": ["topdown", events], "c2": c2, "result": result, "elf": elf})


def _topdown_compare(base: str, candidate: str, job):
    return run_function(job, "rvw.perf.cli", "execute_json", {"paths": ["topdown-compare", base, candidate]})


def mcp_tools():
    return [
        ToolSpec("perf_topdown_compare", "Compare top-down slot counts for the same ELF.",
                 schema({"base": S, "candidate": S}, ["base", "candidate"]),
                 _topdown_compare, long=True, annotations={"readOnlyHint": True}, side_effects="read-only", native_tools=()),
        ToolSpec("perf_topdown", "Commit-slot top-down attribution (retiring, bad speculation, back-end bound, front-end "
                 "bound) from a run's topdown_* counter probes, checked against the C2 retirement count.",
                 schema({"events": S, "c2": S, "result": S, "elf": S}, ["events"]),
                 _topdown, long=True, annotations={"readOnlyHint": True}, side_effects='read-only; long-running', native_tools=()),
        ToolSpec("perf_report", "Measure pipeline stage residence, IPC windows, discarded work and inferred retirement bubbles "
                 "from a Kanata 0004 log (or load a saved report). Large logs run as a job. Stage names are explicit options.",
                 schema({"path": S, **OPTIONS, "result": {**S, "description": "C1 result.json for counter cross-check"}}, ["path"]),
                 _report, long=True, annotations={"readOnlyHint": True}, side_effects='read-only; long-running', native_tools=()),
        ToolSpec("perf_compare", "Compare two pipeline logs or rvw.perf/1 reports to find performance changes above tolerance. "
                 "Analysis settings must match; differences are magnitudes, not statistical significance. Runs as a job.",
                 schema({"base": S, "candidate": S, **OPTIONS,
                         "tolerance": {"type": "number", "minimum": 0, "default": .05}}, ["base", "candidate"]),
                 _compare, long=True, annotations={"readOnlyHint": True}, side_effects='read-only; long-running', native_tools=()),
    ]
