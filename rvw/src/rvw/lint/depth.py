"""Bounded topology checks. Declarations are assumptions, never protocol proof."""
from collections import defaultdict
import re


def analyze(c, regs, signals, domains, incoming, outgoing, crossings, reset_crossings, emit, intent):
    if not isinstance(intent, dict) or set(intent) - {'protocols', 'reset_order', 'reconvergence_depth'}:
        raise ValueError('intent must contain only protocols, reset_order and reconvergence_depth')
    limit = intent.get('reconvergence_depth', 1)
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError('reconvergence_depth must be 1..64 register boundaries')
    by_path = {s['path']: i for i, s in signals.items()}

    def domain(i):
        return domains.get(regs[i]['clock_domain_id'], {})

    def clock(i):
        d = domain(i)
        return d.get('clock_key'), d.get('clock_edge')

    def chain(source, first, last):
        ids = [by_path.get(x) for x in (source, first, last)]
        if any(i not in regs for i in ids) or len(set(ids)) != 3:
            return False
        a, b, d = ids
        return (clock(a)[0] is not None and clock(b)[0] is not None
                and clock(a) != clock(b) and clock(b) == clock(d)
                and regs[b]['clock_domain_id'] == regs[d]['clock_domain_id']
                and regs[a]['width'] == regs[b]['width'] == regs[d]['width']
                and incoming[b] == {a} and outgoing[b] == {d} and incoming[d] == {b})

    def gray_encoder(path):
        node = by_path.get(path)
        if node not in regs:
            return None
        assignments = [dict(a) for a in c.execute(
            "SELECT * FROM assignments WHERE target_id=? AND kind!='init'", (node,))]
        if len(assignments) != 1 or assignments[0]['cond_id'] is not None:
            return None
        width = regs[node]['width']
        # Match the extractor's exact typed expression, not a source-name hint.
        pattern = (rf" := CastUIntToBits\[{width}\]\(Operator\$UInt\$Xor\[{width}\]"
                   rf"\(([^(), ]+:UInt\[{width}\]),Operator\$UInt\$ShiftRightByIntFixedWidth"
                   rf"<1>\[{width}\]\(\1\)\)\)")
        key = assignments[0]['key'] or ''
        return key if re.fullmatch(pattern, key) else None

    structures = []
    # Direct chains have no combinational logic or first-stage fanout.
    for crossing in crossings:
        first = by_path[crossing['destination']]
        if len(outgoing[first]) != 1:
            continue
        last = next(iter(outgoing[first]))
        if last in regs and chain(crossing['source'], regs[first]['path'], regs[last]['path']):
            structures.append(dict(kind='two_ff', source=crossing['source'],
                                   first=regs[first]['path'], last=regs[last]['path'],
                                   width=regs[first]['width'], status='candidate'))

    def upstream_registers(node):
        pending, seen, found = list(incoming[node]), set(), set()
        while pending:
            n = pending.pop()
            if n in seen:
                continue
            seen.add(n)
            if n in regs:
                found.add(n)
            else:
                pending.extend(incoming[n])
        return found

    # Search each sequential layer separately. Cycles cannot exceed the declared bound.
    def synchronized_ancestors(node, ends):
        pending, seen, found = [(node, 0)], set(), {}
        while pending:
            current, distance = pending.pop()
            if (current, distance) in seen or distance >= limit:
                continue
            seen.add((current, distance))
            for source in upstream_registers(current):
                if source in ends:
                    found[source] = min(found.get(source, limit + 1), distance + 1)
                else:
                    pending.append((source, distance + 1))
        return found

    ends = {by_path[s['last']]: s for s in structures}
    for dst, signal in regs.items():
        sources = upstream_registers(dst)
        ancestors = synchronized_ancestors(dst, ends)
        syncs = [ends[i] for i in sorted(ancestors)]
        if len(syncs) > 1:
            for s in syncs[1:]:
                finding = emit('cdc.reconvergence', regs[by_path[s['source']]], signal,
                     'Independent synchronized paths merge within the declared register depth. Relative latency is unproved.')
                finding['reconvergence'] = [dict(endpoint=signals[i]['path'], register_depth=d)
                                             for i, d in sorted(ancestors.items())]
        signatures = {tuple(domain(i).get(k) for k in
                      ('reset_key', 'reset_kind', 'reset_active_high', 'soft_reset_key', 'soft_reset_active_high'))
                      for i in sources}
        if len(signatures) > 1:
            emit('rdc.reconvergence', regs[min(sources)], signal,
                 'State with different reset signatures merges here. Reset isolation is unproved.')

    protocols = intent.get('protocols', [])
    if not isinstance(protocols, list):
        raise ValueError('intent.protocols must be a list')
    for p in protocols:
        if not isinstance(p, dict) or p.get('kind') not in {'handshake', 'async_fifo'}:
            raise ValueError('protocol kind must be handshake or async_fifo')
        kind = p['kind']
        keys = {'kind', 'forward', 'reverse'} | ({'memory', 'encoding'} if kind == 'async_fifo' else set())
        if set(p) != keys or any(not isinstance(p[k], list) or len(p[k]) != 3
                                or not all(isinstance(x, str) for x in p[k]) for k in ('forward', 'reverse')):
            raise ValueError('protocol needs forward/reverse [source, first, last] paths')
        if kind == 'async_fifo' and (not isinstance(p['memory'], str) or p['encoding'] != 'gray'):
            raise ValueError('async_fifo needs a memory path and encoding gray')
        forward, reverse = p['forward'], p['reverse']
        memory, ports = None, []
        ok = chain(*forward) and chain(*reverse)
        if ok:
            a, b = by_path[forward[0]], by_path[reverse[0]]
            ok = (clock(a) == clock(by_path[reverse[1]]) and clock(b) == clock(by_path[forward[1]]))
            if kind == 'handshake':
                ok &= regs[a]['width'] == regs[b]['width'] == 1
            else:
                memory = next((dict(m) for m in c.execute(
                    'SELECT m.*,s.path FROM memories m JOIN signals s ON s.id=m.signal_id')
                               if m['path'] == p['memory']), None)
                ports = [dict(x) for x in c.execute('SELECT * FROM mem_ports')
                         if memory and x['memory_id'] == memory['id']]
                write_domains = {x['clock_domain_id'] for x in ports if x['kind'] == 'write'}
                read_domains = {x['clock_domain_id'] for x in ports if x['kind'] == 'read_sync'}
                ok &= (bool(memory) and regs[a]['width'] == regs[b]['width']
                       and regs[a]['width'] > 1 and gray_encoder(forward[0]) is not None and gray_encoder(reverse[0]) is not None
                       and memory['depth'] > 1
                       and memory['depth'] & (memory['depth'] - 1) == 0
                       and regs[a]['width'] == memory['depth'].bit_length()
                       and write_domains == {regs[a]['clock_domain_id']}
                       and read_domains == {regs[b]['clock_domain_id']})
        endpoint = next((regs[by_path[x]] for x in forward if by_path.get(x) in regs), None)
        if endpoint is None:
            raise ValueError('protocol must name at least one existing register')
        finding = emit('cdc.' + kind + ('_candidate' if ok else '_invalid'), None, endpoint,
             ('Declared protocol matches bounded topology; behavior remains unproved. ' if ok else
              'Declared protocol does not match bounded topology. ') + repr(p))
        finding['protocol_evidence'] = dict(memory=memory, ports=ports,
            gray_keys=[gray_encoder(forward[0]), gray_encoder(reverse[0])] if kind == 'async_fifo' else None)
        structures.append(dict(kind=kind, status='candidate' if ok else 'invalid', declaration=p,
                               encoding_evidence=([gray_encoder(forward[0]), gray_encoder(reverse[0])]
                                                  if kind == 'async_fifo' else None)))

    order = intent.get('reset_order', [])
    if not isinstance(order, list) or any(not isinstance(pair, list) or len(pair) != 2
            or not all(isinstance(x, str) and x for x in pair) for pair in order):
        raise ValueError('reset_order must be a list of [earlier reset_key, later reset_key]')
    keys = {d['reset_key'] for d in domains.values() if d.get('reset_key')}
    if any(x not in keys for pair in order for x in pair):
        raise ValueError('reset_order names an unknown reset_key')
    graph = defaultdict(set)
    for a, b in order:
        graph[a].add(b)

    def reaches(a, b):
        pending, seen = list(graph[a]), set()
        while pending:
            n = pending.pop()
            if n == b:
                return True
            if n not in seen:
                seen.add(n)
                pending.extend(graph[n])
        return False

    if any(reaches(k, k) for k in keys):
        raise ValueError('reset_order contains a cycle')
    ordering = []
    for crossing in reset_crossings:
        src, dst = by_path[crossing['source']], by_path[crossing['destination']]
        a, b = domain(src).get('reset_key'), domain(dst).get('reset_key')
        status = 'declared_source_before_destination' if a != b and reaches(a, b) else 'unproved'
        ordering.append(dict(**crossing, status=status))
        if status == 'unproved':
            emit('rdc.release_order_unproved', regs[src], regs[dst],
                 'No source-before-destination release order is declared. Isolation and release remain unproved.')
    return dict(reconvergence_depth=limit, structures=structures, reset_ordering=ordering,
                intent=intent, scope='bounded topology and declared ordering; no protocol or timing proof')
