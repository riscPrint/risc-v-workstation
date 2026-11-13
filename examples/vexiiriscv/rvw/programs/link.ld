ENTRY(_start)
PHDRS {
  text PT_LOAD FLAGS(5);
  data PT_LOAD FLAGS(6);
}
SECTIONS {
  . = 0x80000000;
  .text : { *(.text*) } :text
  . = ALIGN(0x1000);
  .data : { *(.data*) } :data
  .bss : { *(.bss*) } :data
  /DISCARD/ : { *(.riscv.attributes) *(.comment) }
}
