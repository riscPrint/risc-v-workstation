"""Run studies and sweeps over traces with the native engine."""
from __future__ import annotations

import itertools
import json
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from rvw.common.proc import run_group

from . import config as cfg
from . import engine, traces

REPORT = "rvw.csim-study-report/1"


def prepare(trace: Path, fmt: str, work: Path, values: bool = False) -> tuple[Path, str, dict]:
    """Return (engine input path, engine format, conversion info)."""
    trace = Path(trace)
    if fmt == "auto":
        fmt = traces.detect(trace)
    if fmt in ("csim", "branch"):
        if trace.suffix in (".gz", ".xz"):
            return traces.decompress(trace, work), "csim", {"format": fmt}
        return trace, "csim", {"format": fmt}
    if fmt == "champsim":
        return traces.decompress(trace, work), "champsim", {"format": "champsim"}
    out = work / (trace.name + ".csim")
    if fmt == "c2":
        info = traces.from_c2(trace, out, values=values)
    elif fmt == "bt9":
        info = traces.from_bt9(trace, out)
    elif fmt == "spike":
        info = traces.from_spike(trace, out, values=values)
    else:
        raise ValueError(f"unknown trace format {fmt}")
    return out, "csim", info


def _engine(kv: str, path: Path, fmt: str, timeout: float | None, budget: bool = False) -> dict:
    exe = engine.build("cli")
    with tempfile.NamedTemporaryFile("w", suffix=".kv", delete=False) as f:
        f.write(kv)
        kv_path = f.name
    try:
        cmd = [str(exe), kv_path, "--format", fmt]
        if budget:
            cmd.append("--budget")
        else:
            cmd.append(str(path))
        res = run_group(cmd, timeout=timeout, capture=True)
        if res.timed_out:
            raise TimeoutError("engine timed out")
        if res.returncode:
            raise ValueError((res.stderr or "").strip() or f"engine exit {res.returncode}")
        return json.loads(res.stdout)
    finally:
        os.unlink(kv_path)


def budget(study) -> dict:
    data = cfg.load(study)
    rep = _engine(cfg.to_kv(data), Path("-"), "csim", None, budget=True)
    return {"schema": "rvw.csim-budget/1", "study": data.get("name"), "storage": rep["storage"]}


def run(study, trace_paths: list, fmt: str = "auto", timeout: float | None = None,
        values: bool | None = None, hash_traces: bool = True) -> dict:
    """Run one study on each trace. Results stay per trace; the aggregate is named."""
    data = cfg.load(study)
    kv = cfg.to_kv(data)
    want_values = bool(data.get("vp")) if values is None else values
    results = []
    with tempfile.TemporaryDirectory(prefix="rvw-csim-") as tmp:
        for t in trace_paths:
            t = Path(t)
            path, efmt, info = prepare(t, fmt, Path(tmp), want_values)
            rep = _engine(kv, path, efmt, timeout)
            rep["input"] = {"path": str(t), **info}
            if hash_traces:
                rep["input"]["sha256"] = traces.sha256(t)
            results.append(rep)
    out = {"schema": REPORT, "status": "reported", "study": data.get("name"), "study_sha256": cfg.digest(data),
           "source": data.get("source"), "engine": engine.identity(), "results": results,
           "aggregate": aggregate(results), "rtl_comparison": "inconclusive",
           "fidelity": (data.get("source") or {}).get("fidelity", "unqualified")}
    return out


def metrics(rep: dict) -> dict:
    """Headline numbers of one engine report (flat, for tables and sweeps)."""
    m: dict = {}
    b = rep.get("branch") or {}
    if "direction" in b:
        m["direction_mpki"] = b["direction"]["mpki"]
        m["direction_accuracy"] = b["direction"]["accuracy"]
    if "target" in b:
        m["target_mpki"] = b["target"]["target_mpki"]
        m["execute_redirect_mpki"] = b["execute_redirect_mpki"]
    fe = rep.get("frontend")
    if fe:
        m["frontend_ipc"] = fe["delivered_ipc"]
    for level, v in (rep.get("memory") or {}).items():
        if isinstance(v, dict) and "demand_mpki" in v:
            m[f"{level}_mpki"] = v["demand_mpki"]
            m[f"{level}_prefetch_accuracy"] = v["prefetch"]["accuracy"]
            m[f"{level}_prefetch_coverage"] = v["prefetch"]["coverage"]
    tlb = (rep.get("memory") or {}).get("tlb")
    if tlb:
        m["walk_mpki"] = tlb["walk_mpki"]
    if rep.get("mdp"):
        m["mdp_violations_pki"] = rep["mdp"]["violations_pki"]
        m["mdp_false_dependences"] = rep["mdp"]["false_dependences"]
    if rep.get("vp"):
        m["vp_coverage"] = rep["vp"]["coverage"]
        m["vp_accuracy"] = rep["vp"]["accuracy"]
    m["storage_kib"] = rep["storage"]["total_kib"]
    m["metadata_kib"] = rep["storage"]["metadata_kib"]
    return m


