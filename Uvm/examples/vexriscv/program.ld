ENTRY(_start)
SECTIONS {
 .text 0x80000000 : { *(.text*) }
 .tohost ALIGN(64) : { *(.tohost) }
 .data ALIGN(16) : { *(.data*) }
}
