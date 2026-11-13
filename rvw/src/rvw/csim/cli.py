"""`rvw csim`: trace-driven component studies (branch, target, front end, memory)."""
from __future__ import annotations

import json
from pathlib import Path

FORMATS = ["auto", "csim", "branch", "c2", "bt9", "spike", "champsim"]


def _overrides(study_path: str, sets: list[str] | None):
    from . import config as cfg
    data = cfg.load(study_path)
    for s in sets or []:
        if "=" not in s:
            raise ValueError(f"--set needs KEY=VALUE, got {s!r}")
        k, v = s.split("=", 1)
        cfg.set_path(data, k, cfg.parse_value(v))
    return data


def _params(items: list[str]) -> dict:
    from . import config as cfg
    out = {}
    for s in items:
        if "=" not in s:
            raise ValueError(f"--param needs KEY=V1,V2,..., got {s!r}")
        k, v = s.split("=", 1)
        if v.startswith("["):
            vals = json.loads(v)
            if not isinstance(vals, list):
                raise ValueError("--param JSON value must be a list")
        else:
            vals = [cfg.parse_value(x) for x in v.split(",")]
        out[k] = vals
    return out


def register(subparsers):
    p = subparsers.add_parser("csim", help="trace-driven component studies (predictors, BTB/RAS, caches, prefetchers)")
    sub = p.add_subparsers(dest="csim_command", required=True)

    r = sub.add_parser("run", help="run one study over traces")
    r.add_argument("study"); r.add_argument("traces", nargs="+")
    r.add_argument("--format", choices=FORMATS, default="auto")
    r.add_argument("--set", action="append", metavar="KEY=VALUE", help="override a dotted study key")
    r.add_argument("--timeout", type=float)
    r.add_argument("--out"); r.add_argument("--json", action="store_true")
    r.set_defaults(func=_run)

    s = sub.add_parser("sweep", help="cartesian parameter sweep with storage budget and Pareto front")
    s.add_argument("study"); s.add_argument("traces", nargs="+")
    s.add_argument("--param", action="append", required=True, metavar="KEY=V1,V2")
    s.add_argument("--set", action="append", metavar="KEY=VALUE")
    s.add_argument("--format", choices=FORMATS, default="auto")
    s.add_argument("--budget-kib", type=float); s.add_argument("--budget-scope", choices=["metadata", "all"], default="metadata")
    s.add_argument("--metric", help="metric to minimise, e.g. direction_mpki")
    s.add_argument("--jobs", type=int); s.add_argument("--timeout", type=float)
    s.add_argument("--out"); s.add_argument("--json", action="store_true")
    s.set_defaults(func=_sweep)

    b = sub.add_parser("budget", help="storage accounting of a study without a trace")
    b.add_argument("study"); b.add_argument("--set", action="append", metavar="KEY=VALUE")
    b.add_argument("--json", action="store_true")
    b.set_defaults(func=_budget)

    c = sub.add_parser("convert", help="convert C2, a Spike commit log or CBP BT9 into rvw.csim-trace/1")
    c.add_argument("source_format", choices=["c2", "spike", "bt9"]); c.add_argument("source")
    c.add_argument("--out", required=True); c.add_argument("--values", action="store_true", help="C2/Spike: add register-write rows")
    c.add_argument("--json", action="store_true")
    c.set_defaults(func=_convert)

    m = sub.add_parser("models", help="list models and study keys")
    m.add_argument("--json", action="store_true")
    m.set_defaults(func=_models)

    x = sub.add_parser("compare-rtl", help="per-branch comparison of a model with explicit RTL predictor events")
    x.add_argument("study"); x.add_argument("--trace", required=True, help="C2 rvfi.jsonl of the same run")
    x.add_argument("--events", required=True, help="rvw.bp-events/1 JSONL or a Kanata log")
    x.add_argument("--roi-start", type=int); x.add_argument("--roi-end", type=int)
    x.add_argument("--elf-sha256"); x.add_argument("--top", type=int, default=20)
    x.add_argument("--json", action="store_true")
    x.set_defaults(func=_compare)

    q = sub.add_parser("qualify", help="compare a direction model with a pinned external reference predictor")
    q.add_argument("traces", nargs="+")
    q.add_argument("--reference", default="cbp2016-tage-sc-l-64kb")
    q.add_argument("--study", help="study to qualify (default: the matched example for the reference)")
    q.add_argument("--format", choices=FORMATS, default="auto")
    q.add_argument("--tolerance", type=float, default=0.10, help="relative MPKI tolerance")
    q.add_argument("--archive", help="local copy of the reference archive (checked against the pinned sha256)")
    q.add_argument("--out"); q.add_argument("--json", action="store_true")
    q.set_defaults(func=_qualify)

    cp = sub.add_parser("compare", help="per-trace metric deltas between two rvw csim run reports")
    cp.add_argument("base"); cp.add_argument("candidate")
    cp.add_argument("--tolerance", type=float, default=0.0, help="relative change below which a metric is 'same'")
    cp.add_argument("--out"); cp.add_argument("--json", action="store_true")
    cp.set_defaults(func=_compare_reports)

    sp = sub.add_parser("simpoint", help="choose weighted simulation points (basic-block vectors + k-means)")
    sp.add_argument("trace"); sp.add_argument("--interval", type=int, required=True, help="instructions per interval")
    sp.add_argument("--max-k", type=int, default=10); sp.add_argument("--dims", type=int, default=15)
    sp.add_argument("--seed", type=int, default=1); sp.add_argument("--format", choices=FORMATS, default="auto")
    sp.add_argument("--out"); sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=_simpoint)

    rp = sub.add_parser("run-points", help="run a study on simulation points and weight the results")
    rp.add_argument("study"); rp.add_argument("trace"); rp.add_argument("--points", required=True)
    rp.add_argument("--warmup", type=int, help="instructions of functional warming before each point (default: all)")
    rp.add_argument("--set", action="append", metavar="KEY=VALUE"); rp.add_argument("--format", choices=FORMATS, default="auto")
    rp.add_argument("--out"); rp.add_argument("--json", action="store_true")
    rp.set_defaults(func=_run_points)

    e = sub.add_parser("build", help="build the native engine and library; print their paths")
    e.add_argument("--json", action="store_true")
    e.set_defaults(func=_build)


