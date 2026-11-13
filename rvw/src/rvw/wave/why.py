"""Active-driver tracing: why does a signal have its value at time T?

Joins waveform values (an indexed snapshot) with the drivers in a SpinalDB design database.
For each signal: its value at T, the assignments that drive it, which assignment was active
(from the wave values of the condition signals), and the values of the signals it reads.
Registers are explained at their last value change: the inputs are read just before that
clock edge. The walk continues through the read signals up to `depth` levels.

Every step says what it is based on. `active: inferred` means the database conditions were
evaluated from wave values; `ambiguous` or `unknown` means the wave did not decide it.
"""
from __future__ import annotations

import json
import re

from . import index as wave_index
from .expr import value_of
from .vcd import WaveError, fmt_value


def _int(text):
    try:
        return int(str(text).strip().replace('_', ''), 0)
    except (TypeError, ValueError):
        m = re.fullmatch(r"\s*(\d+)'[bB]([01]+)\s*", str(text))
        return int(m.group(2), 2) if m else None


class _Wave:
    def __init__(self, path):
        self.path = wave_index.ensure(path)
        self._cm = wave_index.reader(self.path)
        self.conn, self.hdr = self._cm.__enter__()
        meta = json.loads(self.conn.execute('SELECT value FROM metadata').fetchone()[0])
        self.identity = {'index': self.path, 'source': meta.get('source'), 'sha256': meta.get('sha256')}
        self.by_name = {v.name: v for v in self.hdr.vars}

    def close(self):
        self._cm.__exit__(None, None, None)

    def raw(self, var, t):
        row = self.conn.execute('SELECT raw FROM events WHERE code=? AND t<=? ORDER BY t DESC, seq DESC LIMIT 1',
                                (var.code, t)).fetchone()
        return row[0] if row else None

    def changed_at(self, var, t):
        """Time of the last value change at or before t (None if the value was never changed)."""
        now = self.raw(var, t)
        if now is None:
            return None
        row = self.conn.execute('SELECT MAX(t) FROM events WHERE code=? AND t<=? AND raw<>?',
                                (var.code, t, now)).fetchone()
        if row[0] is None:
            first = self.conn.execute('SELECT MIN(t) FROM events WHERE code=?', (var.code,)).fetchone()[0]
            return first
        nxt = self.conn.execute('SELECT MIN(t) FROM events WHERE code=? AND t>? AND t<=?',
                                (var.code, row[0], t)).fetchone()
        return nxt[0]


def _conds(db, cid):
    """Condition chain (outermost first) with the condition signal ids."""
    out = []
    while cid is not None:
        r = db.conn.execute('SELECT parent_id, kind, expr, keys, signal_id FROM conds WHERE id=?', (cid,)).fetchone()
        if r is None:
            break
        out.append({'kind': r[1], 'expr': r[2], 'keys': r[3], 'signal_id': r[4]})
        cid = r[0]
    return list(reversed(out))


