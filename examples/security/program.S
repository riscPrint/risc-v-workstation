.option norvc
.section .text
.global _start
_start:
  beq x0,x0,1f
  lw x5,0(x1)
1:
  add x3,x1,x2
  ebreak
