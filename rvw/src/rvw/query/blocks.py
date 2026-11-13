"""SpinalBlocks diagrams (format version 1) from a design database, for any front end.

One diagram per module name (the first instance in path order). Endpoints are the module's
ports, its children's ports, and its named registers and memories. A net joins one driver
endpoint to the sink endpoints it reaches backwards through wires, bit nodes and hidden cell
hubs of the same module. Register bits stand for their named register."""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
import re


def _loc(files, fid, line):
    return {'file': files[fid], 'line': line} if fid in files and line else None


def blocks(conn) -> dict:
    files = dict(conn.execute('SELECT id, path FROM files'))
    comps = {r[0]: r for r in conn.execute(
        'SELECT id, parent_id, path, name, module, class_name, blackbox, file_id, line FROM components ORDER BY path')}
    sigs = {r[0]: r for r in conn.execute(
        'SELECT id, component_id, name, kind, direction, type, width, generated, file_id, line FROM signals')}
    by_comp = defaultdict(list)
    for s in sigs.values():
        by_comp[s[1]].append(s)
    children = defaultdict(list)
    for c in comps.values():
        if c[1] is not None:
            children[c[1]].append(c)
    incoming = defaultdict(list)
    for src, dst, kind in conn.execute("SELECT src, dst, kind FROM edges WHERE kind != 'init'"):
        incoming[dst].append((src, kind))
    # A bit node stands for the named net that aliases it ("Yosys net alias" rows).
    owner, bits_of = defaultdict(list), defaultdict(list)
    for target, bit in conn.execute(
            "SELECT a.target_id, r.signal_id FROM assignments a JOIN assign_reads r ON r.assignment_id = a.id "
            "WHERE a.source = 'Yosys net alias'"):
        if not sigs[target][7]:
            owner[bit].append(target)
            bits_of[target].append(bit)
    clocks = {r[0] for r in conn.execute("SELECT id FROM signals WHERE clock_role IS NOT NULL")}
    counts = defaultdict(int)
    for c in comps.values():
        counts[c[4]] += 1
    modules = {}
    for c in comps.values():
        if c[4] in modules:
            continue
        modules[c[4]] = _module(c, comps, by_comp, children, incoming, owner, bits_of, files, sigs, clocks,
                                counts[c[4]])
    root = next(c for c in comps.values() if c[1] is None)
    return {'format': 'spinalblocks', 'version': 1, 'top': root[4],
            'generated': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'modules': modules}


def _groups(name):
    """Record fields (`a_i[data]`) group under their record; other names are ungrouped."""
    m = re.match(r'^([^\[]+)\[[A-Za-z_]', name)
    return [m[1]] if m else []


