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

The runtime writes `mscratch` before its first GPR initialization instruction.
This defines scratch state before the first per-retirement CSR snapshot.
VexRiscv does not give that storage a defined reset value. Leaving it untouched
can produce a real strict comparison mismatch against Spike's zero startup
value. The software write defines an architectural input. It does not mask a
comparison or change the observed CSR value.

## Declared architectural target

Pass `--csrs examples/CORE/csr.json` to `scripts/riscv-dv-project.py` to
write `target.json` and select it with `target_profile` in the settings.
The CSR file uses the shared CSR catalog. Only present project-selected CSRs
enter the generator. Unknown reset state stays unknown in this metadata.
The profile derives ISA groups, XLEN, privilege modes, alignment policy,
PMP presence, reset address and RAM bounds. The launcher replaces architectural
preset values before pygen imports its configuration. It does not change the
pinned installation. The `imc` name remains an upstream module locator.
A CSR selection can describe a subset. It does not certify a complete CSR set.
This bare integer flow does not exercise all selected privilege modes or CSRs.

## Reproduced initial-state and adapter errors

`examples/vexriscv/rvw/random/uninitialized-scratch.S` is a four-instruction
negative control. It leaves scratch state undefined. On the private VexRiscv
sample it passed C1 at 17 cycles, then strict Spike comparison failed at order
zero: `csr[0x340]` was `0xdba352fc` instead of zero. The normal runtime writes
`mscratch` first. An arithmetic seed 48 run then passed C1 at 456 cycles with
125 retirements and matched Spike without masks or synchronization.

The adapter error also reproduced when the tools worktree changed from clean
to dirty during launch. C1 passed, but its `source.tools_dirty` claim differed
from the captured adapter identity. Keep the tools revision and worktree state
fixed through a campaign. This check remains strict. Neither error is evidence
of a new core difference. The original seed 48 record has the same mechanism
with `source.tools_rev` instead of the dirty flag.

Regenerate the negative control from the workstation root. Set `RVW_HOME`,
`VEXRISCV`, `RVW_VEX_LOCK=vex-dv2`, `RVW_SBT_LOCK=sbt-dv2`, and
`RISCVSIM_WORK` to private locations first:

```sh
python scripts/riscv-dv-project.py examples/vexriscv/rvw/platform.json \
  --csrs examples/vexriscv/csr.json --out "$RUN_ROOT/profile"
riscv64-unknown-elf-gcc -march=rv32im_zicsr_zifencei -mabi=ilp32 \
  -mcmodel=medany -nostdlib -nostartfiles -static -T "$RUN_ROOT/profile/link.ld" \
  examples/vexriscv/rvw/random/uninitialized-scratch.S -o "$RUN_ROOT/scratch.elf"
nice -n 10 "$VEXRISCV/rvw/run.sh" run --elf "$RUN_ROOT/scratch.elf" \
  --out "$RUN_ROOT/negative" --seed 49 --mem-latency 0 --rvfi-trace --json
rvw cosim check --core vexriscv --elf "$RUN_ROOT/scratch.elf" \
  --trace "$RUN_ROOT/negative/rvfi.jsonl" \
  --platform examples/vexriscv/rvw/platform.json --strict --json
```

The last command must report mismatch. Raw runs stay outside the repository.
This is a bounded native sample. It does not establish broad ISA coverage.
