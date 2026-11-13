.option norvc
.section .text
.globl _start
_start:
  li a0,0
.globl fault_region
.type fault_region,@function
fault_region:
  addi a1,zero,7
  addi a2,zero,8
  addi a3,zero,9
  addi a0,a0,1
  addi a4,zero,10
  addi a5,zero,11
  addi a6,zero,12
  addi a7,zero,13
.size fault_region,.-fault_region
  li t2,1
  beq a0,zero,done
  li t2,3
done:
  la t0,tohost
  sw t2,0(t0)
1: j 1b
.section .tohost,"aw",@progbits
.balign 8
.globl tohost
tohost:.dword 0
