// Minimal type and operation-class definitions that the CBP 2016 predictor
// sources expect from the competition framework. Owner-written shim.
#pragma once
#include <cstdint>
typedef uint64_t UINT64;
typedef int64_t INT64;
typedef uint32_t UINT32;
typedef int32_t INT32;
typedef uint16_t UINT16;
typedef int16_t INT16;
typedef uint8_t UINT8;
typedef int8_t INT8;
typedef enum {
    OPTYPE_OP = 2,
    OPTYPE_RET_UNCOND, OPTYPE_JMP_DIRECT_UNCOND, OPTYPE_JMP_INDIRECT_UNCOND,
    OPTYPE_CALL_DIRECT_UNCOND, OPTYPE_CALL_INDIRECT_UNCOND,
    OPTYPE_RET_COND, OPTYPE_JMP_DIRECT_COND, OPTYPE_JMP_INDIRECT_COND,
    OPTYPE_CALL_DIRECT_COND, OPTYPE_CALL_INDIRECT_COND,
    OPTYPE_ERROR, OPTYPE_MAX
} OpType;
