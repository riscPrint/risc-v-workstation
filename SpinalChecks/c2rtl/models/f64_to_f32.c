#include <stdint.h>
#include "platform.h"
#include "softfloat.h"
uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags) {
 softfloat_roundingMode=rm; softfloat_detectTininess=softfloat_tininess_afterRounding; softfloat_exceptionFlags=0;
 uint64_t bits=f64_to_f32((float64_t){a}).v; *flags=softfloat_exceptionFlags;
 if ((bits & 2139095040ULL)==2139095040ULL && (bits & 8388607ULL)) bits=2143289344ULL;
 return bits;
}
