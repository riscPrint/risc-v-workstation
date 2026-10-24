ENTRY(_start)
PHDRS { ram PT_LOAD FLAGS(7); }
SECTIONS {
  . = 0x80000000;
  .text : { *(.text*) } :ram
  .data : { *(.data*) } :ram
  .bss : { *(.bss*) } :ram
}
