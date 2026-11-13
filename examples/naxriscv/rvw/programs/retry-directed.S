.section .text
.globl _start
_start:
  la s0, scratch
  lw s1, 0(s0)
  fence
  li t0, 100
  li t1, 10
  div t2, t0, t1
  addi t2, t2, -10
  add t3, s0, t2
  sw t0, 0(t3)
  lw s2, 0(s0)
  fence
  sb t1, 0(s0)
  lw s3, 0(s0)
  fence
  la t0, root
  li t1, 0x200000cf
  sw t1, 2048-4(t0)
  addi t0, t0, 4
  sw t1, 2044(t0)
  addi t0, t0, -4
  srli t0, t0, 12
  li t1, 0x80000000
  or t0, t0, t1
  csrw satp, t0
  sfence.vma
  li t0, 0x20800
  csrw mstatus, t0
  lw s4, 0(s0)
  csrw mstatus, zero
  csrw satp, zero
  sfence.vma
  li t0, 1
  la t1, tohost
  sw t0, 0(t1)
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
scratch: .word 0
.balign 4096
root: .space 4096
