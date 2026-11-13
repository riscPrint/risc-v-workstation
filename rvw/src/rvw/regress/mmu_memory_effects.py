"""Independent project transaction/effect oracle for memory-type campaigns."""
from .mmu import number


def check(events, transactions, ordering=()):
    if not transactions:
        return dict(status='inconclusive', reason='missing project transaction oracle')
    expected = {r['id']: r for r in transactions}
    if len(expected) != len(transactions):
        raise ValueError('duplicate transaction oracle id')
    observed, errors = {}, []
    previous = -1
    for event in events:
        if event['kind'] != 'bus_effect':
            continue
        sequence = event['sequence']
        if type(sequence) is not int or sequence <= previous:
            raise ValueError('device effect sequence must strictly increase')
        previous = sequence
        identity = event['id']
        if identity not in expected or identity in observed:
            errors.append('extra or repeated device effect')
            continue
        observed[identity] = sequence
        reference = expected[identity]
        for key in ('access', 'memory_type', 'width'):
            if event.get(key) != reference[key]:
                errors.append(f'{identity}: wrong {key}')
        if number(event['address']) != number(reference['address']):
            errors.append(f'{identity}: wrong physical address')
        if 'data' in reference and number(event.get('data', -1)) != number(reference['data']):
            errors.append(f'{identity}: wrong device data')
    for before, after in ordering:
        if before not in expected or after not in expected:
            raise ValueError('ordering edge names an unknown transaction')
        if before in observed and after in observed and observed[before] >= observed[after]:
            errors.append('device effects violate declared ordering')
    return dict(status='mismatch' if errors else 'consistent' if len(observed) == len(expected) else 'inconclusive',
                errors=errors, observed=len(observed), expected=len(expected),
                scope='independent declared transactions and device-visible effect sequence only')
