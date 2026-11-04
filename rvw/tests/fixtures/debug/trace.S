.option norvc
.section .text
.global _start
_start:
  li t0, 6
  li t1, 0
loop:
  addi t0, t0, -1
  beq t0, zero, done
  addi t1, t1, 1
  jal zero, loop
done:
  la t2, again
  jalr zero, t2, 0
again:
.option rvc
  c.nop
  j _start
