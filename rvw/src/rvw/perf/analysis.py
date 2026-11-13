"""Measurements of observed events; residence is never labelled a stall cause."""
from bisect import bisect_right
from collections import Counter, defaultdict
import heapq
import math

from rvw.results import load_run

from .classify import identify
from .events import event_report
from .kanata import Trace, read


def distribution(values):
    values = sorted(values)
    if not values:
        return {"n": 0, "sum": 0, "mean": None, "p50": None, "p95": None, "max": None}
    return {"n": len(values), "sum": sum(values), "mean": sum(values) / len(values),
            "p50": values[math.ceil(len(values) * .5) - 1],
            "p95": values[math.ceil(len(values) * .95) - 1], "max": values[-1]}


def _bubbles(trace: Trace, commits, head_stage, lane):
    """Sweep event boundaries, never iterate per simulated cycle."""
    boundary = {trace.start, trace.end + 1}
    changes = defaultdict(list)
    stages = {}
    admitted = 0
    for ins in trace.instructions.values():
        spans = [s for s in ins.spans if s.lane == lane]
        stages[ins.id] = ([s.start for s in spans], spans)
        boundary.update(s.start for s in spans)
        boundary.update(s.end for s in spans if s.end is not None)
        matches = [s.start for s in spans if s.stage == head_stage] if head_stage else []
        if matches and min(matches) <= trace.end and (ins.end is None or ins.end > trace.start):
            admitted += 1
            changes[max(min(matches), trace.start)].append((True, ins))
            if ins.end is not None:
                changes[ins.end].append((False, ins))
                boundary.add(ins.end)
    for cycle in commits:
        boundary.update((cycle, cycle + 1))
    points = sorted(t for t in boundary if trace.start <= t <= trace.end + 1)
    heaps = defaultdict(list)
    live = set()
    heads = Counter()
    intervals = []
    total = 0
    for left, right in zip(points, points[1:]):
        for add, ins in changes[left]:
            if add:
                live.add(ins.id)
                heapq.heappush(heaps[ins.thread], (ins.ordinal, ins.id))
            else:
                live.discard(ins.id)
        if commits[left] or right <= left:
            continue
        total += right - left
        observed = []
        for thread, heap in heaps.items():
            while heap and heap[0][1] not in live:
                heapq.heappop(heap)
            if not heap:
                continue
            ins = trace.instructions[heap[0][1]]
            starts, spans = stages[ins.id]
            index = bisect_right(starts, left) - 1
            span = spans[index] if index >= 0 else None
            stage = span.stage if span and (span.end is None or span.end > left) else "unobserved"
            pc, _ = identify(ins.labels, "none")
            heads[thread, pc, stage] += right - left
            observed.append({"thread": thread, "id": ins.id, "pc": pc, "stage": stage})
        # Merge adjacent pieces with identical head state, preserving actual bubble runs.
        if intervals and intervals[-1]["end"] == left and intervals[-1]["heads"] == observed:
            intervals[-1]["end"] = right
        else:
            intervals.append({"start": left, "end": right, "heads": observed})
    return {"cycles": total, "head_basis": f"oldest created live instruction that entered {head_stage}"
            if head_stage else "unavailable: specify --head-stage and --in-order-retirement",
            "admitted": admitted,
            "head_residency": [{"thread": t, "pc": pc, "stage": s, "cycles": n}
                               for (t, pc, s), n in heads.most_common()],
            "longest": sorted(intervals, key=lambda x: x["end"] - x["start"], reverse=True)[:20]}


