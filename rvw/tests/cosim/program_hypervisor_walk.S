.section .text
.global _start
_start:
  li t0, -1
  csrw pmpaddr0, t0
  li t0, 15
  csrw pmpcfg0, t0
  la t0, vtable
  srli t0, t0, 12
  li t1, 8
  slli t1, t1, 60
  or t0, t0, t1
  csrw vsatp, t0
  la t0, gtable
  srli t0, t0, 12
  or t0, t0, t1
  csrw hgatp, t0
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

.section .data
.balign 16384
gtable:
  .zero 16
  .dword 0x200000df
  .dword 0x200000df
  .zero 16352
.balign 4096
vtable:
  .zero 16
  .dword 0x300000cf
  .zero 4072
