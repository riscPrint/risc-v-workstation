.option norvc
.section .text
.globl _start
_start:
  li t0, 1
  csrw mcycleh, t0
  li t0, -16
  csrw mcycle, t0
  csrw minstreth, zero
  csrw minstret, t0
  li t1, 48
1:
  addi t1, t1, -1
  bnez t1, 1b
  csrw mcycleh, zero
  csrw minstreth, zero
  csrr t0, mcycle
  csrr t1, minstret
  csrr t2, cycle
  csrr t3, instret
  li t0, 1
  la t1, tohost
  sw t0, 0(t1)
2:
  j 2b
.section .data
.balign 8
.globl tohost
 tohost: .dword 0
.globl fromhost
 fromhost: .dword 0
