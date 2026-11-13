.option norvc
.section .text
.globl _start
_start:
  li t0, 0x10000000
  li t1, 83
  sb t1, 0(t0)
  li a7, 0x10
  li a6, 0
  ecall
  bnez a0, fail
  li t2, 0x2000000
  bne a1, t2, fail
  li t0, 0x80001000
  li t1, 1
  sw t1, 0(t0)
1: j 1b
fail:
  li t0, 0x80001000
  li t1, 3
  sw t1, 0(t0)
  j 1b
