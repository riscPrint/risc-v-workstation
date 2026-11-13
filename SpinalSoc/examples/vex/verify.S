.option norvc
.section .text
.global _start
_start:
  # UART scratch and LCR reset. Use a plain scratch register for data checks.
  li t1,0x10000000
  lw t0,12(t1)
  li t2,3
  bne t0,t2,fail
  lw t0,28(t1)
  bnez t0,fail
  li t2,0x5a
  sw t2,28(t1)
  lw t0,28(t1)
  bne t0,t2,fail
  # CLINT software IRQ state. Machine interrupts remain disabled.
  li t1,0x02000000
  lw t0,0(t1)
  bnez t0,fail
  li t2,1
  sw t2,0(t1)
  lw t0,0(t1)
  bne t0,t2,fail
  sw zero,0(t1)
  lw t0,0(t1)
  bnez t0,fail
  # PLIC source priority and enable reset.
  li t1,0x0c000000
  lw t0,4(t1)
  bnez t0,fail
  sw t2,4(t1)
  lw t0,4(t1)
  bne t0,t2,fail
  li t1,0x0c002000
  lw t0,0(t1)
  bnez t0,fail
  # Finisher is initially clear.
  li t1,0x10001000
  lw t0,0(t1)
  bnez t0,fail
  li t0,1
  j finish
fail:
  li t0,3
finish:
  li t1,0x10001000
  sw t0,0(t1)
1: j 1b
