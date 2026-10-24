"""Telling a hang from a run that only reached its max-cycles cap (shared by reduce and bisect).

A `timeout` result is a hang when its RVFI trace (C2) shows no retirement in the last
`hang_cycles` cycles before the end. Without a trace the question cannot be answered.

Review 11: an empty, truncated or foreign file counted as "nothing retired", so a run that was
still retiring reproduced a hang. The trace is now evidence only when it is a C2 trace (header
first), every line read from its end parses as a C2 record with a cycle, cycles do not decrease,
and it covers the final interval: either a retirement inside it (not a hang) or a C2 `end` event
at or after the run's last cycle (the capture did not stop early). Anything else is undetermined.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass
class TraceEvidence:
    ok: bool                       # the trace can be used (see the module text)
    why: str | None = None         # why not, when not ok
    last_retire: int | None = None # cycle of the last retirement, None if nothing retired
    end_cycle: int | None = None   # cycle of the C2 `end` event, None if there is none


def read_evidence(path: str) -> TraceEvidence:
    """Validate the C2 trace at `path` and read its last retirement and end event (reading back
    from the end only as far as the last retirement)."""
    from ..bundle.trace import reverse_lines
    try:
        with open(path, "rb") as f:
            first = f.readline()
        try:
            h = json.loads(first)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return TraceEvidence(False, "no C2 header (empty or not JSON)")
        if not isinstance(h, dict) or not str(h.get("schema", "")).startswith("rvw.rvfi/"):
            return TraceEvidence(False, "no C2 header (first line is not an rvw.rvfi schema record)")
        ev = TraceEvidence(True)
        later: int | None = None          # cycle of the record after this one (reading backwards)
        last_line = True
        for line in reverse_lines(path):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                return TraceEvidence(False, "a line near the end does not parse (truncated trace?)")
            if not isinstance(r, dict):
                return TraceEvidence(False, "a line near the end is not a C2 record")
            if "schema" in r:             # the header: the whole file was read
                break
            c = r.get("cycle")
            if not isinstance(c, int) or isinstance(c, bool) or c < 0:
                return TraceEvidence(False, "a record near the end has no valid cycle")
            if later is not None and c > later:
                return TraceEvidence(False, "cycles decrease near the end of the trace")
            later = c
            kind = r.get("event")
            if kind == "end":
                if not last_line:
                    return TraceEvidence(False, "records follow the end event")
                ev.end_cycle = c
            elif kind is None:
                if "pc" not in r:
                    return TraceEvidence(False, "a record near the end is neither a retirement nor an event")
                ev.last_retire = c
                break
            last_line = False
        return ev
    except OSError as e:
        return TraceEvidence(False, f"cannot read the trace: {e.strerror or e}")


def validate_hang_cycles(hang_cycles: int) -> None:
    """Reject thresholds that cannot establish a positive no-retirement interval."""
    if isinstance(hang_cycles, bool) or not isinstance(hang_cycles, int) or hang_cycles <= 0:
        raise ValueError("hang_cycles must be a positive integer")


def hang_check(run, hang_cycles: int) -> tuple[bool | None, str]:
    """Is this `timeout` a hang? True/False with the reason; None (undetermined) when there is no
    RVFI trace or it does not prove what happened in the last `hang_cycles` cycles."""
    validate_hang_cycles(hang_cycles)
    p = run.artifact("rvfi_trace")
    end = run.get("cycles")
    if not p or not os.path.isfile(p) or end is None:
        return None, "no RVFI trace to tell a hang from the max-cycles cap"
    ev = read_evidence(str(p))
    if not ev.ok:
        return None, f"the RVFI trace is not evidence: {ev.why}"
    end = int(end)
    last = ev.last_retire
    if last is not None and last > end:
        return None, f"the RVFI trace retires at cycle {last}, after the run's end ({end})"
    since = end - (last if last is not None else 0)
    what = f"last retirement at cycle {last}, {since} cycles before the end ({end})"
    if since < hang_cycles:
        return False, what
    if ev.end_cycle is None or ev.end_cycle < end:
        return None, (f"{what}, but the RVFI trace has no end event at or after cycle {end}: "
                      "it may have stopped early")
    return True, what
