.option norvc
.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  li t0, 0x1234
  csrw sscratch, t0
  csrr t1, sscratch
  bne t0, t1, handler
  li t2, 1
  j done
.balign 4
handler:
  li t2, 3
done:
  la t0, tohost
  sw t2, 0(t0)
1: j 1b
.section .tohost,"aw",@progbits
.balign 8
.globl tohost
tohost: .dword 0
