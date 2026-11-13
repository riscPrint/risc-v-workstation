# VexRiscv keeps the previous mtval on an interrupt trap. The privileged ISA
# (Machine Trap Value Register) sets mtval to zero for traps other than the
# listed exceptions. Select the matching interrupt pin schedule, for example
# --irq-schedule 1:0x0,200:0x80. tohost 1 = zero mtval, 3 = old value kept.
.option norvc
.section .text
.globl _start
_start:
 la t0, handler
 csrw mtvec, t0
 li t0, 0x55
 csrw mtval, t0
 li t0, 0x800
 csrw mie, t0
 csrsi mstatus, 8
1: wfi
 j 1b
handler:
 csrr t0, mcause
 li t1, 0x8000000b
 bne t0, t1, fail
 csrr t0, mtval
 bnez t0, fail
 li t1, 1
 j finish
fail:
 li t1, 3
finish:
 csrw mie, zero
 la t0, tohost
 sw t1, 0(t0)
2: j 2b
.section .tohost,"aw"
.balign 64
.globl tohost, fromhost
tohost: .dword 0
fromhost: .dword 0
