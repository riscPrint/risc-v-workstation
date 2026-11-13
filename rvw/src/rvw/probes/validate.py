"""Validate a probe event stream against the `rvw.probe-events/1` contract.

Each finding names the probe (`kind/name`), the check and the first cycle, so a designer can
see which probe is misplaced. Checks without C2 use the stream alone: header and end record,
value widths, counter totals, instruction-ID life cycles and walk grouping. With the run's
C2 trace, the probes that claim retired events (branch, interrupt, bus, csr, retire, walk)
are compared with the retirements, through the same converters the consumer tools use.
`clean` says only that no check found a problem; it is not a proof of the probe wiring.
"""
from __future__ import annotations

import json
import tempfile
from collections import defaultdict
from pathlib import Path

from .events import read


def _finding(probe, check, message, cycle=None, severity="error"):
    f = {"probe": probe, "check": check, "severity": severity, "message": message}
    if cycle is not None:
        f["first_cycle"] = cycle
    return f


def _label(p) -> str:
    return f"{p.kind}/{p.name}"


def stream_findings(stream) -> list[dict]:
    """Checks that need only the stream."""
    out = []
    end = stream.end
    last = stream.rows[-1][0] if stream.rows else 0
    counts = defaultdict(int)
    first = {}
    for cycle, pid, values in stream.rows:
        counts[pid] += 1
        first.setdefault(pid, cycle)
        p = stream.probes[pid]
        for (name, width), v in zip(p.fields, values):
            if v < 0 or v >> width:
                out.append(_finding(_label(p), "width", f"field {name} value {v} does not fit {width} bits", cycle))
                break
    if end is None:
        out.append(_finding("stream", "end", "no end record: the run did not finish or the collector was not closed",
                            severity="warning"))
    else:
        if int(end.get("cycles", -1)) < last:
            out.append(_finding("stream", "end", f"end cycles {end.get('cycles')} is before the last event cycle {last}"))
        recorded = {int(k): int(v) for k, v in (end.get("events") or {}).items()}
        for p in stream.probes:
            if p.kind in ("counter", "fault"):
                continue
            if recorded.get(p.id, 0) != counts.get(p.id, 0):
                out.append(_finding(_label(p), "end", f"end record counts {recorded.get(p.id, 0)} events, the stream has "
                                    f"{counts.get(p.id, 0)}"))
        totals = end.get("counters") or {}
        cycles = int(end.get("cycles", 0))
        for p in stream.of_kind("counter"):
            if p.name not in totals:
                out.append(_finding(_label(p), "counter", "counter has no total in the end record"))
                continue
            total, active = int(totals[p.name]), recorded.get(p.id)
            width = dict(p.fields).get("inc", 1)
            if total < 0:
                out.append(_finding(_label(p), "counter", f"negative total {total}"))
            elif total > cycles * ((1 << width) - 1):
                out.append(_finding(_label(p), "counter", f"total {total} exceeds {cycles} cycles times the largest "
                                    f"{width}-bit increment"))
            if active is not None and (active > cycles or total < active or (width == 1 and total != active)):
                out.append(_finding(_label(p), "counter", f"total {total} does not fit {active} active cycles"))
    out += _id_findings(stream)
    out += _walk_findings(stream)
    return out


def _id_findings(stream) -> list[dict]:
    """Stage, retire and flush IDs: retire or flush only a staged ID, once; no stage after it."""
    if not stream.of_kind("retire") and not stream.of_kind("flush"):
        return []
    staged, closed, out, reported = set(), {}, [], set()

    def once(p, check, message, cycle):
        if (p.id, check) not in reported:
            reported.add((p.id, check))
            out.append(_finding(_label(p), check, message, cycle))

    for cycle, p, v in stream.events("stage", "retire", "flush"):
        i = v["id"]
        if p.kind == "stage":
            if i in closed:
                once(p, "id", f"stage event for ID {i} after it was {closed[i]}: IDs are reused or the retire/flush "
                     "probe fires too early", cycle)
            staged.add(i)
        else:
            what = "retired" if p.kind == "retire" else "flushed"
            if stream.of_kind("stage") and i not in staged:
                once(p, "id", f"{what} ID {i} was never in a stage: the {p.kind} probe uses another ID source", cycle)
            if i in closed:
                once(p, "id", f"ID {i} {what} after it was {closed[i]}", cycle)
            closed[i] = what
    return out


def _walk_findings(stream) -> list[dict]:
    """Each walk result closes the walker's responses; responses need a following result."""
    out, open_reads = [], defaultdict(list)
    results = {p.meta.get("walker", p.name) for p in stream.of_kind("walk") if p.meta.get("event") == "result"}
    if not results:
        return out
    for cycle, p, v in stream.events("walk"):
        w = p.meta.get("walker", p.name)
        if p.meta.get("event") == "response":
            open_reads[w].append(cycle)
        elif p.meta.get("event") == "result":
            if not open_reads[w] and v.get("status") == 0:
                out.append(_finding(_label(p), "walk", "a successful walk result with no PTE response before it", cycle))
            open_reads[w] = []
    for w, cycles in open_reads.items():
        if cycles and w in results:
            out.append(_finding(f"walk/{w}_response", "walk", f"{len(cycles)} PTE responses after the last walk result",
                                cycles[0]))
    return out


def c2_findings(stream, events_path, c2_path) -> list[dict]:
    """Probes that claim retired events, against the run's C2, through the consumer converters."""
    from . import api, convert as cv
    out = []
    with tempfile.TemporaryDirectory(prefix="rvw-probes-check-") as tmp:
        tmp = Path(tmp)

        def run(label, to, probe=None, field="status"):
            try:
                rep = api.run_convert(events_path, to, tmp / f"{to}-{probe}.json", c2=c2_path, probe=probe)
            except (ValueError, KeyError) as e:
                out.append(_finding(label, "c2", f"{to}: {e}"))
                return
            if rep.get(field) == "mismatch":
                first = (rep.get("mismatches") or [{}])[0]
                out.append(_finding(label, "c2", f"{to}: {json.dumps(first)}", first.get("cycle")))

        for p in stream.of_kind("branch"):
            run(_label(p), "bp-events", p.name)
        if stream.of_kind("interrupt"):
            run(_label(stream.of_kind("interrupt")[0]), "interrupts")
        for p in stream.of_kind("bus"):
            if "write" in dict(p.fields):
                run(_label(p), "bus", p.name)
        for p in stream.of_kind("csr"):
            run(_label(p), "csr-writes", p.name)
        retires = stream.of_kind("retire")
        if retires:
            header, recs, _ = cv.read_c2(c2_path)
            n = sum(1 for _, p, _ in stream.events("retire"))
            if stream.end is not None and n != len(recs):
                out.append(_finding("/".join(_label(p) for p in retires), "c2",
                                    f"{n} retire events, C2 has {len(recs)} retirements"))
    return out


def validate(events, c2=None) -> dict:
    try:
        stream = read(events)
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        return {"status": "violations", "findings": [_finding("stream", "format", str(e))], "probes": 0}
    findings = stream_findings(stream)
    if c2 is not None:
        findings += c2_findings(stream, events, c2)
    errors = [f for f in findings if f["severity"] == "error"]
    status = "violations" if errors else ("inconclusive" if stream.end is None else "clean")
    return {"status": status, "probes": len(stream.probes), "events": len(stream.rows), "c2": str(c2) if c2 else None,
            "findings": findings,
            "note": "clean means no check found a problem; it does not prove the probe wiring"}
