"""Reset-domain crossings from SpinalDB clock-domain data.

Each register-to-register path between different reset domains gets one class. Declared
isolation and reset order are project assumptions with reasons; they make a path
`protected`, never proved. Missing domain data makes the result inconclusive."""
from .graph import RESET_FIELDS


def reset_domain(design, reg):
    """Reset signature of one register. A register without init has no reset, even in a
    clock domain with a reset. None means the domain data is missing."""
    d = design.domains.get(reg['clock_domain_id'])
    if d is None:
        return None
    if reg.get('reset_value') is None or not (d.get('reset') or d.get('soft_reset')):
        return ('none',)
    return tuple(d.get(k) for k in RESET_FIELDS)


def _chain(design, root, clock_key):
    """Register stages that drive `root` as a synchronizer chain with a constant input.
    Returns the stage paths (input first) or None."""
    node, stages = root, []
    # Wires and inverters between the last stage and the reset net: one input each.
    while node not in design.regs:
        inputs = design.incoming[node]
        if len(inputs) != 1:
            return None
        node = next(iter(inputs))
    while True:
        if design.clock(node)[0] != clock_key or design.signals[node]['width'] != 1:
            return None
        stages.append(node)
        internal, leaves = design.cone(node)
        regs = {n for n in leaves if n in design.regs and n != node}
        if any(design.is_top_input(n) for n in leaves) or node in leaves:
            return None
        if not regs:
            break
        if len(regs) != 1 or len(stages) > 8:
            return None
        node = next(iter(regs))
    return [design.signals[i]['path'] for i in reversed(stages)] if len(stages) >= 2 else None


def reset_synchronizer(design, d, control='reset'):
    """Recognize async-assert/sync-deassert: the reset net comes from a chain of at least two
    registers in the controlled clock, with a constant first input and an asynchronous reset."""
    root = design.by_path.get(d.get(control))
    if root is None:
        return None
    stages = _chain(design, root, d.get('clock_key'))
    if not stages:
        return None
    kinds = {(design.domain(design.by_path[p]) or {}).get('reset_kind') for p in stages}
    if kinds != {'ASYNC'}:
        return None
    return dict(kind='reset_synchronizer', stages=stages, clock=d.get('clock'))


