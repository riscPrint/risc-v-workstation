# mip reads with and without evidence of an interrupt source (review round 2, finding 1):
# software sets SEIP, then a timer interrupt is taken and its handler returns with mret.
.section .text
.globl _start, mip_site, interrupt_site, handler_mip_site, after_mip_site
_start:
  li t1, 0x200
  csrs mip, t1
mip_site:
  csrr s1, mip            # SEIP written by software: compared strictly
  csrc mip, t1
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
handler_mip_site:
  csrr s1, mip            # MTIP may still be asserted here
  csrw mie, zero
  la t0, after
  csrw mepc, t0
  mret
after:
after_mip_site:
  csrr s3, mip            # after the handler's mret: no evidence left
  la t0, tohost
  li t1, 1
  sd t1, 0(t0)
1: j 1b
.section .data
.globl tohost
.align 3
tohost: .dword 0
