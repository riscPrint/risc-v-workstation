.option rvc
.text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  li t0, 0x2004000
  li t1, 600
  sd t1, 0(t0)
  li t0, 0x80
  csrw mie, t0
  li t0, 8
  csrs mstatus, t0
  li t0, 0x10000000
  li t1, 65
  sb t1, 0(t0)
1: wfi
  j 1b
.balign 4
handler:
  li t0, 0x10000000
  li t1, 73
  sb t1, 0(t0)
  li t0, 0x100000
  li t1, 0x5555
  sw t1, 0(t0)
2: j 2b
.data
.dword 0
