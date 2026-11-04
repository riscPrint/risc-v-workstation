#include <stdint.h>
#include "util.h"
int main(void) {
  volatile uint32_t sum = 0;
  setStats(1);
  for (uint32_t i=0; i<4096; ++i) {
    /* Force a conditional branch rather than conditional arithmetic. */
#if defined(__riscv)
    __asm__ volatile ("andi t0, %1, 1\n\tbnez t0, 1f\n\taddi %0, %0, 1\n1:"
                      : "+r"(sum) : "r"(i) : "t0");
#else
    if (!(i & 1)) ++sum;
#endif
  }
  setStats(0);
  return sum != 2048;
}
