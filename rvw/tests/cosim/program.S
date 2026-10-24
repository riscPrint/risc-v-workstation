.section .text
.globl _start, rd_site, branch_site, counter_site, mmio_site, trap_site, interrupt_site, mmio_upper_site, cycle_site, instret_site, hpm_site, time_site, second_instret_site
_start:
  la t0, handler
  csrw mtvec, t0
  li t1, 8
  csrs mstatus, t1
  li t1, 128
  csrw mie, t1
interrupt_site:
  addi s0, zero, 1
rd_site:
  addi a0, zero, 42
branch_site:
  beq s0, s0, target
  addi a0, zero, 99
target:
counter_site:
  csrr s1, mcycle
  addi s2, s1, 1
cycle_site:
  csrr a1, cycle
  addi a2, a1, 1
instret_site:
  csrr a3, instret
hpm_site:
  csrr a4, hpmcounter3
time_site:
  csrr a5, time
second_instret_site:
  csrr a6, instret
  li t0, 0x02000000
mmio_site:
  ld s3, 0(t0)
  addi s4, s3, 1
mmio_upper_site:
  lb s5, 7(t0)
  addi s6, s5, 1
  la t0, data
  li t1, -2
  sd t1, 0(t0)
  sb t1, 3(t0)
  lb t2, 3(t0)
  amoadd.d zero, t1, (t0)
  ld t2, 0(t0)
trap_site:
  ecall
  addi s0, s0, 1
  la t0, tohost
  li t1, 1
  sd t1, 0(t0)
  j .
handler:
  csrr t0, mcause
  bltz t0, irq_ret
  csrr t0, mepc
  addi t0, t0, 4
  csrw mepc, t0
irq_ret:
  mret
.section .data
.balign 8
data: .dword 0
.globl tohost
tohost: .dword 0
