#!/usr/bin/env python3
"""Bounded cross-hart instruction visibility and machine software IRQ programs."""
import argparse
from programs import build


def program(body, handler=''):
    return '''.option norvc
.text
.globl _start
_start:
li s0, 0x81000000
'''+body+'''
li a0, 1
j finish
fail:
li a0, 3
finish:
la t0, tohost
sd a0, 0(t0)
park: j park
'''+handler+'''
.section .tohost,"aw",@progbits
.balign 64
.globl tohost
tohost: .dword 0
.section .shared,"aw",@nobits
.zero 8192
'''


def sources(name):
    if name=='fence-i-cross':
        return [program('''li t0, 0x81001000
li t1, 0x02a00513
sw t1, 0(t0)
li t1, 0x00008067
sw t1, 4(t0)
fence rw,rw
li t1, 1
sd t1, 0(s0)
wait_ack: ld t1, 8(s0)
beqz t1, wait_ack
'''),program('''wait_code: ld t1, 0(s0)
beqz t1, wait_code
fence rw,rw
fence.i
li t0, 0x81001000
jalr ra, t0, 0
li t1, 42
bne a0, t1, fail
li t1, 1
sd t1, 8(s0)
''')]
    if name=='ipi':
        return [program('''wait_ready: ld t0, 0(s0)
beqz t0, wait_ready
fence rw,rw
li t0, 0x02000004
li t1, 1
sw t1, 0(t0)
wait_ack: ld t1, 8(s0)
beqz t1, wait_ack
'''), program('''la t0, trap_handler
csrw mtvec, t0
li t0, 8
csrw mie, t0
csrs mstatus, t0
li t0, 1
sd t0, 0(s0)
wait_irq: ld t0, 8(s0)
beqz t0, wait_irq
''','''.balign 4
trap_handler:
csrr t0, mcause
li t1, 0x8000000000000003
bne t0, t1, fail
li t0, 0x02000004
sw zero, 0(t0)
li t1, 1
sd t1, 8(s0)
mret
''')]
    raise ValueError('unsupported visibility suite')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--suite',choices=['fence-i-cross','ipi'],required=True)
    p.add_argument('--out',required=True);a=p.parse_args()
    print(build(a.out,sources=sources(a.suite)))
