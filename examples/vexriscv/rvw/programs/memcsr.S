/* RV32 loads, stores (word, half, byte) and CSR writes (all six forms, one illegal access)
 * for the bus and CSR-write probes. Pass when the checksum and the trap count match. */
.option norvc
.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  li s2, 0               /* traps taken */
  la s0, buffer
  li s1, 0               /* checksum */
  li t1, 20              /* iterations */
loop:
  sw t1, 0(s0)
  sh t1, 4(s0)
  sb t1, 7(s0)
  lw t2, 0(s0)
  lhu t3, 4(s0)
  lbu t4, 7(s0)
  add s1, s1, t2
  add s1, s1, t3
  add s1, s1, t4
  csrrw t5, mscratch, t1
  csrrs t5, mscratch, t1
  csrrc t5, mscratch, s1
  csrrwi t5, mscratch, 5
  csrrsi t5, mscratch, 3
  csrrci t5, mscratch, 1
  csrrs t5, mscratch, zero   /* reads only: no write */
  addi t1, t1, -1
  bnez t1, loop
  csrw satp, zero            /* not implemented in M-only: illegal, traps */
  li t0, 630                 /* 3 * sum(1..20) */
  bne s1, t0, fail
  li t0, 1
  bne s2, t0, fail
  li t1, 1
  j finish
fail:
  li t1, 3
finish:
  la t0, tohost
  sw t1, 0(t0)
1: j 1b

.balign 4
handler:
  addi s2, s2, 1
  csrr t0, mepc
  addi t0, t0, 4
  csrw mepc, t0
  mret

.section .data
.balign 8
.globl tohost
tohost: .dword 0
buffer: .word 0, 0
