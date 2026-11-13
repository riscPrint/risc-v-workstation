# Self-checking byte and halfword loads and stores.
#define CHECK(n, reg, value) li t6, value; li a0, ((n) << 1) | 1; bne reg, t6, fail
.section .text.init
.globl _start
_start:
  la a1, data
  lb a2, 0(a1)
  CHECK(2, a2, -128)
  lbu a2, 0(a1)
  CHECK(3, a2, 0x80)
  lh a2, 2(a1)
  CHECK(4, a2, -2)
  lhu a2, 2(a1)
  CHECK(5, a2, 0xfffe)
  li a3, 0x1234
  sh a3, 4(a1)
  lw a2, 4(a1)
  CHECK(6, a2, 0x55551234)
  li a3, 0x77
  sb a3, 7(a1)
  lw a2, 4(a1)
  CHECK(7, a2, 0x77551234)
  li a0, 1
fail: la t5, tohost
  sw a0, 0(t5)
2: j 2b
.section .data
.align 2
data: .word 0xfffe1180
      .word 0x55555555
.section .tohost,"aw",@progbits
.align 6
.globl tohost
tohost: .dword 0
.globl fromhost
fromhost: .dword 0
