/* Minimal reset-state difference. This check expects the pinned Ibex value. */
.section .text.init,"ax",@progbits
.globl _start
_start:
  csrr s0,mtvec
  li s1,0x80000001
  li a0,3
  bne s0,s1,1f
  li a0,1
1:
  la t0,tohost
  sw a0,0(t0)
2:
  j 2b
.section .tohost,"aw",@progbits
.balign 8
.globl tohost
tohost: .dword 0
