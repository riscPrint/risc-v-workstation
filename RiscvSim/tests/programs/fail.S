// Reports failure code 3 through tohost: stores (3 << 1) | 1 = 7.
#include "common.h"
  .section .text.init
  .globl _start
_start:
  li a0, 1
  addi a0, a0, 2        // a0 = 3
  slli a1, a0, 1
  ori a1, a1, 1         // a1 = 7
  la t0, tohost
1: sd a1, 0(t0)
  j 1b
TOHOST_SECTION
