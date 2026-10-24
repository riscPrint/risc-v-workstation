# A jump outside RAM: the next fetch faults (review round 4). Sail prints no instruction line for
# a fetch fault; the checker must see it as a step of its own, as Spike and RVFI do.
.section .text
.globl _start, jump_site
_start:
  la t0, handler
  csrw mtvec, t0
  li t0, 0x90000000
jump_site:
  jr t0
.align 2
handler:
  csrr a0, mcause
  csrr a1, mtval
  la t0, tohost
  li t1, 1
  sd t1, 0(t0)
1: j 1b
.section .data
.globl tohost
.align 3
tohost: .dword 0
