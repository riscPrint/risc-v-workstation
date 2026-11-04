.option norvc
.section .text.init
.globl _start, wait_start, wait_end, handler, tohost
_start:
  csrw mstatus, zero
  csrw mtval, zero
  csrw mepc, zero
  la t0, handler
  csrw mtvec, t0
  li t0, (1 << IRQ_CODE)
  csrw mie, t0
  li s0, 0
#if PRIV != 3
  la t0, wait_start
  csrw mepc, t0
  li t0, ((PRIV << 11) | (TW << 21))
  csrw mstatus, t0
  mret
#else
 #ifndef MASK_GLOBAL
  csrsi mstatus, 8
 #endif
#endif
wait_start:
  wfi
  addi s0, s0, 1
  j wait_start
wait_end:
.balign 4
handler:
  li t1, 1
  la t0, tohost
  sw t1, 0(t0)
1: j 1b
.section .tohost,"aw",@progbits
.balign 8
tohost: .dword 0
