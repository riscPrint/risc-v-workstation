"""Wave time <-> run cycle mapping, wave coverage of a failure, and the RVFI stamp skew.

Adapters that follow C1 record in `details`:

    wave_time_per_cycle    wave time units per cycle (BOOM: 10)
    wave_time_of_cycle_1   wave time of the first sampled cycle (BOOM: after reset, about 16 cycles in)
    wave_window            {"from": cycle or null, "to": cycle or null} when --wave-from/--wave-to were given

so cycle N is at wave time `time_of_cycle_1 + (N - 1) * period`. Without `wave_time_of_cycle_1` the
mapping is unknown: the bundle then assumes cycle N at N * period, says so, and does not trust the
wave to cover the failure (it re-runs instead).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ..wave import ops as wops
from ..wave import vcd


@dataclass
class WaveClock:
    period: int
    t1: int                 # wave time of cycle 1
    known: bool             # t1 came from the run, not assumed
    source: str

    def time(self, cycle: int) -> int:
        return self.t1 + (int(cycle) - 1) * self.period

    def cycle(self, t: int) -> int:
        return (int(t) - self.t1) // self.period + 1

    def to_dict(self) -> dict:
        return {"period": self.period, "time_of_cycle_1": self.t1, "known": self.known, "source": self.source}


def wave_clock(run, core_cfg: dict, wave=None) -> WaveClock:
    d = run.get("details") or {}
    per = d.get("wave_time_per_cycle")
    src = "run details"
    if not per:
        per = core_cfg.get("period")
        src = "[core].period"
    if not per and wave is not None:
        per = wops.detect_period(str(wave))
        src = "clock detected in the wave"
    per = int(per or 10)
    t1 = d.get("wave_time_of_cycle_1")
    if isinstance(t1, (int, float)) and t1 >= 0:
        return WaveClock(per, int(t1), True, f"period from {src}; time of cycle 1 from run details")
    return WaveClock(per, per, False, f"period from {src}; time of cycle 1 unknown (assumed cycle N at N x period)")


def covers(run, wave, fail_cycle: int, clock: WaveClock) -> tuple[bool, str]:
    """Does `wave` (of `run`) reach the failure cycle? (answer, reason).

    No slack, on purpose: the wave must reach the failing cycle's own edge, `clock.time(fail_cycle)`.
    A wave that ends earlier holds the cycle before the failure. BOOM's waves end exactly at that
    edge (cycle 125 at 1410 with time of cycle 1 = 170, period 10)."""
    if wave is None:
        return False, "no wave"
    if not clock.known:
        return False, "the run does not record the wave time of cycle 1 (details.wave_time_of_cycle_1)"
    ww = (run.get("details") or {}).get("wave_window") or {}
    if ww.get("to") is not None and int(ww["to"]) < fail_cycle:
        return False, f"the wave window ends at cycle {int(ww['to'])}, before the failure at {fail_cycle}"
    if ww.get("from") is not None and int(ww["from"]) > fail_cycle:
        return False, f"the wave window starts at cycle {int(ww['from'])}, after the failure at {fail_cycle}"
    end = vcd.end_time(str(wave))
    if end is None or end < clock.time(fail_cycle):
        return False, (f"the wave ends at cycle {clock.cycle(end)}, before the failure at {fail_cycle}"
                       if end is not None else "the wave is empty")
    return True, f"wave reaches cycle {clock.cycle(end)}"


def commit_cycles(wave: str, regex: str, clock: WaveClock) -> tuple[Counter, int, int]:
    """Per cycle, how many of the commit-valid signals matching `regex` were 1 (from the wave)."""
    rows = wops.changes(wave, regex)
    end = vcd.end_time(wave)
    cnt: Counter = Counter()
    if not rows or end is None:
        return cnt, 0, -1
    names = {r["signal"] for r in rows}
    vals: dict[str, int | None] = {}
    lo = None                  # first cycle where every commit signal has a known value
    hi = clock.cycle(end)
    i = 0
    while i < len(rows):
        t = rows[i]["time"]
        while i < len(rows) and rows[i]["time"] == t:
            v = rows[i]["value"]
            vals[rows[i]["signal"]] = 1 if v in ("1", "0x1") else 0 if v in ("0", "0x0") else None
            i += 1
        t_next = rows[i]["time"] if i < len(rows) else end + 1
        if len(vals) < len(names) or any(x is None for x in vals.values()):
            lo = None
            cnt.clear()
            continue
        if lo is None:
            lo = clock.cycle(t)
        k = sum(vals.values())
        if k:
            for c in range(clock.cycle(t), clock.cycle(t_next - 1) + 1):
                cnt[c] = k
    return cnt, (lo if lo is not None else hi + 1), hi


def rvfi_skew(wave: str, regex: str, clock: WaveClock, retired: list[dict], max_skew: int = 8) -> dict | None:
    """Cycles by which the RVFI trace's retirement stamps follow the wave's commit signals.

    Matches the per-cycle retirement counts of the RVFI tail against the per-cycle commit counts in
    the wave for every shift in [-max_skew, max_skew]; reports the shift that explains them, or
    None when no shift does (fewer than 4 cycles to compare, or < 90% agreement)."""
    rv = Counter(int(r["cycle"]) for r in retired if r.get("cycle") is not None)
    if not rv:
        return None
    first = min(rv)
    rv.pop(first, None)          # the oldest cycle of the tail may be cut
    wc, lo, hi = commit_cycles(wave, regex, clock)
    if not rv or not wc:
        return None
    best, tie = None, False
    for s in range(-max_skew, max_skew + 1):
        cyc = [c for c in rv if lo <= c - s <= hi]
        if len(cyc) < 4:
            continue
        span = range(min(cyc) - s, max(cyc) - s + 1)
        extra = [c for c in span if wc.get(c) and (c + s) not in rv]
        ok = sum(1 for c in cyc if wc.get(c - s) == rv[c])
        score = ok / (len(cyc) + len(extra))
        if best is None or score > best[0]:
            best, tie = (score, s, len(cyc), max(cyc)), False
        elif score == best[0]:
            tie = True
    if best is None or best[0] < 0.9 or tie:
        return None                      # no shift explains the trace, or several do equally well
    score, s, n, last = best
    return {"rvfi_minus_wave_commit": s, "agreement": round(score, 3), "cycles_compared": n,
            "last_rvfi_cycle": last, "last_wave_commit_cycle": last - s, "commit_signals": regex}
