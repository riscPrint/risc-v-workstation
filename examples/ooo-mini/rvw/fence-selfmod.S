.section .text
.globl _start
_start:
  la t0, patch
  li t1, 0x00100513
  li t2, 123456
  li t3, 7
  div t4, t2, t3
  sw t1, 0(t0)
  fence.i
patch:
  addi a0, x0, 0
  li a1, 1
  bne a0, a1, fail
  j report
fail:
  li a1, 3
report:
  la a2, tohost
  sw a1, 0(a2)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
