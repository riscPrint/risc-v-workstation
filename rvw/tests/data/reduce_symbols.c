/* Fixture for rvw reduce --symbol tests (tests/data/reduce_symbols.elf). Built with:
   riscv64-unknown-elf-gcc -nostdlib -Os -Wl,-Ttext=0x80000000 -Wl,--build-id=none reduce_symbols.c -o reduce_symbols.elf
   riscv64-unknown-elf-strip --strip-debug reduce_symbols.elf */
volatile unsigned long limit = 100;
volatile unsigned int table[4] = {7, 1, 2, 3};
void _start(void) { for (;;) {} }
