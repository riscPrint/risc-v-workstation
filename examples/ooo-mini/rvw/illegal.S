.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  li s0, 0
  csrr s1, minstret
  .word 0xfe000033
  .word 0x00003003
  .word 0x00002067
  csrr s2, minstret
  sub s2, s2, s1
  li s3, 34
  bne s2, s3, fail
  li t0, 3
  bne s0, t0, fail
  li a1, 1
  j report
handler:
  csrr t0, mcause
  li t1, 2
  bne t0, t1, fail
  csrr t0, mepc
  lw t1, 0(t0)
  csrr t2, mtval
  bne t1, t2, fail
  addi s0, s0, 1
  addi t0, t0, 4
  csrw mepc, t0
  mret
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
