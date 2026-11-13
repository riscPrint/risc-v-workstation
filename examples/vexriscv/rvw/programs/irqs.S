/* RV32 machine-mode interrupt mix for probe runs with --irq-schedule.
 * Timer (mip bit 7) and external (bit 11) pulses; the handler waits until the
 * level drops, counts the interrupt and returns. Pass after three interrupts.
 * Schedule: --irq-schedule '1:0x0,2000:0x80,2200:0x0,4000:0x800,4200:0x0,6000:0x80,6200:0x0' */
.option norvc
.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  li t0, (1 << 7) | (1 << 11)
  csrw mie, t0
  li s0, 0             /* interrupts taken */
  li s1, 0             /* loop iterations */
  csrsi mstatus, 8
spin:
  addi s1, s1, 1
  li t0, 3
  blt s0, t0, spin
  csrci mstatus, 8
  li t1, 1
  la t0, tohost
  sw t1, 0(t0)
1: j 1b

.balign 4
handler:
  csrr t2, mcause
  li t3, 31
  srl t3, t2, t3
  beqz t3, fail        /* only interrupts are expected */
  andi t2, t2, 0x1f
  li t3, 1
  sll t3, t3, t2       /* the cause's mip bit */
2:
  csrr t4, mip
  and t4, t4, t3
  bnez t4, 2b          /* wait for the scheduled level to drop */
  addi s0, s0, 1
  mret
fail:
  li t1, 3
  la t0, tohost
  sw t1, 0(t0)
3: j 3b

.section .data
.balign 8
.globl tohost
tohost: .dword 0
