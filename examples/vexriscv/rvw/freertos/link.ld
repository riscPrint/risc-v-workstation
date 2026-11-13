ENTRY(_start)
PHDRS { text PT_LOAD FLAGS(5); data PT_LOAD FLAGS(6); }
SECTIONS {
  . = 0x80000000;
  .text : { *(.text.start) *(.text*) *(.rodata*) } :text
  . = ALIGN(0x1000);
  .data : { *(.data*) *(.sdata*) } :data
  __global_pointer$ = . + 0x800;
  .bss : { *(.bss*) *(.sbss*) *(COMMON) } :data
  /DISCARD/ : { *(.riscv.attributes) *(.comment) }
}
