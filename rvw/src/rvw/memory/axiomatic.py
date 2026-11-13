"""Bounded scalar candidate search for the RVWMO/Ztso axioms.

Relations follow herdtools7 7.58 riscv.cat and riscv-defs.cat. Dependencies
must be complete project observations. Capture order is never global order.
"""
from itertools import permutations, product
import json
import re
from pathlib import Path
from rvw.cosim.trace import Trace


def cyclic(edges):
    graph = {}
    degree = {}
    for a, b in edges:
        graph.setdefault(a, set()).add(b)
        degree.setdefault(a, 0)
        degree.setdefault(b, 0)
    for targets in graph.values():
        for b in targets:
            degree[b] += 1
    ready = [n for n, d in degree.items() if not d]
    count = 0
    while ready:
        a = ready.pop()
        count += 1
        for b in graph.get(a, ()):
            degree[b] -= 1
            if degree[b] == 0:
                ready.append(b)
    return count != len(degree)


def compose(a, b):
    right = {}
    for x, y in b:
        right.setdefault(x, set()).add(y)
    return {(x, z) for x, y in a for z in right.get(y, ())}


def search(events, initial, model='rvwmo', limit=100000):
    """Search co and rf for all scalar events with complete dependency metadata.

    RMW events combine a read and write at one indivisible node. Each successful
    SC names its LR in rmw. Failed SC has no write event. Mixed-size overlapping
    accesses and device memory are outside this profile.
    """
    report = {'schema': 'rvw.axiomatic/1', 'status': 'inconclusive',
              'model': model, 'candidates': 0, 'exhaustive_proof': False,
              'scope': 'scalar execution under declared complete dependencies'}
    if model not in ('rvwmo', 'ztso') or limit < 1:
        raise ValueError('invalid model or candidate limit')
    if not events:
        return report | {'reason': 'no memory events'}
    rows = [dict(e) for e in events]
    ids = [e['id'] for e in rows]
    if len(set(ids)) != len(ids) or any(not isinstance(i, str) or not i for i in ids):
        raise ValueError('duplicate or empty event ID')
    for e in rows:
        if e['kind'] not in ('R', 'W', 'AMO', 'LR', 'SC', 'FENCE'):
            return report | {'reason': 'unsupported event kind'}
        if e.get('space', 'memory') != 'memory':
            return report | {'reason': 'device ordering is unsupported'}
        if not isinstance(e['hart'], int) or e['hart'] < 0 or not isinstance(e['order'], int) or e['order'] < 0:
            raise ValueError('hart and order must be nonnegative integers')
        for dep in ('addr', 'data', 'ctrl'):
            if dep not in e:
                return report | {'reason': 'complete dependency sets required'}
        if e['kind'] != 'FENCE':
            if e['size'] not in (1, 2, 4, 8) or e['address'] < 0 or e['address'] % e['size']:
                return report | {'reason': 'unsupported size or alignment'}
            bound = 1 << (8*e['size'])
            for field in ('read', 'write'):
                if field in e and not 0 <= e[field] < bound:
                    raise ValueError('event value is outside its access width')
    if len({(e['hart'], e['order']) for e in rows}) != len(rows):
        raise ValueError('duplicate hart retirement order')
    memory = [e for e in rows if e['kind'] != 'FENCE']
    locations = {(e['address'], e['size']) for e in memory}
    for a, size in locations:
        for b, other in locations:
            if (a, size) != (b, other) and a < b + other and b < a + size:
                return report | {'reason': 'mixed-size overlapping accesses are unsupported'}
    by_id = {e['id']: e for e in rows}
    po = {(a['id'], b['id']) for a in rows for b in rows
          if a['hart'] == b['hart'] and a['order'] < b['order']}
    deps = {}
    for name in ('addr', 'data', 'ctrl'):
        deps[name] = {(a, e['id']) for e in rows for a in e[name]}
        if not deps[name] <= po:
            raise ValueError('dependency must point from an earlier event on the same hart')
    for a, size in sorted(locations):
        value = initial.get((a, size))
        if value is None:
            return report | {'reason': 'initial bytes missing for accessed location'}
        if not 0 <= value < 1 << (8*size):
            raise ValueError('invalid initial value')
        identity = f'initial:{a}:{size}'
        if identity in by_id:
            raise ValueError('reserved initial event ID')
        e = {'id': identity, 'hart': -1, 'kind': 'W', 'address': a, 'size': size, 'write': value}
        rows.append(e); by_id[identity] = e
    reads = {e['id'] for e in rows if e['kind'] in ('R', 'LR', 'AMO')}
    writes = {e['id'] for e in rows if e['kind'] in ('W', 'AMO', 'SC')}
    mem = reads | writes
    def loc(i):
        return by_id[i]['address'], by_id[i]['size']
    for i in reads:
        if 'read' not in by_id[i]:
            raise ValueError('read value missing')
    for i in writes:
        if 'write' not in by_id[i]:
            raise ValueError('write value missing')
    rmw = {(e['rmw'], e['id']) for e in rows if e['kind'] == 'SC'}
    for a, b in rmw:
        if a not in reads or by_id[a]['kind'] != 'LR' or (a, b) not in po or loc(a) != loc(b) or any(
                e['kind'] == 'LR' and (a, e['id']) in po and (e['id'], b) in po for e in rows):
            raise ValueError('SC requires matching earlier LR')
    if len({a for a, _ in rmw}) != len(rmw):
        raise ValueError('one LR cannot pair with two successful SC events')
    po_mem = {(a, b) for a, b in po if a in mem and b in mem}
    po_loc = {(a, b) for a, b in po_mem if loc(a) == loc(b)}
    fixed = {(a, b) for a, b in po_loc if b in writes}
    for a, b in po_mem:
        ea, eb = by_id[a], by_id[b]
        if ea.get('aq') or eb.get('rl'):
            fixed.add((a, b))
        rcsc = lambda e: e['kind'] in ('AMO', 'LR', 'SC') and (e.get('aq') or e.get('rl'))
        if rcsc(ea) and rcsc(eb):
            fixed.add((a, b))
        if model == 'ztso' and (a in reads or b in writes):
            fixed.add((a, b))
        for f in events:
            if f['kind'] != 'FENCE' or (a, f['id']) not in po or (f['id'], b) not in po:
                continue
            pred, succ = set(f['pred']), set(f['succ'])
            if pred - set('RW') or succ - set('RW'):
                return report | {'reason': 'device fence domains are unsupported'}
            before = (a in reads and 'R' in pred) or (a in writes and 'W' in pred)
            after = (b in reads and 'R' in succ) or (b in writes and 'W' in succ)
            if before and after and not (f.get('tso') and a not in reads and b not in writes):
                fixed.add((a, b))
    fixed |= rmw | {(a, b) for a, b in deps['addr'] if a in mem and b in mem}
    fixed |= {(a, b) for a, b in deps['data'] | deps['ctrl'] if a in mem and b in writes}
    fixed |= {(a, c) for a, b in deps['addr'] for x, c in po_mem if b == x and c in writes}
    groups = []
    for location in sorted(locations):
        ws = sorted(i for i in writes if loc(i) == location and by_id[i]['hart'] != -1)
        init = next(i for i in writes if loc(i) == location and by_id[i]['hart'] == -1)
        groups.append((init, ws))
    sources = []
    read_ids = sorted(reads)
    for r in read_ids:
        candidates = sorted(w for w in writes if w != r and loc(w) == loc(r)
                            and by_id[w]['write'] == by_id[r]['read'])
        if not candidates:
            return report | {'status': 'forbidden', 'reason': f'no read-from source for {r}'}
        sources.append(candidates)
    # Recursive lazy product avoids materializing factorial-sized permutation pools.
    def orders(index=0, co=frozenset()):
        if index == len(groups):
            yield set(co)
        else:
            init, ws = groups[index]
            for perm in permutations(ws):
                order = (init,) + perm
                edges = {(a, b) for i, a in enumerate(order) for b in order[i+1:]}
                yield from orders(index+1, co | edges)
    for co in orders():
        for selection in product(*sources):
            if report['candidates'] >= limit:
                return report | {'reason': 'candidate limit reached'}
            report['candidates'] += 1
            rf = set(zip(selection, read_ids))
            fr = {(r, w) for source, r in rf for a, w in co if a == source and r != w}
            rfi = {(w, r) for w, r in rf if by_id[w]['hart'] == by_id[r]['hart']}
            rfe = rf - rfi
            rsw = compose({(r, w) for w, r in rf}, rf)
            ppo = fixed | {(a, b) for a, b in po_loc if a in reads and b in reads and (a, b) not in rsw
                           and not any((a, w) in po_loc and (w, b) in po_loc for w in writes)}
            ppo |= {(w, r) for w, r in rfi if by_id[w]['kind'] in ('AMO', 'SC')}
            ppo |= compose({(a, w) for a, w in deps['addr'] | deps['data'] if a in mem and w in writes}, rfi)
            atomic = rmw | {(a, a) for a in reads & writes}
            # A successful RMW write immediately follows its source in coherence.
            if any((a, middle) in fr and (middle, b) in co and
                   by_id[a]["hart"] != by_id[middle]["hart"] and by_id[middle]["hart"] != by_id[b]["hart"]
                   for a, b in atomic for middle in writes):
                continue
            if cyclic(co | rf | fr | po_loc) or cyclic(co | rfe | fr | ppo):
                continue
            return report | {'status': 'allowed', 'witness': {'co': sorted(co), 'rf': sorted(rf), 'ppo': sorted(ppo)}}
    return report | {'status': 'forbidden', 'reason': 'all candidates violate the model axioms'}


