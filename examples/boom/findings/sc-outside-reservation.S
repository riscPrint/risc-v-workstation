/* BOOM's 64-byte reservation excludes the SC target. Failure is expected. */
.option norvc
.section .text
.globl _start
_start:
  la t0, cells
  addi t1, t0, 64
  li t3, 101
1:
#ifdef WORD
  lr.w zero, (t0)
  sc.w t2, zero, (t1)
#else
  lr.d zero, (t0)
  sc.d t2, zero, (t1)
#endif
  beqz t2, fail
  addi t3, t3, -1
  bnez t3, 1b
  li a0, 1
  j finish
fail:
  li a0, 3
finish:
  la t0, tohost
  sd a0, 0(t0)
2: j 2b
.section .tohost,"aw"
.balign 8
.globl tohost, fromhost
tohost: .dword 0
fromhost: .dword 0
.section .data
.balign 64
cells: .zero 128
