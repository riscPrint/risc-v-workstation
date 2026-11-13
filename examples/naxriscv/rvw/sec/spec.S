# rvw sec speculative self-test template (spec-suite) for NaxRiscv. The adapter replaces the markers.
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
sec_slot: .word 0
sec_public: .word 0x80000000
.balign 64
sec_probe: .fill 512, 4, 0x80000000
# RVW_DATA
