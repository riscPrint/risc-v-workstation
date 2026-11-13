/* CASE=0..5 selects CSRR C/CI/S/SI/W/WI. This profile has IALIGN=32. */
#ifndef CASE
#define CASE 0
#endif
#if CASE == 0 || CASE == 3
#define VALUE 3
#elif CASE == 1 || CASE == 2
#define VALUE 2
#else
#define VALUE 1
#endif
.section .text.init
.global rvtest_entry_point
rvtest_entry_point:
  li t0, VALUE
  csrw mepc, t0
#if CASE == 0
  csrrc t1, mepc, zero
#elif CASE == 1
  csrrci t1, mepc, 0
#elif CASE == 2
  csrrs t1, mepc, zero
#elif CASE == 3
  csrrsi t1, mepc, 0
#elif CASE == 4
  csrrw t1, mepc, zero
#elif CASE == 5
  csrrwi t1, mepc, 13
#else
#error CASE must be in 0..5
#endif
  andi t1, t1, 3
  li gp, 1
  beqz t1, finish
  li gp, 3
finish:
  la t0, tohost
  sw gp, 0(t0)
  sw zero, 4(t0)
1: j 1b
.section .data
.balign 8
.global tohost
tohost: .dword 0
