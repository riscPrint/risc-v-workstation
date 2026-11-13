OUTPUT_ARCH("riscv")
ENTRY(_start)
MEMORY
{
  ram (rwx) : ORIGIN = 0x80000000, LENGTH = 64K
}
SECTIONS
{
  .text : { *(.text.init) *(.text*) } > ram
  .data : { *(.data*) *(.sdata*) *(.bss*) } > ram
  .tohost : ALIGN(64) { *(.tohost) } > ram
}
