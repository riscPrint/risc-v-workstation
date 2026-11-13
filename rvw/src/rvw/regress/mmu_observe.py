"""Check a bounded, immutable page-table walk against scenario data.

This is independent of retirement comparison. It is not a TLB protocol check.
"""
from __future__ import annotations

from .mmu import DATA, FLAGS, ROOT, number


def check_walk(s, events):
    """Check returned PTEs and require a physical target transaction.

    Only successful, immutable, already accessed/dirty mappings are supported.
    Killed requests need no response. A response must follow a matching read.
    Missing observations stay inconclusive, including cache-satisfied targets.
    """
    from .mmu_paging import geometry
    g = geometry(s)
    limit = 'successful immutable ' + s.get('mode', 'sv39') + ' mapping with preset A/D bits only'
    if ('guest' in s or 'shootdown' in s or 'control' in s or s.get('expect') != 'success' or s.get('remap')
            or s.get('satp_mode', 'sv39') != 'sv39' or not s.get('mprv', True)
            or s.get('walk_deny') or s.get('mode_switch') or 'pbmt' in s or s.get('napot') or not {'A', 'D'} <= set(s['flags'])):
        return dict(status='inconclusive', reason=limit)
    va = number(s.get('va', 0x40000000)) + s.get('offset', 0)
    pa = number(s.get('pa', DATA))
    expected = {}
    for depth in range(g.levels - s['level']):
        level = g.levels - 1 - depth
        address = ROOT + depth * 4096 + ((va >> (12 + g.vpn_bits * level)) & ((1 << g.vpn_bits) - 1)) * g.width
        pte = (((ROOT + (depth + 1) * 4096) >> 12) << 10) | 1 | (FLAGS['G'] if s.get('nonleaf_global') else 0)
        if level == s['level']:
            pte = ((pa >> 12) << 10) | sum(FLAGS[f] for f in set(s['flags']))
        expected[address] = pte
    # A superpage replaces the low PPN bits with the corresponding VPN bits.
    from .mmu_paging import geometry
    physical = pa | (va & ((1 << (12 + geometry(s).vpn_bits * s['level'])) - 1))
    requests, responses, errors = set(), set(), []
    target = False
    previous = -1
    for event in events:
        cycle = number(event['cycle'])
        if cycle < previous:
            raise ValueError('observation cycles must be ordered')
        previous = cycle
        kind = event['kind']
        address = number(event['address'])
        if kind == 'walk_request':
            if address not in expected or event['command'] != 0:
                errors.append('unexpected PTE read or non-read walk command')
            else:
                requests.add(address)
        elif kind == 'walk_response':
            if address not in requests:
                errors.append('PTE response has no preceding expected request')
            elif number(event['data']) != expected[address]:
                errors.append('PTE response differs from declared table contents')
            else:
                responses.add(address)
        elif kind == 'bus_a':
            size = event['size_log2']
            if type(size) is not int or not 0 <= size <= 6:
                raise ValueError('unsupported TileLink size')
            # Get, AcquireBlock and AcquirePerm are possible cache paths.
            if event['opcode'] in (4, 6, 7) and address <= physical < address + (1 << size):
                target = True
    status = 'mismatch' if errors else 'consistent' if responses == expected.keys() and target else 'inconclusive'
    return dict(status=status, scope=limit, errors=errors,
                expected_ptes={hex(k): hex(v) for k, v in expected.items()},
                returned_ptes=len(responses), physical_target=hex(physical),
                physical_target_observed=target,
                reason=None if status != 'inconclusive' else 'missing PTE responses or physical target transaction')


def check_pma(s, events, regions):
    """Check a single MMIO request and independent harness register state.

    No verdict for RAM, fault paths, cacheable aliases or unobserved devices.
    Declared PMA attributes are the oracle. Capture does not define attributes.
    """
    unknown = dict(status='inconclusive', reason='need one declared non-cacheable device access and independent state')
    if ('guest' in s or 'shootdown' in s or 'control' in s or s.get('expect') != 'success' or s.get('remap')
            or s.get('access') not in ('load', 'store') or not regions):
        return unknown
    pa = number(s.get('pa', DATA))
    va = number(s.get('va', 0x40000000)) + s.get('offset', 0)
    from .mmu_paging import geometry
    physical = pa | (va & ((1 << (12 + geometry(s).vpn_bits * s['level'])) - 1))
    selected = [r for r in regions if number(r['start']) <= physical < number(r['start']) + number(r['size'])]
    if len(selected) != 1 or selected[0]['cacheable']:
        return unknown
    region = selected[0]
    transfers = [e for e in events if e['kind'] == 'bus_a' and number(e['address']) == physical]
    states = [e for e in events if e['kind'] == 'device_state' and number(e['address']) == physical and e.get('scheduled') is False]
    if not transfers or not states:
        return unknown
    errors = []
    write = s['access'] == 'store'
    # A store program also reads the device once to check the stored value.
    expected_opcodes = (0, 1) if write else (4,)
    tested = [e for e in transfers if e['opcode'] in expected_opcodes]
    readbacks = [e for e in transfers if e['opcode'] == 4]
    if len(tested) != 1 or (write and len(readbacks) != 1):
        errors.append('device access or readback transfer count differs from the program')
    for e in transfers:
        size = e['size_log2']
        if type(size) is not int or not 0 <= size <= 6:
            raise ValueError('unsupported TileLink size')
        width = 1 << size
        if width != s.get('access_width', 8) or width not in region['widths']:
            errors.append('device transfer width differs from scenario or PMA declaration')
        if physical + width > number(region['start']) + number(region['size']):
            errors.append('device transfer crosses a declared PMA boundary')
        direction = 'read' if e['opcode'] == 4 else 'write'
        if not region[direction] or e['opcode'] not in ((0, 1, 4) if write else (4,)):
            errors.append('device transfer direction differs from scenario or PMA declaration')
    expected = s.get('store_value', 43) if s['access'] == 'store' else s.get('value', 42)
    final = states[-1]
    if write and (not tested or number(final['cycle']) < number(tested[-1]['cycle'])):
        return unknown
    if number(final['value']) != expected:
        errors.append('independent device state differs from expected value')
    return dict(status='mismatch' if errors else 'consistent', errors=errors,
                region=region['name'], physical_target=hex(physical),
                scope='one accepted device transfer and sampled harness register state only')
