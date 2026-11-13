# PMP isolation case: M-mode writes the secret into the keystore region (0x80008000, 256 B).
# PMP entry 0 denies U-mode access to it; entry 1 gives U-mode the rest of the 64 KiB RAM.
# The M-mode handler skips a faulting instruction and returns.
.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
# RVW_SETUP
  li t1, 0x80008000
  sw t0, 0(t1)
  li t0, 0
  li t1, 0x2000201f
  csrw pmpaddr0, t1
  li t1, 0x20001fff
  csrw pmpaddr1, t1
  li t1, 0x1f18
  csrw pmpcfg0, t1
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
  csrr t6, mepc
  addi t6, t6, 4
  csrw mepc, t6
  li t6, 0
  mret
.section .data
.balign 8
.globl tohost
tohost: .dword 0
.balign 64
sec_probe: .fill 512, 4, 0x80000000
# RVW_DATA
