OUTPUT_ARCH(riscv)
ENTRY(_start)
PHDRS { reset PT_LOAD FLAGS(5); firmware PT_LOAD FLAGS(7); }
SECTIONS {
  . = 0x80000000;
  .text : { *(.text.reset) } :reset
  . = 0x80200000;
  .firmware : { *(.firmware) } :firmware
  /* Required by the adapter. The bounded smoke does not write this address. */
  tohost = 0x8fff0000;
  /DISCARD/ : { *(.riscv.attributes) *(.comment) }
}
