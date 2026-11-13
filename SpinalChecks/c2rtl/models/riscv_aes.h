#ifndef RVW_AES_H
#define RVW_AES_H
#include <stdint.h>
/* Functional scalar AES models. Byte zero is the low byte. */
static uint8_t rvw_gf8(uint8_t a,uint8_t b) {
    uint8_t r=0;
    for(unsigned i=0;i<8;i++) {if(b&1)r^=a;uint8_t h=a>>7;a=(uint8_t)(a<<1)^(h?0x1b:0);b>>=1;}
    return r;
}
static uint8_t rvw_rot8(uint8_t x,unsigned n) {return (uint8_t)((x<<n)|(x>>(8-n)));}
static uint8_t rvw_sbox(uint8_t x,unsigned inverse) {
    if(inverse)x=rvw_rot8(x,1)^rvw_rot8(x,3)^rvw_rot8(x,6)^5;
    uint8_t power=x,r=1;
    for(unsigned i=0;i<8;i++) {if((254u>>i)&1)r=rvw_gf8(r,power);power=rvw_gf8(power,power);}
    if(inverse)return r;
    return r^rvw_rot8(r,1)^rvw_rot8(r,2)^rvw_rot8(r,3)^rvw_rot8(r,4)^0x63;
}
static uint32_t rvw_mixcolumn(uint32_t x,unsigned inverse) {
    const uint8_t f[4]={2,3,1,1},d[4]={14,11,13,9};uint32_t result=0;
    for(unsigned row=0;row<4;row++) {
        uint8_t byte=0;
        for(unsigned col=0;col<4;col++)byte^=rvw_gf8((uint8_t)(x>>(8*col)),inverse?d[(col-row)&3]:f[(col-row)&3]);
        result|=(uint32_t)byte<<(8*row);
    }
    return result;
}
static uint32_t rvw_aes32(unsigned op,uint32_t a,uint32_t b,unsigned bs) {
    uint32_t x=rvw_sbox((uint8_t)(b>>(8*bs)),op>=2);
    if(op&1)x=rvw_mixcolumn(x,op>=2);
    unsigned shift=8*bs;
    return a^(shift?((x<<shift)|(x>>(32-shift))):x);
}
static uint64_t rvw_aes64(unsigned op,uint64_t a,uint64_t b,unsigned immediate) {
    if(op==4)return ((uint64_t)rvw_mixcolumn((uint32_t)(a>>32),1)<<32)|rvw_mixcolumn((uint32_t)a,1);
    if(op==5) {uint32_t low=(uint32_t)(a>>32)^(uint32_t)b;return ((uint64_t)(low^(uint32_t)(b>>32))<<32)|low;}
    if(op==6) {
        if(immediate>10)return 0; /* Only legal fixed-immediate wrappers are exposed. */
        uint32_t x=(uint32_t)(a>>32),word=0;uint8_t rc=0;
        if(immediate!=10) {x=(x>>8)|(x<<24);rc=1;for(unsigned i=0;i<immediate;i++)rc=rvw_gf8(rc,2);}
        for(unsigned i=0;i<4;i++)word|=(uint32_t)rvw_sbox((uint8_t)(x>>(8*i)),0)<<(8*i);
        word^=rc;return ((uint64_t)word<<32)|word;
    }
    unsigned inverse=op>=2;uint64_t result=0;
    for(unsigned i=0;i<8;i++) {
        unsigned row=i&3,col=i/4,source=4*((col+(inverse?4-row:row))&3)+row;
        uint8_t byte=(uint8_t)(source<8?(a>>(8*source)):(b>>(8*(source-8))));
        result|=(uint64_t)rvw_sbox(byte,inverse)<<(8*i);
    }
    if(op&1)result=((uint64_t)rvw_mixcolumn((uint32_t)(result>>32),inverse)<<32)|rvw_mixcolumn((uint32_t)result,inverse);
    return result;
}
#endif
