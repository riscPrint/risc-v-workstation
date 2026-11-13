#include <stdint.h>
#include "platform.h"
#include "softfloat.h"
uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags) {
 softfloat_roundingMode=rm; softfloat_detectTininess=softfloat_tininess_afterRounding; softfloat_exceptionFlags=0;
 uint64_t result=(uint32_t)f32_to_i32((float32_t){a},rm,true); *flags=softfloat_exceptionFlags; return result;
}
