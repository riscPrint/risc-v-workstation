/* PicoRV32 test environment for the workstation: tohost completion, no CSRs.
   Force-included; the guard matches tests/riscv_test.h, so that file is skipped. */
#ifndef _ENV_PICORV32_TEST_H
#define _ENV_PICORV32_TEST_H
#define RVTEST_RV32U
#define TESTNUM x28
#define RVTEST_CODE_BEGIN .section .text.init; .globl _start; _start:
#define RVTEST_PASS li a0, 1; la a1, tohost; sw a0, 0(a1); 1: j 1b;
#define RVTEST_FAIL slli a0, TESTNUM, 1; ori a0, a0, 1; la a1, tohost; sw a0, 0(a1); 1: j 1b;
#define RVTEST_CODE_END
#define RVTEST_DATA_BEGIN .section .data; .balign 8; .globl tohost; tohost: .dword 0; .balign 4;
#define RVTEST_DATA_END
#endif
