#include "riscv_sha512_split.h"
uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags) {return rvw_sha512_split(1,(uint32_t)a,(uint32_t)b);}
