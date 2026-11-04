#include "support.h"
/* Require the upstream checker to return exactly 1. -1 means no check. */
int main(void) {
  initialise_benchmark();
  int result = benchmark();
  return verify_benchmark(result) == 1 ? 0 : 1;
}
