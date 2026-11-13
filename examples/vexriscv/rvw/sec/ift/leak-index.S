# Leak: a table lookup indexed by a secret byte changes the data bus address.
.section .text
.globl _start
_start:
  la a0, secret_key
  lw t0, 0(a0)
  andi t0, t0, 0x3c
  la a1, table
  add a1, a1, t0
  lw t1, 0(a1)
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
2: j 2b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
.globl secret_key
secret_key: .word 0x01234567, 0x89abcdef, 0xdeadbeef, 0x0badf00d
table: .fill 16, 4, 0
