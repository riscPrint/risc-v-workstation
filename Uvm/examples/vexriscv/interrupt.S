.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  li t0, 0x888
  csrw mie, t0
  li t0, 8
  csrs mstatus, t0
  li s0, 0
  li s1, 8
  li s2, 100000
loop:
  addi s2, s2, -1
  beqz s2, failed
  blt s0, s1, loop
  csrw mie, zero
  li t0, 1
  la t1, tohost
  sw t0, 0(t1)
  j .
failed:
  li t0, 3
  la t1, tohost
  sw t0, 0(t1)
  j .
.balign 4
handler:
  addi s0, s0, 1
  mret
.section .tohost,"aw",@progbits
.balign 64
.globl tohost
tohost: .dword 0
