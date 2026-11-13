"""Clocked wave analyses: temporal sequences and handshake transactions.

Signals are sampled at each rising edge of the clock with their values just before the edge
(the SystemVerilog sampled value). `rose()`/`fell()`/`changed()` compare with the previous
sampled edge.
"""
from __future__ import annotations

import re
from typing import Iterator

from .expr import Expr, value_of
from .ops import CLOCK_RX
from .search import _steps, _validate, open_wave
from .vcd import WaveError, fmt_value


def pick_clock(hdr, clock: str):
    clocks = sorted((v for v in hdr.match(clock) if v.width == 1), key=lambda v: (v.name.count('.'), v.name))
    if not clocks:
        raise WaveError(f'no 1-bit clock matches {clock!r}; pass --clock')
    return clocks[0]


def sampled(src, clk, codes: set[str], t0: int, t1: int | None) -> Iterator[tuple[int, dict]]:
    """Yield (edge time, raw values before the edge) for each rising clock edge in [t0, t1]."""
    before, events = src.window(set(codes) | {clk.code}, t0, t1)
    cur = dict(before)
    for t, batch in _steps(events):
        old = value_of(cur.get(clk.code))
        new = old
        for code, raw in batch:
            if code == clk.code:
                new = value_of(raw)
        if old == 0 and new == 1:
            yield t, dict(cur)
        cur.update(batch)


# ------------------------------------------------------------------------------------------- sequences
_DELAY = re.compile(r'##\s*(\[\s*(\d+)\s*:\s*(\d+|\$)\s*\]|\d+)')


def parse_sequence(text: str) -> list[tuple[int, int | None, str]]:
    """'a ##1 b ##[1:3] c' -> [(0, 0, 'a'), (1, 1, 'b'), (1, 3, 'c')]. `$` is an open upper bound."""
    parts = _DELAY.split(text)
    # split returns: expr, delay, lo, hi, expr, ...
    first = parts[0].strip()
    if not first:
        raise WaveError('a sequence starts with an expression')
    steps = [(0, 0, first)]
    for i in range(1, len(parts), 4):
        whole, lo, hi, expr = parts[i], parts[i + 1], parts[i + 2], parts[i + 3].strip()
        if not expr:
            raise WaveError(f'missing expression after ##{whole}')
        if lo is None:
            lo = hi = int(whole)
        else:
            lo, hi = int(lo), (None if hi == '$' else int(hi))
            if hi is not None and hi < lo:
                raise WaveError(f'bad delay range ##[{lo}:{hi}]')
        steps.append((lo, hi, expr))
    return steps


def sequence(path: str, text: str, t0: int = 0, t1: int | None = None, clock: str = CLOCK_RX,
             limit: int | None = 100, enums: dict | None = None) -> dict:
    """Match `text` (`e0 ##N e1 ##[a:b] e2 ...`) at every clock edge where e0 holds.

    Each start is a thread. A thread advances at the first edge inside its delay window where
    the next expression holds, fails when the window passes, and is `pending` when the wave
    ends first. An unknown expression value does not advance a thread; it is counted.
    """
    _validate(t0, t1)
    steps = parse_sequence(text)
    lim = limit or None
    with open_wave(path) as src:
        exprs = [Expr(e, src.hdr.vars, enums) for _, _, e in steps]
        clk = pick_clock(src.hdr, clock)
        codes = set().union(*(e.codes for e in exprs))
        threads: list[list] = []      # [start time, start cycle, step index, cycle of last match]
        matches, failures = [], []
        n_match = n_fail = unknown = cycles = 0
        prev: dict = {}
        cycle = -1
        for t, vals in sampled(src, clk, codes, t0, t1):
            cycle += 1
            cycles += 1
            results = []
            for e in exprs:
                v = e.evaluate(vals, prev)
                if v is None:
                    unknown += 1
                results.append(v is not None and bool(v))
            alive = []
            for th in threads:
                start, start_cycle, k, last = th
                lo, hi, _ = steps[k]
                gap = cycle - last
                if gap >= lo and (hi is None or gap <= hi) and results[k]:
                    if k + 1 == len(steps):
                        n_match += 1
                        if lim is None or len(matches) < lim:
                            matches.append({'start': start, 'end': t, 'cycles': cycle - start_cycle})
                        continue
                    alive.append([start, start_cycle, k + 1, cycle])
                elif hi is not None and gap >= hi:
                    n_fail += 1
                    if lim is None or len(failures) < lim:
                        failures.append({'start': start, 'failed_step': k, 'expr': steps[k][2], 'at': t})
                else:
                    alive.append(th)
            threads = alive
            if results[0]:
                if len(steps) == 1:
                    n_match += 1
                    if lim is None or len(matches) < lim:
                        matches.append({'start': t, 'end': t, 'cycles': 0})
                else:
                    threads.append([t, cycle, 1, cycle])
            prev = vals
    return {'sequence': text, 'clock': clk.name, 'from': t0, 'to': t1, 'cycles': cycles,
            'matched': n_match, 'failed': n_fail, 'pending': len(threads),
            'pending_starts': [th[0] for th in threads[:lim or len(threads)]],
            'matches': matches, 'failures': failures, 'unknown_evaluations': unknown,
            'truncated': lim is not None and (n_match > lim or n_fail > lim), 'limit': lim}


