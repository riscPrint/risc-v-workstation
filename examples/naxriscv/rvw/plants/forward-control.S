.section .text.init
.globl _start
_start:
  la s0, scratch
  la s1, cold
  li s2, 32
loop:
  lw t3, 0(s1)
  li t0, 7
  sw t0, 0(s0)
  li t0, 9
  sw t0, 0(s0)
  lw t1, 0(s0)
  bne t1, t0, fail
  addi s1, s1, 64
  addi s2, s2, -1
  bnez s2, loop
  li t0, 1
  j done
fail:
  li t0, 3
done:
  la t1, tohost
  sw t0, 0(t1)
1: j 1b
.section .tohost,"aw",@progbits
.balign 8
.globl tohost
tohost: .dword 0
.section .data
.balign 64
scratch: .space 64
cold: .space 2048
