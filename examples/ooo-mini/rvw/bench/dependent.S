.section .text
.globl _start
_start:
  li a0, 100
  li a1, 17
  li a2, 3
loop:
  mul a1, a1, a2
  addi a1, a1, 1
  xor a1, a1, a2
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
