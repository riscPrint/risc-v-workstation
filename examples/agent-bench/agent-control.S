.section .text.init
.globl _start
_start:
  csrw mscratch, zero
  lui t0, %hi(tohost)
  addi t0, t0, %lo(tohost)
  addi t1, zero, 1
  sw t1, 0(t0)
1: j 1b
.section .tohost,"aw",@progbits
.balign 8
.globl tohost
tohost: .dword 0
.globl fromhost
fromhost: .dword 0
