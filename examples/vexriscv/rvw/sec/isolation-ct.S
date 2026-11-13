# Isolation case: the secret lives in M-mode mscratch. U-mode code makes system calls.
# The M-mode handler uses the secret in constant time and clears the registers it used.
.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
# RVW_SETUP
  csrw mscratch, t0
  li t0, 0
  li t1, 0x1800
  csrc mstatus, t1
  la t1, user
  csrw mepc, t1
  li t1, 0
  mret
.balign 64
user:
# RVW_PROGRAM
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
1: j 1b
.balign 64
handler:
  csrrw t3, mscratch, t3
  xor t4, t3, a0
  div t4, t4, t3
  la t5, mresult
  sw t4, 0(t5)
  csrrw t3, mscratch, t3
  li t4, 0
  li t5, 0
  csrr t6, mepc
  addi t6, t6, 4
  csrw mepc, t6
  li t6, 0
  mret
.section .data
.balign 8
.globl tohost
tohost: .dword 0
mresult: .word 0
# RVW_DATA
