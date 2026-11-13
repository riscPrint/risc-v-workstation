"""Deterministic BBV phase selection over complete C2 traces."""
from collections import Counter
from hashlib import sha256
from pathlib import Path
import json

from rvw.arch.ledger import store
from rvw.common.riscv import decode
from rvw.cosim.trace import Trace


def vectors(trace_path, interval):
    if type(interval) is not int or interval < 1:
        raise ValueError("interval must be positive")
    trace = Trace(trace_path)
    try:
        if trace.multihart:
            raise ValueError("sampling requires a single hart")
        result, counts = [], Counter()
        total, start, block = 0, 0, None
        ended = False
        for row in trace:
            if row.get("event") == "end":
                if row["status"] != "pass":
                    raise ValueError("trace must end with pass")
                ended = True
                continue
            if "event" in row or any(row[k] for k in ("trap", "intr", "halt", "mem_fault")):
                raise ValueError("unsupported external or exceptional trace event")
            op = decode(row["insn"], trace.header["xlen"])
            if op.cls == "unknown":
                raise ValueError("unknown instruction in BBV input")
            if block is None:
                block = row["pc"]
            counts[block] += 1
            total += 1
            if op.cls in ("branch", "jump") or row["pc_next"] != row["pc"] + op.length:
                block = None
            if total - start == interval:
                result.append(dict(start=start, end=total, counts=dict(counts)))
                counts.clear()
                start = total
        if counts:
            result.append(dict(start=start, end=total, counts=dict(counts)))
        if not ended or not total:
            raise ValueError("complete nonempty C2 required")
        return result
    finally:
        trace.close()


def distance(a, b):
    return sum((a.get(k, 0)-b.get(k, 0))**2 for k in a.keys() | b.keys())


def sample(trace, out, interval=1_000_000, clusters=8, warmup=100_000, project=None):
    if project is not None:
        from rvw.common.project import load_project
        load_project(project)
    if type(clusters) is not int or not 1 <= clusters <= 256:
        raise ValueError("clusters must be in 1..256")
    if type(warmup) is not int or warmup < 0:
        raise ValueError("warmup must be nonnegative")
    rows = vectors(trace, interval)
    points = [{k: v/(r["end"]-r["start"]) for k, v in r["counts"].items()} for r in rows]
    # Farthest-first centers avoid random and dependency-version drift.
    centers = [points[0]]
    for _ in range(min(clusters, len(points))-1):
        farthest = max(range(len(points)), key=lambda i: min(distance(points[i], c) for c in centers))
        if min(distance(points[farthest], c) for c in centers) == 0:
            break
        centers.append(points[farthest])
    previous = None
    for iteration in range(100):
        labels = [min(range(len(centers)), key=lambda j: distance(p, centers[j])) for p in points]
        if labels == previous:
            break
        previous = labels
        updated = []
        for j, old in enumerate(centers):
            members = [i for i, label in enumerate(labels) if label == j]
            length = sum(rows[i]["end"]-rows[i]["start"] for i in members)
            if not length:
                updated.append(old)
                continue
            counts = Counter()
            for i in members:
                counts.update(rows[i]["counts"])
            updated.append({k: v/length for k, v in counts.items()})
        centers = updated
    # Reassign after the final update, including when the iteration cap is reached.
    labels = [min(range(len(centers)), key=lambda j: distance(p, centers[j])) for p in points]
    total = rows[-1]["end"]
    selected = []
    for j, center in enumerate(centers):
        members = [i for i, label in enumerate(labels) if label == j]
        if not members:
            continue
        representative = min(members, key=lambda i: (distance(points[i], center), i))
        region = rows[representative]
        represented = sum(rows[i]["end"]-rows[i]["start"] for i in members)
        capture = max(0, region["start"]-warmup)
        selected.append(dict(cluster=j, interval=representative, start=region["start"], end=region["end"],
            capture=capture, actual_warmup=region["start"]-capture,
            represented_instructions=represented, weight=represented/total, members=members))
    return store(out, dict(schema="rvw.arch-sampling/1", status="reported", trace=str(Path(trace).resolve()),
        trace_sha256=sha256(Path(trace).read_bytes()).hexdigest(), instret=total,
        interval=interval, requested_clusters=clusters, iterations=iteration+1,
        method="instruction-weighted BBV k-means; deterministic farthest-first centers",
        samples=selected, intervals=rows, accuracy_status="inconclusive",
        limits=["BBV similarity does not establish timing similarity", "no checkpoint or cache/predictor state restore",
                "warmup lengths are plans, not bias measurements"]))


def sampled_cpi(plan, observations, full_cycles):
    """Aggregate measured CPI using represented instruction fractions."""
    if type(full_cycles) is not int or full_cycles < 1:
        raise ValueError("positive full-run cycles required")
    if set(observations) != {str(r["cluster"]) for r in plan["samples"]}:
        raise ValueError("every selected sample needs an observation")
    cpi = 0
    for row in plan["samples"]:
        observation = observations[str(row["cluster"])]
        if observation["instret"] != row["end"]-row["start"]:
            raise ValueError("sample instruction count mismatch")
        if type(observation["cycles"]) is not int or observation["cycles"] < 1:
            raise ValueError("positive sample cycles required")
        cpi += row["weight"] * observation["cycles"] / observation["instret"]
    full_cpi = full_cycles / plan["instret"]
    return dict(sampled_cpi=cpi, sampled_ipc=1/cpi, full_cpi=full_cpi,
                signed_cpi_bias_percent=100*(cpi/full_cpi-1), accuracy_status="inconclusive")
