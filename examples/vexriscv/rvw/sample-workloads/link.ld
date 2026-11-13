ENTRY(_start)
SECTIONS {
  . = 0x80000000;
  .text : { *(.text.start) *(.text*) }
  . = ALIGN(0x1000);
  .data : { *(.data*) *(.sdata*) }
  .bss : { *(.bss*) *(.sbss*) *(COMMON) }
  ASSERT(. < 0x800d0000, "workload overlaps stack or bootstrap reserve")
}
