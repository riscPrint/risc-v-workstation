# rvw sec case template: machine-mode straight-line case. The adapter replaces the markers.
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
# RVW_DATA
