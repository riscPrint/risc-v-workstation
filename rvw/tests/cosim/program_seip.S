# Software sets SSIP and SEIP in mip with interrupts disabled; then an interrupt is injected for one step.
# The input going away must leave the software-set bit pending.
.section .text
.globl _start, inject_site, read_site, cleared_site
_start:
  li t0, 0x202
  csrs mip, t0
inject_site:
  addi s0, zero, 1
read_site:
  csrr s1, mip
  csrc mip, t0
cleared_site:
  csrr s2, mip
  la t0, tohost
  li t1, 1
  sd t1, 0(t0)
1: j 1b
.section .data
.globl tohost
.align 3
tohost: .dword 0
