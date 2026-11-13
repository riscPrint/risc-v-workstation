"""Project-probe translation protocol checks, separate from instruction effects."""
from .mmu import number


def check(events, *, required_harts, pbmt_types=None):
    """Check observed TLB entries, synchronization and atomic PTE updates.

    Each invalidation is an observed completion, not merely a fence request.
    Legal over-invalidation is allowed. A write alone does not forbid stale
    entries. A completed invalidation removes them for its declared scope.
    """
    events = list(events)
    entries, memory, requests, acks = {}, {}, {}, set()
    completions = []
    completed, checked = set(), 0
    errors, counts = [], {}
    last = -1
    required_harts = set(required_harts)
    if not required_harts:
        raise ValueError('required_harts must be nonempty')
    for e in events:
        cycle = number(e['cycle'])
        if cycle < last:
            raise ValueError('protocol cycles must be ordered')
        last = cycle
        kind = e['kind']
        counts[kind] = counts.get(kind, 0) + 1
        if kind in ('ad_atomic', 'tlb_fill', 'tlb_hit', 'shootdown_ack', 'shootdown_complete', 'memory_type'):
            checked += 1
        hart = e.get('hart')
        if kind in ('tlb_fill', 'tlb_hit', 'tlb_invalidate') and hart not in required_harts:
            raise ValueError('translation event has undeclared hart')
        if kind == 'pte_write':
            memory[number(e['address'])] = number(e['data'])
        elif kind == 'ad_atomic':
            address, old, new = map(number, (e['address'], e['old'], e['new']))
            bits = number(e['set_bits'])
            if bits not in (64, 192):
                raise ValueError('A/D update must set A or A/D')
            if address not in memory:
                return dict(status='inconclusive', reason='missing initial PTE value', counts=counts)
            if memory[address] != old or new != old | bits:
                errors.append('A/D update is not an atomic OR of the current PTE')
            memory[address] = new
        elif kind in ('tlb_fill', 'tlb_hit'):
            key = (hart, e['entry'])
            if kind == 'tlb_fill':
                pte_address, pte = number(e['pte_address']), number(e['pte'])
                if pte_address not in memory:
                    return dict(status='inconclusive', reason='missing reference PTE before fill', counts=counts)
                if memory[pte_address] != pte:
                    errors.append('TLB fill uses stale PTE data')
                entry = dict(e)
                entry['va'], entry['pa'] = number(e['va']), number(e['pa'])
                if type(e['size']) is not int or e['size'] < 4096 or e['size'] & (e['size'] - 1):
                    raise ValueError('TLB size must be a power of two at least 4096')
                if entry['va'] % e['size'] or entry['pa'] % e['size']:
                    raise ValueError('TLB bases must be aligned')
                entries[key] = entry
            elif key not in entries:
                errors.append('hit uses an absent or invalidated TLB entry')
            else:
                entry = entries[key]
                va = number(e['va'])
                if not entry['va'] <= va < entry['va'] + entry['size'] or number(e['pa']) != entry['pa'] + va - entry['va']:
                    errors.append('TLB hit translation differs from fill')
                if not entry.get('global', False) and e['asid'] != entry['asid']:
                    errors.append('TLB hit uses another ASID')
        elif kind == 'tlb_invalidate':
            completions.append(e)
            va = number(e['va']) if e.get('va') is not None else None
            asid = e.get('asid')
            for key, entry in list(entries.items()):
                if key[0] == hart and (va is None or entry['va'] <= va < entry['va'] + entry['size']) and (asid is None or not entry.get('global', False) and entry['asid'] == asid):
                    del entries[key]
        elif kind == 'shootdown_request':
            request = e['request']
            if request in requests or not set(e['targets']) <= required_harts or not e['targets']:
                raise ValueError('invalid shootdown request')
            requests[request] = (set(e['targets']), cycle, e.get('va'), e.get('asid'))
        elif kind == 'shootdown_ack':
            request = e['request']
            if request not in requests or hart not in requests[request][0]:
                errors.append('acknowledgement has no matching target request')
            else:
                # Require a real local completion since the request.
                _, start, va, asid = requests[request]
                matching = [x for x in completions if x.get('hart') == hart and start <= number(x['cycle']) <= cycle
                            and (x.get('va') is None or va is not None and number(x['va']) == number(va))
                            and (x.get('asid') is None or asid is not None and x['asid'] == asid)]
                if not matching:
                    errors.append('shootdown acknowledged before local invalidation')
                acks.add((request, hart))
        elif kind == 'shootdown_complete':
            request = e['request']
            if request not in requests or any((request, h) not in acks for h in requests[request][0]):
                errors.append('shootdown completed before all acknowledgements')
            else:
                completed.add(request)
        elif kind == 'memory_type':
            if pbmt_types is None:
                return dict(status='inconclusive', reason='missing project memory-type policy', counts=counts)
            pbmt = str(e['pbmt'])
            if pbmt not in pbmt_types:
                raise ValueError('unsupported project PBMT rule')
            if e['memory_type'] != pbmt_types[pbmt]:
                errors.append('transaction memory type differs from project PBMT policy')
        else:
            raise ValueError(f'unknown translation protocol event {kind}')
    return dict(status='mismatch' if errors else 'consistent' if checked and completed == requests.keys() else 'inconclusive', errors=errors, counts=counts,
                scope='observed project probes only; no missing event coverage inferred')


def configured_check(events, path):
    import json
    from pathlib import Path
    if not path:
        return dict(status='inconclusive', reason='missing project translation probe declaration')
    config = json.loads(Path(path).read_text())
    if config.get('schema') != 'rvw.mmu-probes/1' or not isinstance(config.get('probes'), dict) or not config.get('harts'):
        raise ValueError('expected rvw.mmu-probes/1 with harts and probes')
    kinds = {'pte_write', 'ad_atomic', 'tlb_fill', 'tlb_hit', 'tlb_invalidate', 'shootdown_request', 'shootdown_ack', 'shootdown_complete', 'memory_type', 'bus_effect'}
    if set(config['probes']) - kinds or any(not isinstance(v, str) or not v for v in config['probes'].values()):
        raise ValueError('invalid project translation probes')
    selected = [e for e in events if e['kind'] in kinds]
    if any(e['kind'] not in config['probes'] for e in selected):
        raise ValueError('capture uses an undeclared translation probe')
    from .mmu_memory_effects import check as check_effects
    result = check([e for e in selected if e['kind'] != 'bus_effect'], required_harts=config['harts'], pbmt_types=config.get('pbmt_types'))
    result['memory_effects'] = check_effects(selected, config.get('transactions'), config.get('ordering', []))
    if result['memory_effects']['status'] == 'mismatch':
        result['status'] = 'mismatch'
    return result
