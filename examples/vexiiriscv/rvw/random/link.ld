OUTPUT_ARCH(riscv)
ENTRY(_start)
MEMORY { ram (rwx) : ORIGIN = 0x80000000, LENGTH = 0x1000000 }
SECTIONS {
  .text : { *(.text*) } > ram
  .tohost : ALIGN(0x1000) { *(.tohost*) } > ram
  .data : ALIGN(0x1000) { *(.data*) *(.user_stack*) } > ram
  .bss : { *(.bss*) } > ram
}
