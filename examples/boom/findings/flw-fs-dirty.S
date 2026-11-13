.option norvc
.section .text
.globl _start
_start:
  li t0, 0x6000
  csrs mstatus, t0
  fmv.w.x f0, zero
  li t0, 0x6000
  csrc mstatus, t0
  li t0, 0x2000
  csrs mstatus, t0
  la t0, cell
  flw f0, 0(t0)
  csrr t1, mstatus
  li t0, 0x6000
  and t1, t1, t0
  bne t1, t0, fail
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
cell: .word 0x3f800000
