/* Alternate a short forward branch over a shadowable integer operation. */
.option norvc
.section .text
.global _start
_start:
  li t0, 16
  li t1, 0
  li t2, 0
1:
  xori t1, t1, 1
  beqz t1, 2f
  addi t2, t2, 1
2:
  addi t0, t0, -1
  bnez t0, 1b
  li t3, 8
  bne t2, t3, 3f
  li t4, 1
  j 4f
3:
  li t4, 3
4:
  la t5, tohost
  sd t4, 0(t5)
5:
  j 5b
.section .tohost,"aw",@progbits
.balign 8
.global tohost
tohost:
  .dword 0
