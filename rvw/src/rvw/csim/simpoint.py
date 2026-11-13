"""Phase sampling in the SimPoint style (Sherwood et al., ASPLOS 2002).

Basic-block vectors per fixed instruction interval, random projection, k-means
with a BIC-style choice of k, one representative interval per cluster and its
weight. Pure Python; meant for traces of up to a few thousand intervals.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

from . import config as cfg
from . import study as st
from . import traces

SCHEMA = "rvw.csim-simpoints/1"


def bbvs(path: Path, interval: int) -> tuple[list[dict[int, int]], int]:
    """Per interval: {block start PC: instructions}. Blocks end at branch rows."""
    vecs: list[dict[int, int]] = [{}]
    start_pc, last_ord, total = 0, 0, 0
    with Path(path).open() as f:
        if f.readline().strip() != traces.HEADER:
            raise ValueError("simpoint needs rvw.csim-trace/1 input")
        for line in f:
            if not line or line[0] != "B":
                if line.startswith("END"):
                    total = int(line.split()[1])
                continue
            _, o, pc, kind, taken, target, *rest = line.split()
            o = int(o)
            n = o - last_ord
            # Split the block's instructions over interval boundaries.
            pos = last_ord
            while n > 0:
                idx = pos // interval
                while len(vecs) <= idx:
                    vecs.append({})
                take = min(n, (idx + 1) * interval - pos)
                vecs[idx][start_pc] = vecs[idx].get(start_pc, 0) + take
                pos += take; n -= take
            last_ord = o
            pcv = int(pc, 16)
            length = int(rest[0]) if rest else 4
            start_pc = int(target, 16) if taken == "1" else pcv + (length or 4)
    if total > last_ord:
        pos, n = last_ord, total - last_ord
        while n > 0:
            idx = pos // interval
            while len(vecs) <= idx:
                vecs.append({})
            take = min(n, (idx + 1) * interval - pos)
            vecs[idx][start_pc] = vecs[idx].get(start_pc, 0) + take
            pos += take; n -= take
    if total and len(vecs) > (total + interval - 1) // interval:
        vecs = vecs[: (total + interval - 1) // interval]
    return vecs, total


def project(vecs, dims: int, seed: int) -> list[list[float]]:
    rng = random.Random(seed)
    cols: dict[int, list[float]] = {}
    out = []
    for v in vecs:
        tot = sum(v.values()) or 1
        p = [0.0] * dims
        for k, c in v.items():
            col = cols.get(k)
            if col is None:
                col = cols[k] = [rng.uniform(-1, 1) for _ in range(dims)]
            w = c / tot
            for d in range(dims):
                p[d] += w * col[d]
        out.append(p)
    return out


def _dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


def kmeans(pts, k: int, seed: int, iters: int = 50):
    rng = random.Random(seed)
    cents = [pts[rng.randrange(len(pts))]]
    while len(cents) < k:  # k-means++ seeding
        d = [min(_dist(p, c) for c in cents) for p in pts]
        tot = sum(d)
        if tot == 0:
            break
        r, acc = rng.uniform(0, tot), 0.0
        for p, w in zip(pts, d):
            acc += w
            if acc >= r:
                cents.append(p); break
    assign = [0] * len(pts)
    for _ in range(iters):
        new = [min(range(len(cents)), key=lambda j: _dist(p, cents[j])) for p in pts]
        if new == assign and _ > 0:
            break
        assign = new
        for j in range(len(cents)):
            mem = [p for p, a in zip(pts, assign) if a == j]
            if mem:
                cents[j] = [sum(c) / len(mem) for c in zip(*mem)]
    return cents, assign


def bic(pts, cents, assign) -> float:
    """BIC under identical spherical Gaussians (Pelleg & Moore, X-means)."""
    n, d, k = len(pts), len(pts[0]), len(cents)
    sse = sum(_dist(p, cents[a]) for p, a in zip(pts, assign))
    if n <= k:
        return float("-inf")
    var = max(sse / (d * (n - k)), 1e-12)
    ll = 0.0
    for j in range(k):
        nj = sum(1 for a in assign if a == j)
        if nj:
            ll += nj * math.log(nj / n) - nj * d / 2 * math.log(2 * math.pi * var) - (nj - 1) * d / 2
    params = k * (d + 1)
    return ll - params / 2 * math.log(n)


def choose(path: Path, interval: int, max_k: int = 10, dims: int = 15, seed: int = 1, threshold: float = 0.9) -> dict:
    vecs, total = bbvs(path, interval)
    if not vecs or not total:
        raise ValueError("empty trace")
    pts = project(vecs, dims, seed)
    runs = []
    for k in range(1, min(max_k, len(pts)) + 1):
        cents, assign = kmeans(pts, k, seed + k)
        runs.append((k, cents, assign, bic(pts, cents, assign)))
    finite = [r for r in runs if math.isfinite(r[3])]
    runs = finite or [runs[0][:3] + (0.0,)]
    lo, hi = min(r[3] for r in runs), max(r[3] for r in runs)
    # Smallest k whose BIC reaches `threshold` of the observed BIC range (the SimPoint rule).
    pick = next(r for r in runs if hi == lo or (r[3] - lo) / (hi - lo) >= threshold)
    k, cents, assign, score = pick
    points = []
    for j in range(len(cents)):
        mem = [i for i, a in enumerate(assign) if a == j]
        if not mem:
            continue
        rep = min(mem, key=lambda i: _dist(pts[i], cents[j]))
        instr = [min(interval, total - i * interval) for i in mem]
        points.append({"interval": rep, "start_instruction": rep * interval,
                       "instructions": min(interval, total - rep * interval),
                       "weight": sum(instr) / total, "members": len(mem)})
    points.sort(key=lambda p: p["interval"])
    return {"schema": SCHEMA, "trace": str(path), "sha256": traces.sha256(Path(path)), "interval": interval,
            "intervals": len(vecs), "instructions": total, "k": k, "bic": score, "dims": dims, "seed": seed,
            "points": points, "weighting": "instructions in each cluster over all instructions"}


def run_points(study, trace: Path, points: dict, warmup: int | None = None, fmt: str = "auto") -> dict:
    """Run a study on each simulation point and combine metrics with the point weights.
    `warmup` limits functional warming before each point (default: from trace start)."""
    data = cfg.load(study)
    import tempfile
    with tempfile.TemporaryDirectory(prefix="rvw-csim-sp-") as tmp:
        path, efmt, info = st.prepare(Path(trace), fmt, Path(tmp))
        results = []
        for p in points["points"]:
            d = json.loads(json.dumps(data))
            start = p["start_instruction"]
            d["warmup_instructions"] = start
            d["skip_instructions"] = 0 if warmup is None else max(0, start - warmup)
            d["simulation_instructions"] = p["instructions"]
            rep = st._engine(cfg.to_kv(d), path, efmt, None)
            results.append({"point": p, "metrics": st.metrics(rep), "report": rep})
    keys = sorted(set().union(*(r["metrics"] for r in results)))
    wsum = sum(r["point"]["weight"] for r in results) or 1
    agg = {k: sum(r["point"]["weight"] * r["metrics"][k] for r in results if r["metrics"].get(k) is not None) / wsum
           for k in keys if k not in ("storage_kib", "metadata_kib")}
    return {"schema": "rvw.csim-simpoint-report/1", "status": "reported", "study": data.get("name"),
            "study_sha256": cfg.digest(data), "trace": str(trace), "input": info, "simpoints_sha256": cfg.digest(points),
            "warmup_per_point": warmup, "points": results, "weighted": agg,
            "weighting": "simulation-point weights from the clustering; sampling error is not estimated"}
