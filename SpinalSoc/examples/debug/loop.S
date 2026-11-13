.option norvc
.text
.globl _start
_start:
  li t0, 0x10000000
  li t1, 0x12345678
  sw t1, 4(t0)
loop:
  addi s0, s0, 1
  j loop
