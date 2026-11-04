"""Explicit producer cause samples. Never promote residence or dependency edges to causes."""
from collections import Counter, defaultdict


def event_report(trace, commits):
    # Each sample covers [cycle, cycle+1). Deduplicate repeated signals in one scope.
    samples = defaultdict(set)
    by_cause = defaultdict(set)
    for cycle, scope, cause, evidence in trace.stalls:
        samples[evidence, cycle].add((scope, cause))
        by_cause[scope, cause, evidence].add(cycle)
    measured = {cycle for evidence, cycle in samples if evidence == "measured"}
    overlaps = Counter()
    for (evidence, cycle), causes in samples.items():
        if evidence == "measured" and len(causes) > 1:
            overlaps[tuple(sorted(causes))] += 1
    # Find zero-retirement intervals with no measured cause, without expanding quiet tails.
    points = {trace.start, trace.end + 1}
    for cycle in measured | set(commits):
        points.update((cycle, cycle + 1))
    points = sorted(points)
    unknown = []
    for left, right in zip(points, points[1:]):
        if left not in measured and not commits[left]:
            if unknown and unknown[-1]["end"] == left:
                unknown[-1]["end"] = right
            else:
                unknown.append({"start": left, "end": right})
    replays = Counter((cause, evidence) for _, _, cause, evidence in trace.replays)
    kinds = Counter(i.commit_kind or "unknown" for i in trace.instructions.values()
                    if i.end is not None and not i.flushed)
    from .prediction import report as prediction_report
    return {
        "predictions": prediction_report(trace.predictions),
        "stall_causes": {
            "basis": "Explicit one-cycle producer samples. Causes may overlap. Inferred samples are separate.",
            "by_cause": [{"scope": scope, "cause": cause, "evidence": evidence,
                          "cycles": len(cycles),
                          "zero_retirement_cycles": sum(not commits[t] for t in cycles)}
                         for (scope, cause, evidence), cycles in sorted(by_cause.items())],
            "measured_cycles": len(measured),
            "measured_zero_retirement_cycles": sum(not commits[t] for t in measured),
            "overlap_cycles": sum(overlaps.values()),
            "overlaps": [{"causes": [{"scope": s, "cause": c} for s, c in causes], "cycles": n}
                         for causes, n in sorted(overlaps.items())],
            "unknown_zero_retirement_cycles": sum(r["end"] - r["start"] for r in unknown),
            "longest_unknown": sorted(unknown, key=lambda r: r["end"] - r["start"], reverse=True)[:20],
            "unknown_intervals": len(unknown),
            "unknown_basis": "No measured cause sample during zero R-retirement cycles; includes idle and uninstrumented time.",
        },
        "replays": [{"cause": cause, "evidence": evidence, "events": n}
                    for (cause, evidence), n in sorted(replays.items())],
        "commit_kinds": {
            "physical_observed": kinds["architectural"] + kinds["predicated_off"],
            "architectural_observed": kinds["architectural"],
            "predicated_off_observed": kinds["predicated_off"],
            "unknown": kinds["unknown"],
            "architectural_total": kinds["architectural"] if not kinds["unknown"] else None,
            "basis": "Explicit commit annotations only. R type 0 and event IPC retain their original meaning.",
        },
    }
