.option norvc
.section .text
.global _start
_start:
  li t0,0x80001080
  li t1,0x600dffff
wait_dma:
  lw t2,0(t0)
  bne t2,t1,wait_dma
  li t0,0x80001000
  li t1,0x600d0000
  li t3,32
check:
  lw t2,0(t0)
  bne t2,t1,fail
  addi t0,t0,4
  addi t1,t1,1
  addi t3,t3,-1
  bnez t3,check
  li t0,1
  j finish
fail:
  li t0,3
finish:
  li t1,0x10001000
  sw t0,0(t1)
1:j 1b
