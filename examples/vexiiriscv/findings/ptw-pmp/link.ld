OUTPUT_ARCH("riscv")
ENTRY(_start)
SECTIONS {
 . = 0x80000000; .text : { *(.text) }
 . = 0x80008000; .tohost : { *(.tohost) }
 . = 0x80010000; .tables : { *(.tables) }
 . = 0x80200000; .data : { *(.data) }
}
