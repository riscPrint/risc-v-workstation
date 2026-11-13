"""Commit-slot top-down attribution from RTL counter probes (`rvw perf topdown`).

The core project binds five counter probes: `topdown_slots` (commit width each cycle) and the
four classes `topdown_retiring`, `topdown_bad_speculation`, `topdown_backend_bound` and
`topdown_frontend_bound`. Their per-cycle predicates are the project's; the recommended ones
are those of the OoO model (`rvw/src/rvw/ooo/attribution.py`), so that the RTL and model
partitions compare like for like. This module only checks and reports the totals.
"""
from __future__ import annotations

import json
from pathlib import Path

from rvw.probes.events import read

CLASSES = ("retiring", "bad_speculation", "backend_bound", "frontend_bound")
SCHEMA = "rvw.topdown/1"


def _c2_retirements(path) -> int:
    with Path(path).open() as f:
        header = json.loads(f.readline())
        count = 0
        for line in f:
            record = json.loads(line)
            if "event" not in record and not record.get("trap"):
                count += 1
    if header.get("schema") != "rvw.rvfi/1":
        raise ValueError(f"{path}: not a C2 trace")
    return count


def report(events, c2=None, c1=None) -> dict:
    """`rvw.topdown/1` from a probe stream. The partition must cover every slot exactly once.

    `status` is `checked` when `retiring` equals the C2 retirement count (and the C1 instret
    when given), `unchecked` without C2. A mismatch raises: the binding is wrong."""
    stream = read(events)
    if stream.end is None:
        raise ValueError("probe stream has no end record (incomplete run); counters are not totals")
    counters = stream.counters
    names = ["topdown_slots"] + [f"topdown_{c}" for c in CLASSES]
    missing = [n for n in names if n not in counters]
    if missing:
        raise ValueError("probe stream lacks top-down counters: " + ", ".join(missing))
    slots = counters["topdown_slots"]
    values = {c: counters[f"topdown_{c}"] for c in CLASSES}
    if slots <= 0 or sum(values.values()) != slots:
        raise ValueError(f"top-down classes sum to {sum(values.values())}, not the {slots} slots")
    checks = {}
    if c2 is not None:
        checks["c2_retirements"] = _c2_retirements(c2)
        if checks["c2_retirements"] != values["retiring"]:
            raise ValueError(f"retiring slots {values['retiring']} differ from {checks['c2_retirements']} C2 retirements")
    if c1 is not None:
        result = json.loads(Path(c1).read_text())
        checks["c1_instret"] = int(result["instret"])
        if checks["c1_instret"] != values["retiring"]:
            raise ValueError(f"retiring slots {values['retiring']} differ from C1 instret {checks['c1_instret']}")
    cycles = int(stream.end.get("cycles", 0))
    return {"schema": SCHEMA, "unit": "commit_slots", "total_slots": slots, "cycles": cycles,
            "width": slots / cycles if cycles else None, "slots": values,
            "fractions": {c: v / slots for c, v in values.items()},
            "status": "checked" if c2 is not None else "unchecked", "checks": checks,
            "identity": stream.identity, "source": str(events),
            "method": "project-bound commit-slot partition; not hardware top-down counters"}


def render(r: dict) -> str:
    lines = [f"top-down ({r['unit']}, {r['total_slots']} slots over {r['cycles']} cycles, {r['status']})"]
    for c in CLASSES:
        lines.append(f"  {c:16s} {r['fractions'][c] * 100:6.1f} %  ({r['slots'][c]})")
    for name, slots in sorted(r.get("functions", {}).items()):
        lines.append(f"  {name}: " + ", ".join(f"{k}={slots[k]} ({100*slots[k]/max(1,sum(slots.values())):.1f}%)" for k in CLASSES))
    return "\n".join(lines)
