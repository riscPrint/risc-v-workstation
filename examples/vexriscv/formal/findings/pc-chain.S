/* Write an odd MEPC, read it back, then return to its aligned target. */
.section .text
.global _start
_start:
    la t0, after_mret
    ori t0, t0, 1
    csrw mepc, t0
    csrr s0, mepc
    mret
after_mret:
    la t0, observed_mepc
    sw s0, 0(t0)
    la t0, tohost
    li t2, 1
    sw t2, 0(t0)
1: j 1b
.section .data
.balign 8
.global tohost
tohost: .dword 0
.global fromhost
fromhost: .dword 0
.global observed_mepc
observed_mepc: .word 0
