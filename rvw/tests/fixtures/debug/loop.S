.section .text
.global _start
_start:
  addi s0,s0,1
  j _start
.section .tohost,"aw",@progbits
.align 6
.global tohost
 tohost: .dword 0
.global fromhost
 fromhost: .dword 0
