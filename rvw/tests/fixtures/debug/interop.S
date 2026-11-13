# Interoperability fixture: a loop that stores a counter, with a labelled instruction.
.section .text
.global _start
_start:
  la a0, counter
loop:
  lw t0, 0(a0)
  addi t0, t0, 1
  sw t0, 0(a0)
.global target
target:
  addi s1, s1, 1
  j loop
.section .data
.align 3
.global counter
counter: .word 0
.section .tohost,"aw",@progbits
.align 6
.global tohost
 tohost: .dword 0
.global fromhost
 fromhost: .dword 0
