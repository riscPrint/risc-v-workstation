"""Agent queries over captured declarations and structural references."""
from __future__ import annotations

from . import ops
from .db import DesignDB, QueryError


def definition(db, signal):
    s = db.resolve_one(signal)
    return {'signal': db.signal_json(s), 'source': {'file': s.file, 'line': s.line},
            'status': 'mapped' if s.file and s.line else 'unmapped'}


def references(db, signal, limit=500):
    s = db.resolve_one(signal)
    uses = ops.loads(db, signal, limit=limit)
    return {'definition': definition(db, signal), 'readers': uses['readers'],
            'statements': uses['statements'], 'conditions': uses['conditions'],
            'assignments': ops.drivers(db, signal)['assignments'],
            'reader_count': uses['reader_count'], 'limit': limit,
            'semantics': db.meta.get('graph_semantics', 'elaborated structural references')}


def parameters(db, path=None):
    c = db.resolve_component(path)
    values = ops.hdl_parameters(db)
    known = values is not None and c['path'] in values
    return {'component': c['path'] or db.top, 'status': 'captured' if known else 'unavailable',
            'parameters': values[c['path']] if known else None}


def explain_module(db, path=None):
    c = db.resolve_component(path)
    out = ops.component(db, path)
    out.update(schema='rvw.module-explanation/1', parameters_capture=parameters(db, path),
               clock_domains=[db.clock_domain(i) for (i,) in db.q(
                   'SELECT DISTINCT clock_domain_id FROM signals WHERE component_id=? AND clock_domain_id IS NOT NULL', (c['id'],))],
               semantics=db.meta.get('graph_semantics', 'elaborated design'),
               purpose='unknown: a structural database does not describe design intent')
    return out


def hierarchy_diff(old, new):
    def snapshot(db):
        values = ops.hdl_parameters(db) or {}
        return {p: {'module': m, 'blackbox': bool(b), 'parameters': values.get(p)}
                for p, m, b in db.q('SELECT path,module,blackbox FROM components')}
    a, b = snapshot(old), snapshot(new)
    return {'schema': 'rvw.hierarchy-diff/1', 'added': sorted(b.keys()-a.keys()),
            'removed': sorted(a.keys()-b.keys()),
            'changed': [{'path': p, 'old': a[p], 'new': b[p]} for p in sorted(a.keys() & b.keys()) if a[p] != b[p]],
            'semantics': 'structural hierarchy only; no logic equivalence claim'}


def expression_type(db, expression):
    """Use elaborated signal types. Do not infer HDL sizing rules from text."""
    import re
    match = re.fullmatch(r'(.+)\[(\d+)(?::(\d+))?\]', expression)
    # Try exact names first: indices can be part of an elaborated signal name.
    try:
        if match and not db.q("SELECT 1 FROM signals WHERE path=? OR spinal_path=? OR name=?", (expression, expression, expression)):
            raise QueryError("select")
        s = db.resolve_one(expression)
        return {'expression': expression, 'type': s.type, 'width': s.width, 'status': 'captured'}
    except QueryError:
        if not match:
            raise QueryError('expression type needs a captured signal or a constant bit/part select') from None
    s = db.resolve_one(match[1])
    hi, lo = int(match[2]), int(match[3] or match[2])
    if min(hi, lo) < 0 or max(hi, lo) >= s.width:
        raise QueryError('select is outside the captured signal width')
    return {'expression': expression, 'type': 'Bits', 'width': abs(hi-lo)+1, 'status': 'derived',
            'base': s.path, 'limit': 'indices use normalized zero-based bit positions'}


def port_status(db, path=None):
    import gzip
    import json
    c = db.resolve_component(path)
    rows = db.q("SELECT encoding, content FROM artifacts WHERE name='hdl/port-connections.json'")
    if not rows:
        return {'component': c['path'] or db.top, 'status': 'unavailable', 'ports': []}
    encoding, content = rows[0]
    values = json.loads(gzip.decompress(content) if encoding == 'gzip' else content)
    return {'component': c['path'] or db.top, 'status': 'captured', 'ports': values.get(c['path'], []),
            'coverage': db.meta.get('hdl_port_connection_coverage', 'legacy-connections-only'),
            'limit': 'Native lowered connections. Unknown bits do not establish a tie-off or an unconnected source.'}