def analyze(design, emit, intent):
    isolation = intent.get('isolation', [])
    if not isinstance(isolation, list) or any(
            not isinstance(x, dict) or set(x) - {'source', 'destination', 'qualifier', 'reason'}
            or not isinstance(x.get('qualifier'), str) or not isinstance(x.get('reason'), str)
            or not x['reason'].strip() or not (x.get('source') or x.get('destination'))
            for x in isolation):
        raise ValueError('intent.isolation needs qualifier, reason and source or destination')
    for x in isolation:
        for k in ('source', 'destination', 'qualifier'):
            if x.get(k) and x[k] not in design.by_path:
                raise ValueError(f'intent.isolation names an unknown signal: {x[k]}')
    order = intent.get('reset_order', [])
    before = {}
    for a, b in order if isinstance(order, list) else []:
        before.setdefault(a, set()).add(b)

    def ordered(a, b):
        pending, seen = list(before.get(a, ())), set()
        while pending:
            n = pending.pop()
            if n == b:
                return True
            if n not in seen:
                seen.add(n)
                pending.extend(before.get(n, ()))
        return False

    regs = design.regs
    used = sorted({s['clock_domain_id'] for s in regs.values()}, key=str)
    missing = [s for s in regs.values() if s['clock_domain_id'] not in design.domains]
    for s in missing[:20]:
        emit('rdc.missing_domain', None, s, 'Register has no clock-domain record. Reset analysis is inconclusive.')

    # Reset domains: one per reset signature.
    groups = {}
    for s in regs.values():
        sig = reset_domain(design, s)
        if sig is None:
            continue
        g = groups.setdefault(sig, dict(signature=list(sig), registers=0, clock_domains=set()))
        g['registers'] += 1
        g['clock_domains'].add(s['clock_domain_id'])
    domains, ids, sync_regs, pending = [], {}, set(), []
    for n, (sig, g) in enumerate(sorted(groups.items(), key=lambda x: str(x[0]))):
        ids[sig] = f'R{n}'
        cds = [design.domains[i] for i in sorted(g['clock_domains'])]
        d0 = cds[0]
        row = dict(id=f'R{n}', registers=g['registers'], clock_domains=sorted(g['clock_domains']),
                   clocks=sorted({d.get('clock') or '?' for d in cds}))
        if sig == ('none',):
            row.update(kind='none', reset=None, release='not_applicable')
        else:
            row.update(kind=d0.get('reset_kind'), reset=d0.get('reset'), reset_key=d0.get('reset_key'),
                       active_high=d0.get('reset_active_high'), soft_reset=d0.get('soft_reset'),
                       soft_reset_key=d0.get('soft_reset_key'))
            if d0.get('reset_kind') == 'ASYNC' and d0.get('reset'):
                syncs = [reset_synchronizer(design, d) for d in cds]
                row['synchronizers'] = syncs
                row['release'] = 'synchronized' if all(syncs) else 'unsynchronized'
                for s in syncs:
                    for p in (s or {}).get('stages', []):
                        sync_regs.add(design.by_path[p])
                pending.append((row, sig))
            else:
                row['release'] = 'synchronous' if d0.get('reset_kind') == 'SYNC' else 'boot'
        domains.append(row)
    # A synchronizer's own stages use the raw reset; their release is what the chain resolves.
    for row, sig in pending:
        members = [i for i, r in regs.items() if reset_domain(design, r) == sig]
        if row['release'] == 'synchronized':
            continue
        if members and all(i in sync_regs for i in members):
            row['release'] = 'synchronizer_stages'
            continue
        emit('rdc.async_release_unsynchronized', None, regs[members[0]],
             f"Asynchronous reset {row['reset']} has no recognized synchronizer for "
             'de-assertion in its clock domain. Release can be metastable.')

    # Reset nets: combinational logic on asynchronous resets and resets used as data.
    reset_nets = {}
    for d in design.domains.values():
        for control in ('reset', 'soft_reset'):
            i = design.by_path.get(d.get(control))
            if i is not None:
                reset_nets.setdefault(i, (d, control))
    reported = set()
    for i, (d, control) in reset_nets.items():
        internal, leaves = design.cone(i)
        if d.get('reset_kind') == 'ASYNC' and control == 'reset' and (
                len(leaves) > 1 or any(len(design.incoming[n]) > 1 for n in internal | {i})):
            emit('rdc.comb_reset_logic', None, design.signals[i],
                 'Combinational logic drives an asynchronous reset. A glitch can reset state.',
                 severity='error')
        found, _ = design.fanout(i, stop=lambda n: n in reset_nets)
        for r in sorted(found):
            if r in regs and r not in sync_regs and r not in reported:
                reported.add(r)
                emit('rdc.reset_as_data', design.signals[i], regs[r],
                     'A reset net reaches register data or control logic.')

    crossings = []
    for dst_id, dst in regs.items():
        b = reset_domain(design, dst)
        for src_id in sorted(design.upstream_regs(dst_id)):
            src = regs[src_id]
            a = reset_domain(design, src)
            if a == b:
                continue
            row = dict(source=src['path'], destination=dst['path'],
                       source_reset=ids.get(a), destination_reset=ids.get(b))
            crossings.append(row)
            if a is None or b is None:
                row.update(status='inconclusive', **{'class': 'missing_domain'})
                continue
            if a == ('none',):
                row.update(status='no_hazard', **{'class': 'source_not_reset'})
                continue
            cone = design.cone(dst_id)[0] | design.cone(dst_id)[1]
            rule = None
            for x in isolation:
                if x.get('source') not in (None, src['path']) or x.get('destination') not in (None, dst['path']):
                    continue
                if design.by_path[x['qualifier']] in cone:
                    row.update(status='protected', protected_by='declared_isolation',
                               qualifier=x['qualifier'], reason=x['reason'])
                else:
                    rule = 'rdc.isolation_unmatched'
            if row.get('status') == 'protected':
                continue
            if b != ('none',) and a[0] and b[0] and ordered(a[0], b[0]):
                row.update(status='protected', protected_by='declared_reset_order',
                           reason='destination is declared to stay in reset while the source is in reset')
                continue
            if rule:
                emit(rule, src, dst, 'Declared isolation qualifier is not in the destination fan-in.', severity='error')
            if a[1] == 'ASYNC':
                cls, sev = 'async_assert_crossing', 'error'
                msg = ('Asynchronous assertion of the source reset can change the source at any time. '
                       'The destination is not reset with it and can go metastable.')
            elif b == ('none',):
                cls, sev = 'resetless_receiver', 'warning'
                msg = 'A register without reset samples state from a reset domain. It can capture reset values.'
            else:
                cls, sev = 'independent_reset', 'warning'
                msg = 'State has different reset controls or modes. Reset ordering and isolation are unproved.'
            row.update(status='finding', **{'class': cls})
            emit('rdc.' + cls, src, dst, msg, severity=sev)
    statuses = {r['status'] for r in crossings}
    status = ('inconclusive' if missing or not design.domains and regs or 'inconclusive' in statuses else
              'findings' if 'finding' in statuses else 'protected' if 'protected' in statuses else 'no_crossings_found')
    return dict(status=status, domains=domains, crossings=crossings, used_clock_domains=used,
                scope='structural reset-domain classes; declared constraints are assumptions')
