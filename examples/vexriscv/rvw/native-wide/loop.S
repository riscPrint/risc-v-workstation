.section .text
.globl _start
_start:
li t0, 5000
li t1, 0
loop:
addi t1, t1, 3
addi t0, t0, -1
bnez t0, loop
la t0, tohost
li t1, 1
sw t1, 0(t0)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
