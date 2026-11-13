.option norvc
.section .text
.globl _start
_start:
  li t0, 0x501660ed5af74dea
  li t1, 0x8000000000000000
  remw t2, t0, t1
  li t3, 0x5af74dea
  bne t2, t3, fail
  li t0, 0xcbdc4b23d6d844d9
  remuw t2, t0, t1
  li t3, 0xffffffffd6d844d9
  bne t2, t3, fail
  li a0, 1
  j finish
fail:
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
