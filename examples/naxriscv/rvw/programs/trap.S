/* Read the actual machine ECALL cause before reporting pass. */
.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  ecall
  j fail
handler:
  csrr t0, mcause
  li t1, 11
  bne t0, t1, fail
  li t1, 1
  j finish
fail:
  li t1, 3
finish:
  la t0, tohost
  sw t1, 0(t0)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
