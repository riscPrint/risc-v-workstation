.option norvc
.section .text
.globl _start
_start:
  la t0, trap
  csrw mtvec, t0
  csrr t1, minstret
  ecall
  csrr t2, minstret
  sub t2, t2, t1
  li t0, 5
  bne t2, t0, fail
  li a0, 1
  j finish
trap:
  csrr t0, mepc
  addi t0, t0, 4
  csrw mepc, t0
  mret
fail:
  li a0, 3
finish:
  la t0, tohost
  sd a0, 0(t0)
1: j 1b
.section .tohost,"aw"
.balign 8
.globl tohost, fromhost
tohost: .dword 0
fromhost: .dword 0
