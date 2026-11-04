#include <stdint.h>
#include "util.h"
/* Sequential reads over a 256 KiB array. Each initialized word equals one. */
static volatile uint32_t data[65536];
int main(void) {
  for (unsigned i = 0; i < 65536; ++i) data[i] = 1;
  uint32_t sum = 0;
  setStats(1);
  for (unsigned i = 0; i < 65536; ++i) sum += data[i];
  setStats(0);
  return sum != 65536;
}
