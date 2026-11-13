"""Compare two waves and report the first divergence.

Signals are paired by name (after optional prefix mapping). Values compare by meaning:
`b0001` and `b1` are equal; x/z bits differ from known bits. With `clock`, both waves are
sampled at A's rising edges (pre-edge values); otherwise at every time either wave changes.
`offset` shifts B's times: B time = A time + offset.
"""
from __future__ import annotations

import heapq

from .expr import value_of
from .search import _steps, _validate, open_wave
from .temporal import pick_clock
from .vcd import WaveError, fmt_value


def _norm(raw, width):
    return None if raw is None else fmt_value(raw, width)


def diff(a: str, b: str, regex: str | None = None, t0: int = 0, t1: int | None = None,
         offset: int = 0, clock: str | None = None, map_prefix: tuple[str, str] | None = None,
         limit: int = 50, stop: bool = True) -> dict:
    """First divergence and per-signal first divergence times.

    `stop` ends the scan at the first divergent time; otherwise the scan continues and
    reports each signal's first divergence and a count of divergent times.
    """
    _validate(t0, t1)
    if t0 + offset < 0:
        raise WaveError('offset moves the window before time 0 in wave B')
    with open_wave(a) as wa, open_wave(b) as wb:
        va = wa.hdr.match(regex)
        bname = {v.name: v for v in wb.hdr.vars}

        def other(name):
            if map_prefix and name.startswith(map_prefix[0]):
                return map_prefix[1] + name[len(map_prefix[0]):]
            return name
        pairs = [(x, bname[other(x.name)]) for x in va if other(x.name) in bname]
        only_a = sorted(x.name for x in va if other(x.name) not in bname)
        if not pairs:
            raise WaveError('no signal names in common; use --map A_PREFIX=B_PREFIX')
        codes_a = {x.code for x, _ in pairs}
        codes_b = {y.code for _, y in pairs}
        clk = pick_clock(wa.hdr, clock) if clock else None
        if clk:
            codes_a.add(clk.code)
        ba, ea = wa.window(codes_a, t0, t1)
        bb, eb = wb.window(codes_b, t0 + offset, None if t1 is None else t1 + offset)
        cur_a, cur_b = dict(ba), dict(bb)
        tagged = heapq.merge(((t, 0, c, r) for t, c, r in ea), ((t - offset, 1, c, r) for t, c, r in eb),
                             key=lambda e: e[0])
        first = None
        first_signals: list[dict] = []
        per_signal: dict[str, int] = {}
        divergent_times = 0
        compared = 0

        def compare(t, va_, vb_):
            nonlocal first, divergent_times, compared
            compared += 1
            found = []
            for x, y in pairs:
                ra, rb = _norm(va_.get(x.code), x.width), _norm(vb_.get(y.code), y.width)
                if ra != rb:
                    found.append({'signal': x.name, 'b_signal': y.name, 'a': ra, 'b': rb})
                    per_signal.setdefault(x.name, t)
            if found:
                divergent_times += 1
                if first is None:
                    first = t
                    first_signals.extend(found[:limit])
            return bool(found)

        def batches():
            cur, ba_, bb_ = None, [], []
            for t, side, c, r in tagged:
                if t != cur and cur is not None:
                    yield cur, ba_, bb_
                    ba_, bb_ = [], []
                cur = t
                (ba_ if side == 0 else bb_).append((c, r))
            if cur is not None:
                yield cur, ba_, bb_
        stopped = False
        it = batches()
        nxt = next(it, None)
        if not clk:
            if nxt is not None and nxt[0] == t0:
                cur_a.update(nxt[1])
                cur_b.update(nxt[2])
                nxt = next(it, None)
            stopped = compare(t0, cur_a, cur_b) and stop
        while nxt is not None and not stopped:
            t, xa, xb = nxt
            if clk:
                old = value_of(cur_a.get(clk.code))
                new = old
                for c, r in xa:
                    if c == clk.code:
                        new = value_of(r)
                if old == 0 and new == 1:
                    stopped = compare(t, cur_a, cur_b) and stop
                cur_a.update(xa)
                cur_b.update(xb)
            else:
                cur_a.update(xa)
                cur_b.update(xb)
                stopped = compare(t, cur_a, cur_b) and stop
            nxt = next(it, None)
    return {'a': a, 'b': b, 'offset': offset, 'from': t0, 'to': t1,
            'mode': f'clock {clk.name}' if clk else 'events', 'signals_compared': len(pairs),
            'only_in_a': only_a[:limit], 'only_in_a_count': len(only_a),
            'status': 'diverged' if first is not None else 'match' if compared else 'no_points',
            'match': first is None and compared > 0, 'complete': not stopped,
            'first_divergence': first, 'divergent': first_signals,
            'first_divergence_by_signal': [{'signal': k, 'time': v} for k, v in
                                           sorted(per_signal.items(), key=lambda kv: (kv[1], kv[0]))[:limit]],
            'divergent_times': divergent_times, 'points_compared': compared}
