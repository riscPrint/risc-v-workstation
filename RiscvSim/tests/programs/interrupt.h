/* Fixed instruction regions give an independent interrupt boundary oracle. */
#include "common.h"
.option norvc
.section .text.init
.globl _start, irq_wait, irq_wait_end, irq_handler
_start:
  /* Define writable status fields before testing interrupt entry. */
  csrw mstatus, zero
  li s0, 0
  la t0, irq_handler
#ifdef DELEGATED
  csrw stvec, t0
  csrw stval, zero
 #ifndef NO_PMP
  li t0, -1
  csrw pmpaddr0, t0
  li t0, 15
  csrw pmpcfg0, t0
 #endif
  li t0, (1 << IRQ_CODE)
  csrw mideleg, t0
#else
  csrw mtvec, t0
  csrw mtval, zero
#endif
  li t0, (1 << IRQ_CODE)
  csrw mie, t0
  /* Input can be pending here, but global enable stays low. */
  li t2, 1000
1: addi t2, t2, -1
  bnez t2, 1b
#ifdef DELEGATED
  la t0, irq_wait
  csrw mepc, t0
  li t0, 0x802 /* MPP=S, SIE=1 */
  csrw mstatus, t0
  mret
#else
  csrsi mstatus, 8
#endif
irq_wait:
  addi s0, s0, 1
  j irq_wait
irq_wait_end:
.balign 4
irq_handler:
#ifdef DELEGATED
  csrr s1, scause
  csrr s2, sepc
  csrr s3, sstatus
#else
  csrr s1, mcause
  csrr s2, mepc
  csrr s3, mstatus
#endif
  li t0, 1
  slli t0, t0, (__riscv_xlen - 1)
  ori t0, t0, IRQ_CODE
  bne s1, t0, fail
  la t0, irq_wait
  bltu s2, t0, fail
  la t0, irq_wait_end
  bgeu s2, t0, fail
  /* Interrupt entry clears the current privilege's global enable. */
#ifdef DELEGATED
  andi t0, s3, 2
#else
  andi t0, s3, 8
#endif
  bnez t0, fail
  li t1, 1
  j finish
fail:
  li t1, 3
finish:
  la t0, tohost
 #if __riscv_xlen == 64
  sd t1, 0(t0)
 #else
  sw t1, 0(t0)
 #endif
2: j 2b
TOHOST_SECTION
