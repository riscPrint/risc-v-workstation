/* A permitted four-byte instruction must reach its denied data store. */
.option norvc
.section .text
.globl _start
_start:
  la t0, trap
  csrw mtvec, t0
  csrw mie, zero
  csrw mideleg, zero
  csrw medeleg, zero
  csrw satp, zero
  la a1, cell
  la t0, payload
  srli t0, t0, 2
  csrw pmpaddr0, t0
#ifdef TOR
  addi t0, t0, 1
  csrw pmpaddr1, t0
  srli t0, a1, 2
  csrw pmpaddr2, t0
  li t0, -1
  csrw pmpaddr3, t0
  li t0, 0x1f100c00
#else
  srli t0, a1, 2
  csrw pmpaddr1, t0
  li t0, -1
  csrw pmpaddr2, t0
  li t0, 0x1f1014
#endif
  csrw pmpcfg0, t0
  sfence.vma
  la t0, payload
  csrw mepc, t0
  li t0, 0x1800
  csrc mstatus, t0
  li t0, 0x800
  csrs mstatus, t0
  mret
.balign 64
payload:
  sd zero, 0(a1)
  j fail
trap:
  csrr t0, mcause
  li t1, 7
  bne t0, t1, fail
  csrr t0, mtval
  bne t0, a1, fail
  li a0, 1
  j finish
fail:
  li a0, 3
finish:
  la t0, tohost
  sd a0, 0(t0)
1: j 1b
.section .tohost,"aw"
.balign 8
.globl tohost, fromhost
tohost: .dword 0
fromhost: .dword 0
.section .data
.balign 64
cell: .dword 0
