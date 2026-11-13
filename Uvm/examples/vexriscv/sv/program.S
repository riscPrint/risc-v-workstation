.section .text
.globl _start
_start:
  li t0, 19
  li t1, 23
  add t2, t0, t1
  la t3, scratch
  sw t2, 0(t3)
  lw t4, 0(t3)
  bne t2, t4, fail
  li t5, 1
  j finish
fail:
  li t5, 3
finish:
  la t3, tohost
  sw t5, 0(t3)
1: j 1b
.section .data
.balign 16
scratch: .word 0
.globl tohost
tohost: .word 0
