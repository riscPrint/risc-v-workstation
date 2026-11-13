OUTPUT_ARCH( "riscv" )
ENTRY(_boot)

SECTIONS
{
  . = 0x80000080;
  .text.boot : { *(.text.boot) }
  .text.init : { *(.text.init) }
  . = ALIGN(0x1000);
  .tohost : { *(.tohost) }
  . = ALIGN(0x1000);
  .text : { *(.text) }
  . = ALIGN(0x1000);
  .data : { *(.data) }
  .bss : { *(.bss) }
  _end = .;
}

