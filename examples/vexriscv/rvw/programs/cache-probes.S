/* Sweep twice the L1 capacity, then force dirty victims and check all values. */
.option norvc
.section .text
.globl _start
_start:
  la s0, buffer
  li s1, 256
  li t1, 1
write:
  sw t1, 0(s0)
  addi s0, s0, 64
  addi t1, t1, 1
  addi s1, s1, -1
  bnez s1, write
  la s0, buffer
  li s1, 256
  li t1, 1
read:
  lw t2, 0(s0)
  bne t1, t2, fail
  addi t2, t2, 1
  sw t2, 0(s0)
  addi s0, s0, 64
  addi t1, t1, 1
  addi s1, s1, -1
  bnez s1, read
  fence.i
  li t0, 1
  j finish
fail:
  li t0, 3
finish:
  la t1, tohost
  sw t0, 0(t1)
1: j 1b
.section .data
.balign 64
.globl tohost
tohost: .dword 0
.section .bss
.balign 64
buffer: .space 16384
