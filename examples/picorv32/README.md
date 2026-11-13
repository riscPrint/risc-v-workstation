# PicoRV32 project example (Verilog core)

This folder holds the project files for an external
[PicoRV32](https://github.com/YosysHQ/picorv32) checkout at
`ef203c2b0a3fb793280f5114941416c425c5b461`. It is a Verilog core with no Scala
code. One `rvw init` command wrote these files. Only `rvw/env/`,
`rvw/build-tests.sh` and the `isa` suite in `rvw.toml` were added by hand.

## Setup

```sh
git clone https://github.com/YosysHQ/picorv32 "$HOME/projects/picorv32"
cd "$HOME/projects/picorv32"
git checkout -b rvw-project ef203c2b0a3fb793280f5114941416c425c5b461
rvw init --isa rv32im --name picorv32 --verilog-top picorv32 --verilog picorv32.v \
  --define RISCV_FORMAL --param PROGADDR_RESET=0x80000000 --param PROGADDR_IRQ=0x80000010 \
  --param ENABLE_MUL=1 --param ENABLE_DIV=1 --clock clk --reset resetn --reset-active low \
  --reset-pc 0x80000000 --accept-platform-defaults
cp -R "$RVW_HOME/examples/picorv32/rvw/env" rvw/env
cp "$RVW_HOME/examples/picorv32/rvw/build-tests.sh" rvw/
cp "$RVW_HOME/examples/picorv32/rvw.toml" rvw.toml   # adds the isa suite
rvw/build-smoke.sh && rvw/build-tests.sh
git add rvw.toml rvw && git commit -m 'Add workstation project files'
```

`rvw init` reads the ports with Yosys. It found the `mem_*` valid-ready bus and
the `rvfi_*` ports. It tied `irq` and the `pcpi_*` inputs to zero. Use JDK 21,
sbt, Verilator, Yosys and the RISC-V GCC. The adapter is the generic RiscvSim
`MappedAdapter`; this folder holds no adapter code.

## Run

```sh
rvw regress run --tier full --rvfi-trace --out rvw/out/full --no-index --json
rvw cosim check --elf rvw/out/isa/add --trace rvw/out/full/isa/default/tests/add/rvfi.jsonl --json
rvw query build --config default
rvw query path mem_rdata mem_wdata
```

`build-tests.sh` compiles the RV32IM test copies in PicoRV32's `tests/` with
`rvw/env/riscv_test.h`. That header ends a test with a store to `tohost`
and uses no CSRs.

## Measured results (2026-11-13, macOS arm64, Verilator 5.049)

- `rvw regress run --tier full`: 46 pass (45 tests and the smoke program).
- `rvw cosim check`: 40 of 46 traces match Spike. Six (`lb`, `lbu`, `lh`,
  `lhu`, `sb`, `sh`) differ in `mem_rmask`/`mem_rdata` only: PicoRV32 reports
  a full-word read mask for byte and halfword loads. The checker compares the
  mask exactly. This is a cosim platform question, not a fixed core bug.
- `rvw query build`: 15444 signals, 1443 registers, one memory (`cpuregs`).
  `path mem_rdata mem_wdata` finds 4-stage register paths.
- `rvw run.sh identity` and the C1 `rtl_sha256` agree. The hash covers the
  generated wrapper, the defines and `picorv32.v`.

## Limits

- No interrupts are mapped (`ENABLE_IRQ=0`). No CSRs beyond the counters.
- C2 has trap records but no trap events, so cosim does not check `cause`.
- The query database is the Yosys navigation subset (see C6 in the contracts).
