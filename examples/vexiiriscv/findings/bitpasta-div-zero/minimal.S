# Minimal RV32IM bitpasta IPC division-by-zero check.
.section .text
.globl _start
_start:
  li t0, 1
  divu t1, t0, zero
  li t2, -1
  bne t1, t2, fail
  li t1, 1
  j report
fail:
  li t1, 3
report:
  la t0, tohost
  sw t1, 0(t0)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
