# Directed state comparison. Includes CSR and branch effects before a stable loop.
.section .text
.global _start
_start:
  li x31, 0x123
  csrw mscratch, x31
  csrr x30, mscratch
  addi x29, x30, -1
  xor x28, x29, x31
  addi x27, x0, 2
1:
  addi x27, x27, -1
  bne x27, x0, 1b
  csrrw x26, mscratch, x29
  csrr x25, mscratch
2:
  addi x24, x24, 1
  j 2b
.section .tohost,"aw",@progbits
.align 6
.global tohost
tohost: .dword 0
.global fromhost
fromhost: .dword 0
