"""Zicfilp expected-landing-pad preservation across a repairable fetch fault."""
from .programs import HEAD,TAIL
from .disabled import enter


def programs(config):
    isa=config.get('isa','')
    if not isa.startswith('rv64') or 'zicfilp' not in isa:
        raise ValueError('landing recovery requires RV64 Zicfilp')
    if config.get('landing',{}).get('pmp_entries',0)<8:
        raise ValueError('landing recovery requires eight declared PMP entries')
    rows=[]
    for mode in ('S','U'):
        for pad in (('valid','missing','mismatch','unaligned') if 'c' in isa.split('_')[0][4:] else ('valid','missing','mismatch')):
            for disable in (False,True):
                soft=pad!='valid' and not disable
                word={'valid':0x12345017,'missing':0x13,'mismatch':0x12346017,'unaligned':0x12345017}[pad]
                cfg=(15<<56)|0x1b
                code=HEAD+f''' csrw pmpcfg0, zero
 csrw pmpaddr6, zero
 li t0, -1
 csrw pmpaddr7, t0
 la t0, landing_target
 srli t0, t0, 2
 ori t0, t0, 1
 csrw pmpaddr0, t0
 li t0, {cfg}
 csrw pmpcfg0, t0
 sfence.vma
 li t0, 4
 csrs 0x30a, t0
 csrs 0x10a, t0
 la t0, handler
 csrw mtvec, t0
 li s0, 0
 li t2, 0x12345000
'''+enter(mode)+'''access_site:
 la a0, landing_target
 jr a0
 j fail
handler:
 mv s5, t2
 csrr t0, mcause
 bnez s0, completed
 li t1, 1
 bne t0, t1, fail
 csrr t0, mepc
 la t1, landing_target
 bne t0, t1, fail
 csrr t0, mstatus
 srli t0, t0, 41
 andi t0, t0, 1
 li t1, 1
 bne t0, t1, fail
'''
                if disable:
                    code+=f' li t0, 4\n csrc {"0x30a" if mode=="S" else "0x10a"}, t0\n'
                code+=f''' li t0, {(15<<56)|0x1f}
 csrw pmpcfg0, t0
 sfence.vma
 li s0, 1
 mv t2, s5
 mret
completed:
 li t1, {18 if soft else 9 if mode=='S' else 8}
 bne t0, t1, fail
 csrr t0, mepc
 la t1, {'landing_target' if soft else 'landing_done'}
 bne t0, t1, fail
 csrr t0, mstatus
 srli t0, t0, 41
 andi t0, t0, 1
 li t1, {int(soft)}
 bne t0, t1, fail
'''
                if soft:code+=' csrr t0, mtval\n li t1, 2\n bne t0, t1, fail\n'
                code+=' j pass\n'+TAIL+f'''.section .landing_target,"ax"
.balign 16
.globl landing_target
{'.hword 0x0001' if pad=='unaligned' else ''}
landing_target: .word {word}
landing_done:
 ecall
 j fail
'''
                name=f'landing-recovery-{mode.lower()}-{pad}-{int(disable)}'
                rows.append(dict(id=name,family='landing',assembly=code,bins=[name],
                    spec='https://docs.riscv.org/reference/isa/v20260120/priv/priv-cfi.html',
                    link_options=['-Wl,--section-start=.landing_target=0x80008000']))
    return rows
