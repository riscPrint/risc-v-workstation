.option norvc
.text
.globl _start
_start:
csrr a0, mhartid
li s0, 0x81000000
li s1, 128
li s2, 0
loop:
li t0, 1
amoadd.d.aqrl t1, t0, (s0)
li t2, 256
bgeu t1, t2, fail
addi s2, s2, 3
xor t3, s2, t1
slli t3, t3, 1
srli t3, t3, 1
addi s1, s1, -1
bnez s1, loop
li t2, 384
bne s2, t2, fail
addi s3, s0, 8
li t0, 1
amoadd.d.aqrl zero, t0, (s3)
barrier:
ld t1, 0(s3)
li t2, 2
bne t1, t2, barrier
fence rw, rw
ld t1, 0(s0)
li t2, 256
bne t1, t2, fail
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
.zero 64
