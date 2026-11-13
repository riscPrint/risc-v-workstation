.option norvc
.text
.global _start
_start:
  li a0, 1
  la a1, marker
  li a2, 20
  li a7, 64
  ecall
  # The tty write queues bytes. Drain them before SBI power-off can stop the
  # machine. TCSBRK with a nonzero argument waits without sending a break.
  li a0, 1
  li a1, 0x5409
  li a2, 1
  li a7, 29
  ecall
  bltz a0, 1f
  li a0, 0xfee1dead
  li a1, 672274793
  li a2, 0x4321fedc
  li a3, 0
  li a7, 142
  ecall
1: j 1b
.section .rodata
marker: .ascii "RVW_LINUX_USERSPACE\n"
marker_end:
