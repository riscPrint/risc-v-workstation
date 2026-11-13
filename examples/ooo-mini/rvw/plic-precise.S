.option norvc
.section .text
.globl _start
_start:
  la t0, vectors
  ori t0, t0, 1
  csrw mtvec, t0
  li t0, 0x123
  csrw mtval, t0
  li s0, 0
  li s1, 0
  li a0, 0x0c000000
  li t0, 3
  sw t0, 4(a0)
  li t0, 2
  li a1, 0x0c002000
  sw t0, 0(a1)
  li a2, 0x0c200004
illegal_claim:
  .word 0x00063e03
  li t0, 1234
  li t1, 7
  div t2, t0, t1
  beq zero, zero, recovered
wrong_path_claim:
  lw t3, 0(a2)
recovered:
  li t0, 0x800
  csrw mie, t0
wake_start:
  csrsi mstatus, 8
  wfi
wait_irq:
  beqz s0, wait_irq
wake_end:
  li t0, 1
  bne s1, t0, fail
  bne s0, t0, fail
  li a1, 1
  j report
handler:
  csrr t0, mcause
  li t1, 2
  beq t0, t1, illegal_handler
  li t1, 0x8000000b
  bne t0, t1, fail
  csrr t0, mtval
  bnez t0, fail
  csrr t0, mepc
  la t1, wake_start
  bltu t0, t1, fail
  la t1, wake_end
  bgeu t0, t1, fail
  csrr t0, mstatus
  andi t1, t0, 8
  bnez t1, fail
  andi t1, t0, 128
  beqz t1, fail
  lw t0, 0(a2)
  li t1, 1
  bne t0, t1, fail
  csrw mie, zero
  sw t0, 0(a2)
  sw zero, 0(a1)
  addi s0, s0, 1
  mret
illegal_handler:
  csrr t0, mepc
  la t1, illegal_claim
  bne t0, t1, fail
  csrr t1, mtval
  li t2, 0x00063e03
  bne t1, t2, fail
  addi t0, t0, 4
  csrw mepc, t0
  addi s1, s1, 1
  mret
fail:
  li a1, 3
report:
  la a2, tohost
  sw a1, 0(a2)
1: j 1b
.balign 64
vectors:
.rept 12
  j handler
.endr
.section .data
.balign 8
.globl tohost
tohost: .dword 0
