.option norvc
.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  la t0, secret
  srli t0, t0, 2
  csrw pmpaddr0, t0
  li t0, -1
  csrw pmpaddr1, t0
  li t0, 0x1f10
  csrw pmpcfg0, t0
  li s0, 0
  li t0, 0x1800
  csrc mstatus, t0
  la t0, user
  csrw mepc, t0
  mret
user:
  la a0, secret
  li t0, 1234
  li t1, 7
  div t2, t0, t1
  beq zero, zero, recovered
  lw t3, 0(a0)
  sw t2, 0(a0)
recovered:
  bnez s0, fail
fault_load:
  lw t3, 0(a0)
fault_store:
  sw t2, 0(a0)
  li t0, 2
  bne s0, t0, fail
  ecall
handler:
  csrr t0, mcause
  li t1, 8
  beq t0, t1, complete
  csrr t1, mtval
  la t4, secret
  bne t1, t4, fail
  csrr t1, mepc
  beqz s0, check_load
  la t4, fault_store
  bne t1, t4, fail
  li t4, 7
  bne t0, t4, fail
  j advance
check_load:
  la t4, fault_load
  bne t1, t4, fail
  li t4, 5
  bne t0, t4, fail
advance:
  addi s0, s0, 1
  addi t1, t1, 4
  csrw mepc, t1
  mret
complete:
  la t0, secret
  lw t0, 0(t0)
  li t1, 0x12345678
  bne t0, t1, fail
  li a1, 1
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
.balign 4
secret: .word 0x12345678
