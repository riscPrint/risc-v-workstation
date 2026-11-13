"""MCP tools for trace-driven component studies."""
from rvw.mcp.spec import ToolSpec, schema
from rvw.mcp.worker import run_function

S = {"type": "string"}
FMT = {**S, "enum": ["auto", "csim", "branch", "c2", "bt9", "spike", "champsim"], "default": "auto"}
SETS = {"type": "array", "items": S, "description": "KEY=VALUE overrides of dotted study keys"}
TRACES = {"type": "array", "items": S, "minItems": 1}


def _run(study, traces, job, format="auto", sets=None, timeout=None):
    return run_function(job, "rvw.csim.cli", "run_json", dict(study=study, traces=traces, format=format, sets=sets, timeout=timeout))


def _sweep(study, traces, params, job, **kw):
    return run_function(job, "rvw.csim.cli", "sweep_json", dict(study=study, traces=traces, params=params, **kw))


def _compare(study, trace, events, job, **kw):
    return run_function(job, "rvw.csim.cli", "compare_json", dict(study=study, trace=trace, events=events, **kw))


def _compare_cache(study, trace, events, job, **kw):
    return run_function(job, "rvw.csim.cli", "compare_cache_json", dict(study=study, trace=trace, events=events, **kw))


def _qualify(traces, job, **kw):
    return run_function(job, "rvw.csim.cli", "qualify_json", dict(traces=traces, **kw))


def _simpoint(trace, interval, job, **kw):
    return run_function(job, "rvw.csim.cli", "simpoint_json", dict(trace=trace, interval=interval, **kw))


def _run_points(study, trace, points, job, **kw):
    return run_function(job, "rvw.csim.cli", "run_points_json", dict(study=study, trace=trace, points=points, **kw))


def _compare_reports(base, candidate, tolerance=0.0):
    from .cli import compare_reports_json
    return compare_reports_json(base, candidate, tolerance)


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
    if source_format == "spike":
        return traces.from_spike(Path(source), Path(out), values=values)
    if source_format == "bt9":
        return traces.from_bt9(Path(source), Path(out))
    raise ValueError("source_format must be c2, spike or bt9")


