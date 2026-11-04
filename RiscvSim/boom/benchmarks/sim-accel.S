.section .text.init
.globl _start
_start:
  la t1, scratch
  li t0, 100000
  li t2, 0
1:
  sd t2, 0(t1)
  ld t3, 0(t1)
  bne t2, t3, fail
  addi t2, t2, 1
  addi t0, t0, -1
  bnez t0, 1b
  li a0, 1
  j done
fail:
  li a0, 3
done:
  la t1, tohost
  sd a0, 0(t1)
2: j 2b
.section .data
.balign 8
scratch: .dword 0
.section .tohost,"aw",@progbits
.balign 64
.globl tohost
tohost: .dword 0
.globl fromhost
fromhost: .dword 0
