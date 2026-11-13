#include "FreeRTOS.h"
#include "task.h"
volatile unsigned long long tohost __attribute__((aligned(8)));
static volatile unsigned steps[2];
static void text(const char *s) {
    volatile unsigned char *uart = (void *)0x10000000;
    while (*s) *uart = *s++;
}
void boot_assert(void) {
    tohost = 3;
    for (;;) __asm__ volatile("nop");
}
static void worker(void *arg) {
    unsigned id = (unsigned)(uintptr_t)arg;
    for (unsigned i = 0; i < 3; ++i) {
        ++steps[id];
        text(id ? "B\n" : "A\n");
        vTaskDelay(2);
    }
    if (id) {
        while (steps[0] < 3) vTaskDelay(1);
        if (xTaskGetTickCount() < 6) boot_assert();
        text("FreeRTOS PASS\n");
        tohost = 1;
    }
    vTaskDelete(0);
}
int main(void) {
    text("FreeRTOS boot\n");
    if (xTaskCreate(worker, "A", 256, (void *)0, 1, 0) != pdPASS) boot_assert();
    if (xTaskCreate(worker, "B", 256, (void *)1, 1, 0) != pdPASS) boot_assert();
    vTaskStartScheduler();
    boot_assert();
}