def _module(c, comps, by_comp, children, incoming, owner, bits_of, files, sigs, clocks, count):
    cid = c[0]
    own = by_comp[cid]
    ports = [s for s in own if s[4] and not s[7]]
    ports.sort(key=lambda s: (s[9] or 0, s[2]))
    out = {'name': c[4], 'className': c[5], 'loc': _loc(files, c[7], c[8]), 'instanceCount': count,
           'blackbox': bool(c[6]),
           'ports': [{'name': s[2], 'dir': s[4], 'width': s[6] or 1, 'type': s[5] or 'Bits',
                      'group': (_groups(s[2]) or [''])[-1], 'groups': _groups(s[2]),
                      'loc': _loc(files, s[8], s[9])} for s in ports],
           'instances': [], 'nodes': [], 'nets': [], 'fsms': []}
    endpoint = {}  # signal id -> endpoint dict
    role = {}  # signal id -> 'driver', 'sink' or 'both'
    for s in ports:
        endpoint[s[0]] = {'kind': 'port', 'port': s[2]}
        role[s[0]] = 'driver' if s[4] == 'in' else 'sink'
    for k in sorted(children[cid], key=lambda k: k[3]):
        iid = f'inst:{k[3]}'
        out['instances'].append({'id': iid, 'name': k[3], 'module': k[4], 'parent': None,
                                 'loc': _loc(files, k[7], k[8])})
        for s in by_comp[k[0]]:
            if s[4] and not s[7]:
                endpoint[s[0]] = {'kind': 'inst', 'id': iid, 'port': s[2]}
                role[s[0]] = 'sink' if s[4] == 'in' else 'driver'
    for s in own:
        if s[7] or s[4] or s[3] not in ('reg', 'mem'):
            continue
        nid = ('mem:' if s[3] == 'mem' else 'sig:') + s[2]
        out['nodes'].append({'id': nid, 'name': s[2], 'kind': s[3], 'parent': None, 'compound': False,
                             'className': None, 'loc': _loc(files, s[8], s[9]),
                             'signals': [{'name': s[2], 'width': s[6] or 1,
                                          'type': s[5] if s[3] == 'reg' else f'Mem[{s[6]}]',
                                          'reg': s[3] == 'reg', 'loc': _loc(files, s[8], s[9])}],
                             'regCount': int(s[3] == 'reg'), 'combCount': 0})
        endpoint[s[0]] = {'kind': 'node', 'id': nid}
        role[s[0]] = 'both'
    # A registered output port also gets its own node, wired to the port, unless it only
    # aliases a named register of this module.
    for s in ports:
        if s[4] == 'out' and s[3] == 'reg' and not any(
                role.get(o) == 'both' for b in bits_of[s[0]] for o in owner[b]):
            nid = f'sig:{s[2]}'
            out['nodes'].append({'id': nid, 'name': s[2], 'kind': 'reg', 'parent': None, 'compound': False,
                                 'className': None, 'loc': _loc(files, s[8], s[9]),
                                 'signals': [{'name': s[2], 'width': s[6] or 1, 'type': s[5] or 'Bits',
                                              'reg': True, 'loc': _loc(files, s[8], s[9])}],
                                 'regCount': 1, 'combCount': 0})
            out['nets'].append({'id': f'n{len(out["nets"])}', 'name': s[2], 'width': s[6] or 1, 'via': [],
                                'control': False, 'clock': False, 'from': {'kind': 'node', 'id': nid},
                                'to': [{'kind': 'port', 'port': s[2]}]})
            endpoint[s[0]] = {'kind': 'node', 'id': nid}
            role[s[0]] = 'both'
    if c[6]:
        return out

    def stand_in(n):
        """The endpoint a signal stands for: itself, or the named register owning a register bit."""
        if n in endpoint:
            return n
        # A bit of a port stands for the port; a register bit for its register node.
        owners = [o for o in owner.get(n, ()) if o in endpoint]
        if sigs[n][3] == 'reg':
            for o in owners:
                if role[o] == 'both':
                    return o
        for o in owners:
            if endpoint[o]['kind'] != 'node':
                return o
        return None

    allowed = {s[0] for s in own} | set(endpoint)
    allowed |= {b for e in endpoint if sigs[e][1] != cid for b in bits_of[e]}  # child port bits
    nets = defaultdict(lambda: {'sinks': [], 'via': set(), 'control': True})
    for sink, r in role.items():
        if r == 'driver':
            continue
        seen, queue = {sink}, deque((src, kind, ()) for src, kind in incoming[sink])
        while queue:
            n, kind, via = queue.popleft()
            if n in seen or n not in allowed:
                continue
            seen.add(n)
            e = stand_in(n)
            if e is not None and e != sink:
                if role[e] != 'sink':
                    net = nets[e]
                    if sink not in net['sinks']:
                        net['sinks'].append(sink)
                    net['via'].update(via)
                    net['control'] &= kind in ('sel', 'cond')
                continue
            # e == sink: one of the sink register's own bits; its drivers feed the sink.
            step = via + ((sigs[n][2],) if not sigs[n][7] else ())
            queue.extend((src, k if kind == 'data' else kind, step) for src, k in incoming[n])
    for driver, net in nets.items():
        s = sigs[driver]
        out['nets'].append({'id': f'n{len(out["nets"])}', 'name': s[2], 'width': s[6] or 1,
                            'via': sorted(net['via']), 'control': net['control'],
                            'clock': driver in clocks,
                            'from': endpoint[driver], 'to': [endpoint[x] for x in net['sinks']]})
    return out
