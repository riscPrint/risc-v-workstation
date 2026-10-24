# Drops to user mode with mret and returns with ecall: both change the privilege mode.
.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  li t1, 0x1800
  csrc mstatus, t1        # MPP = user
  la t0, user
  csrw mepc, t0
  mret
user:
  addi a0, zero, 7
  ecall
handler:
  la t0, tohost
  li t1, 1
  sd t1, 0(t0)
1: j 1b
.section .data
.globl tohost
.align 3
tohost: .dword 0
