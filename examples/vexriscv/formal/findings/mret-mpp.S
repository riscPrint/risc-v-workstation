/* RV32IM machine-only profile: MRET must leave MPP=3. */
.section .text
.global _start
_start:
    la t0, after_mret
    csrw mepc, t0
    mret
after_mret:
    csrr t1, mstatus
    srli t1, t1, 11
    andi t1, t1, 3
    la t0, observed_mpp
    sw t1, 0(t0)
    la t0, tohost
    li t2, 1
    sw t2, 0(t0)
1:  j 1b
.section .data
.balign 8
.global tohost
 tohost: .dword 0
.global fromhost
 fromhost: .dword 0
.global observed_mpp
 observed_mpp: .word 0
