# Isolation case U <-> S on VexiiRiscv rv32imasu with Sv32 on. The secret is in sscratch.
# U-mode ecalls are delegated to the S-mode handler, which runs from a supervisor-only page.
# Public a0 selects the handler: 0 constant time, else a secret-dependent loop (control).
.section .text
.globl _start
_start:
  la t0, mfail
  csrw mtvec, t0
  la t0, shandler
  csrw stvec, t0
  li t0, 0x100
  csrw medeleg, t0
  # Sv32: root[512] points to pt_l0; pt_l0[i] maps the 4 KiB page 0x80000000 + i*4096
  # (16 pages). Flags: 0xdf, except the supervisor page (0xcf). A and D are set.
  la t0, pt_l0
  srli t1, t0, 12
  slli t1, t1, 10
  ori t1, t1, 1
  la t2, pt_root
  li t3, 2048
  add t2, t2, t3
  sw t1, 0(t2)
  la t6, super_page
  srli t6, t6, 12
  li t1, 0x80000
  li t3, 0x80010
3:
  slli t2, t1, 10
  ori t2, t2, 0xdf
  bne t1, t6, 4f
  slli t2, t1, 10
  ori t2, t2, 0xcf
4:
  sw t2, 0(t0)
  addi t0, t0, 4
  addi t1, t1, 1
  bltu t1, t3, 3b
  la t0, pt_root
  srli t0, t0, 12
  li t1, 0x80000000
  or t0, t0, t1
  csrw satp, t0
  sfence.vma
# RVW_SETUP
  csrw sscratch, t0
  li t0, 0
  li t1, 0x1800
  csrc mstatus, t1
  la t1, user
  csrw mepc, t1
  li t1, 0
  mret
.balign 256
user:
# RVW_PROGRAM
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
1: j 1b
# Any trap the case does not expect ends the run with tohost = 3.
mfail:
  la t0, tohost
  li t1, 3
  sw t1, 0(t0)
5: j 5b
.balign 4096
super_page:
shandler:
  csrr t6, scause
  li t5, 8
  bne t6, t5, sfail
  csrrw t3, sscratch, t3
  beqz a0, 6f
  andi t4, t3, 15
2:
  addi t4, t4, -1
  bgez t4, 2b
  j 7f
6:
  xor t4, t3, a1
  or t4, t4, t3
  and t4, t4, a1
7:
  csrrw t3, sscratch, t3
  li t4, 0
  li t5, 0
  csrr t6, sepc
  addi t6, t6, 4
  csrw sepc, t6
  li t6, 0
  sret
sfail:
  ecall
.section .data
.balign 4096
pt_root: .fill 1024, 4, 0
pt_l0: .fill 1024, 4, 0
.balign 4096
.globl page_a
page_a: .fill 1024, 4, 0x11111111
.globl page_b
page_b: .fill 1024, 4, 0x22222222
.balign 8
.globl tohost
tohost: .dword 0
# RVW_DATA