def analyze(inputs, *, window=1000, isa="none", lane="0", queue_stage=None,
            issue_stage=None, head_stage=None, in_order_retirement=False):
    # All callers capture the complete command input set before entering this calculation.
    if window <= 0:
        raise ValueError("window must be positive")
    if bool(queue_stage) != bool(issue_stage):
        raise ValueError("queue-stage and issue-stage must be supplied together")
    if head_stage and not in_order_retirement:
        raise ValueError("head-stage requires --in-order-retirement (creation order must be program order)")
    trace = read(inputs.trace.copy)
    commits = Counter()
    grouped = defaultdict(lambda: defaultdict(list))
    by_pc = defaultdict(lambda: {"count": 0, "retired": 0, "flushed": 0, "open": 0,
                                 "lifetime_cycles": 0, "stages": defaultdict(list), "queue": []})
    by_class = defaultdict(lambda: {"count": 0, "stages": defaultdict(list), "queue": []})
    flush_lifetimes = []
    censored = 0
    retired = flushed = opened = 0
    for ins in trace.instructions.values():
        pc, cls = identify(ins.labels, isa)
        p, c = by_pc[pc], by_class[cls]
        p["count"] += 1
        c["count"] += 1
        status = "open" if ins.end is None else "flushed" if ins.flushed else "retired"
        p[status] += 1
        if status == "retired":
            retired += 1
            commits[ins.end] += 1
        elif status == "flushed":
            flushed += 1
            flush_lifetimes.append(ins.end - ins.start)
        else:
            opened += 1
        if ins.end is not None:
            p["lifetime_cycles"] += ins.end - ins.start
        selected = [s for s in ins.spans if s.lane == lane]
        for span in selected:
            if span.end is None:
                censored += 1
                continue
            duration = span.end - span.start
            grouped[span.stage][status].append(duration)
            p["stages"][span.stage].append(duration)
            c["stages"][span.stage].append(duration)
        if queue_stage:
            queues = [s.start for s in selected if s.stage == queue_stage]
            issues = [s.start for s in selected if s.stage == issue_stage]
            if queues and issues and min(issues) >= min(queues):
                # First admission to first issue only, never conflate replay with queue wait.
                wait = min(issues) - min(queues)
                p["queue"].append(wait)
                c["queue"].append(wait)
    cycles = trace.end - trace.start + 1
    windows = []
    # Sparse commit accumulation plus an output-size bound against accidentally enormous logs.
    if math.ceil(cycles / window) > 1_000_000:
        raise ValueError("more than one million IPC windows; increase --window")
    window_counts = Counter()
    for t, n in commits.items():
        window_counts[(t - trace.start) // window] += n
    for index, start in enumerate(range(trace.start, trace.end + 1, window)):
        end = min(start + window, trace.end + 1)
        n = window_counts[index]
        windows.append({"start": start, "end": end, "cycles": end - start, "instret": n, "ipc": n / (end - start)})
    stages = {}
    for name, populations in sorted(grouped.items()):
        stages[name] = {"all": distribution([v for values in populations.values() for v in values]),
                        **{status: distribution(populations[status]) for status in ("retired", "flushed", "open")}}
    def finish_groups(groups):
        rows = []
        for key, data in groups.items():
            rows.append({"key": key, **{k: v for k, v in data.items() if k not in ("stages", "queue")},
                         "stages": {s: distribution(v) for s, v in sorted(data["stages"].items())},
                         "queue_to_first_issue": distribution(data["queue"])})
        return sorted(rows, key=lambda r: (-r.get("lifetime_cycles", r["count"]), r["key"]))
    report = {"schema": "rvw.perf/1", "trace": inputs.trace.resolved,
              "trace_sha256": inputs.trace.sha256,
              "retirement_basis": "Kanata R type 0 records. Whether these are architectural instructions depends on the producer; IPC is event IPC until scopes and semantics are verified.",
              "configuration": {"isa": isa, "lane": lane, "window": window, "queue_stage": queue_stage,
                                "issue_stage": issue_stage, "head_stage": head_stage,
                                "in_order_retirement": in_order_retirement},
              "summary": {"start": trace.start, "end_exclusive": trace.end + 1, "cycles": cycles,
                          "fetched": len(trace.instructions), "instret": retired, "flushed": flushed,
                          "open": opened, "ipc": retired / cycles, "flush_fraction": flushed / len(trace.instructions)
                          if trace.instructions else 0, "dependencies": trace.dependencies},
              "stages": stages, "by_pc": finish_groups(by_pc), "by_class": finish_groups(by_class),
              "wrong_path": {"flushed_lifetime_instruction_cycles": sum(flush_lifetimes),
                             "lifetime": distribution(flush_lifetimes),
                             "meaning": "overlapping instruction lifetimes, not lost wall cycles or branch penalty"},
              "ipc_windows": windows, "commit_bubbles": _bubbles(trace, commits, head_stage, lane),
              "warnings": trace.warnings,
              "limits": ["No causal stall attribution without explicit reason/dependency events.",
                         "Stage durations are per visit, half-open; repeated visits include replay.",
                         "Open instructions and open stage intervals are censored, never assumed flushed.",
                         "Head is inferred per thread from creation order after the configured admission stage; not a hardware ROB-head signal.",
                         "R type 1 means discarded; not every discard proves a branch wrong path.",
                         f"{censored} open stage intervals excluded from latency distributions."]}
    report.update(event_report(trace, commits))
    if inputs.result is not None:
        result_path = inputs.result.resolved
        run = load_run(inputs.result.copy)
        if why := run.why_inconclusive:
            raise ValueError(f"{result_path}: inconclusive counter evidence: {why}")
        counters = run.to_dict()
        report["run"] = {key: counters[key] for key in ("core", "config", "seed", "elf", "elf_sha256",
                         "mem_latency", "max_cycles", "source", "tools", "replay") if key in counters}
        rc, ri = counters["cycles"], counters["instret"]
        if not isinstance(rc, int) or not isinstance(ri, int) or rc <= 0 or ri < 0:
            raise ValueError("result counters must be positive cycles and nonnegative integer instret")
        artifact_match = inputs.artifact_matches
        report["cross_check"] = {"result": inputs.result.resolved,
                                 "result_sha256": inputs.result.sha256, "result_ipc": ri / rc,
                                 "result_status": counters.get("status"), "artifact_matches": artifact_match,
                                 "cycles_delta": cycles - rc, "instret_delta": retired - ri,
                                 "ipc_delta": retired / cycles - ri / rc,
                                 "exact_counter_match": cycles == rc and retired == ri,
                                 "note": "Only comparable if both counters cover the same interval and retirement event. A mismatch is evidence, never silently normalized."}
        if artifact_match is False:
            report["warnings"].append("result.json identifies a different Konata artifact")
        if retired != ri:
            report["warnings"].append("R-retire count differs from result instret; trace event IPC must not be treated as architectural IPC")
    return report


def compare(a, b, tolerance=.05):
    if not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("tolerance must be finite and nonnegative")
    if a["configuration"] != b["configuration"]:
        raise ValueError("comparison requires identical analysis settings")
    differences = []
    def check(metric, av, bv, absolute=0):
        if av is None or bv is None:
            return
        delta = bv - av
        relative = delta / abs(av) if av else None
        if abs(delta) > max(absolute, tolerance * abs(av)):
            differences.append({"metric": metric, "base": av, "candidate": bv,
                                "delta": delta, "relative_change": relative})
    for key in ("cycles", "instret", "flushed", "open"):
        check(key, a["summary"][key], b["summary"][key], 1)
    for key in ("ipc", "flush_fraction"):
        check(key, a["summary"][key], b["summary"][key], .01)
    for stage in sorted(a["stages"].keys() & b["stages"].keys()):
        for metric in ("mean", "p95"):
            check(f"stage.{stage}.{metric}", a["stages"][stage]["all"][metric], b["stages"][stage]["all"][metric], 1)
    check("commit_bubble_cycles", a["commit_bubbles"]["cycles"], b["commit_bubbles"]["cycles"], 1)
    # Class and PC changes identify actionable local differences, not just global means.
    for group in ("by_pc", "by_class"):
        left, right = ({r["key"]: r for r in report[group]} for report in (a, b))
        for key in sorted(left.keys() & right.keys()):
            check(f"{group}.{key}.queue_mean", left[key]["queue_to_first_issue"]["mean"],
                  right[key]["queue_to_first_issue"]["mean"], 1)
            for stage in sorted(left[key]["stages"].keys() & right[key]["stages"].keys()):
                check(f"{group}.{key}.stage.{stage}.mean", left[key]["stages"][stage]["mean"],
                      right[key]["stages"][stage]["mean"], 1)
    return {"schema": "rvw.perf.compare/1", "base": a["trace"], "candidate": b["trace"],
            "tolerance": tolerance, "significance": "practical magnitude threshold, not statistical confidence",
            "differences": differences,
            "stage_added": sorted(b["stages"].keys() - a["stages"].keys()),
            "stage_removed": sorted(a["stages"].keys() - b["stages"].keys())}


def render(report, top=10):
    if report["schema"] == "rvw.perf.compare/1":
        lines = ["Differences exceeding practical thresholds (not a statistical test):"]
        for row in report["differences"]:
            lines.append(f"  {row['metric']}: {row['base']:.4g} -> {row['candidate']:.4g} ({row['delta']:+.4g})")
        if not report["differences"]:
            lines.append("  None.")
        if report["stage_added"] or report["stage_removed"]:
            lines.append(f"  Stages added: {report['stage_added']}; removed: {report['stage_removed']}")
        return "\n".join(lines)
    s = report["summary"]
    lines = [f"{s['instret']} R-retire events / {s['cycles']} observed cycles = {s['ipc']:.4f} event IPC; "
             f"{s['flushed']} discarded, {s['open']} still open.",
             f"Zero-retirement cycles: {report['commit_bubbles']['cycles']}. Stage residence per visit (all paths):"]
    for name, row in report["stages"].items():
        d = row["all"]
        lines.append(f"  {name}: n={d['n']} mean={d['mean']:.2f} p50={d['p50']} p95={d['p95']} max={d['max']}")
    lines.append("Top PCs by completed instruction lifetime cycles (overlapping, not wall time):")
    for row in report["by_pc"][:top]:
        q = row["queue_to_first_issue"]["mean"]
        lines.append(f"  {row['key']}: cycles={row['lifetime_cycles']} count={row['count']} "
                     f"retired={row['retired']} discarded={row['flushed']} queue_mean={q if q is not None else 'unavailable'}")
    lines.append("Instruction classes:")
    for row in report["by_class"]:
        q = row["queue_to_first_issue"]
        lines.append(f"  {row['key']}: count={row['count']} queue_n={q['n']} queue_mean={q['mean']}")
    lines.append("Inferred heads during commit bubbles: " + report["commit_bubbles"]["head_basis"])
    for row in report["commit_bubbles"]["head_residency"][:top]:
        lines.append(f"  thread={row['thread']} {row['pc']} in {row['stage']}: {row['cycles']} cycles")
    cost = report["wrong_path"]["flushed_lifetime_instruction_cycles"]
    lines.append(f"Discarded lifetime cost: {cost} instruction-cycles; no branch recovery penalty inferred.")
    if "cross_check" in report:
        x = report["cross_check"]
        lines.append(f"result.json cross-check: cycles delta={x['cycles_delta']:+d}, instret delta={x['instret_delta']:+d}, "
                     f"IPC delta={x['ipc_delta']:+.6f}; exact match={x['exact_counter_match']}.")
    lines.extend("Warning: " + w for w in report["warnings"])
    if "predictions" in report:
        predictions = report["predictions"]
        lines.append(f"Observed prediction outcomes: {predictions['outcomes']}")
        for row in predictions["by_context"]:
            lines.append(f"  {row['predictor']} {row['kind']} warmup={row['warmup']} alias={row['alias']} context={row['context']}: {row['correct']}/{row['outcomes']} correct; recovery={row['recovery_cycles']}; wrong-path={row['wrong_path_instructions']}")
        for row in predictions.get("effects", []):
            def acc(s):
                return "n/a" if s["accuracy"] is None else f"{s['accuracy']:.3f} ({s['correct']}/{s['outcomes']})"
            parts = [f"overall {acc(row['overall'])}", f"steady-state {acc(row['steady_state'])}"]
            for dim in ("warmup", "alias"):
                parts.append(f"{dim} " + ", ".join(f"{k}: {acc(v)}" for k, v in row[f"by_{dim}"].items()))
            lines.append(f"  {row['predictor']} {row['kind']} accuracy: " + "; ".join(parts))
    if "stall_causes" in report:
        causes = report["stall_causes"]
        lines.append(f"Measured stall cycles: {causes['measured_cycles']}; overlap cycles: {causes['overlap_cycles']}; "
                     f"zero-retirement cycles with unknown cause: {causes['unknown_zero_retirement_cycles']}.")
        for row in causes["by_cause"]:
            lines.append(f"  {row['evidence']} {row['scope']} {row['cause']}: {row['cycles']} cycles")
        for row in report["replays"]:
            lines.append(f"  {row['evidence']} replay {row['cause']}: {row['events']} events")
        kinds = report["commit_kinds"]
        lines.append(f"Observed physical commits: {kinds['physical_observed']}; architectural: "
                     f"{kinds['architectural_observed']}; predicated off: {kinds['predicated_off_observed']}; "
                     f"unknown commit kind: {kinds['unknown']}.")
    lines.append("Only explicit measured samples attribute stall causes. Open stage intervals are excluded. Use --json for full data.")
    return "\n".join(lines)
