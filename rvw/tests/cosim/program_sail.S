# Sail as second reference on BOOM-style traces (review round 2, finding 3): compressed
# loads/stores (virtual address from rs1 + offset), a misaligned load that traps on BOOM,
# and a supervisor software interrupt that Sail takes itself.
.section .text
.globl _start, misaligned_site, interrupt_site, done_site
.option norvc
_start:
  la t0, handler
  csrw mtvec, t0
  la s0, data
  addi sp, s0, 32
.option rvc
  c.ld a1, 8(s0)
  c.lw a2, 4(s0)
  c.sd a1, 16(s0)
  c.sw a2, 28(s0)
  c.ldsp a3, 8(sp)
  c.lwsp a4, 12(sp)
  c.sdsp a3, 40(sp)
  c.swsp a4, 52(sp)
.option norvc
misaligned_site:
  ld a5, 9(s0)
  li t1, 2
  csrw mie, t1
  csrsi mstatus, 8
interrupt_site:
  csrsi mip, 2
done_site:
  la t0, tohost
  li t1, 1
  sd t1, 0(t0)
1: j 1b
handler:
  csrr t3, mcause
  bltz t3, 2f
  csrr t4, mepc
  addi t4, t4, 4
  csrw mepc, t4
  mret
2:
  csrci mip, 2
  csrw mie, zero
  mret
.section .data
.globl tohost
.align 3
tohost: .dword 0
.align 6
data:
  .dword 0x1111222233334444, 0x5555666677778888, 0, 0
  .dword 0x99990000aaaabbbb, 0xccccddddeeeeffff, 0, 0
