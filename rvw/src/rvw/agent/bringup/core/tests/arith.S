# Self-checking arithmetic. A failed check stores its code in tohost ((n << 1) | 1).
#define CHECK(n, reg, value) li t6, value; li a0, ((n) << 1) | 1; bne reg, t6, fail
.section .text.init
.globl _start
_start:
  li a1, 100
  li a2, 58
  sub a3, a1, a2
  CHECK(2, a3, 42)
  li a1, -7
  li a2, 3
  slt a3, a1, a2
  CHECK(3, a3, 1)
  sltu a3, a1, a2
  CHECK(4, a3, 0)
  li a1, 0xf0
  xori a3, a1, 0xff
  CHECK(5, a3, 0x0f)
  li a1, -64
  srai a3, a1, 3
  CHECK(6, a3, -8)
  li a2, 3
  sra a3, a1, a2
  CHECK(7, a3, -8)
  srl a3, a1, a2
  CHECK(8, a3, 0x1ffffff8)
  li a0, 1
fail: la t5, tohost
  sw a0, 0(t5)
2: j 2b
.section .tohost,"aw",@progbits
.align 6
.globl tohost
tohost: .dword 0
.globl fromhost
fromhost: .dword 0
