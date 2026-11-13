"""Smepmp 1.0 policy transitions. Keep these separate from base PMP."""
from .programs import HEAD, TAIL


def programs(config):
    if 'smepmp' not in config.get('isa', ''):
        raise ValueError('ePMP campaign requires Smepmp in isa')
    rows = []
    for kind in ('mmwp', 'mml-su', 'mml-m', 'rlb'):
        # RLB permits bootstrap changes to locked rules. M-mode code is RX;
        # data/tohost are RW. The test target lies outside these boot regions.
        code = HEAD + ''' csrw pmpcfg0, zero
 la t0, handler
 csrw mtvec, t0
 csrr t0, 0x747
 bnez t0, fail
 li t0, 4
 csrw 0x747, t0
 li t0, 0x200001ff
 csrw pmpaddr0, t0
 li t0, 0x200007ff
 csrw pmpaddr1, t0
 la t0, probe
 srli t0, t0, 2
 ori t0, t0, 1
 csrw pmpaddr2, t0
'''
        target = {'mmwp': 0, 'mml-su': 0x19, 'mml-m': 0x99, 'rlb': 0x99}[kind]
        cfg = 0x9d | (0x9b << 8) | (target << 16)
        code += f' li t0, {cfg}\n csrw pmpcfg0, t0\n'
        policy = 2 if kind == 'mmwp' else 1
        code += f''' li t0, {policy | 4}
 csrw 0x747, t0
 # MML and MMWP are sticky until reset.
 li t0, 4
 csrw 0x747, t0
 csrr t0, 0x747
 andi t0, t0, 3
 li t1, {policy}
 bne t0, t1, fail
'''
        if kind == 'rlb':
            code += ''' csrr s0, pmpaddr2
 addi t0, s0, 4
 csrw pmpaddr2, t0
 csrr t1, pmpaddr2
 bne t0, t1, fail
 csrw pmpaddr2, s0
'''
        code += f''' li t0, {policy}
 csrw 0x747, t0
 # RLB cannot be re-enabled while any entry is locked.
 li t0, {policy | 4}
 csrw 0x747, t0
 csrr t0, 0x747
 andi t0, t0, 4
 bnez t0, fail
'''
        if kind in ('mml-m', 'rlb'):
            code += ''' csrr s0, pmpaddr2
 csrw pmpaddr2, zero
 csrr t0, pmpaddr2
 bne t0, s0, fail
'''
        denied = kind in ('mmwp', 'mml-su')
        code += f''' la a0, probe
access_site:
 lw t0, 0(a0)
 {'j fail' if denied else 'li t1, 42'}
 {'nop' if denied else 'bne t0, t1, fail'}
 j pass
handler:
 csrr t0, mcause
 li t1, 5
 bne t0, t1, fail
 csrr t0, mepc
 la t1, access_site
 bne t0, t1, fail
 csrr t0, mtval
 la t1, probe
 bne t0, t1, fail
 {'j pass' if denied else 'j fail'}
''' + TAIL + '''.section .probe,"aw"
.balign 16
probe: .word 42, 0, 0, 0
'''
        rows.append(dict(id='epmp-' + kind, family='epmp', assembly=code,
            bins=['epmp.' + kind], spec='https://docs.riscv.org/reference/isa/v20260120/priv/smepmp.html', link_options=['-Wl,--section-start=.probe=0x80008000']))
    return rows
