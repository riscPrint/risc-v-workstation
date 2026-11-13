#ifndef FREERTOS_CONFIG_H
#define FREERTOS_CONFIG_H
#include <stdint.h>
#define configUSE_PREEMPTION 1
#define configUSE_TIME_SLICING 1
#define configCPU_CLOCK_HZ 100000UL
#define configTICK_RATE_HZ 1000
#define configMAX_PRIORITIES 3
#define configMINIMAL_STACK_SIZE 128
#define configTOTAL_HEAP_SIZE 32768
#define configMAX_TASK_NAME_LEN 8
#define configUSE_16_BIT_TICKS 0
#define configIDLE_SHOULD_YIELD 1
#define configUSE_MUTEXES 0
#define configUSE_TIMERS 0
#define configUSE_COUNTING_SEMAPHORES 0
#define configUSE_TICK_HOOK 0
#define configUSE_IDLE_HOOK 0
#define configCHECK_FOR_STACK_OVERFLOW 0
#define configUSE_MALLOC_FAILED_HOOK 0
#define configSUPPORT_DYNAMIC_ALLOCATION 1
#define configSUPPORT_STATIC_ALLOCATION 0
#define configMTIME_BASE_ADDRESS 0x0200bff8UL
#define configMTIMECMP_BASE_ADDRESS 0x02004000UL
#define configISR_STACK_SIZE_WORDS 256
#define INCLUDE_vTaskDelay 1
#define INCLUDE_vTaskDelete 1
#define INCLUDE_vTaskSuspend 0
#define INCLUDE_xTaskGetSchedulerState 1
extern void boot_assert(void);
#define configASSERT(x) do { if (!(x)) boot_assert(); } while (0)
#endif
