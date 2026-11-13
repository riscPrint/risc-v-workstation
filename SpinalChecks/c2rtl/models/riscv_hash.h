#ifndef RVW_HASH_H
#define RVW_HASH_H
#include <stdint.h>
static uint32_t rvw_ror32(uint32_t x,unsigned n) {return (x>>n)|(x<<(32-n));}
static uint64_t rvw_ror64(uint64_t x,unsigned n) {return (x>>n)|(x<<(64-n));}
static uint64_t rvw_hash(unsigned op,unsigned width,uint64_t a) {
    uint32_t x=(uint32_t)a, r=0;
    switch(op) {
    case 0:r=rvw_ror32(x,7)^rvw_ror32(x,18)^(x>>3);break;
    case 1:r=rvw_ror32(x,17)^rvw_ror32(x,19)^(x>>10);break;
    case 2:r=rvw_ror32(x,2)^rvw_ror32(x,13)^rvw_ror32(x,22);break;
    case 3:r=rvw_ror32(x,6)^rvw_ror32(x,11)^rvw_ror32(x,25);break;
    case 4:r=x^rvw_ror32(x,23)^rvw_ror32(x,15);break;
    case 5:r=x^rvw_ror32(x,17)^rvw_ror32(x,9);break;
    case 6:return rvw_ror64(a,1)^rvw_ror64(a,8)^(a>>7);
    case 7:return rvw_ror64(a,19)^rvw_ror64(a,61)^(a>>6);
    case 8:return rvw_ror64(a,28)^rvw_ror64(a,34)^rvw_ror64(a,39);
    case 9:return rvw_ror64(a,14)^rvw_ror64(a,18)^rvw_ror64(a,41);
    }
    /* RV64 SHA-256 and SM3 sign-extend their 32-bit result. */
    return (uint64_t)r | ((width==64 && (r>>31))?0xffffffff00000000ULL:0);
}
#endif
