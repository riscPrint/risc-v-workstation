.option norvc
.section .text
.globl _start
_start:
  la t0,handler
  csrw mtvec,t0
  li t0,8
  csrw mie,t0
  csrsi mstatus,8
  li t0,250
loop:
  addi t0,t0,-1
  bnez t0,loop
  li t2,1
  j done
.balign 4
handler:
  li t2,3
done:
  la t0,tohost
  sw t2,0(t0)
1: j 1b
.section .tohost,"aw",@progbits
.balign 8
.globl tohost
tohost:.dword 0
