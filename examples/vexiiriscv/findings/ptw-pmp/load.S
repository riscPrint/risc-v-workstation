.option norvc
.section .text
.globl _start
_start:
 la t0, trap
 csrw mtvec, t0
 csrw mie, zero
 csrw medeleg, zero
 csrw mideleg, zero
 # Allow below the tables, deny the tables, allow the remaining RAM.
 li t0, 0x80010000 >> 2
 csrw pmpaddr0, t0
 li t0, 0x80013000 >> 2
 csrw pmpaddr1, t0
 li t0, -1
 csrw pmpaddr2, t0
 li t0, 0x0f080f
 csrw pmpcfg0, t0
 li t0, 0x8000000000080010
 csrw satp, t0
 sfence.vma x0, x0
 li t0, 0xe1800
 csrc mstatus, t0
 li t0, 0x20800
 csrs mstatus, t0
 li t3, 0x40000000
access:
 ld a0, 0(t3)
 # A completed load is a failure. No PTE read is permitted by PMP.
 j fail
trap:
 li t0, 0x20000
 csrc mstatus, t0
 csrr t0, mcause
 li t1, 5
 bne t0, t1, fail
 csrr t0, mtval
 li t1, 0x40000000
 bne t0, t1, fail
 csrr t0, mepc
 la t1, access
 bne t0, t1, fail
 li t1, 1
 j finish
fail:
 li t1, 3
finish:
 li t0, 0x20000
 csrc mstatus, t0
 la t0, tohost
 sd t1, 0(t0)
1: j 1b
.section .tohost,"aw"
.balign 8
.globl tohost
tohost: .dword 0
.globl fromhost
fromhost: .dword 0
.section .tables,"aw"
.dword 0
.dword ((0x80011000 >> 12) << 10) | 1
.zero 4096-16
.dword ((0x80012000 >> 12) << 10) | 1
.zero 4096-8
.dword ((0x80200000 >> 12) << 10) | 0xc7
.zero 4096-8
.section .data
.dword 42