def aggregate(results: list[dict]) -> dict:
    if not results:
        return {}
    rows = [metrics(r) for r in results]
    keys = sorted(set().union(*rows))
    mean = {k: sum(r[k] for r in rows if r.get(k) is not None) / max(1, sum(1 for r in rows if r.get(k) is not None)) for k in keys}
    return {"weighting": "arithmetic mean of per-trace values (equal trace weights)", "traces": len(rows), "mean": mean}


def grid(params: dict[str, list]) -> list[dict]:
    keys = list(params)
    return [dict(zip(keys, combo)) for combo in itertools.product(*(params[k] for k in keys))]


def sweep(study, trace_paths: list, params: dict[str, list], fmt: str = "auto", jobs: int | None = None,
          budget_kib: float | None = None, metric: str | None = None, timeout: float | None = None,
          budget_scope: str = "metadata") -> dict:
    """Cartesian sweep over dotted study keys. Rows over the storage budget are reported
    and marked, not dropped. `metric` (lower is better) selects the Pareto front.
    `budget_scope` "metadata" excludes cache data arrays; "all" counts every bit."""
    if budget_scope not in ("metadata", "all"):
        raise ValueError("budget_scope must be metadata or all")
    skey = "metadata_kib" if budget_scope == "metadata" else "storage_kib"
    base = cfg.load(study)
    points = grid(params)
    if not points:
        raise ValueError("empty sweep")
    jobs = jobs or max(1, min(len(points), (os.cpu_count() or 2) // 2))
    with tempfile.TemporaryDirectory(prefix="rvw-csim-sweep-") as tmp:
        prepared = [prepare(Path(t), fmt, Path(tmp), bool(base.get("vp"))) for t in trace_paths]

        def one(point):
            data = json.loads(json.dumps(base))
            for k, v in point.items():
                cfg.set_path(data, k, v)
            try:
                kv = cfg.to_kv(data)
                reps = [_engine(kv, p, f, timeout) for p, f, _ in prepared]
            except (ValueError, TimeoutError) as exc:  # one invalid point does not stop the sweep
                return {"parameters": point, "error": str(exc)}
            agg = aggregate(reps)
            row = {"parameters": point, "metrics": agg["mean"], "per_trace": [metrics(r) for r in reps]}
            if budget_kib is not None:
                row["within_budget"] = agg["mean"][skey] <= budget_kib
            return row

        with ThreadPoolExecutor(jobs) as pool:
            rows = list(pool.map(one, points))
    out = {"schema": "rvw.csim-sweep/1", "status": "reported", "study": base.get("name"), "study_sha256": cfg.digest(base),
           "parameters": params, "budget_kib": budget_kib, "budget_scope": budget_scope, "traces": [str(t) for t in trace_paths], "rows": rows,
           "weighting": "arithmetic mean of per-trace values", "engine": engine.identity()}
    if metric:
        cands = [r for r in rows if "error" not in r and r.get("within_budget", True) and metric in r["metrics"]]
        if not cands:
            raise ValueError(f"metric {metric} not reported by any row within budget")
        front = []
        for r in sorted(cands, key=lambda r: (r["metrics"][skey], r["metrics"][metric])):
            if not front or r["metrics"][metric] < front[-1]["metrics"][metric]:
                front.append(r)
        out["pareto"] = {"metric": metric, "storage": skey, "lower_is_better": True, "rows": [r["parameters"] for r in front]}
        out["best"] = min(cands, key=lambda r: r["metrics"][metric])["parameters"]
    return out
