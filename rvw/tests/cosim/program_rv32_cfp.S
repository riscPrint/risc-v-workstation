# RV32 compressed FP loads and stores (review round 12): on RV32, compressed funct3 3 and 7 are
# c.flw/c.fsw and c.flwsp/c.fswsp (word offsets), not c.ld/c.sd (doubleword offsets, RV64 only).
# Sail logs physical addresses, so a wrongly decoded offset makes the Sail model's address differ
# from the core's. (An RV32 c.fld/c.fsd moves 8 bytes, wider than one C2 word: the checker refuses it.)
.section .text
.globl _start
_start:
  li t0, 0x2000
  csrs mstatus, t0          # FS = initial: FP instructions allowed
  la a0, data
  addi sp, a0, 32
  c.flw fa0, 4(a0)
  c.fsw fa0, 12(a0)
  c.flwsp fa1, 4(sp)
  c.fswsp fa1, 20(sp)
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
1: j 1b
.section .data
.align 3
data:
  .word 0x11111111, 0x3f800000, 0x22222222, 0x33333333
  .word 0x44444444, 0x55555555, 0x66666666, 0x77777777
  .word 0x88888888, 0x40000000, 0x99999999, 0xaaaaaaaa
  .word 0xbbbbbbbb, 0xcccccccc, 0xdddddddd, 0xeeeeeeee
.globl tohost
tohost: .dword 0
