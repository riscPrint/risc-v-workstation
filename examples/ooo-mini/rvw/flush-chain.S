.option norvc
.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  li s0, 0
  li s1, 4
loop:
  li t0, 1234
  li t1, 7
  div t2, t0, t1
  la a0, scratch
  sw t2, 0(a0)
  beq zero, zero, recovered
  lw t3, 0(a0)
  sw zero, 0(a0)
recovered:
  lw t3, 0(a0)
  bne t2, t3, fail
  fence.i
  ecall
  csrr t0, mstatus
  csrw mstatus, t0
  lw t3, 0(a0)
  li t4, 176
  bne t3, t4, fail
  addi s1, s1, -1
  bnez s1, loop
  li t0, 4
  bne s0, t0, fail
  li a1, 1
  j report
handler:
  csrr t0, mcause
  li t1, 11
  bne t0, t1, fail
  csrr t0, mepc
  addi t0, t0, 4
  csrw mepc, t0
  addi s0, s0, 1
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
scratch: .word 0
