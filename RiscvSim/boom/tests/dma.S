.option norvc
.section .text
.globl _start
_start:
 la t0, fail
 csrw mtvec, t0
 la s0, shared
 li t1, 37
 sw t1, 0(s0)
 fence iorw, iorw
 li s1, 0x0c000100
 li t1, 1
 sw t1, 0(s1)
 li t1, 10
1: lw t2, 8(s1)
 bne t2, t1, 1b
 fence i, rw
 lw t2, 0(s0)
 sw t2, 16(s1)
 fence iorw, iorw
 sw t1, 0(s1)
 li t1, 1
6: lw t2, 8(s1)
 bne t2, t1, 6b
 fence i, rw
 lw t2, 0(s0)
 li t3, 73
 bne t2, t3, fail
 li t3, 5
 amoadd.w.aqrl t2, t3, (s0)
 li t3, 73
 bne t2, t3, fail
 fence iorw, iorw
 li t1, 2
 sw t1, 0(s1)
2: lw t2, 8(s1)
 bne t2, t1, 2b
 fence i, rw
 lw t2, 0(s0)
 li t3, 0x1234
 bne t2, t3, fail
 li t1, 3
 sw t1, 0(s1)
4: lw t2, 8(s1)
 bne t2, t1, 4b
 fence i, rw
 li t3, 5
 amoadd.w.aqrl t2, t3, (s0)
 sw t2, 16(s1)
 fence iorw, iorw
 li t1, 4
 sw t1, 0(s1)
5: lw t2, 8(s1)
 bne t2, t1, 5b
 fence i, rw
 li a0, 1
 j finish
fail:
 li a0, 3
finish:
 la t0, tohost
 sd a0, 0(t0)
3: j 3b
.section .tohost,"aw"
.balign 64
.globl tohost
tohost: .dword 0
.section .data
.balign 64
.globl shared
shared: .space 64
