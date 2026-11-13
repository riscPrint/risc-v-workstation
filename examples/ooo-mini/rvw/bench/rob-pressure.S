.section .text
.globl _start
_start:
  la a0, data
  li a1, 123456
  li a2, 7
  li s0, 0
  li s1, 32
  li s2, 1
  li t0, 0
loop:
  div a3, a1, a2
  addi t0, t0, 1
  addi t0, t0, 1
  addi t0, t0, 1
  addi t0, t0, 1
  addi t0, t0, 1
  addi t0, t0, 1
  addi t0, t0, 1
  addi t0, t0, 1
  addi t0, t0, 1
  addi t0, t0, 1
  addi s0, s0, 1
  bne s0, s1, loop
  la t0, tohost
  sw s2, 0(t0)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
.balign 4
data: .space 32