def _emit(args, result) -> int:
    text = json.dumps(result, indent=None if getattr(args, "json", False) else 2)
    if getattr(args, "out", None):
        Path(args.out).write_text(text + "\n")
    print(text)
    return 0


def _guard(fn):
    def wrapper(args):
        try:
            return _emit(args, fn(args))
        except (ValueError, OSError, KeyError, RuntimeError, TimeoutError, json.JSONDecodeError) as exc:
            print(json.dumps({"error": str(exc)}))
            return 2
    return wrapper


@_guard
def _run(args):
    from . import study
    return study.run(_overrides(args.study, args.set), args.traces, args.format, args.timeout)


@_guard
def _sweep(args):
    from . import study
    return study.sweep(_overrides(args.study, args.set), args.traces, _params(args.param), args.format, args.jobs,
                       args.budget_kib, args.metric, args.timeout, args.budget_scope)


@_guard
def _budget(args):
    from . import study
    return study.budget(_overrides(args.study, args.set))


@_guard
def _convert(args):
    from . import traces
    if args.source_format == "bt9":
        info = traces.from_bt9(Path(args.source), Path(args.out))
    else:
        fn = traces.from_c2 if args.source_format == "c2" else traces.from_spike
        info = fn(Path(args.source), Path(args.out), values=args.values)
    return {"schema": "rvw.csim-convert/1", "out": args.out, **info}


@_guard
def _models(args):
    from .models import CATALOG
    return CATALOG


@_guard
def _compare(args):
    from . import rtl
    return rtl.compare(args.study, args.trace, args.events, args.roi_start, args.roi_end, args.elf_sha256, args.top)


@_guard
def _qualify(args):
    from . import qualify
    return qualify.qualify(args.reference, args.traces, args.study, args.format, args.tolerance,
                           Path(args.archive) if args.archive else None)


@_guard
def _compare_reports(args):
    return compare_reports_json(args.base, args.candidate, args.tolerance)


def compare_reports_json(base, candidate, tolerance=0.0):
    from . import study
    return study.compare(json.loads(Path(base).read_text()), json.loads(Path(candidate).read_text()), tolerance)


@_guard
def _simpoint(args):
    return simpoint_json(args.trace, args.interval, args.max_k, args.dims, args.seed, args.format)


@_guard
def _run_points(args):
    from . import simpoint
    points = json.loads(Path(args.points).read_text())
    return simpoint.run_points(_overrides(args.study, args.set), args.trace, points, args.warmup, args.format)


@_guard
def _build(args):
    from . import engine
    return {"engine": str(engine.build("cli")), "library": str(engine.build("lib")), **engine.identity()}


# MCP entry points (run in a worker process).
def run_json(study, traces, format="auto", sets=None, timeout=None):
    from . import study as st
    return st.run(_overrides(study, sets), traces, format, timeout)


def sweep_json(study, traces, params, format="auto", sets=None, budget_kib=None, budget_scope="metadata",
               metric=None, jobs=None, timeout=None):
    from . import study as st
    return st.sweep(_overrides(study, sets), traces, params, format, jobs, budget_kib, metric, timeout, budget_scope)


def compare_json(study, trace, events, roi_start=None, roi_end=None, elf_sha256=None, top=20):
    from . import rtl
    return rtl.compare(study, trace, events, roi_start, roi_end, elf_sha256, top)


def qualify_json(traces, reference="cbp2016-tage-sc-l-64kb", study=None, format="auto", tolerance=0.10, archive=None):
    from . import qualify
    return qualify.qualify(reference, traces, study, format, tolerance, Path(archive) if archive else None)


def simpoint_json(trace, interval, max_k=10, dims=15, seed=1, format="auto"):
    import tempfile
    from . import simpoint, study
    if interval < 1:
        raise ValueError("interval must be positive")
    with tempfile.TemporaryDirectory(prefix="rvw-csim-sp-") as tmp:
        path, fmt, info = study.prepare(Path(trace), format, Path(tmp))
        if fmt != "csim":
            raise ValueError("simpoint needs a text trace (csim, c2, spike or bt9)")
        out = simpoint.choose(path, interval, max_k, dims, seed)
    out["trace"] = str(trace)
    return out


def run_points_json(study, trace, points, warmup=None, sets=None, format="auto"):
    from . import simpoint
    if isinstance(points, str):
        points = json.loads(Path(points).read_text())
    return simpoint.run_points(_overrides(study, sets), trace, points, warmup, format)
