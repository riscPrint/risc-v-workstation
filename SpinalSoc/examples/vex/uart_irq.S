.option norvc
.section .text
.global _start
_start:
  la t0,handler
  csrw mtvec,t0
  li t0,0x800
  csrw mie,t0
  li t0,8
  csrw mstatus,t0
  li t1,0x10000000
  li t0,2
  sw t0,4(t1)
1: j 1b
handler:
  csrr t0,mcause
  li t2,0x8000000b
  bne t0,t2,fail
  li t1,0x10000000
  lw t0,8(t1)
  li t2,2
  bne t0,t2,fail
  sw zero,4(t1)
  li t0,73
  sw t0,0(t1)
  li t0,1000
2: addi t0,t0,-1
  bnez t0,2b
  li t0,1
  j finish
fail:
  li t0,3
finish:
  li t1,0x10001000
  sw t0,0(t1)
3: j 3b
