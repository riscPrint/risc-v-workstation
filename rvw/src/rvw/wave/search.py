"""Window reads shared by VCD/FST streams and indexed snapshots, and the searches built on them.

`open_wave(path)` yields a `Source` with the header and one `window(codes, t0, t1)` call:
the raw values strictly before `t0`, then every change of the selected codes with
`t0 <= t <= t1` in file order. Indexed snapshots read only the selected codes' rows
through the `signal_time` index. Streams make one pass and keep one value per code.
"""
from __future__ import annotations

import heapq
from contextlib import contextmanager
from typing import Iterator

from . import vcd
from .capture import wave_input
from .expr import Expr, value_of
from .vcd import WaveError

MAX_T = 2 ** 63 - 1


def _validate(t0: int, t1: int | None) -> None:
    if t0 < 0 or (t1 is not None and t1 < 0):
        raise WaveError('wave time bounds must be non-negative')
    if t1 is not None and t1 < t0:
        raise WaveError('wave end time must not be before start time')


class Source:
    def __init__(self, hdr, window, end):
        self.hdr = hdr
        self.window = window
        self.end = end


@contextmanager
def open_wave(path: str) -> Iterator[Source]:
    if str(path).endswith('.rvwi'):
        from .index import reader, state
        with reader(path) as (db, hdr):
            def window(codes, t0, t1):
                before = state(db, codes, t0 - 1) if t0 > 0 else {}
                hi = MAX_T if t1 is None else t1
                streams = [db.execute('SELECT t, seq, code, raw FROM events INDEXED BY signal_time '
                                      'WHERE code=? AND t>=? AND t<=? ORDER BY t, seq', (c, t0, hi))
                           for c in sorted(codes)]
                merged = heapq.merge(*streams)
                return before, ((t, c, r) for t, _, c, r in merged)

            def end():
                return db.execute('SELECT MAX(t) FROM events WHERE code IS NULL').fetchone()[0]
            yield Source(hdr, window, end)
        return
    with wave_input(path) as saved, vcd.open_text(saved) as f:
        hdr = vcd.read_header(f)
        used = []

        def window(codes, t0, t1):
            if used:
                raise WaveError('a streamed wave supports one window read per open')
            used.append(1)
            before: dict[str, str] = {}

            def events():
                for t, code, raw in vcd.body_records(f):
                    if t1 is not None and t > t1:
                        return
                    if code is None or code not in codes:
                        continue
                    if t < t0:
                        before[code] = raw
                    else:
                        yield t, code, raw
            gen = events()
            # Fill `before` up to the first event in the window, then hand back the rest.
            first = next(gen, None)
            snapshot = dict(before)
            if first is None:
                return snapshot, iter(())

            def rest():
                yield first
                yield from gen
            return snapshot, rest()
        yield Source(hdr, window, lambda: vcd.end_time(saved))


def _steps(events) -> Iterator[tuple[int, list[tuple[str, str]]]]:
    """Group (t, code, raw) by time."""
    cur, batch = None, []
    for t, code, raw in events:
        if t != cur and batch:
            yield cur, batch
            batch = []
        cur = t
        batch.append((code, raw))
    if batch:
        yield cur, batch


def find(path: str, expression: str, t0: int = 0, t1: int | None = None, limit: int | None = 1000) -> dict:
    """Intervals where `expression` is true in [t0, t1], with first and last match.

    The expression is evaluated at t0 and after all changes at each time where a referenced
    signal changes. An interval's `end` is the time it became false or unknown; `null` means
    it holds through the window end. Unknown evaluation points never count as true.
    """
    _validate(t0, t1)
    if limit is not None and limit < 0:
        raise WaveError('wave match limit must be non-negative')
    lim = limit or None
    with open_wave(path) as src:
        ex = Expr(expression, src.hdr.vars)
        before, events = src.window(ex.codes, t0, t1)
        cur, prev = dict(before), dict(before)
        intervals: list[dict] = []
        n_intervals = steps = unknown = true_time = 0
        first = last = open_start = None
        it = _steps(events)
        nxt = next(it, None)

        def points():
            nonlocal nxt
            if nxt is not None and nxt[0] == t0:
                cur.update(nxt[1])
                nxt = next(it, None)
            yield t0
            while nxt is not None:
                t, batch = nxt
                cur.update(batch)
                nxt = next(it, None)
                yield t
        last_t = t0
        for t in points():
            v = ex.evaluate(cur, prev)
            prev = dict(cur)
            steps += 1
            if v is None:
                unknown += 1
            hold = v is not None and bool(v)
            if hold and open_start is None:
                open_start = t
                if first is None:
                    first = t
            elif not hold and open_start is not None:
                n_intervals += 1
                true_time += t - open_start
                last = {'start': open_start, 'end': t}
                if lim is None or len(intervals) < lim:
                    intervals.append(last)
                open_start = None
            last_t = t
        if open_start is not None:
            n_intervals += 1
            end = t1 if t1 is not None else src.end()
            true_time += max(0, (end or last_t) - open_start)
            last = {'start': open_start, 'end': None}
            if lim is None or len(intervals) < lim:
                intervals.append(last)
    return {'expr': expression, 'signals': ex.signals(), 'from': t0, 'to': t1,
            'first': first, 'last': last, 'count': n_intervals, 'matches': intervals,
            'truncated': lim is not None and n_intervals > lim, 'limit': lim,
            'true_time': true_time, 'steps': steps, 'unknown_steps': unknown}


def edges(path: str, regex: str, t0: int = 0, t1: int | None = None) -> dict:
    """Per-signal value-change counts in [t0, t1]; rising/falling counts for 1-bit signals.

    A transition at time t compares the value after all changes at t with the value before t.
    Repeated dumps of the same value are not changes. Transitions to or from x/z count under
    `unknown`, not as edges.
    """
    _validate(t0, t1)
    with open_wave(path) as src:
        vars = src.hdr.match(regex)
        by_code: dict[str, list] = {}
        for v in vars:
            by_code.setdefault(v.code, []).append(v)
        before, events = src.window(set(by_code), t0, t1)
        prev = dict(before)
        counts = {c: {'changes': 0, 'rising': 0, 'falling': 0, 'unknown': 0} for c in by_code}
        for t, batch in _steps(events):
            final: dict[str, str] = {}
            for code, raw in batch:
                final[code] = raw
            for code, raw in final.items():
                old = prev.get(code)
                prev[code] = raw
                if old is None or old == raw:
                    continue      # first value or a repeated dump
                c = counts[code]
                c['changes'] += 1
                a, b = value_of(old), value_of(raw)
                if a is None or b is None:
                    c['unknown'] += 1
                elif by_code[code][0].width == 1 and isinstance(a, int) and isinstance(b, int):
                    if b and not a:
                        c['rising'] += 1
                    elif a and not b:
                        c['falling'] += 1
    out = []
    for code, vs in by_code.items():
        for v in vs:
            row = {'signal': v.name, 'width': v.width, **counts[code]}
            if v.width != 1:
                row.pop('rising')
                row.pop('falling')
            out.append(row)
    return {'from': t0, 'to': t1, 'signals': out}
