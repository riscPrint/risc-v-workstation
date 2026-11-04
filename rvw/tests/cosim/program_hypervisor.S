.section .text
.global _start
_start:
  li t0, -1
  csrw pmpaddr0, t0
  li t0, 15
  csrw pmpcfg0, t0
  la t0, host
  csrw stvec, t0
  li t0, 1024
  csrw medeleg, t0
  li t0, 0x800
  csrw mstatus, t0
  li t0, 0x80
  slli t0, t0, 32
  csrs mstatus, t0
  la t0, guest
  csrw mepc, t0
  mret
guest:
  addi s0, zero, 7
  ecall
host:
  wfi
