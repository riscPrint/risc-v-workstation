"""Compare paired endpoint observations. Samples never prove full bridge behavior."""
from rvw.cosim.platform import number
from .model import keys


def uint(value, bits):
    value = number(value)
    if not 0 <= value < 1 << bits:
        raise ValueError('bridge value exceeds width')
    return value


def compare(t, bridge, region, record, prefix):
    keys(t, {'bridge', 'software_address', 'bus_address', 'size', 'write', 'data',
             'error', 'beats', 'register'},
         {'bridge', 'software_address', 'bus_address', 'size', 'write', 'data', 'error', 'beats'})
    size = number(t['size'])
    if not 1 <= size <= 64 or type(t['write']) is not bool or type(t['error']) is not bool:
        raise ValueError('invalid paired access')
    if not isinstance(t['beats'], list) or not t['beats']:
        raise ValueError('paired access needs observed beats')
    width = bridge['data_bytes']
    byteorder = bridge.get('byteorder', 'little')
    software_order = bridge.get('software_byteorder', 'little')
    expected = uint(t['data'], size * 8).to_bytes(size, software_order)
    start = number(t['bus_address'])
    observed = {}
    errors = []
    for i, beat in enumerate(t['beats']):
        keys(beat, {'address', 'data', 'mask', 'error', 'write'}, {'address', 'data', 'mask', 'error', 'write'})
        address = number(beat['address'])
        mask = uint(beat['mask'], width)
        data = uint(beat['data'], width * 8).to_bytes(width, byteorder)
        if address < 0 or address % width or type(beat['error']) is not bool or type(beat['write']) is not bool or not mask:
            raise ValueError('invalid observed bridge beat')
        record(f'{prefix}:beat:{i}:direction', beat['write'], t['write'])
        errors.append(beat['error'])
        for lane in range(width):
            if mask & (1 << lane):
                absolute = address + lane
                record(f'{prefix}:beat:{i}:unique:{lane}', absolute not in observed, True)
                observed[absolute] = data[lane]
    record(prefix + ':lanes', sorted(observed), list(range(start, start + size)))
    record(prefix + ':error', t['error'], any(errors))
    # Failed accesses can have arbitrary response data.
    if not t['error'] and not any(errors):
        record(prefix + ':data', [observed.get(start + i) for i in range(size)], list(expected))
    if 'register' in t:
        state = t['register']
        keys(state, {'before', 'after', 'hw_clear', 'hw_set', 'write_mask'}, {'before', 'after'})
        address = number(t['software_address'])
        matches = [r for r in region['registers']
                   if address == region['base'] + r['offset'] and size * 8 == r['width']]
        if len(matches) != 1:
            raise ValueError('register observations need an exact full-width mapped register')
        reg = matches[0]
        before, after = (uint(state[k], reg['width']) for k in ('before', 'after'))
        permitted = ('w' if t['write'] else 'r') in reg['access']
        record(prefix + ':register:access', permitted or t['error'], True)
        value = uint(t['data'], reg['width'])
        bit_mask = uint(state.get('write_mask', (1 << reg['width']) - 1), reg['width'])
        hw_clear = uint(state.get('hw_clear', 0), reg['width'])
        hw_set = uint(state.get('hw_set', 0), reg['width'])
        target = before
        if not t['error'] and permitted:
            if t['write']:
                target = (before & ~(value & bit_mask) if reg['write_action'] == 'one_to_clear'
                          else (before & ~bit_mask) | (value & bit_mask))
            else:
                record(prefix + ':register:read', value, before)
                if reg['read_action'] == 'clear':
                    target = 0
        target = (target & ~hw_clear) | hw_set
        record(prefix + ':register:effect', after, target)
