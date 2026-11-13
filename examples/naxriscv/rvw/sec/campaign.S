# rvw sec campaign template: x30 is a public buffer, x5/x28/x29 public values. The adapter replaces the markers.
.section .text
.globl _start
_start:
# RVW_SETUP
  la x30, sec_buf
  li x5, 1
  li x28, 2
  li x29, -3
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
sec_buf: .fill 32, 4, 0x01020304
# RVW_DATA
