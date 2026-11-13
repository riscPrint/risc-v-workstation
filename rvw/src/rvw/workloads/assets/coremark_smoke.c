/* A short algorithm check. This program does not produce a CoreMark score. */
#include <stddef.h>
#include "coremark.h"
static unsigned char memory[6000] __attribute__((aligned(8)));
static int errors;
int ee_printf(const char *format, ...) { (void)format; errors++; return 0; }
int main(void) {
    core_results r = {0};
    r.seed1 = 0; r.seed2 = 0; r.seed3 = 0x66;
    r.size = 2000; r.iterations = 1; r.execs = ALL_ALGORITHMS_MASK;
    r.memblock[0] = memory;
    for (unsigned i=0; i<3; i++) r.memblock[i+1] = memory + 2000*i;
    r.list = core_list_init(r.size, r.memblock[1], r.seed1);
    core_init_matrix(r.size, r.memblock[2], 0, &r.mat);
    core_init_state(r.size, r.seed1, r.memblock[3]);
    iterate(&r);
    /* Upstream core_main.c's 6k performance-seed reference vectors. */
    return errors || check_data_types() || r.crclist != 0xd4b0 ||
           r.crcmatrix != 0xbe52 || r.crcstate != 0x5e47;
}
