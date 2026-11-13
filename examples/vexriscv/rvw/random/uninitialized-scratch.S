.section .text.init,"ax"
.globl _start
.type _start, @function
_start:
  li t0, 1
  la t1, tohost
  sw t0, 0(t1)
1: j 1b
.size _start, .-_start
.section .tohost,"aw"
.balign 8
.globl tohost
tohost: .dword 0
