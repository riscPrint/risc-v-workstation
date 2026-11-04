OUTPUT_ARCH(riscv)
ENTRY(_start)
SECTIONS {
  . = 0x80000000;
  .text : { *(.text.init) *(.text .text.*) }
  .rodata : { *(.rodata .rodata.*) }
  .data : { *(.data .data.*) }
  .sdata : { __global_pointer$ = . + 0x800; *(.sdata .sdata.*) }
  .tohost : { *(.tohost) }
  . = ALIGN(8);
  __bss_start = .;
  .bss : { *(.sbss .sbss.*) *(.bss .bss.*) *(COMMON) }
  . = ALIGN(8);
  __bss_end = .;
  _end = .;
  . += 0x100000;
  _stack_top = .;
}
