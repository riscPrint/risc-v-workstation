.section .text
.globl _start
_start:
  li x1, 7
  li x2, 9
  mul x3, x1, x2
  addi x4, x0, 63
  bne x3, x4, fail
  la x5, scratch
  sw x3, 0(x5)
  lw x6, 0(x5)
  bne x3, x6, fail
  div x7, x3, x1
  bne x7, x2, fail
  li x8, 1
  j report
fail:
  li x8, 3
report:
  la x9, tohost
  sw x8, 0(x9)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
scratch: .word 0
