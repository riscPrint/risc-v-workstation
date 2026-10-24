# A load outside the platform RAM (BOOM: 256 MiB from 0x80000000) must fault (review round 4).
# The BSS makes the load segment 8 KiB, for the ELF segment check with a smaller RAM.
.section .text
.globl _start, load_site
_start:
  la t0, handler
  csrw mtvec, t0
  li t0, 0x90002000
load_site:
  ld s0, 0(t0)
  addi s1, s0, 1
  la t0, tohost
  li t1, 1
  sd t1, 0(t0)
1: j 1b
.align 2
handler:                 # the load faulted: end with fail (tohost 3)
  la t0, tohost
  li t1, 3
  sd t1, 0(t0)
2: j 2b
.section .data
.globl tohost
.align 3
tohost: .dword 0
.section .bss
.space 0x2000
