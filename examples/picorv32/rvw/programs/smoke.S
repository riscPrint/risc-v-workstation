/* Smoke program: arithmetic, one load and one store, then tohost = 1. */
.section .text.init
.globl _start
_start:
  li t0, 9
  li t1, 7
  add t2, t0, t1
  li t3, 16
  bne t2, t3, fail
  la t0, scratch
  sw t2, 0(t0)
  lw t3, 0(t0)
  bne t3, t2, fail
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
