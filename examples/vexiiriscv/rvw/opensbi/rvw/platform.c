/* SPDX-License-Identifier: BSD-2-Clause */
#include <sbi/sbi_const.h>
#include <sbi/sbi_platform.h>
#include <sbi_utils/ipi/aclint_mswi.h>
#include <sbi_utils/serial/uart8250.h>
#include <sbi_utils/timer/aclint_mtimer.h>

/* Project-owned map. The OS map uses one timer tick per 100 MHz RTL cycle. */
static struct aclint_mswi_data mswi = {
 .addr = 0x02000000, .size = 0x4000, .first_hartid = 0, .hart_count = 1,
};
static struct aclint_mtimer_data mtimer = {
 .mtime_freq = 100000000, .mtime_addr = 0x0200bff8, .mtime_size = 8,
 .mtimecmp_addr = 0x02004000, .mtimecmp_size = ACLINT_DEFAULT_MTIMECMP_SIZE,
 .first_hartid = 0, .hart_count = 1, .has_64bit_mmio = true,
};
static int early_init(bool cold) {
 return cold ? uart8250_init(0x10000000, 1843200, 115200, 0, 1, 0) : 0;
}
static int ipi_init(void) { return aclint_mswi_cold_init(&mswi); }
static int timer_init(void) { return aclint_mtimer_cold_init(&mtimer, NULL); }
static const struct sbi_platform_operations operations = {
 .early_init = early_init, .ipi_init = ipi_init, .timer_init = timer_init,
};
const struct sbi_platform platform = {
 .opensbi_version = OPENSBI_VERSION,
 .platform_version = SBI_PLATFORM_VERSION(0, 1), .name = "rvw-vexii",
 .features = SBI_PLATFORM_DEFAULT_FEATURES, .hart_count = 1,
 .hart_stack_size = SBI_PLATFORM_DEFAULT_HART_STACK_SIZE,
 .heap_size = SBI_PLATFORM_DEFAULT_HEAP_SIZE(1),
 .platform_ops_addr = (unsigned long)&operations,
};
