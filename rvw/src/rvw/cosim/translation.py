"""Bounded independent Sv39/Sv39x4 address observations from reference RAM.

This checks successful address mappings. It does not check walk traffic, PMP,
TLB state, fault precedence or A/D update atomicity.
"""


def walk(address, root, read, *, guest=False):
    mode = root >> 60
    if mode == 0:
        return address
    if mode != 8:
        raise ValueError('two-stage observation supports Bare or Sv39/Sv39x4 only')
    if guest:
        if address >= 1 << 41 or root & 3:
            raise ValueError('invalid Sv39x4 GPA or root alignment')
    else:
        sign = (address >> 38) & 1
        if address >> 39 != ((1 << 25)-1 if sign else 0):
            raise ValueError('noncanonical Sv39 address')
    table = (root & ((1 << 44)-1)) << 12
    for level in (2, 1, 0):
        index = (address >> (12+9*level)) & (2047 if guest and level == 2 else 511)
        pte = read(table+index*8)
        if pte >> 54 or not pte & 1 or (pte & 4 and not pte & 2):
            raise ValueError('unsupported or invalid translation PTE')
        ppn = pte >> 10
        if pte & 10:
            if ppn & ((1 << (9*level))-1):
                raise ValueError('misaligned translation superpage')
            bits = 12+9*level
            return (ppn << 12) | (address & ((1 << bits)-1))
        if level == 0 or pte & 0xd0:
            raise ValueError('invalid nonleaf translation PTE')
        table = ppn << 12
    raise ValueError('translation did not reach a leaf')


def observations(effect, context, read):
    if effect['trap']:
        raise ValueError('faulting two-stage observations are unsupported')
    if effect['mem_wmask']:
        raise ValueError('two-stage store observations need pre-step page-table capture')
    virtual, vsatp, hgatp = context
    if not virtual:
        return []
    def stage2(gpa):
        return walk(gpa, hgatp, read, guest=True)
    def stage1_read(gpa):
        return read(stage2(gpa))
    accesses = [('fetch', effect['pc'])]
    if effect['mem_rmask']:
        accesses.append(('load', effect['mem_addr']))
    if effect['mem_wmask']:
        accesses.append(('store', effect['mem_addr']))
    rows = []
    for access, va in accesses:
        gpa = walk(va, vsatp, stage1_read)
        rows.append(dict(access=access, va=va, gpa=gpa, pa=stage2(gpa)))
    return rows
