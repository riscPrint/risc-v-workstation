.section .text
.globl _start
_start:
  li s0, 0x10000000
  li s1, 0x0c000000
  li s2, 0x02000000
  lbu t0, 1(s0)
  bnez t0, fail
  lbu t0, 7(s0)
  bnez t0, fail
  lbu t0, 3(s0)
  bnez t0, fail
  lbu t0, 2(s0)
  li t1, 1
  bne t0, t1, fail
  lbu t0, 5(s0)
  li t1, 0x60
  bne t0, t1, fail
  li t0, 128
  sb t0, 3(s0)
  lbu t0, 0(s0)
  bnez t0, fail
  lbu t0, 1(s0)
  bnez t0, fail
  sb zero, 3(s0)
  lw t0, 0(s2)
  bnez t0, fail
  li t1, 0x4000
  add t1, s2, t1
  lw t0, 0(t1)
  li t2, -1
  bne t0, t2, fail
  lw t0, 4(t1)
  bne t0, t2, fail
  lw t0, 4(s1)
  bnez t0, fail
  li t1, 0x1000
  add t1, s1, t1
  lw t0, 0(t1)
  bnez t0, fail
  li t1, 0x2000
  add t1, s1, t1
  lw t0, 0(t1)
  bnez t0, fail
  li t1, 0x200000
  add t1, s1, t1
  lw t0, 0(t1)
  bnez t0, fail
  lw t0, 4(t1)
  bnez t0, fail
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
1: j 1b
fail:
  la t0, tohost
  li t1, 3
  sw t1, 0(t0)
  j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
