#include "riscv_m.h"
uint64_t reference(uint64_t a, uint64_t b, uint64_t c, uint8_t rm, uint8_t *flags) {
    *flags=0; return rvw_m(0, 64, a, b);
}
