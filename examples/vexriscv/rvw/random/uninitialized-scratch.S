.section .text.init,"ax"
.globl _start
_start:
  li t0, 1
  la t1, tohost
  sw t0, 0(t1)
1: j 1b
.section .tohost,"aw"
.balign 8
.globl tohost
tohost: .dword 0
