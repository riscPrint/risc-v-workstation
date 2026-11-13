#include <stdint.h>
#include "platform.h"
#include "softfloat.h"
uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags) {
 softfloat_roundingMode=rm; softfloat_detectTininess=softfloat_tininess_afterRounding; softfloat_exceptionFlags=0;
 uint64_t result=(uint64_t)f64_to_ui64((float64_t){a},rm,true); *flags=softfloat_exceptionFlags; return result;
}
