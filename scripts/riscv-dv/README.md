# Native riscv-dv runtime

`user_init.s` initializes all integer registers before the upstream pygen
setup. The pinned base generator can read a register that its own setup does
not initialize. A reference model's zero startup value must not become a DUT
requirement. Use this project runtime to define those architectural inputs.

Put this directory before the upstream `user_extension` include directory:

```sh
riscv64-unknown-elf-gcc -march=rv64im_zicsr -mabi=lp64 -mcmodel=medany \
  -nostdlib -nostartfiles -static -I scripts/riscv-dv \
  -I /path/to/riscv-dv/user_extension \
  -T /path/to/riscv-dv/scripts/link.ld program_0.S -o program.elf
```

Select RV32IM / ILP32 for an RV32 project. Keep the memory map and termination
protocol consistent with that core's adapter. The runtime defines input values;
it does not supply expected instruction results. Check C1 completion and a
complete independent model comparison separately. Preserve the initial ELF
and mismatch if a previous build used undefined register inputs.
