.option norvc
.equ HSM, 0x48534d
.text
.globl _start
_start:
csrr s0, mhartid
li gp, 0x81000000
li sp, 0x81100000
slli t0, s0, 12
add sp, sp, t0
la t0, machine_trap
csrw mtvec, t0
li t0, 8
csrw mie, t0
csrs mstatus, t0
bnez s0, park_secondary
la t0, supervisor0
j enter_supervisor

# M-mode park is an SBI software state, not clock or power gating.
.globl park_secondary
park_secondary:
nop
ld t0, 0(gp)
li t1, 2
beq t0, t1, start_secondary
wfi
j park_secondary
start_secondary:
li t0, 0x02000004
sw zero, 0(t0)
ld t0, 8(gp)
ld a1, 16(gp)
li a0, 1
sd zero, 0(gp)
enter_supervisor:
csrw mepc, t0
li t0, 0x1800
csrc mstatus, t0
li t0, 0x880
csrs mstatus, t0
mret

supervisor0:
li a7, HSM
li a6, 0
li a0, 1
la a1, supervisor1
li a2, 0x55
ecall
bnez a0, fail
wait_stopped:
li a7, HSM
li a6, 2
li a0, 1
ecall
bnez a0, fail
li t0, 1
bne a1, t0, wait_stopped
ld t0, 24(gp)
li t1, 1
bne t0, t1, fail
li a7, HSM
li a6, 0
li a0, 1
la a1, supervisor1
li a2, 0x66
ecall
bnez a0, fail
wait_second:
ld t0, 24(gp)
li t1, 2
bne t0, t1, wait_second
j pass

.globl supervisor1
supervisor1:
li t0, 1
bne a0, t0, fail
li t0, 0x55
beq a1, t0, first_start
li t0, 0x66
bne a1, t0, fail
li t0, 2
sd t0, 24(gp)
j pass
first_start:
li t0, 1
sd t0, 24(gp)
li a7, HSM
li a6, 1
ecall
j fail # Successful SBI hart_stop must not return here.

.balign 4
machine_trap:
addi sp, sp, -64
sd t0, 0(sp)
sd t1, 8(sp)
sd t2, 16(sp)
sd t3, 24(sp)
sd t4, 32(sp)
sd t5, 40(sp)
sd t6, 48(sp)
csrr t0, mcause
li t1, 0x8000000000000003
beq t0, t1, software_irq
li t1, 9
bne t0, t1, fail
li t0, HSM
bne a7, t0, fail
beqz a6, hart_start
li t0, 1
beq a6, t0, hart_stop
li t0, 2
bne a6, t0, fail
li t0, 1
bne a0, t0, fail
ld a1, 0(gp)
li a0, 0
j return_ecall
hart_start:
csrr t0, mhartid
bnez t0, fail
li t0, 1
bne a0, t0, fail
ld t1, 0(gp)
bne t1, t0, fail
.globl hsm_start_request
hsm_start_request:
sd a1, 8(gp)
sd a2, 16(gp)
li t0, 2
sd t0, 0(gp)
fence rw,rw
li t0, 0x02000004
li t1, 1
sw t1, 0(t0)
li a0, 0
li a1, 0
j return_ecall
hart_stop:
csrr t0, mhartid
li t1, 1
bne t0, t1, fail
.globl hsm_stop_request
hsm_stop_request:
li t0, 3
sd t0, 0(gp)
la t0, park_secondary
csrw mepc, t0
li t0, 0x1880
csrs mstatus, t0
li t0, 1
.globl hsm_stopped
hsm_stopped:
sd t0, 0(gp)
j restore
software_irq:
li t0, 0x02000004
sw zero, 0(t0)
j restore
return_ecall:
csrr t0, mepc
addi t0, t0, 4
csrw mepc, t0
restore:
ld t0, 0(sp)
ld t1, 8(sp)
ld t2, 16(sp)
ld t3, 24(sp)
ld t4, 32(sp)
ld t5, 40(sp)
ld t6, 48(sp)
addi sp, sp, 64
mret
pass:
li a1, 1
j finish
fail:
li a1, 3
finish:
mv a0, s0
la t0, tohost
slli t1, a0, 3
add t0, t0, t1
sd a1, 0(t0)
finished: j finished
.section .tohost,"aw",@progbits
.balign 64
.globl tohost
tohost: .zero 16
.section .shared,"aw",@progbits
.dword 1, 0, 0, 0
