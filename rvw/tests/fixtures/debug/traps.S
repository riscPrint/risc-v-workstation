# E-Trace fixture: branches, an ecall in M, a drop to U-mode, an ecall from U and returns.
.section .text
.global _start
_start:
  la t0, handler
  csrw mtvec, t0
  li s0, 6
1:
  addi s0, s0, -1
  andi t1, s0, 1
  beqz t1, 2f
  ecall
2:
  bnez s0, 1b
  la t0, user
  csrw mepc, t0
  li t0, 0x1800
  csrc mstatus, t0
  mret
user:
  li s1, 3
3:
  addi s1, s1, -1
  ecall
  bnez s1, 3b
.global done
done:
  j done
handler:
  csrr t2, mepc
  addi t2, t2, 4
  csrw mepc, t2
  mret
.section .tohost,"aw",@progbits
.align 6
.global tohost
 tohost: .dword 0
.global fromhost
 fromhost: .dword 0
