# Constant-time: secret key words are loaded, mixed with public data and stored.
.section .text
.globl _start
_start:
  la a0, secret_key
  la a1, plaintext
  la a2, ciphertext
  li a3, 4
1:
  lw t0, 0(a0)
  lw t1, 0(a1)
  xor t2, t0, t1
  add t2, t2, t1
  sw t2, 0(a2)
  addi a0, a0, 4
  addi a1, a1, 4
  addi a2, a2, 4
  addi a3, a3, -1
  bnez a3, 1b
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
plaintext: .word 1, 2, 3, 4
ciphertext: .word 0, 0, 0, 0
