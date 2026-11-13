.option norvc
.text
.globl _start
_start:
csrr a0, mhartid
li s0, 0x81000000
li t0, 1
amoadd.d.aqrl t1, t0, (s0)
li t2, 2
bgeu t1, t2, fail
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
