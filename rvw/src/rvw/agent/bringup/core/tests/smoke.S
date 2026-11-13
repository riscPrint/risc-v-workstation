# Sum 1..10 with a loop, store and load it back, check it, then report through tohost.
.section .text.init
.globl _start
_start:
  li t0, 0
  li t1, 10
1: add t0, t0, t1
  addi t1, t1, -1
  bnez t1, 1b
  la t2, scratch
  sw t0, 0(t2)
  lw t3, 0(t2)
  li t4, 55
  bne t3, t4, fail
  li a0, 1
  j done
fail: li a0, 3
done: la t5, tohost
  sw a0, 0(t5)
2: j 2b
.section .data
scratch: .word 0
.section .tohost,"aw",@progbits
.align 6
.globl tohost
tohost: .dword 0
.globl fromhost
fromhost: .dword 0
