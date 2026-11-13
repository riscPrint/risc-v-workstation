# Self-checking branches. A failed check stores its code in tohost ((n << 1) | 1).
.section .text.init
.globl _start
_start:
  li a1, -1
  li a2, 1
  li a0, 5
  blt a2, a1, fail      # 1 < -1 is false (signed)
  blt a1, a2, 1f
  j fail
1: li a0, 7
  bltu a1, a2, fail     # 0xffffffff < 1 is false (unsigned)
  bltu a2, a1, 1f
  j fail
1: li a0, 9
  bge a1, a2, fail
  bgeu a2, a1, fail
  bgeu a1, a2, 1f
  j fail
1: li a0, 11
  jal ra, sub1
  li t6, 77
  bne a3, t6, fail
  li a0, 1
fail: la t5, tohost
  sw a0, 0(t5)
2: j 2b
sub1: li a3, 77
  jalr zero, 0(ra)
.section .tohost,"aw",@progbits
.align 6
.globl tohost
tohost: .dword 0
.globl fromhost
fromhost: .dword 0
