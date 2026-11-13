.option norvc
.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  li s0, 0
  li t0, -1
  csrw mtval, t0
  li t0, 0x888
  csrw mie, t0
  csrsi mstatus, 8
wait_start:
  li t0, 1234
  li t1, 7
  div t2, t0, t1
  addi t3, t2, 1
  la t4, scratch
  sw t3, 0(t4)
  lw t5, 0(t4)
  bne t3, t5, fail
  beqz s0, wait_start
wait_end:
  li t0, 1
  bne s0, t0, fail
  li a1, 1
  j report
handler:
  csrr t0, mcause
  li t1, IRQ_CAUSE
  bne t0, t1, fail
  csrr t0, mtval
  bnez t0, fail
  csrr t0, mepc
  la t1, wait_start
  bltu t0, t1, fail
  la t1, wait_end
  bgeu t0, t1, fail
  csrr t0, mstatus
  andi t1, t0, 8
  bnez t1, fail
  andi t1, t0, 128
  beqz t1, fail
  csrw mie, zero
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
