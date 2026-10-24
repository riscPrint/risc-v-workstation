// Counts a loop as a region of interest, stores (cycles, instret) to bench_stats like the
// riscv-tests benchmarks do, then passes.
#include "common.h"
  .section .text.init
  .globl _start
_start:
  rdcycle s0
  rdinstret s1
  li t0, 1000
1: addi t0, t0, -1
  bnez t0, 1b
  rdcycle s2
  rdinstret s3
  sub s2, s2, s0
  sub s3, s3, s1
  la t1, bench_stats
  sd s2, 0(t1)
  sd s3, 8(t1)
  li a1, 1
  la t0, tohost
2: sd a1, 0(t0)
  j 2b
  .data
  .align 3
  .globl bench_stats
bench_stats: .dword 0, 0
TOHOST_SECTION
