.section .text.start
.globl _start
_start:
.option push
.option norelax
  la gp, __global_pointer$
.option pop
  la sp, stack_top
  la t0, freertos_risc_v_trap_handler
  csrw mtvec, t0
  csrw mie, zero
  csrw mstatus, zero
  call main
1: j 1b
.section .bss
.balign 16
.space 4096
stack_top:
