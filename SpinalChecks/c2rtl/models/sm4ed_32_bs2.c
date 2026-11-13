#include "riscv_sm4.h"
uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags) {
 uint32_t r=rvw_sm4(0,(uint32_t)a,(uint32_t)b,2);
 return (uint64_t)r;
}
