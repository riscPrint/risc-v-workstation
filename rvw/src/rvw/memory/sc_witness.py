"""Sparse sufficient witness, with no inference from capture order.

A failed greedy schedule is not a forbidden result. The general axiomatic
search must still run. Equal ready choices use a stable hart order; this avoids
exploring equivalent schedules of independent enabled operations.
"""
from collections import defaultdict


def sc_witness(events, initial):
    by_id = {e['id']: e for e in events}
    harts = defaultdict(list)
    for e in events:
        harts[e['hart']].append(e)
        for name in ('addr', 'data', 'ctrl'):
            for source in e[name]:
                a = by_id.get(source)
                if a is None or a['hart'] != e['hart'] or a['order'] >= e['order']:
                    raise ValueError('dependency must point from an earlier event on the same hart')
        if e['kind'] != 'FENCE':
            key = e['address'], e['size']
            if key not in initial:
                return None
            if not 0 <= initial[key] < 1 << (8*e['size']):
                raise ValueError('invalid initial value')
            if f'initial:{key[0]}:{key[1]}' in by_id:
                raise ValueError('reserved initial event ID')
            for kind, field in [(('R', 'LR', 'AMO'), 'read'), (('W', 'SC', 'AMO'), 'write')]:
                if e['kind'] in kind and field not in e:
                    raise ValueError(f'{field} value missing')
        elif set(e['pred']) - set('RW') or set(e['succ']) - set('RW'):
            return None
    paired = set()
    for rows in harts.values():
        rows.sort(key=lambda e: e['order'])
        last_lr = None
        for e in rows:
            if e['kind'] == 'LR':
                last_lr = e
            elif e['kind'] == 'SC':
                if (last_lr is None or e.get('rmw') != last_lr['id'] or
                    e['id'] == last_lr['id'] or last_lr['id'] in paired or
                    (e['address'], e['size']) != (last_lr['address'], last_lr['size'])):
                    raise ValueError('SC requires matching earlier LR')
                paired.add(last_lr['id'])
    state = dict(initial)
    latest = {key: f'initial:{key[0]}:{key[1]}' for key in initial}
    positions = dict.fromkeys(harts, 0)
    reservations = {}
    order, co, rf = [], [], []
    remaining = len(events)
    # Each pass advances at least one hart. All work per event is bounded by N.
    while remaining:
        progress = False
        for hart in sorted(harts):
            pos = positions[hart]
            if pos == len(harts[hart]):
                continue
            e = harts[hart][pos]
            key = (e.get('address'), e.get('size'))
            kind = e['kind']
            if kind in ('R', 'LR', 'AMO') and state[key] != e['read']:
                continue
            if kind == 'SC' and reservations.get(e['rmw']) != latest[key]:
                continue
            if kind in ('R', 'LR', 'AMO'):
                rf.append((latest[key], e['id']))
            if kind == 'LR':
                reservations[e['id']] = latest[key]
            if kind in ('W', 'SC', 'AMO'):
                co.append((latest[key], e['id']))
                latest[key], state[key] = e['id'], e['write']
            order.append(e['id'])
            positions[hart] += 1
            remaining -= 1
            progress = True
        if not progress:
            from rvw.memory.sc_schedule import schedule
            return schedule(harts, initial)
    return {'global_order': order, 'co': co, 'rf': rf,
            'certificate': 'sequential consistency; co contains adjacent edges'}
