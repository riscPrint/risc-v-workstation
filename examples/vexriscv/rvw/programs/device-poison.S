.section .text
.globl _start
_start:
  csrw mie, zero
  csrw mstatus, zero
  li s0, 0x10000000
  li s1, 0x0c000000
  li s2, 0x02000000
  li t0, 1
  sb t0, 1(s0)
  li t0, 7
  sw t0, 4(s1)
  li t0, 2
  li t1, 0x2000
  add t1, s1, t1
  sw t0, 0(t1)
  li t1, 0xbff8
  add t1, s2, t1
wait:
  lw t0, 0(t1)
  li t2, 400
  bltu t0, t2, wait
  li t1, 0x200004
  add t1, s1, t1
  lw t0, 0(t1)
  li t2, 1
  bne t0, t2, bad
  # Leave the claim incomplete, RX pending and overrun set.
  sb t2, 2(s0)
  li t0, 99
  sb t0, 7(s0)
  li t0, 80
  sb t0, 0(s0)
  li t0, 128
  sb t0, 3(s0)
  li t0, 42
  sb t0, 0(s0)
  li t0, 1
  sb t0, 1(s0)
  sb zero, 3(s0)
  sw t0, 0(s2)
  li t1, 0x4000
  add t1, s2, t1
  sw zero, 0(t1)
  sw zero, 4(t1)
  la t0, tohost
  li t1, 7
  sw t1, 0(t0)
1: j 1b
bad:
  la t0, tohost
  li t1, 3
  sw t1, 0(t0)
  j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
