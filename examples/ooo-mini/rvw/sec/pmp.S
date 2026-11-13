.option norvc
.section .text
.globl _start
_start:
# RVW_SETUP
  la t0, handler
  csrw mtvec, t0
  la t0, private_word
  srli t0, t0, 2
  csrw pmpaddr0, t0
  li t0, -1
  csrw pmpaddr1, t0
  li t0, 0x1f10
  csrw pmpcfg0, t0
  li t0, 0x1800
  csrc mstatus, t0
  la t0, user
  csrw mepc, t0
  mret
handler:
  csrr t0, mcause
  li t1, 5
  bne t0, t1, fail
  csrr t0, mepc
  addi t0, t0, 4
  csrw mepc, t0
  mret
fail:
  li a1, 3
  la a2, tohost
  sw a1, 0(a2)
1: j 1b
.org 0x100
user:
  la a0, private_word
# RVW_PROGRAM
  li a1, 1
  la a2, tohost
  sw a1, 0(a2)
2: j 2b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
# RVW_DATA
