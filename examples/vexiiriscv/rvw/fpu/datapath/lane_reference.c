#include <stdint.h>
#include "softfloat.h"
#ifndef UNIT_OP
#define UNIT_OP 0
#endif
uint64_t reference_case(unsigned op, uint64_t a, uint64_t b, uint64_t c, uint8_t rm, uint8_t *flags) {
    softfloat_roundingMode=rm;
    softfloat_exceptionFlags=0;
    uint64_t result;
#if FP_WIDTH == 32
    float32_t x={(uint32_t)a}, y={(uint32_t)b}, z={(uint32_t)c};
    switch(op){
      case 0:result=f32_add(x,y).v;break;
      case 1:result=f32_mul(x,y).v;break;
      case 2:result=f32_div(x,y).v;break;
      case 3:result=f32_sqrt(x).v;break;
      case 4:result=(uint32_t)f32_to_i32(x,rm,true);break;
      case 5:result=i32_to_f32((int32_t)(uint32_t)a).v;break;
      case 6:result=f32_mulAdd(x,y,z).v;break;
      case 8:result=(uint32_t)f32_to_ui32(x,rm,true);break;
      case 9:result=ui32_to_f32((uint32_t)a).v;break;
      default:result=f32_sub(x,y).v;break;
    }
#else
    float64_t x={a}, y={b}, z={c};
    switch(op){
      case 0:result=f64_add(x,y).v;break;
      case 1:result=f64_mul(x,y).v;break;
      case 2:result=f64_div(x,y).v;break;
      case 3:result=f64_sqrt(x).v;break;
      case 4:result=(uint64_t)(int64_t)(int32_t)f64_to_i32(x,rm,true);break;
      case 5:result=i32_to_f64((int32_t)(uint32_t)a).v;break;
      case 6:result=f64_mulAdd(x,y,z).v;break;
      case 8:result=(uint64_t)(int64_t)(int32_t)(uint32_t)f64_to_ui32(x,rm,true);break;
      case 9:result=ui32_to_f64((uint32_t)a).v;break;
      case 10:result=(uint64_t)f64_to_i64(x,rm,true);break;
      case 11:result=i64_to_f64((int64_t)a).v;break;
      case 12:result=f64_to_ui64(x,rm,true);break;
      case 13:result=ui64_to_f64(a).v;break;
      case 14:{float32_t source={(uint32_t)a};result=f32_to_f64(source).v;break;}
      case 15:result=UINT64_C(0xffffffff00000000)|f64_to_f32(x).v;break;
      default:result=f64_sub(x,y).v;break;
    }
#endif
    *flags=softfloat_exceptionFlags;
    return result;
}
uint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags) {
    return reference_case(UNIT_OP,a,b,c,rm,flags);
}
