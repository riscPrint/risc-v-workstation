#ifndef RVW_SHA512_SPLIT_H
#define RVW_SHA512_SPLIT_H
#include <stdint.h>
static uint32_t rvw_sha512_split(unsigned op,uint32_t a,uint32_t b) {
    switch(op) {
    case 0:return (a>>1)^(a>>7)^(a>>8)^(b<<31)^(b<<24);
    case 1:return (a>>1)^(a>>7)^(a>>8)^(b<<31)^(b<<25)^(b<<24);
    case 2:return (a<<3)^(a>>6)^(a>>19)^(b>>29)^(b<<13);
    case 3:return (a<<3)^(a>>6)^(a>>19)^(b>>29)^(b<<26)^(b<<13);
    case 4:return (a<<25)^(a<<30)^(a>>28)^(b>>7)^(b>>2)^(b<<4);
    case 5:return (a<<23)^(a>>14)^(a>>18)^(b>>9)^(b<<18)^(b<<14);
    default:return 0;
    }
}
#endif
