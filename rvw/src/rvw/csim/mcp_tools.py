"""MCP tools for trace-driven component studies."""
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function

S = {"type": "string"}
FMT = {**S, "enum": ["auto", "csim", "branch", "c2", "bt9", "champsim"], "default": "auto"}
SETS = {"type": "array", "items": S, "description": "KEY=VALUE overrides of dotted study keys"}
TRACES = {"type": "array", "items": S, "minItems": 1}


def _run(study, traces, job, format="auto", sets=None, timeout=None):
    return run_function(job, "rvw.csim.cli", "run_json", dict(study=study, traces=traces, format=format, sets=sets, timeout=timeout))


def _sweep(study, traces, params, job, **kw):
    return run_function(job, "rvw.csim.cli", "sweep_json", dict(study=study, traces=traces, params=params, **kw))


def _compare(study, trace, events, job, **kw):
    return run_function(job, "rvw.csim.cli", "compare_json", dict(study=study, trace=trace, events=events, **kw))


def _budget(study, sets=None):
    from .cli import _overrides
    from .study import budget
    return budget(_overrides(study, sets))


def _models():
    from .models import CATALOG
    return CATALOG


def _convert(source_format, source, out, values=False):
    from pathlib import Path
    from . import traces
    if source_format == "c2":
        return traces.from_c2(Path(source), Path(out), values=values)
    if source_format == "bt9":
        return traces.from_bt9(Path(source), Path(out))
    raise ValueError("source_format must be c2 or bt9")


def mcp_tools():
    return [
        ToolSpec("csim_run", "Run a trace-driven component study (direction predictors incl. TAGE-SC-L, BTB/RAS/ITTAGE, "
                 "front-end FTQ model, caches, replacement, prefetchers, TLB, store sets, value prediction) on C2, "
                 "CBP BT9, ChampSim or rvw.csim-trace/1 traces. Reports MPKI, coverage, accuracy and storage per trace. Runs as a job.",
                 schema({"study": S, "traces": TRACES, "format": FMT, "sets": SETS, "timeout": {"type": "number"}}, ["study", "traces"]),
                 _run, long=True, annotations={"readOnlyHint": True}),
        ToolSpec("csim_sweep", "Cartesian sweep of dotted study keys over traces, with storage-budget marking and a Pareto "
                 "front on one lower-is-better metric (e.g. direction_mpki, l1d_mpki). Runs as a job.",
                 schema({"study": S, "traces": TRACES, "params": {"type": "object", "additionalProperties": {"type": "array"}},
                         "format": FMT, "sets": SETS, "budget_kib": {"type": "number"},
                         "budget_scope": {**S, "enum": ["metadata", "all"], "default": "metadata"},
                         "metric": S, "jobs": {"type": "integer", "minimum": 1}, "timeout": {"type": "number"}},
                        ["study", "traces", "params"]),
                 _sweep, long=True, annotations={"readOnlyHint": True}),
        ToolSpec("csim_budget", "Storage accounting (bits/KiB per table) of a component study without running a trace.",
                 schema({"study": S, "sets": SETS}, ["study"]), _budget, annotations={"readOnlyHint": True}),
        ToolSpec("csim_models", "List the component models and their study keys.", schema({}), _models,
                 annotations={"readOnlyHint": True}),
        ToolSpec("csim_convert", "Convert a C2 RVFI trace (optionally with register values) or a CBP 2016 BT9 trace "
                 "into rvw.csim-trace/1.",
                 schema({"source_format": {**S, "enum": ["c2", "bt9"]}, "source": S, "out": S, "values": {"type": "boolean", "default": False}},
                        ["source_format", "source", "out"]), _convert, isolate=True),
        ToolSpec("csim_compare_rtl", "Compare a predictor model with explicit RTL predictor events (rvw.bp-events/1 or Kanata "
                 "#rvw prediction records) on the same C2 run, branch by branch. Missing identity or events gives inconclusive. Runs as a job.",
                 schema({"study": S, "trace": S, "events": S, "roi_start": {"type": "integer"}, "roi_end": {"type": "integer"},
                         "elf_sha256": S, "top": {"type": "integer", "default": 20}}, ["study", "trace", "events"]),
                 _compare, long=True, annotations={"readOnlyHint": True}),
    ]
