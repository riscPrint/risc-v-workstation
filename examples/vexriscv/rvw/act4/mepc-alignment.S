#ifndef MEPC_VALUE
#define MEPC_VALUE 1
#endif
.section .text.init
.global rvtest_entry_point
rvtest_entry_point:
  li t0, MEPC_VALUE
  csrw mepc, t0
  csrr t1, mepc
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
