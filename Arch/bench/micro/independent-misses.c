#include <stdint.h>
#include "util.h"
/* Separate load addresses. Cache capacity determines whether they miss. */
static volatile uint32_t data[4][65536];
int main(void) {
  uint32_t a=0, b=0, c=0, d=0;
  for (unsigned k=0; k<4; ++k)
    for (unsigned i=0; i<65536; i+=16) data[k][i] = 1;
  setStats(1);
  for (unsigned i=0; i<65536; i+=16) {
    a += data[0][i]; b += data[1][i]; c += data[2][i]; d += data[3][i];
  }
  setStats(0);
  return a+b+c+d != 16384;
}
