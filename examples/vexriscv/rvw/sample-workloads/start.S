.section .text.start,"ax"
.globl _start
_start:
  /* Define every GPR before a C prologue can save it. */
  .irp reg,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31
    addi x\reg, x0, 0
  .endr
  li sp, 0x800e0000
  call main
  la t0, tohost
  sw a0, 0(t0)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
