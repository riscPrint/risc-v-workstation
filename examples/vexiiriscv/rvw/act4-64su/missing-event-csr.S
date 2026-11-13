.option norvc
.section .text
.globl _start
_start:
  csrw mscratch, zero
  la t0, trap_handler
  csrw mtvec, t0
.globl event_write
event_write:
  csrw 0x323, zero
  li t1, 1
  j finish
trap_handler:
  csrr s0, mcause
  csrr s1, mtval
  csrr s2, mepc
  li t1, 3
finish:
  la t0, tohost
  sw t1, 0(t0)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
