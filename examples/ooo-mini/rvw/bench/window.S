.section .text
.globl _start
_start:
  li a0, 100
  li a1, 123456
  li a2, 7
loop:
  div a3, a1, a2
  addi s0, s0, 1
  addi s1, s1, 2
  addi s2, s2, 3
  addi s3, s3, 4
  addi s4, s4, 5
  addi s5, s5, 6
  addi s6, s6, 7
  addi s7, s7, 8
  addi s8, s8, 9
  addi s9, s9, 10
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
