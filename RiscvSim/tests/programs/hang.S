// Never writes tohost: runs into the cycle limit.
#include "common.h"
  .section .text.init
  .globl _start
_start:
  li a0, 0
1: addi a0, a0, 1
  j 1b
TOHOST_SECTION
