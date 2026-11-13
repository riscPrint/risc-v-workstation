.option norvc
.text
.globl _start
_start:
csrr a0, mhartid
li s0, 0x80080000
bnez a0, receiver
li t0, 37
sd t0, 0(s0)
fence rw, rw
li t0, 1
sd t0, 128(s0)
wait_ack:
ld t0, 136(s0)
li t1, 2
bne t0, t1, wait_ack
fence rw, rw
ld t0, 0(s0)
li t1, 85
bne t0, t1, fail
j pass
receiver:
ld t0, 128(s0)
li t1, 1
bne t0, t1, receiver
fence rw, rw
ld t0, 0(s0)
li t1, 37
bne t0, t1, fail
li t0, 85
sd t0, 0(s0)
fence rw, rw
li t0, 2
sd t0, 136(s0)
pass:
li a1, 1
j finish
fail:
li a1, 3
finish:
la t0, tohost
slli t1, a0, 3
add t0, t0, t1
sd a1, 0(t0)
park: j park
.section .tohost,"aw",@progbits
.balign 64
.globl tohost
tohost: .zero 16
.section .shared,"aw",@nobits
.zero 256
