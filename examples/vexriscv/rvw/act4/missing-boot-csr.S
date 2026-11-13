/* Compile with -DCSR_ADDR=0x310 or -DCSR_ADDR=0x323. */
#ifndef CSR_ADDR
#define CSR_ADDR 0x310
#endif
.section .text.init
.global rvtest_entry_point
rvtest_entry_point:
  la t0, trap
  csrw mtvec, t0
  csrw CSR_ADDR, zero
  li gp, 1
  j finish
.balign 4
trap:
  csrr t1, mcause
  la t0, trap_cause
  sw t1, 0(t0)
  csrr t1, mtval
  la t0, trap_value
  sw t1, 0(t0)
  li gp, 3
finish:
  la t0, tohost
  sw gp, 0(t0)
  sw zero, 4(t0)
1: j 1b
.section .data
trap_cause: .word 0
trap_value: .word 0
.balign 8
.global tohost
tohost: .dword 0
