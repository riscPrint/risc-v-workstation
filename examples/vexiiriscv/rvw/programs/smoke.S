/* RV32IM smoke test. No PMP or virtual-memory setup. */
.section .text
.globl _start
_start:
  li t0, 9
  li t1, 7
  mul t2, t0, t1
  li t3, 63
  bne t2, t3, fail
  div t2, t2, t0
  bne t2, t1, fail
  la t0, scratch
  sw t2, 0(t0)
  lb t3, 0(t0)
  bne t3, t1, fail
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
scratch: .word 0
