.section .text
.global _start
_start:
  la t0, handler
  csrw mtvec, t0
  li t0, 0x600
  csrs mstatus, t0
  vsetivli t1, 4, e32, m1, tu, mu
  vmv.v.i v1, 3
  vmv.v.i v2, 5
  vadd.vv v3, v1, v2
  vmseq.vi v0, v1, 3
  vadd.vi v3, v3, 1, v0.t
  li t0, 1
  csrw vstart, t0
  vadd.vi v3, v3, 1
  wfi

handler:
  csrw vstart, zero
  wfi
