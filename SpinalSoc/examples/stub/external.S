.option norvc
.section .text
.global _start
_start:
  lui x1,%hi(handler)
  addi x1,x1,%lo(handler)
  csrrw x0,mtvec,x1
  lui x2,0xc000
  addi x3,x0,1
  sw x3,4(x2)
  lui x2,0xc002
  addi x3,x0,2
  sw x3,0(x2)
  lui x1,1
  addi x1,x1,-2048
  csrrw x0,mie,x1
  addi x1,x0,8
  csrrw x0,mstatus,x1
1: jal x0,1b
handler:
  lui x2,0xc200
  lw x3,4(x2)
  sw x3,4(x2)
  lui x1,0x10001
  sw x3,0(x1)
2: jal x0,2b
