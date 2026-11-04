"""Check a bounded, immutable Sv39 walk against scenario data.

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
    limit = 'successful immutable Sv39 mapping with preset A/D bits only'
    if ('control' in s or s.get('expect') != 'success' or s.get('remap')
            or s.get('satp_mode', 'sv39') != 'sv39' or not s.get('mprv', True)
            or s.get('walk_deny') or not {'A', 'D'} <= set(s['flags'])):
        return dict(status='inconclusive', reason=limit)
    va = number(s.get('va', 0x40000000)) + s.get('offset', 0)
    pa = number(s.get('pa', DATA))
    expected = {}
    for depth in range(3 - s['level']):
        level = 2 - depth
        address = ROOT + depth * 4096 + ((va >> (12 + 9 * level)) & 511) * 8
        pte = (((ROOT + (depth + 1) * 4096) >> 12) << 10) | 1
        if level == s['level']:
            pte = ((pa >> 12) << 10) | sum(FLAGS[f] for f in set(s['flags']))
        expected[address] = pte
    # A superpage replaces the low PPN bits with the corresponding VPN bits.
    physical = pa | (va & ((1 << (12 + 9 * s['level'])) - 1))
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
