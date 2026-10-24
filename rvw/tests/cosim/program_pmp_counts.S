.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  li t0, 0x1234
  csrw pmpaddr7, t0
  csrw pmpaddr8, t0
  csrr a0, pmpaddr7
  csrr a1, pmpaddr8
  li t1, 1
  j finish
.balign 4
handler:
  li t1, 3
finish:
  la t0, tohost
  sd t1, 0(t0)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
