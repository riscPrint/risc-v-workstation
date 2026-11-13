# Constant-time CSR use: mscratch is read and mixed with public data, then stored.
.section .text
.globl _start
_start:
  csrr t0, mscratch
  li t1, 0x5a5a5a5a
  xor t2, t0, t1
  la a0, out
  sw t2, 0(a0)
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
2: j 2b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
out: .word 0
