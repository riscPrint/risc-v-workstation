#include <stdint.h>
#include "platform.h"
#include "softfloat.h"
uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags) {
 softfloat_roundingMode=rm; softfloat_detectTininess=softfloat_tininess_afterRounding; softfloat_exceptionFlags=0;
 uint64_t bits=f32_to_f64((float32_t){a}).v; *flags=softfloat_exceptionFlags;
 if ((bits & 9218868437227405312ULL)==9218868437227405312ULL && (bits & 4503599627370495ULL)) bits=9221120237041090560ULL;
 return bits;
}
