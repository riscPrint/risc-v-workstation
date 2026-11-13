"""Explicit project mapping for buses whose data and strobes use word lanes."""


def word_bus_address(record, xlen):
    """Map an effective byte address to its bus word, without changing data or masks.

    Call only when the project has reviewed that its data and strobes already
    use word lanes. This is not an architectural-access or trap normalizer.
    The co-simulator must still check every active byte against the reference.
    """
    if xlen not in (32, 64):
        raise ValueError('word bus mapping requires XLEN 32 or 64')
    if record.get('trap') or record.get('mem_fault'):
        raise ValueError('fault addresses require an explicit fault mapping')
    size=xlen//8
    for key in ('mem_rmask','mem_wmask'):
        value=record[key]
        if type(value) is not int or not 0 <= value < 1 << size:
            raise ValueError('invalid word-lane mask')
    address=record['mem_addr']
    if type(address) is not int or not 0 <= address < 1 << xlen:
        raise ValueError('invalid memory address')
    mapped=dict(record)
    if record['mem_rmask'] or record['mem_wmask']:
        mapped['mem_addr']=address & ~(size-1)
    return mapped