def check(trace, reference, model='rvwmo', limit=100000):
    ref = json.loads(Path(reference).read_text())
    if ref.get('schema') != 'rvw.axiomatic-initial/1':
        raise ValueError('axiomatic initial-state schema required')
    initial = {}
    for row in ref['locations']:
        key = int(row['address'], 0), row['size']
        if key in initial:
            raise ValueError('duplicate initial location')
        initial[key] = int(row['value'], 0)
    reader = Trace(trace)
    try:
        if not reader.multihart:
            raise ValueError('C2/2 multi-hart trace required')
        records = list(reader)
        done = {r['hart']: r['status'] for r in records if r.get('event') == 'hart_end'}
        if set(done) != set(reader.header['harts']) or any(s != 'pass' for s in done.values()):
            return {'status': 'inconclusive', 'reason': 'all harts must complete'}
        if reader.header.get('memory_dependencies') != 'complete':
            return {'status': 'inconclusive', 'reason': 'complete project dependency observations required'}
        if reader.header.get('memory_addresses') != 'physical':
            return {'status': 'inconclusive', 'reason': 'physical memory address observations required'}
        events = []
        for r in records:
            if r.get('event'):
                if r['event'] == 'external' and r['action'] in ('write', 'atomic'):
                    return {'status': 'inconclusive', 'reason': 'external writers are unsupported'}
                continue
            if r['trap'] or r['mem_fault']:
                return {'status': 'inconclusive', 'reason': 'faulting executions are unsupported'}
            insn = r['insn']
            is_fence = insn & 0x7f == 0x0f and (insn >> 12) & 7 == 0
            opcode = insn & 0x7f
            if opcode == 0x0f and (insn >> 12) & 7 == 2:
                return {'status': 'inconclusive', 'reason': 'cache-block events are unsupported'}
            failed_sc = opcode == 0x2f and insn >> 27 == 3 and not r['mem_wmask']
            memory = r['mem_rmask'] or r['mem_wmask'] or is_fence or 'memory_model' in r or (opcode in (0x03, 0x23, 0x2f, 0x07, 0x27) and not failed_sc)
            if not memory:
                continue
            if r['trap'] or r['mem_fault'] or 'memory_model' not in r:
                return {'status': 'inconclusive', 'reason': 'missing memory event or fault semantics'}
            e = dict(r['memory_model'])
            for field in ('order', 'address', 'read', 'write'):
                if field not in e:
                    continue
                value = e[field]
                if isinstance(value, str) and re.fullmatch(r'0|[1-9][0-9]*', value):
                    e[field] = int(value)
                elif type(value) is not int or value < 0:
                    raise ValueError('memory annotations require nonnegative integers or canonical decimal strings')
            if e['hart'] != r['hart'] or e['order'] != int(r['order']):
                raise ValueError('memory event retirement identity mismatch')
            if e['hart'] not in reader.header['harts']:
                raise ValueError('undeclared event hart')
            if is_fence:
                if e['kind'] != 'FENCE':
                    raise ValueError('fence kind mismatch')
                pred, succ = (insn >> 24) & 15, (insn >> 20) & 15
                if (pred | succ) & 12 or (insn >> 28) not in (0, 8):
                    return {'status': 'inconclusive', 'reason': 'unsupported fence domains or mode'}
                e['pred'] = ('R' if pred & 2 else '') + ('W' if pred & 1 else '')
                e['succ'] = ('R' if succ & 2 else '') + ('W' if succ & 1 else '')
                e['tso'] = insn >> 28 == 8
                if e['tso'] and (pred != 3 or succ != 3):
                    return {'status': 'inconclusive', 'reason': 'reserved TSO fence encoding'}
            else:
                e.pop('aq', None); e.pop('rl', None)
                if opcode == 0x03:
                    wanted = 'R'
                elif opcode == 0x23:
                    wanted = 'W'
                elif opcode == 0x2f:
                    operation = insn >> 27
                    if operation not in (0, 1, 2, 3, 4, 8, 12, 16, 20, 24, 28):
                        return {'status': 'inconclusive', 'reason': 'unsupported atomic opcode'}
                    wanted = {2: 'LR', 3: 'SC'}.get(operation, 'AMO')
                    e['aq'], e['rl'] = bool(insn & (1 << 26)), bool(insn & (1 << 25))
                else:
                    return {'status': 'inconclusive', 'reason': 'unsupported memory instruction'}
                if e['kind'] != wanted:
                    raise ValueError('memory kind differs from RVFI instruction')
            if e['kind'] != 'FENCE':
                size = e['size']
                funct3 = (insn >> 12) & 7
                if opcode == 0x03 and funct3 < 7:
                    width = 1 << (funct3 & 3)
                elif opcode == 0x23 and funct3 <= 3:
                    width = 1 << funct3
                elif opcode == 0x2f and funct3 in (2, 3):
                    width = 1 << funct3
                else:
                    return {'status': 'inconclusive', 'reason': 'unsupported memory width encoding'}
                if size != width or size > reader.header['xlen']//8:
                    raise ValueError('memory event width differs from RVFI instruction')
                if e['address'] != r['mem_addr']:
                    raise ValueError('memory event address differs from RVFI')
                for direction, field in [('r', 'read'), ('w', 'write')]:
                    mask = r[f'mem_{direction}mask']
                    if mask:
                        if mask != (1 << size)-1 or e.get(field) != r[f'mem_{direction}data'] & ((1 << (8*size))-1):
                            raise ValueError('memory event mask or bytes differ from RVFI')
                    elif field in e:
                        raise ValueError('memory event invents an RVFI access')
                if e['kind'] in ('R', 'LR') and (not r['mem_rmask'] or r['mem_wmask']):
                    raise ValueError('read event access mismatch')
                if e['kind'] in ('W', 'SC') and (not r['mem_wmask'] or r['mem_rmask']):
                    raise ValueError('write event access mismatch')
                if e['kind'] == 'AMO' and not (r['mem_rmask'] and r['mem_wmask']):
                    raise ValueError('AMO event access mismatch')
            elif not is_fence:
                raise ValueError('fence event instruction mismatch')
            events.append(e)
        return search(events, initial, model, limit)
    finally:
        reader.close()
