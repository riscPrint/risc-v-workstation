.option norvc
.section .text
.globl _start
_start:
  la t0, trap
  csrw mtvec, t0
  la t0, cell
  addi t0, t0, 1
  lh t1, 0(t0)
  j fail
trap:
  csrr t0, mcause
  li t1, 4
  bne t0, t1, fail
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
.section .data
.balign 8
cell: .dword 0
