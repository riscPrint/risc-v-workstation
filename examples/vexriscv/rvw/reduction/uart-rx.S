.option norvc
.text
.globl _start
_start:
 li s0,0x10000000
 li t0,1
 sb t0,2(s0)
 li s1,2000
poll:
 lbu t0,5(s0)
 andi t0,t0,1
 beqz t0,next
 lbu t0,0(s0)
 li t1,42
 beq t0,t1,fail
next:
 addi s1,s1,-1
 bnez s1,poll
 li t1,1
 j finish
fail:
 li t1,43
finish:
 la t0,tohost
 sw t1,0(t0)
1: j 1b
.data
.balign 8
.globl tohost
tohost: .dword 0
