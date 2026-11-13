ENTRY(_start)
MEMORY { ram (rwx) : ORIGIN = 0x80000000, LENGTH = 0x100000 }
SECTIONS {
  .text : { *(.text.init) *(.text*) } > ram
  .data : { *(.data*) *(.sdata*) *(.rodata*) *(.srodata*) } > ram
  .bss : { *(.bss*) *(.sbss*) } > ram
  /DISCARD/ : { *(.riscv.attributes) *(.comment) }
}
