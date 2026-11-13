.section .text.start,"ax"
.globl _start
_start:
  li sp, 0x800e0000
  call main
  la t0, tohost
  sw a0, 0(t0)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
