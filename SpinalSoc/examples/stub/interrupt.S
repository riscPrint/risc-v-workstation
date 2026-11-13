.option norvc
.section .text
.global _start
_start:
  lui x1,%hi(handler)
  addi x1,x1,%lo(handler)
  csrrw x0,mtvec,x1
  addi x1,x0,128
  csrrw x0,mie,x1
  lui x2,0x2004
  sw x0,4(x2)
  addi x3,x0,100
  sw x3,0(x2)
  addi x1,x0,8
  csrrw x0,mstatus,x1
1: jal x0,1b
handler:
  addi x3,x0,-1
  sw x3,4(x2)
  lui x1,0x10001
  addi x2,x0,1
  sw x2,0(x1)
2: jal x0,2b
