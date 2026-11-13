# Isolation case U <-> M on VexiiRiscv rv32imasu (bare addressing). The secret is in mscratch.
# U-mode makes system calls. Public a0 selects the handler: 0 constant time, else a
# secret-dependent loop (the positive control).
.section .text
.globl _start
_start:
  la t0, mhandler
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
.balign 256
user:
# RVW_PROGRAM
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
1: j 1b
.balign 256
mhandler:
  csrr t6, mcause
  li t5, 8
  bne t6, t5, mfail
  csrrw t3, mscratch, t3
  beqz a0, 6f
  andi t4, t3, 15
2:
  addi t4, t4, -1
  bgez t4, 2b
  j 7f
6:
  xor t4, t3, a1
  or t4, t4, t3
  and t4, t4, a1
7:
  csrrw t3, mscratch, t3
  li t4, 0
  li t5, 0
  csrr t6, mepc
  addi t6, t6, 4
  csrw mepc, t6
  li t6, 0
  mret
# Any trap the case does not expect ends the run with tohost = 3.
mfail:
  la t0, tohost
  li t1, 3
  sw t1, 0(t0)
5: j 5b
.balign 4096
super_page:
.section .data
.balign 8
.globl tohost
tohost: .dword 0
# RVW_DATA
