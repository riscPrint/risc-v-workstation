#include <stdint.h>
#include "softfloat.h"
/* The standalone mantissa harness discards sign. Only normal inputs are bound. */
uint64_t reference(uint64_t a, uint64_t b, uint64_t c, uint8_t rm, uint8_t *flags) {
    (void)b; (void)c;
    softfloat_roundingMode = rm;
    softfloat_exceptionFlags = 0;
#if FP_WIDTH == 32
    float32_t x = { (uint32_t)a & UINT32_C(0x7fffffff) };
    float32_t y = f32_sqrt(x);
#else
    float64_t x = { a & UINT64_C(0x7fffffffffffffff) };
    float64_t y = f64_sqrt(x);
#endif
    *flags = softfloat_exceptionFlags;
    return y.v;
}
