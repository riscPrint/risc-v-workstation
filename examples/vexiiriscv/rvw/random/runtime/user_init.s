# Initialize architectural inputs before upstream pygen setup.
# Define scratch state before the first per-retirement CSR snapshot.
csrw mscratch, zero
.ifdef RVW_TRAP_SKIP
# Trap class only: resume after each trapping 32-bit instruction.
# The generator emits no CSR instructions in this class, so mscratch is free.
la t0, rvw_trap_skip
csrw mtvec, t0
j rvw_trap_skip_end
.balign 4
rvw_trap_skip:
csrrw t0, mscratch, t0
csrr t0, mepc
addi t0, t0, 4
csrw mepc, t0
csrrw t0, mscratch, t0
mret
rvw_trap_skip_end:
.endif
li x1, 0
li x2, 0
li x3, 0
li x4, 0
li x5, 0
li x6, 0
li x7, 0
li x8, 0
li x9, 0
li x10, 0
li x11, 0
li x12, 0
li x13, 0
li x14, 0
li x15, 0
li x16, 0
li x17, 0
li x18, 0
li x19, 0
li x20, 0
li x21, 0
li x22, 0
li x23, 0
li x24, 0
li x25, 0
li x26, 0
li x27, 0
li x28, 0
li x29, 0
li x30, 0
li x31, 0
