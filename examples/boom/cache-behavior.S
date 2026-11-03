/* Bounded single-hart functional test. No hit/miss counter claims. */
.section .text.init
.globl _start
_start:
  li t0, 0x1f
  csrw pmpcfg0, t0
  li t0, -1
  csrw pmpaddr0, t0
  la a0, buffer
  li a1, 4096
  li t0, 0
1:
  sd t0, 0(a0)
  addi a0, a0, 8
  addi t0, t0, 1
  bltu t0, a1, 1b
  /* Check each word after replacement pressure. */
  la a0, buffer
  li t0, 0
2:
  ld t1, 0(a0)
  bne t0, t1, fail
  addi a0, a0, 8
  addi t0, t0, 1
  bltu t0, a1, 2b
  /* Repeated accesses exercise the same cache line, then byte lanes. */
  la a0, buffer
  li t2, 32
3:
  ld t1, 8(a0)
  li t0, 1
  bne t0, t1, fail
  addi t2, t2, -1
  bnez t2, 3b
  li t0, 0x5a
  sb t0, 9(a0)
  ld t1, 8(a0)
  li t0, 0x5a01
  bne t0, t1, fail
  /* Patch an already fetched function. FENCE.I must expose the new code. */
  call patch_target
  li t0, 1
  bne a0, t0, fail
  la t0, patch_target
  li t1, 0x00200513 /* addi a0, zero, 2 */
  sw t1, 0(t0)
  fence rw, rw
  fence.i
  call patch_target
  li t0, 2
  bne a0, t0, fail
  li t1, 1
  j finish
fail:
  li t1, 3
finish:
  la t0, tohost
  sd t1, 0(t0)
4: j 4b
.balign 4
.option push
.option norvc
patch_target:
  addi a0, zero, 1
  ret
.option pop
.section .tohost,"aw",@progbits
.balign 64
.globl tohost
tohost: .dword 0
.globl fromhost
fromhost: .dword 0
.section .bss
.balign 4096
buffer: .skip 32768
