/* Short integer loop for a whole-trace timing comparison. No trap setup. */
.option norvc
.section .text
.global _start
_start:
  li t0, 16
  li t1, 0
1:
  addi t1, t1, 1
  addi t0, t0, -1
  bnez t0, 1b
  la t2, tohost
  li t3, 1
  sd t3, 0(t2)
2:
  j 2b
.section .tohost,"aw",@progbits
.balign 8
.global tohost
tohost:
  .dword 0
