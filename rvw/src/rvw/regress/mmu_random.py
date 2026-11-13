"""Seeded constrained random page tables and self-checking access programs."""
import random

from .mmu_paging import geometry, page_tables


def validate(s):
    import re
    if not re.fullmatch(r'[a-z][a-z0-9-]*', s['id']):
        raise ValueError('invalid random scenario id')
    geometry(s)
    config = s['random_program']
    if not isinstance(config, dict) or set(config) != {'seed', 'pages', 'accesses'}:
        raise ValueError('random_program requires seed, pages and accesses')
    if type(config['seed']) is not int or type(config['pages']) is not int or not 1 <= config['pages'] <= 64 or type(config['accesses']) is not int or not 1 <= config['accesses'] <= 128:
        raise ValueError('random program exceeds bounded page/access counts')
    if s.keys() - {'id', 'mode', 'level', 'flags', 'access', 'expect', 'bins', 'random_program'} or s['level'] != 0 or s['expect'] != 'success':
        raise ValueError('random programs require a standalone level-zero success scenario')


def plan(s):
    from .mmu import ROOT, DATA
    validate(s)
    config = s['random_program']
    rng = random.Random(config['seed'])
    g = geometry(s)
    tables, _ = page_tables(s, ROOT, DATA, 0xc7)
    flags = [rng.choice([0xc7, 0xc3, 0xc1, 0]) for _ in range(config['pages'])]
    values = [rng.randrange(1, 1000) for _ in flags]
    for page, bits in enumerate(flags):
        index = ((0x40000000 >> 12) + page) & ((1 << g.vpn_bits) - 1)
        tables[-1][index] = ((DATA + page * 4096) >> 12 << 10) | bits
    accesses = []
    current = list(values)
    for _ in range(config['accesses']):
        page = rng.randrange(len(flags))
        access = rng.choice(['load', 'store'])
        allowed = bool(flags[page] & (2 if access == 'load' else 4))
        value = rng.randrange(1, 1000) if access == 'store' else current[page]
        accesses.append(dict(page=page, access=access, value=value, fault=not allowed))
        if allowed and access == 'store':
            current[page] = value
    return dict(tables=tables, flags=flags, initial=values, final=current, accesses=accesses)


def assembly(s):
    from .mmu import ROOT, DATA
    g = geometry(s)
    p = plan(s)
    load, store = ('lw', 'sw') if g.xlen == 32 else ('ld', 'sd')
    code = f'''.option norvc
.section .text
.globl _start
_start:
 csrr t0, mhartid
 bnez t0, park
 la t0, trap
 csrw mtvec, t0
 csrw mie, zero
 csrw medeleg, zero
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
    for i, access in enumerate(p['accesses']):
        va = 0x40000000 + access['page'] * 4096
        code += f''' li s2, {(15 if access['access'] == 'store' else 13) if access['fault'] else 0}
 li s3, {va}
 la s4, access_{i}
 la s5, next_{i}
 li t0, 0x21800
 csrc mstatus, t0
 li t0, 0x20800
 csrs mstatus, t0
 li a0, {access['value']}
access_{i}:
 {load if access['access'] == 'load' else store} a0, 0(s3)
 li t0, 0x20000
 csrc mstatus, t0
 bnez s2, fail
 li t1, {access['value']}
 bne a0, t1, fail
next_{i}:
'''
    for i, value in enumerate(p['final']):
        code += f' li t0, {DATA + i * 4096}\n {load} t0, 0(t0)\n li t1, {value}\n bne t0, t1, fail\n'
    code += ''' li t1, 1
 j finish
trap:
 li t0, 0x20000
 csrc mstatus, t0
 beqz s2, fail
 csrr t0, mcause
 bne t0, s2, fail
 csrr t0, mtval
 bne t0, s3, fail
 csrr t0, mepc
 bne t0, s4, fail
 jr s5
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
    if g.xlen == 32:
        code = code.replace(' sd t1, 0(t0)', ' sw t1, 0(t0)')
    for table in p['tables']:
        code += '\n'.join(f' {".word" if g.xlen == 32 else ".dword"} {value}' for value in table) + '\n'
    code += '.section .data\n'
    for value in p['initial']:
        code += f' {".word" if g.xlen == 32 else ".dword"} {value}\n .zero {4096 - g.width}\n'
    return code


def matrix(config):
    if not isinstance(config, dict) or set(config) != {'modes', 'seeds', 'pages', 'accesses'} or not config['modes'] or not config['seeds']:
        raise ValueError('random requires modes, seeds, pages and accesses')
    rows = []
    for mode in config['modes']:
        geometry(dict(mode=mode))
        for seed in config['seeds']:
            row = dict(id=f'{mode}-random-{seed}', mode=mode, level=0, flags='VRWAD', access='load', expect='success',
                       bins=[f'{mode}.random', f'{mode}.random.{seed}'], random_program=dict(seed=seed, pages=config['pages'], accesses=config['accesses']))
            validate(row)
            rows.append(row)
    return rows
