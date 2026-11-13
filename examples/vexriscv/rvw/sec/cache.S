# rvw sec case template for cache runs: like case.S, plus a 64-byte table that spans two
# 32-byte cache lines. The adapter replaces the markers.
.section .text
.globl _start
_start:
# RVW_SETUP
case:
# RVW_PROGRAM
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
.balign 64
.globl table
table: .fill 16, 4, 0x5a5a5a5a
# RVW_DATA
