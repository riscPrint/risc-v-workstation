#include "util.h"

/* Mix compressed and full-width branches. Check the complete path checksum. */
int main(void) {
  unsigned sum = 0;
  setStats(1);
  for (unsigned i = 0; i < 256; ++i) {
    __asm__ volatile (
      ".option push\n\t.option rvc\n\t"
      "andi a4, %1, 3\n\t"
      "c.beqz a4, 1f\n\t"
      "c.addi %0, 1\n"
      "1:\n\t.option norvc\n\t"
      "andi a4, %1, 1\n\t"
      "beq a4, zero, 2f\n\t"
      "addi %0, %0, 2\n"
      "2:\n\t.option rvc\n\t"
      "c.addi %0, 1\n\t.option pop"
      : "+r"(sum) : "r"(i) : "a4");
  }
  setStats(0);
  return sum != (192 + 256 + 256);
}