def mcp_tools():
    return [
        ToolSpec("csim_run", "Run a trace-driven component study (direction predictors incl. TAGE-SC-L, BTB/RAS/ITTAGE, "
                 "front-end FTQ model, caches, replacement, prefetchers, TLB, store sets, value prediction) on C2, "
                 "CBP BT9, ChampSim or rvw.csim-trace/1 traces. Reports MPKI, coverage, accuracy and storage per trace. Runs as a job.",
                 schema({"study": S, "traces": TRACES, "format": FMT, "sets": SETS, "timeout": {"type": "number"}}, ["study", "traces"]),
                 _run, long=True, annotations={"readOnlyHint": True}, side_effects='long-running; launches native component engine; builds engine cache if absent', native_tools=('native csim',)),
        ToolSpec("csim_sweep", "Cartesian sweep of dotted study keys over traces, with storage-budget marking and a Pareto "
                 "front on one lower-is-better metric (e.g. direction_mpki, l1d_mpki). Runs as a job.",
                 schema({"study": S, "traces": TRACES, "params": {"type": "object", "additionalProperties": {"type": "array"}},
                         "format": FMT, "sets": SETS, "budget_kib": {"type": "number"},
                         "budget_scope": {**S, "enum": ["metadata", "all"], "default": "metadata"},
                         "metric": S, "jobs": {"type": "integer", "minimum": 1}, "timeout": {"type": "number"}},
                        ["study", "traces", "params"]),
                 _sweep, long=True, annotations={"readOnlyHint": True}, side_effects='long-running; launches native component engine; builds engine cache if absent', native_tools=('native csim',)),
        ToolSpec("csim_budget", "Storage accounting (bits/KiB per table) of a component study without running a trace.",
                 schema({"study": S, "sets": SETS}, ["study"]), _budget, annotations={"readOnlyHint": True}, side_effects='long-running; launches native component engine; builds engine cache if absent', native_tools=('native csim',)),
        ToolSpec("csim_models", "List the component models and their study keys.", schema({}), _models,
                 annotations={"readOnlyHint": True}, side_effects='read-only; long-running', native_tools=()),
        ToolSpec("csim_convert", "Convert a C2 RVFI trace or a Spike -l --log-commits log (optionally with register values), or a CBP 2016 BT9 trace "
                 "into rvw.csim-trace/1.",
                 schema({"source_format": {**S, "enum": ["c2", "spike", "bt9"]}, "source": S, "out": S, "values": {"type": "boolean", "default": False}},
                        ["source_format", "source", "out"]), _convert, isolate=True, side_effects='long-running; writes converted trace to out', native_tools=()),
        ToolSpec("csim_qualify", "Compare a csim direction model with a pinned external reference predictor "
                 "(CBP 2016 TAGE-SC-L 64/8 KB, multiperspective perceptron 64/8 KB/unlimited, MPP+TAGE, Pruett; fetched outside "
                 "the repository and checked by sha256) on the same "
                 "traces: MPKI, relative tolerance and per-branch prediction agreement. Runs as a job.",
                 schema({"traces": TRACES, "reference": {**S, "default": "cbp2016-tage-sc-l-64kb",
                                                         "description": "see rvw.csim.qualify.REFERENCES"},
                         "study": S, "format": FMT, "tolerance": {"type": "number", "default": 0.1}, "archive": S}, ["traces"]),
                 _qualify, long=True, annotations={"readOnlyHint": True}, side_effects='long-running; downloads pinned reference sources, builds cache and launches native predictors', native_tools=('native csim',)),
        ToolSpec("csim_simpoint", "Choose weighted simulation points of a trace (basic-block vectors per interval, random "
                 "projection, k-means with BIC). Writes rvw.csim-simpoints/1. Runs as a job.",
                 schema({"trace": S, "interval": {"type": "integer", "minimum": 1}, "max_k": {"type": "integer", "default": 10},
                         "dims": {"type": "integer", "default": 15}, "seed": {"type": "integer", "default": 1}, "format": FMT},
                        ["trace", "interval"]), _simpoint, long=True, annotations={"readOnlyHint": True}, side_effects='read-only; long-running', native_tools=()),
        ToolSpec("csim_run_points", "Run a component study on simulation points (rvw.csim-simpoints/1 path or object) and "
                 "weight the metrics by the point weights. Runs as a job.",
                 schema({"study": S, "trace": S, "points": {"type": ["string", "object"]}, "warmup": {"type": "integer"},
                         "sets": SETS, "format": FMT}, ["study", "trace", "points"]),
                 _run_points, long=True, annotations={"readOnlyHint": True}, side_effects='long-running; launches native component engine; builds engine cache if absent', native_tools=('native csim',)),
        ToolSpec("csim_compare", "Per-trace metric deltas (better/worse/same) between two rvw csim run reports, paired by "
                 "trace hash.", schema({"base": S, "candidate": S, "tolerance": {"type": "number", "default": 0}}, ["base", "candidate"]),
                 _compare_reports, annotations={"readOnlyHint": True}, side_effects='read-only; long-running', native_tools=()),
        ToolSpec("csim_compare_rtl", "Compare a predictor model with explicit RTL predictor events (rvw.bp-events/1 or Kanata "
                 "#rvw prediction records) on the same C2 run, branch by branch. Missing identity or events gives inconclusive. Runs as a job.",
                 schema({"study": S, "trace": S, "events": S, "roi_start": {"type": "integer"}, "roi_end": {"type": "integer"},
                         "elf_sha256": S, "top": {"type": "integer", "default": 20}, "cache": S,
                         "level": {**S, "enum": ["l1d", "l1i"]}, "trace_out": S}, ["study", "trace", "events"]),
                 _compare, long=True, annotations={"readOnlyHint": True}, side_effects='long-running; launches native component engine; builds engine cache if absent', native_tools=('native csim',)),
        ToolSpec("csim_compare_cache", "Compare a cache model (memory.l1d or memory.l1i of a study) with RTL cache probe "
                 "access events (rvw.probe-events/1) on the same C2 run, access by access: per-access hit/miss "
                 "agreement and miss-rate error. Misaligned or missing events give inconclusive. Runs as a job.",
                 schema({"study": S, "trace": S, "events": S, "cache": {**S, "default": "dcache"},
                         "level": {**S, "enum": ["l1d", "l1i"]}, "top": {"type": "integer", "default": 20},
                         "trace_out": S}, ["study", "trace", "events"]),
                 _compare_cache, long=True, annotations={"readOnlyHint": False}, side_effects='long-running; launches native component engine; builds engine cache if absent; trace_out writes a new file', native_tools=('native csim',)),
    ]
