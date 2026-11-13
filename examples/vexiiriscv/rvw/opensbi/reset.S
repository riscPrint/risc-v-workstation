.option norvc
.section .text
.globl _start
_start:
  li a0, 0
  li a1, 0x80f00000
  li t0, 0x80200000
  jr t0
.section .tohost,"aw"
.balign 8
.globl tohost
tohost: .dword 0
