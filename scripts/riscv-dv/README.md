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

## Project settings

Generate a target profile from an existing project platform:

```sh
rvw/.venv/bin/python scripts/riscv-dv-project.py examples/vexriscv/rvw/platform.json \
  --out /tmp/vex-random-profile
```

The profile selects XLEN, ISA, ABI, reset address and RAM size from that file.
It writes `random.toml`, a bounded linker script and the register initialization
runtime. It requires a RAM region that starts at the reset PC. The linker keeps
`tohost` in RAM. This profile supports RV32IM and RV64IM integer programs.
The upstream target still has the `imc` name. The launcher disables compressed
instructions. Use `--checkout` and `--python` to select another pinned install.

Both example projects have generated profiles in `rvw/random/`. Run them with
`regress random --settings examples/CORE/rvw/random/random.toml`. Set the
project explicitly. Use private core copies and set both the project's
`core.lock` and `RVW_VEX_LOCK` to the same private lock for parallel workers.
