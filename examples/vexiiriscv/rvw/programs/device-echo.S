.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  li s0, 0x10000000
  li s1, 0x0c000000
  li s2, 0x02000000
  li s3, 0
  li s4, 0
  li s5, 0
  li t0, 1
  sb t0, 2(s0)
  sb t0, 1(s0)
  sw t0, 4(s1)
  li t0, 2
  li t1, 0x2000
  add t1, s1, t1
  sw t0, 0(t1)
  li t0, 1
  sw t0, 0(s2)
  li t1, 0x4000
  add t1, s2, t1
  li t0, 400
  sw t0, 0(t1)
  sw zero, 4(t1)
  li t0, 0x888
  csrw mie, t0
  csrsi mstatus, 8
wait:
  li t0, 5
  bne s3, t0, wait
  beqz s4, wait
  beqz s5, wait
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
stop: j stop
.balign 4
handler:
  csrr t0, mcause
  li t1, 0x80000003
  beq t0, t1, software
  li t1, 0x80000007
  beq t0, t1, timer
  li t1, 0x8000000b
  bne t0, t1, fail
  li t1, 0x200004
  add t1, s1, t1
  lw t2, 0(t1)
  li t0, 1
  bne t2, t0, fail
rx:
  lbu t0, 5(s0)
  andi t0, t0, 1
  beqz t0, complete
  lbu t0, 0(s0)
  sb t0, 0(s0)
  addi s3, s3, 1
  j rx
complete:
  sw t2, 0(t1)
  mret
software:
  sw zero, 0(s2)
  addi s4, s4, 1
  mret
timer:
  li t1, 0x4000
  add t1, s2, t1
  li t0, -1
  sw t0, 4(t1)
  addi s5, s5, 1
  mret
fail:
  la t0, tohost
  li t1, 3
  sw t1, 0(t0)
  j stop
.section .data
.balign 8
.globl tohost
tohost: .dword 0
