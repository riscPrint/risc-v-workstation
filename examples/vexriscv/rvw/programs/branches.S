/* RV32IM branch mix for predictor probes: a pseudo-random branch from an LFSR,
 * a period-4 pattern, a backward loop branch and a call/return per iteration. */
.section .text
.globl _start
_start:
  li s0, 1500          /* iterations */
  li s1, 0xace1        /* 16-bit LFSR state */
  li s2, 0             /* random-branch count */
  li s3, 0             /* period-4 count */
  li s4, 0             /* iteration counter */
loop:
  /* LFSR step: taps 16, 14, 13, 11 */
  srli t0, s1, 0
  srli t1, s1, 2
  xor t0, t0, t1
  srli t1, s1, 3
  xor t0, t0, t1
  srli t1, s1, 5
  xor t0, t0, t1
  andi t0, t0, 1
  srli s1, s1, 1
  slli t0, t0, 15
  or s1, s1, t0
  andi t2, s1, 1
  beqz t2, 1f          /* random direction */
  addi s2, s2, 1
1:
  andi t3, s4, 3
  bnez t3, 2f          /* taken 3 of 4 times */
  addi s3, s3, 1
2:
  mv a0, s4
  call leaf
  addi s4, s4, 1
  addi s0, s0, -1
  bnez s0, loop        /* backward, taken until the end */
  /* checks: the period-4 branch fell through 375 times */
  li t0, 375
  bne s3, t0, fail
  li t1, 1
  j finish
fail:
  li t1, 3
finish:
  la t0, tohost
  sw t1, 0(t0)
3: j 3b

leaf:
  andi a1, a0, 7
  bltu a1, a0, 4f      /* taken except for the first eight calls */
  addi a1, a1, 1
4:
  ret

.section .data
.balign 8
.globl tohost
tohost: .dword 0