# ---------------------------------------------------------------------------------------- transactions
def stream_signals(database: str, name: str) -> dict:
    """valid/ready/payload wave names of a Stream or Flow bundle, from a SpinalDB database."""
    from ..query.db import DesignDB
    from ..query import ops
    db = DesignDB(database)
    try:
        b = ops.bundle(db, name)
        sigs = db.resolve(name, allow_group=True)
        base = (b or {}).get('path') or db.normalize(name)
        out = {'bundle': base, 'type': (b or {}).get('type'), 'valid': None, 'ready': None, 'payload': []}
        for s in sigs:
            rel = (s.spinal_path or s.path)[len(base) + 1:] if (s.spinal_path or s.path).startswith(base + '.') else s.path
            wave = db.wave_path(s.path)
            if rel == 'valid':
                out['valid'] = wave
            elif rel == 'ready':
                out['ready'] = wave
            else:
                out['payload'].append(wave)
        if out['valid'] is None:
            raise WaveError(f'{name} has no valid signal; is it a Stream or Flow?')
        if out['type'] == 'Stream' and out['ready'] is None:
            raise WaveError(f'Stream {name} has no ready signal in the database')
        return out
    finally:
        db.close()


def transactions(path: str, valid: str, ready: str | None = None, payload: str | None = None,
                 t0: int = 0, t1: int | None = None, clock: str = CLOCK_RX, limit: int | None = 1000,
                 payload_names: list[str] | None = None) -> dict:
    """Handshake transfers sampled at rising clock edges.

    A transfer is an edge with valid && ready (valid alone without `ready`: Flow). For a
    Stream the report also counts stall edges (valid && !ready) and two protocol issues:
    `payload_changed` (payload changed while valid && !ready) and `valid_dropped` (valid fell
    before ready). Edges with unknown valid or ready count as `unknown`, never as transfers.
    """
    _validate(t0, t1)
    lim = limit or None
    with open_wave(path) as src:
        from .expr import resolve
        v = resolve(valid, src.hdr.vars)
        r = resolve(ready, src.hdr.vars) if ready else None
        if payload_names is not None:
            pay = [resolve(n, src.hdr.vars) for n in payload_names]
        else:
            pay = src.hdr.match(payload) if payload else []
        pay = [p for p in pay if p.code not in (v.code, r.code if r else None)]
        clk = pick_clock(src.hdr, clock)
        codes = {v.code, *(p.code for p in pay)} | ({r.code} if r else set())
        out, issues = [], []
        n = stalls = idle = unknown = edges = n_issues = 0
        waiting_since = None
        held = None             # payload while stalled
        prev_valid = None
        max_wait = 0
        for t, vals in sampled(src, clk, codes, t0, t1):
            edges += 1
            vv = value_of(vals.get(v.code))
            rv = value_of(vals.get(r.code)) if r else 1
            if vv is None or rv is None:
                unknown += 1
                prev_valid = None
                continue
            payload_now = {p.name: vals.get(p.code) for p in pay}
            if r and prev_valid == 1 and held is not None and not vv:
                n_issues += 1
                if lim is None or len(issues) < lim:
                    issues.append({'time': t, 'issue': 'valid_dropped', 'since': waiting_since})
            if vv and rv:
                wait = 0 if waiting_since is None else edges - 1 - waiting_since_edge
                max_wait = max(max_wait, wait)
                if held is not None and held != payload_now:
                    n_issues += 1
                    if lim is None or len(issues) < lim:
                        issues.append({'time': t, 'issue': 'payload_changed', 'since': waiting_since})
                n += 1
                if lim is None or len(out) < lim:
                    out.append({'time': t, 'wait_cycles': wait,
                                'payload': {p.name: (fmt_value(payload_now[p.name], p.width)
                                                     if payload_now[p.name] is not None else None) for p in pay}})
                waiting_since = held = None
            elif vv:
                stalls += 1
                if held is not None and held != payload_now:
                    n_issues += 1
                    if lim is None or len(issues) < lim:
                        issues.append({'time': t, 'issue': 'payload_changed', 'since': waiting_since})
                if waiting_since is None:
                    waiting_since, waiting_since_edge = t, edges - 1
                held = payload_now
            else:
                idle += 1
                waiting_since = held = None
            prev_valid = vv
    kind = 'Stream' if r else 'Flow'
    return {'kind': kind, 'valid': v.name, 'ready': r.name if r else None, 'payload': [p.name for p in pay],
            'clock': clk.name, 'from': t0, 'to': t1, 'edges': edges, 'transfers': n, 'stall_edges': stalls,
            'idle_edges': idle, 'unknown_edges': unknown, 'max_wait_cycles': max_wait,
            'throughput': (n / edges) if edges else None, 'pending': waiting_since,
            'transactions': out, 'issues': issues, 'issue_count': n_issues,
            'truncated': lim is not None and (n > lim or n_issues > lim), 'limit': lim}
