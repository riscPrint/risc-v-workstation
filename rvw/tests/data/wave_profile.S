# Source of wave_profile.elf: riscv64-unknown-elf-gcc -nostdlib -march=rv64i -mabi=lp64 -Ttext=0x80000000 -o wave_profile.elf wave_profile.S
  .section .text
  .globl _start
  .type _start, @function
_start:
  li a0, 4
  call work
  j _start
  .size _start, .-_start
  .globl work
  .type work, @function
work:
  addi a0, a0, -1
  bnez a0, work
  ret
  .size work, .-work
