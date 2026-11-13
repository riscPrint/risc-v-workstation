.section .text
.globl _start
_start:
  li a0, 100
  la a1, scratch
  li a2, 1
loop:
  sw a2, 0(a1)
  lw a3, 0(a1)
  add a2, a2, a3
  addi a0, a0, -1
  bnez a0, loop
  la a0, tohost
  li a1, 1
  sw a1, 0(a0)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
scratch: .word 0
