.option norvc
.section .text
.global _start
_start:
  lui x1, 0x10000
.macro put value
  addi x2,x0,\value
  sw x2,0(x1)
  .rept 70
  addi x0,x0,0
  .endr
.endm
  put 104
  put 101
  put 108
  put 108
  put 111
  put 10
  lui x1,0x10001
  addi x2,x0,1
  sw x2,0(x1)
1: jal x0,1b
