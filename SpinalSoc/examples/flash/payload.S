.option norvc
.section .text
.global _start
_start:
  # Only this RAM payload reports success. The ROM reports checksum failure.
  li t0,0x10001000
  li t1,1
  sw t1,0(t0)
1: j 1b
