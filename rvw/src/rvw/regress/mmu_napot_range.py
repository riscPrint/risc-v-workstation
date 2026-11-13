"""Full 64 KiB NAPOT range remapping with required fences for every page."""


def validate(s):
    if s.keys() - {'id', 'mode', 'level', 'flags', 'access', 'expect', 'bins', 'napot', 'napot_remap', 'fence'}:
        raise ValueError('unsupported NAPOT range remap option')
    if s.get('napot_remap') is not True or s.get('napot') is not True or s['mode'] not in ('sv39','sv48','sv57') or s['level'] != 0 or s['flags'] != 'VRWAD' or s['access'] != 'load' or s['expect'] != 'success' or s.get('fence', 'all') not in ('all','va'):
        raise ValueError('NAPOT range requires RV64 level-zero VRWAD load with all/per-page fences')


def assembly(s):
    from .mmu import ROOT, DATA
    from .mmu_paging import geometry, page_tables
    from .mmu_extensions import pte
    validate(s)
    g = geometry(s)
    tables, leaf = page_tables(s, ROOT, DATA, 0xc7)
    code = f'''.option norvc
.section .text
.globl _start
_start:
 csrr t0, mhartid
 bnez t0, park
 la t0, fail
 csrw mtvec, t0
 csrw mie, zero
 li t0, -1
 csrw pmpaddr0, t0
 li t0, 15
 csrw pmpcfg0, t0
 li t0, {g.satp(ROOT)}
 csrw satp, t0
 csrr t1, satp
 bne t0, t1, fail
 sfence.vma x0, x0
 li t0, 0xe1800
 csrc mstatus, t0
'''
    for phase in range(2):
        for page in range(16):
            code += f''' li t3, {0x40000000 + page * 4096}
 li t0, 0x20800
 csrs mstatus, t0
 ld a0, 0(t3)
 li t0, 0x20000
 csrc mstatus, t0
 li t1, {42 + phase + page}
 bne a0, t1, fail
'''
        if phase == 0:
            new_pte = pte(s, DATA + 65536, 0xc7)
            for page in range(16):
                code += f' li t0, {leaf + page * 8}\n li t1, {new_pte}\n sd t1, 0(t0)\n'
            if s.get('fence','all') == 'all':
                code += ' sfence.vma x0, x0\n'
            else:
                # A NAPOT mapping may be cached as several smaller entries.
                for page in range(16):
                    code += f' li t3, {0x40000000 + page * 4096}\n sfence.vma t3, x0\n'
    code += ''' li t1, 1
 j finish
fail:
 li t1, 3
finish:
 la t0, tohost
 sd t1, 0(t0)
park:
 j park
.section .tohost,"aw"
.balign 64
.globl tohost, fromhost
tohost: .dword 0
fromhost: .dword 0
.section .tables,"aw"
'''
    for table in tables:
        code += '\n'.join(f' .dword {value}' for value in table) + '\n'
    code += '.section .data\n'
    for phase in range(2):
        for page in range(16):
            code += f' .dword {42 + phase + page}\n .zero 4088\n'
    return code
