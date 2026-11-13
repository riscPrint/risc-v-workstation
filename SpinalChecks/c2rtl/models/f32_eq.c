#include <stdint.h>
#include "platform.h"
#include "softfloat.h"
uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags) {
    softfloat_exceptionFlags=0;
    float32_t x={a}, y={b};
    uint64_t result=f32_eq(x,y);
    *flags=softfloat_exceptionFlags;
    return result;
}
