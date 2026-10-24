# A supervisor software interrupt (SSIP) that software sets in M-mode and the handler reads back
# from mip before it clears it: SSIP is reference state, not a platform input.
.section .text
.globl _start, before_set_site, set_site, mip_site
_start:
  la t0, handler
  csrw mtvec, t0
  li t0, 2
  csrw mie, t0
  csrsi mstatus, 8
before_set_site:
  addi s0, zero, 1
set_site:
  csrs mip, t0
wait:
  j wait
handler:
mip_site:
  csrr s1, mip
  csrci mip, 2
  csrw mie, zero
  la t0, tohost
  li t1, 1
  sd t1, 0(t0)
  j wait
.section .data
.globl tohost
.align 3
tohost: .dword 0
