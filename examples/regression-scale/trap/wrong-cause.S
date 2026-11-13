.section .text.init
.globl _start
_start:
  la t0, trap_handler
  csrw mtvec, t0
  ecall
  j failed
.balign 4
trap_handler:
  csrr t0, mcause
  li t1, 3
  bne t0, t1, failed
  li t2, 1
  j finish
failed:
  li t2, 5
finish:
  la t3, tohost
  sw t2, 0(t3)
1: j 1b
.section .tohost,"aw",@progbits
.balign 8
.globl tohost
tohost: .dword 0
.globl fromhost
fromhost: .dword 0
