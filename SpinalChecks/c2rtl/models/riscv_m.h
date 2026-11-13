/* Bit-exact RISC-V M semantics. Unsigned operations avoid signed C overflow. */
#include <stdint.h>
static uint64_t rvw_m(unsigned op, unsigned width, uint64_t a, uint64_t b) {
    uint64_t mask = width == 64 ? UINT64_MAX : (UINT64_C(1) << width) - 1; /* 8, 16, 32 or 64 */
    a &= mask; b &= mask;
    uint64_t sa=a>>(width-1), sb=b>>(width-1);
    uint64_t aa=sa ? (-a & mask) : a, bb=sb ? (-b & mask) : b;
    uint64_t hi=(uint64_t)(((__uint128_t)a*b)>>width);
    switch(op) {
    case 0: return (a*b)&mask; /* MUL */
    case 1: return (hi-(sa?b:0)-(sb?a:0))&mask; /* MULH */
    case 2: return (hi-(sa?b:0))&mask; /* MULHSU */
    case 3: return hi; /* MULHU */
    case 4: /* DIV: zero gives -1; min/-1 wraps */
        if(!b) return mask;
        {uint64_t q=aa/bb; return ((sa^sb)?-q:q)&mask;}
    case 5: return b ? a/b : mask; /* DIVU */
    case 6: /* REM: zero gives dividend */
        if(!b) return a;
        {uint64_t r=aa%bb; return (sa?-r:r)&mask;}
    case 7: return b ? a%b : a; /* REMU */
    }
    return 0;
}
