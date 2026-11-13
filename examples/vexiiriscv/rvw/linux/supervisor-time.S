.option norvc
.text
.globl _start
_start:
  li t0, -1
  csrw pmpaddr0, t0
  li t0, 0x1f
  csrw pmpcfg0, t0
  li t0, 7
  csrw mcounteren, t0
  csrw mcountinhibit, zero
  la t0, supervisor
  csrw mepc, t0
  li t0, 0x800
  csrw mstatus, t0
  mret
supervisor:
  rdtime t1
  beqz t1, fail
  rdcycle t2
  beqz t2, fail
  rdinstret t3
  beqz t3, fail
  li t4, 84
  j finish
fail:
  li t4, 70
finish:
  li t0, 0x10000000
  sb t4, 0(t0)
  li t0, 0x100000
  li t4, 0x5555
  sw t4, 0(t0)
1: j 1b
.data
.dword 0
