# Constant-time: keystore words and mscratch are mixed and stored to an output buffer.
.section .text
.globl _start
_start:
  li a0, 0x80008000
  la a2, out
  csrr t3, mscratch
  li a3, 4
1:
  lw t0, 0(a0)
  xor t0, t0, t3
  sw t0, 0(a2)
  addi a0, a0, 4
  addi a2, a2, 4
  addi a3, a3, -1
  bnez a3, 1b
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
2: j 2b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
out: .word 0, 0, 0, 0
