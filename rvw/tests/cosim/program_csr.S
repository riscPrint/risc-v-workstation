# Reads of CSRs whose values are partly implementation-defined (misa, pmpaddr, IDs),
# including a CSRRW whose old value must agree with the value written before.
.section .text
.globl _start, misa_site, pmp_read_site, pmp_swap_site, marchid_site
_start:
misa_site:
  csrr s0, misa
  addi s1, s0, 1
  li t0, 0x1234
  csrw pmpaddr0, t0
pmp_read_site:
  csrr s2, pmpaddr0
  addi s3, s2, 1
  li t1, 0x5678
pmp_swap_site:
  csrrw s4, pmpaddr0, t1
  addi s5, s4, 1
marchid_site:
  csrr s6, marchid
  la t0, tohost
  li t1, 1
  sd t1, 0(t0)
1: j 1b
.section .data
.globl tohost
.align 3
tohost: .dword 0
