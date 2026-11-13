#include "riscv_aes.h"
uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags) {return rvw_aes64(6,a,b,6);}