class Tracer:
    def __init__(self, db, wave, max_nodes=64):
        self.db = db
        self.wave = wave
        self.max_nodes = max_nodes
        self.nodes = 0
        self.seen = set()
        self.truncated = False

    def var(self, s):
        return self.wave.by_name.get(self.db.wave_path(s.path))

    def value(self, s, t):
        v = self.var(s)
        if v is None:
            return None, None
        raw = self.wave.raw(v, t)
        return raw, (fmt_value(raw, v.width) if raw is not None else None)

    def cond_holds(self, c, t):
        """True/False from the wave, None when the wave cannot decide."""
        if c['signal_id'] is None:
            return None, None
        s = self.db.signal_by_id(c['signal_id'])
        raw, shown = self.value(s, t)
        val = value_of(raw)
        if val is None:
            return None, {'signal': s.path, 'value': shown}
        if c['kind'] == 'when':
            holds = bool(val)
        elif c['kind'] == 'else':
            holds = not bool(val)
        elif c['kind'] == 'case':
            keys = [_int(k) for k in str(c['keys'] or '').split(',')]
            holds = None if any(k is None for k in keys) else val in keys
        else:
            holds = None          # switch default: needs all sibling keys
        return holds, {'signal': s.path, 'value': shown}

    def explain(self, s, t, depth):
        node = {'signal': s.path, 'kind': s.kind, 'time': t}
        v = self.var(s)
        node['wave'] = v.name if v else None
        raw, shown = self.value(s, t)
        node['value'] = shown
        if v is None:
            node['status'] = 'unresolved'
            node['cause'] = f'no waveform signal {self.db.wave_path(s.path)}'
            return node
        key = (s.id, t)
        if key in self.seen:
            node['status'] = 'seen'
            return node
        self.seen.add(key)
        self.nodes += 1
        at = t
        if s.is_reg:
            changed = self.wave.changed_at(v, t)
            node['set_at'] = changed
            if changed is None:
                node['status'] = 'never_set'
                return node
            at = changed - 1
            if at < 0:
                node['status'] = 'initial'
                node['cause'] = 'value from the first dump; no earlier clock edge in the wave'
                return node
            cd = self.db.clock_domain(s.clock_domain_id) or {}
            reset = self._reset(s, cd, changed)
            if reset:
                node['reset'] = reset
                if reset.get('asserted'):
                    node['status'] = 'reset'
                    node['cause'] = f"reset {reset['signal']} asserted; reset value {s.reset_value}"
                    return node
        node['evaluated_at'] = at
        rows = self.db.q('SELECT a.id, a.kind, a.range, a.source, a.cond_id, f.path, a.line FROM assignments a '
                         'LEFT JOIN files f ON f.id=a.file_id WHERE a.target_id=? AND a.kind<>? ORDER BY a.seq',
                         (s.id, 'init'))
        candidates = []
        for aid, kind, rng, source, cid, file, line in rows:
            chain = _conds(self.db, cid)
            holds, evidence = True, []
            for c in chain:
                h, e = self.cond_holds(c, at)
                evidence.append({'kind': c['kind'], 'expr': c['expr'], 'keys': c['keys'], 'holds': h,
                                 **(e or {'signal': None, 'value': None})})
                if h is False:
                    holds = False
                    break
                if h is None:
                    holds = None
            candidates.append({'id': aid, 'kind': kind, 'range': rng, 'source': source,
                               'loc': f'{file}:{line}' if file else None, 'holds': holds, 'conditions': evidence})
        if not candidates:
            node['status'] = 'no_driver'
            node['cause'] = 'no assignment in the database (input, clock, BlackBox output or memory)'
            return node
        # The last full-width assignment whose conditions hold wins. An undecided later
        # assignment could also win, so it makes the answer ambiguous.
        active, ambiguous = None, False
        for c in reversed(candidates):
            if c['holds'] is None:
                ambiguous = True
            elif c['holds']:
                active = c
                break
        if active is None and not ambiguous and s.is_reg:
            node['status'] = 'held'
            node['cause'] = 'no assignment condition holds before the edge; the register kept its value'
        elif ambiguous:
            node['status'] = 'ambiguous'
            node['cause'] = 'the wave does not decide every assignment condition'
        elif active is None:
            node['status'] = 'no_active_driver'
            node['cause'] = 'no assignment condition holds (latch, default value or incomplete database)'
        else:
            node['status'] = 'active'
            node['evidence'] = 'inferred from database conditions and wave values'
        node['assignments'] = candidates
        if active is not None:
            node['active'] = active['id']
            reads = self.db.q('SELECT DISTINCT signal_id, kind FROM assign_reads WHERE assignment_id=? ORDER BY signal_id',
                              (active['id'],))
            node['reads'] = []
            children = []
            for sid, kind in reads:
                r = self.db.signal_by_id(sid)
                _, val = self.value(r, at)
                node['reads'].append({'signal': r.path, 'kind': kind, 'value': val})
                if depth > 0 and kind == 'data':
                    if self.nodes >= self.max_nodes:
                        self.truncated = True
                        continue
                    children.append(self.explain(r, at, depth - 1))
            if children:
                node['children'] = children
        return node

    def _reset(self, s, cd, edge):
        name = cd.get('reset')
        if not name:
            return None
        comp = self.db.component(s.component_id)['path']
        sig = None
        for candidate in ([f'{comp}.{name}'] if comp else []) + [name]:
            try:
                sig = self.db.resolve_one(candidate)
                break
            except Exception:
                continue
        if sig is None:
            return {'signal': name, 'asserted': None, 'cause': 'reset signal not found in the database'}
        # A synchronous reset is sampled before the edge; an asynchronous one is checked at the edge too.
        _, before = self.value(sig, edge - 1)
        _, at_edge = self.value(sig, edge)
        level = 1 if cd.get('reset_active', 'high') == 'high' else 0
        vals = [value_of(r) for r in (self.wave.raw(self.var(sig), edge - 1), self.wave.raw(self.var(sig), edge))] \
            if self.var(sig) else [None, None]
        check = vals if cd.get('reset_kind') == 'ASYNC' else vals[:1]
        if any(x is None for x in check):
            return {'signal': sig.path, 'asserted': None, 'value': before}
        return {'signal': sig.path, 'asserted': any(x == level for x in check), 'value': before,
                'kind': cd.get('reset_kind')}


def why(database: str, wave: str, signal: str, t: int, depth: int = 2, max_nodes: int = 64) -> dict:
    """Explain `signal`'s value at `t` from database drivers and wave values."""
    from ..query.db import DesignDB
    if t < 0 or depth < 0 or max_nodes < 1:
        raise WaveError('time and depth must be non-negative and max_nodes positive')
    db = DesignDB(database)
    w = _Wave(wave)
    try:
        s = db.resolve_one(signal)
        tracer = Tracer(db, w, max_nodes)
        root = tracer.explain(s, t, depth)
        return {'signal': s.path, 'time': t, 'trace': root, 'nodes': tracer.nodes,
                'truncated': tracer.truncated, 'wave': w.identity, 'database': db.capture.record(),
                'db_warnings': db.staleness(),
                'binding': 'unverified: wave and database selected by the caller; names joined by wave path'}
    finally:
        w.close()
        db.close()
