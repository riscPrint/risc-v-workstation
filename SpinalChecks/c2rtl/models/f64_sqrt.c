#include <stdint.h>
#include "platform.h"
#include "softfloat.h"
/* RISC-V canonical NaN, after-rounding tininess, all five rounding modes. */
uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags) {
    softfloat_roundingMode=rm;
    softfloat_detectTininess=softfloat_tininess_afterRounding;
    softfloat_exceptionFlags=0;
    float64_t x={a}, y={b}, z={c};
    float64_t r=f64_sqrt(x);
    *flags=softfloat_exceptionFlags;
    uint64_t bits=r.v;
    if ((bits & 9218868437227405312ULL)==9218868437227405312ULL && (bits & 4503599627370495ULL)) bits=9221120237041090560ULL;
    return bits;
}
