.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  li a0, 6
  li a1, 7
  mul a2, a0, a1
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
