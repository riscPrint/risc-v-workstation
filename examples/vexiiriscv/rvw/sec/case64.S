.option norvc
.section .text
.globl _start
_start:
# RVW_SETUP
.globl case
case:
  nop
# RVW_PROGRAM
.globl case_end
case_end:
  nop
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
# RVW_DATA
