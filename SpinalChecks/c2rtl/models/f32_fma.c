#include <stdint.h>
#include "platform.h"
#include "softfloat.h"
/* RISC-V canonical NaN, after-rounding tininess, all five rounding modes. */
uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags) {
    softfloat_roundingMode=rm;
    softfloat_detectTininess=softfloat_tininess_afterRounding;
    softfloat_exceptionFlags=0;
    float32_t x={a}, y={b}, z={c};
    float32_t r=f32_mulAdd(x,y,z);
    *flags=softfloat_exceptionFlags;
    uint64_t bits=r.v;
    if ((bits & 2139095040ULL)==2139095040ULL && (bits & 8388607ULL)) bits=2143289344ULL;
    return bits;
}
