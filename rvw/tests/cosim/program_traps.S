# Synchronous traps without counters or MMIO, so both Spike and offline Sail can run it.
# An illegal instruction is followed by a read of mtval; then WFI, EBREAK and a drop to user mode.
.section .text
.globl _start, illegal_site, mtval_site, wfi_site, ebreak_site, mret_site
_start:
  la t0, handler
  csrw mtvec, t0
illegal_site:
  .word 0xc0001073        # unimp (csrrw x0, cycle, x0): illegal, cycle is read-only
mtval_site:
  csrr a0, mtval
  addi a1, a0, 1
wfi_site:
  wfi                     # no interrupt is enabled: a legal no-op that retires
  addi a2, zero, 5
ebreak_site:
  ebreak
  li t0, -1
  csrw pmpaddr0, t0       # PMP entry 0: all memory for user mode (Spike sets this at reset, Sail does not)
  li t0, 0x1f
  csrw pmpcfg0, t0
  li t1, 0x1800
  csrc mstatus, t1        # MPP = user
  la t0, user
  csrw mepc, t0
mret_site:
  mret
user:
  addi a3, zero, 7
  ecall
handler:
  csrr t0, mcause
  li t1, 8
  beq t0, t1, done        # ecall from user mode ends the test
  csrr t0, mepc
  addi t0, t0, 4
  csrw mepc, t0
  mret
done:
  la t0, tohost
  li t1, 1
  sd t1, 0(t0)
1: j 1b
.section .data
.globl tohost
.align 3
tohost: .dword 0
