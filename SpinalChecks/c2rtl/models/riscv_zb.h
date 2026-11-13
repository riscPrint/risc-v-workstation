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
    default: return 0;
    }
}

#endif
