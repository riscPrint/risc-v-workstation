"""Bounded checks. Structural evidence and sampled transactions are not a proof."""
import json
import sqlite3
from pathlib import Path

from rvw.cosim.platform import number
from .model import ident, keys, load


def check(source, bindings, database, transactions=None):
    soc = load(source)
    spec = json.loads(Path(bindings).read_text())
    keys(spec, {'schema', 'signals', 'decoders', 'bridges'}, {'schema', 'signals', 'decoders', 'bridges'})
    if spec['schema'] != 'rvw.soc-bindings/1':
        raise ValueError('unsupported bindings schema')
    if any(not isinstance(spec[k], list) for k in ('signals', 'decoders', 'bridges')):
        raise ValueError('binding entries must be lists')
    regions = {r['name']: r for r in soc['regions']}
    checks = []
    gaps = ['endianness behavior', 'error propagation', 'register side effects',
            'complete decode coverage', 'source revision freshness', 'transaction capture provenance']
    def record(name, actual, expected):
        checks.append(dict(name=name, actual=actual, expected=expected,
                           status='unavailable' if actual is None else 'consistent' if actual == expected else 'mismatch'))
    db = Path(database).resolve()
    with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True) as conn:
        row = conn.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
        if not row or row[0] != 'rvw.designdb/20':
            raise ValueError('requires rvw.designdb/20')
        for s in spec['signals']:
            keys(s, {'path', 'width'}, {'path', 'width'})
            width = soc['address_bits'] if s['width'] == 'address_bits' else s['width']
            if type(width) is not int or width <= 0:
                raise ValueError('binding width must be positive or address_bits')
            rows = conn.execute('SELECT width FROM signals WHERE path=?', (s['path'],)).fetchall()
            record('width:' + s['path'], rows[0][0] if len(rows) == 1 else None, width)
        for d in spec['decoders']:
            keys(d, {'region', 'path', 'key_template'}, {'region', 'path', 'key_template'})
            r = regions[d['region']]
            # Exact typed expression key, with map-derived hexadecimal literals.
            # Unsupported/hashed expressions cannot be evaluated by this checker.
            template = d['key_template']
            if not isinstance(template, str) or '{base}' not in template or '{mask}' not in template:
                raise ValueError('decoder template must use {base} and {mask}')
            expected = template.format(base=f'{r["base"]:x}', mask=f'{((1 << soc["address_bits"]) - r["size"]):x}')
            if '$incomplete' in expected or 'h:' in expected:
                raise ValueError('decoder template must be complete and unhashed')
            rows = conn.execute('SELECT a.key, a.cond_id, a.range FROM assignments a JOIN signals s ON s.id=a.target_id WHERE s.path=? AND a.kind=? ORDER BY a.seq', (d['path'], 'data')).fetchall()
            # One full assignment only. Multiple drivers need priority analysis.
            actual = rows[0][0] if len(rows) == 1 and rows[0][1] is None and rows[0][2] in (None, '') and rows[0][0] and '$incomplete' not in rows[0][0] and 'h:' not in rows[0][0] else None
            record('decode:' + d['path'], actual, expected)
    bridges = {}
    for b in spec['bridges']:
        keys(b, {'name', 'region', 'local_base', 'data_bytes', 'byteorder', 'software_byteorder'}, {'name', 'region', 'local_base', 'data_bytes'})
        name = ident(b['name'])
        if name in bridges or b['region'] not in regions:
            raise ValueError('duplicate bridge or unknown region')
        b['local_base'] = number(b['local_base'])
        if b['local_base'] < 0 or type(b['data_bytes']) is not int or b['data_bytes'] not in (1, 2, 4, 8, 16):
            raise ValueError('invalid bridge base or data width')
        if any(b.get(k, 'little') not in ('little', 'big') for k in ('byteorder', 'software_byteorder')):
            raise ValueError('unsupported bridge byte order')
        bridges[name] = b
    count = 0
    if transactions:
        with Path(transactions).open() as stream:
            for line in stream:
                t = json.loads(line)
                if 'beats' not in t:
                    keys(t, {'bridge', 'software_address', 'bus_address', 'size'}, {'bridge', 'software_address', 'bus_address', 'size'})
                b = bridges[t['bridge']]
                r = regions[b['region']]
                sw, bus, size = number(t['software_address']), number(t['bus_address']), number(t['size'])
                if size <= 0:
                    raise ValueError('transaction size must be positive')
                count += 1
                record(f'transaction:{count}:bounds', r['base'] <= sw and sw + size <= r['base'] + r['size'], True)
                record(f'transaction:{count}:translation', bus, sw - r['base'] + b['local_base'])
                if 'beats' in t:
                    from .bridge import compare
                    compare(t, b, r, record, f'transaction:{count}')
                else:
                    record(f'transaction:{count}:width', size <= b['data_bytes'] and bus % b['data_bytes'] + size <= b['data_bytes'], True)
    if not count:
        gaps.append('sampled transactions')
    if not spec['decoders']:
        gaps.append('decoder expressions')
    if not spec['bridges']:
        gaps.append('bridge bindings')
    if not spec['signals']:
        gaps.append('signal widths')
    # Even nonempty samples and exact structural keys do not cover full behavior.
    mismatch = any(c['status'] == 'mismatch' for c in checks)
    return dict(schema='rvw.soc-check/1', status='mismatch' if mismatch else 'inconclusive',
                checks=checks, gaps=gaps, transactions=count)
