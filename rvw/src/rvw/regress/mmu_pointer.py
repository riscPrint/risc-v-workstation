"""Smnpm data-pointer masking under MPRV with effective S privilege."""


def validate(s):
    if type(s['pointer_mask']) is not int or s['pointer_mask'] not in (0, 7, 16):
        raise ValueError('pointer_mask must be 0, 7 or 16')
    if s.get('mode') not in ('sv39', 'sv48', 'sv57') or s.get('privilege', 'S') != 'S' or not s.get('mprv', True) or s['access'] != 'load' or s['level'] != 0 or s.get('satp_mode') == 'bare':
        raise ValueError('pointer_mask requires an RV64 MPRV S-mode translated load')
    if s.keys() - {'id', 'mode', 'level', 'flags', 'access', 'expect', 'bins', 'pointer_mask', 'va'}:
        raise ValueError('unsupported pointer-mask scenario option')
    from .mmu import number
    if not 0 <= number(s.get('va', 0x40000000)) < 1 << 47:
        raise ValueError('pointer-mask VA must fit the common positive 48-bit range')
    if s['expect'] != ('success' if s['pointer_mask'] else 'page-fault'):
        raise ValueError('tagged pointer requires success when masking is enabled, otherwise a page fault')


def setup(s):
    pmm = {0: 0, 7: 2, 16: 3}[s['pointer_mask']]
    return f'''li t0, 0x300000000
 csrc menvcfg, t0
 li t0, {pmm << 32}
 csrs menvcfg, t0
 csrr t1, menvcfg
 li t2, 0x300000000
 and t1, t1, t2
 bne t0, t1, fail
 '''
