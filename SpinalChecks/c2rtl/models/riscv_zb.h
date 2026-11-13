#ifndef RVW_ZB_H
#define RVW_ZB_H
#include <stdint.h>
/* Pure unsigned bit-vector models. w is 32 or 64. */
static uint64_t rvw_zb(unsigned op, unsigned w, uint64_t a, uint64_t b) {
    uint64_t mask=UINT64_MAX>>(64-w), sign=1ULL<<(w-1), r=0;
    a&=mask; b&=mask; unsigned n=b&(w-1);
    switch(op) {
    case 0: return a&~b;
    case 1: return (a|~b)&mask;
    case 2: return ~(a^b)&mask;
    case 3: return ((a<<n)|(a>>((w-n)&(w-1))))&mask;
    case 4: return ((a>>n)|(a<<((w-n)&(w-1))))&mask;
    case 5: for(unsigned i=0;i<w;i++) r+=(a>>i)&1; return r;
    case 6: for(unsigned i=w;i>0;i--) {if((a>>(i-1))&1) break; r++;} return r;
    case 7: for(unsigned i=0;i<w;i++) {if((a>>i)&1) break; r++;} return r;
    case 8: return ((a^sign)<(b^sign))?a:b;
    case 9: return ((a^sign)>(b^sign))?a:b;
    case 10: return a<b?a:b;
    case 11: return a>b?a:b;
    case 12: for(unsigned i=0;i<w;i+=8) r|=((a>>i)&255)<<(w-8-i); return r;
    case 13: for(unsigned i=0;i<w;i+=8) if((a>>i)&255) r|=255ULL<<i; return r;
    case 14: for(unsigned i=0;i<w;i++) if((b>>i)&1) r^=a<<i; return r&mask;
    case 15: for(unsigned i=1;i<w;i++) if((b>>i)&1) r^=a>>(w-i); return r;
    case 16: for(unsigned i=0;i<w;i++) if((b>>i)&1) r^=a>>(w-1-i); return r&mask;
    case 17: return (a&255) | ((a&128)?(mask^255):0);
    case 18: return (a&65535) | ((a&32768)?(mask^65535):0);
    case 19: return a&65535;
    case 20: return a|(1ULL<<n);
    case 21: return a&~(1ULL<<n);
    case 22: return a^(1ULL<<n);
    case 23: return (a>>n)&1;
    case 24: return ((a<<1)+b)&mask;
    case 25: return ((a<<2)+b)&mask;
    case 26: return ((a<<3)+b)&mask;
    case 27: case 28: {
        unsigned size=op==27?4:8;uint64_t element_mask=(1ULL<<size)-1;
        for(unsigned i=0;i<w;i+=size) {uint64_t index=(b>>i)&element_mask;
            if(index<w/size)r|=((a>>(index*size))&element_mask)<<i;}
        return r;
    }
    case 29: {unsigned half=w/2;uint64_t hm=(1ULL<<half)-1;return (a&hm)|((b&hm)<<half);}
    case 30: return (a&255)|((b&255)<<8);
    case 31: for(unsigned i=0;i<w;i++)r|=((a>>i)&1)<<((i&~7u)|(7-(i&7)));return r;
    case 32: for(unsigned i=0;i<16;i++)r|=(((a>>i)&1)<<(2*i))|(((a>>(i+16))&1)<<(2*i+1));return r;
    case 33: for(unsigned i=0;i<16;i++)r|=(((a>>(2*i))&1)<<i)|(((a>>(2*i+1))&1)<<(i+16));return r;
    case 34: return (uint64_t)(uint32_t)a+b;
    case 35: case 36: case 37: return ((uint64_t)(uint32_t)a<<(op-34))+b;
    case 38: return (uint64_t)(uint32_t)a<<(b&63);
    case 39: case 40: {
        uint32_t x=(uint32_t)a,z=x;unsigned shift=(unsigned)b&31;
        if(shift)z=op==39?((x<<shift)|(x>>(32-shift))):((x>>shift)|(x<<(32-shift)));
        return (uint64_t)z|((z>>31)?0xffffffff00000000ULL:0);
    }
    case 41: case 42: case 43: {
        uint32_t x=(uint32_t)a;
        if(op==41)for(unsigned i=0;i<32;i++)r+=(x>>i)&1;
        else if(op==42)for(unsigned i=32;i>0;i--){if((x>>(i-1))&1)break;r++;}
        else for(unsigned i=0;i<32;i++){if((x>>i)&1)break;r++;}
        return r;
    }
    case 44: {uint32_t z=(uint32_t)(a&65535)|((uint32_t)(b&65535)<<16);return (uint64_t)z|((z>>31)?0xffffffff00000000ULL:0);}
    default: return 0;
    }
}

#endif
