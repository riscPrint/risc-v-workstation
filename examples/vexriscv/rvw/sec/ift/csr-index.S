# Leak: an address computed from mscratch reaches the data bus.
.section .text
.globl _start
_start:
  csrr t0, mscratch
  andi t0, t0, 0x3c
  la a0, table
  add a0, a0, t0
  lw t1, 0(a0)
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
2: j 2b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
table: .fill 16, 4, 0
