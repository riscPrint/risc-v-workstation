# A timer interrupt whose source stays asserted while the handler reads mip
# (as on BOOM, where mtip follows mtime >= mtimecmp until software moves mtimecmp).
.section .text
.globl _start, interrupt_site, mip_site
_start:
  la t0, handler
  csrw mtvec, t0
  li t1, 128
  csrw mie, t1
  li t1, 8
  csrs mstatus, t1
interrupt_site:
  addi s0, zero, 1
  j interrupt_site
handler:
mip_site:
  csrr s1, mip
  addi s2, s1, 1
  la t0, tohost
  li t1, 1
  sd t1, 0(t0)
1: j 1b
.section .data
.globl tohost
.align 3
tohost: .dword 0
