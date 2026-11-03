#include <stdint.h>
#include "util.h"
int main(void) {
  uintptr_t value = 1;
  setStats(1);
  for (unsigned i=0; i<4096; ++i) {
#if defined(__riscv)
    __asm__ volatile ("addi %0, %0, 1\n\taddi %0, %0, 1\n\taddi %0, %0, 1\n\taddi %0, %0, 1" : "+r"(value));
#else
    value += 4;
#endif
  }
  setStats(0);
  return value != 16385;
}
