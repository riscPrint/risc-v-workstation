.section .text.boot,"ax",@progbits
.option norvc
.globl _boot
_boot:
  j _start
