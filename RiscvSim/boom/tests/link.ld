OUTPUT_ARCH(riscv)
ENTRY(_start)
SECTIONS {
  . = 0x80000000;
  .text : { *(.text*) }
  . = ALIGN(4096);
  .tohost : { *(.tohost) }
  .data : { *(.data*) }
}
