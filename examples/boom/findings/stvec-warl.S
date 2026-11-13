.option norvc
.section .text
.globl _start
_start:
  li t0, 0x4000000000
  csrw stvec, t0
  csrr t1, stvec
  bne t0, t1, different
  li a0, 1
  j finish
different:
  li a0, 3
finish:
  la t0, tohost
  sd a0, 0(t0)
1: j 1b
.section .tohost,"aw"
.balign 8
.globl tohost, fromhost
tohost: .dword 0
fromhost: .dword 0
