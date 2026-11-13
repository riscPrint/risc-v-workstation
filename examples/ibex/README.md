# Ibex SystemVerilog project

This project uses lowRISC Ibex v2.1.0 at
`38c070939183cc10940b66c8e9e04eeca6b65470`. The source stays outside this
repository. No Ibex source file is changed. The configuration has two pipeline
stages, slow RV32M, RV32C, a flip-flop register file, no instruction cache,
no security mode and no PMP. U-mode is present. The boot vector is
`0x80000080`. RAM is 1 MiB at `0x80000000`. The harness maps single-hart CLINT registers at `0x02000000` and a machine
external interrupt control word at `0x0c000004`. These are simulation devices.

## Setup

Set `RVW_HOME` to this workstation checkout. Set `IBEX_SOURCE` to a private
Ibex checkout. Set `IBEX_WORK` to a private output directory outside Git.
Set `RISCV_TESTS` to a pinned riscv-tests checkout. Put the RISC-V GCC,
Verilator, Yosys and this checkout's `rvw/.venv/bin` on PATH.

```sh
git clone https://github.com/lowRISC/ibex.git "$IBEX_SOURCE"
git -C "$IBEX_SOURCE" checkout --detach 38c070939183cc10940b66c8e9e04eeca6b65470
uv pip install --python "$RVW_HOME/rvw/.venv/bin/python" \
  'git+https://github.com/lowRISC/fusesoc.git@14dfc825ced58fe1fb343662fa80fc4fbd0fdc50' \
  'edalize==0.4.1' mako
cd "$RVW_HOME/examples/ibex"
nice -n 15 python rvw/prepare.py
rvw/build-tests.sh
"$RVW_HOME/scripts/with-lock.sh" ibex-ibex rvw/run.sh build
rvw regress run --suite isa --rvfi-trace --out "$IBEX_WORK/regress" --no-index --json
nice -n 15 "$RVW_HOME/Cosim/build.sh" "$IBEX_WORK/librvw_spike.so"
export RVW_SPIKE_SHIM="$IBEX_WORK/librvw_spike.so"
rvw regress cosim "$IBEX_WORK/regress" --platform rvw/platform.json \
  --out "$IBEX_WORK/cosim.json" --json
```

FuseSoC resolves the upstream file list and generic primitive wrappers.
`IBEX_WORK/hdl.json` records the ordered sources, include directories,
defines, parameters, harness and build flags. C1 identity hashes this manifest,
the preprocessed RTL, the harness and the native toolchain. Regression also
captures the resolved source tree. Build and run output stays outside Git.
The adapter rejects another source checkout until `prepare.py` is rerun.
It serves instruction and data requests with one-cycle responses. It supports
zero added memory latency and one simulation at a time. Unsupported CLI
options are errors. There is no wave capture or user IRQ schedule. The device model drives machine
software, timer and external interrupts. C2 records each input-level change.

## Trace decisions

C2 reads Ibex's RVFI output. Ibex starts order at 1. The exporter checks that
sequence and subtracts 1 for C2. Ibex leaves memory masks active on instructions
without a memory effect. The exporter gates read and write masks by the
instruction type. It retains `ibex_raw_mem_rmask` and `ibex_raw_mem_wmask`.
It does not change active mask or data values. It ends the trace when the
`tohost` store retires. It exports no CSR snapshots or trap-cause events.

The riscv-tests instruction profile uses `rvw/riscv_test.h`. It keeps upstream
test bodies and replaces the privileged bootstrap. It does not qualify Sm.
The ELF includes a boot jump so tests can keep their required alignment.
The original standard bootstrap is not used to claim instruction passes.
See [FINDINGS.md](FINDINGS.md) for limits and measured results.

## Measured results

| Check | Result on 2026-11-13 |
| --- | --- |
| Verilator | 5.052; native build passed |
| Committed riscv-tests instruction profile | 51/51 C1 passes: UI 42, UM 8, UC 1 |
| Strict Spike with the device harness | 51/51 complete matches; 14,596 retirements; zero synchronization and masks |
| Committed gate control | Accept, 51 tests compared |
| Committed harness fault | Reject, 51 new failures; fault removed |
| Fast Python set | 3,098 passed, 4 skipped, 8,096 deselected |

The platform enables misaligned scalar RAM accesses. The full strict batch
uses that policy. The gate fault changes a completed pass to
failure in the harness. It does not change Ibex. To repeat it, change
`finish=read(a);` to `finish=read(a); if(finish==1) finish=3;`, commit, and run
the ISA suite in a new directory. Compare clean and fault run directories:

```sh
rvw regress gate --tier full --rvfi-trace --base "$IBEX_WORK/committed"   --cand "$IBEX_WORK/fault" --out "$IBEX_WORK/gate.json" --json
```

## Whole-core navigation

Use Yosys from OSS CAD Suite with its matching slang plugin.

```sh
rvw query build --config default --out "$IBEX_WORK/design.db"
rvw query drivers --db "$IBEX_WORK/design.db" u_ibex_core.load_store_unit_i.data_req_o
rvw query loads --db "$IBEX_WORK/design.db" data_rdata_i --limit 10
rvw query path --db "$IBEX_WORK/design.db" --comb-only --max-paths 1 \
  u_ibex_core.data_req_o data_req_o
rvw query export --db "$IBEX_WORK/design.db" blocks "$IBEX_WORK/blocks.json"
```

| Measurement | Count |
| --- | ---: |
| Elaborated components | 41 |
| Signals | 41,387 |
| Assignments | 33,813 |
| Dependency edges | 153,516 |
| Registers, including aliases | 2,092 |
| Memories | 1 |

The import uses the simulation source list and include directories. It selects
`RV32M=ibex_pkg::RV32MSlow`, because slang requires the enum type. It omits
RVFI instrumentation. RVFI cross-module counter references cannot cross a
preserved module boundary. This does not remove the functional core.
Drivers and loads retain SystemVerilog file and line locations. The database
has conservative signal and whole-cell dependencies. It does not prove an
exact causal path. Use short paths and explicit limits on this large graph.
The block export is an artifact check. No rendered-view check was run.

The front end now ignores comments in its file-input guard. A comment that
mentions `$readmemh` does not read a file. Active file inputs and source
remapping remain refused. Five fast regression tests cover that boundary.

The short path has one data hop from `ibex_core.sv:67` to
`ibex_top.sv:63`. The LSU request driver resolves to a lowered `$buf`.
Its port has a declaration location. The lowered buffer has no statement
location. This is a source-navigation limit. This configuration exercises
packages, enum parameters and generate blocks. It does not establish general
SystemVerilog interface support.

## ACT4 machine and user profile

See [ACT4 setup](../../docs/ACT4.md). Fetch the pinned ACT4 revision into a
private directory. Install its dependencies there. Do not build in a reference
checkout. The profile retains the standard Sm bootstrap and all selected
self-checks. It selects RV32IMC, Zicsr, Zifencei, Sm and U. PMP is absent.

```sh
cd "$RVW_HOME"
git clone https://github.com/riscv/riscv-arch-test.git "$ACT4_SOURCE"
git -C "$ACT4_SOURCE" checkout --detach 56d40ab301dba23dd3104c17bd969afbaaea1931
rvw --project examples/ibex regress act4-build \
  --profile examples/ibex/rvw/act4/profile.json --checkout "$ACT4_SOURCE" \
  --out "$IBEX_WORK/act4"
rvw --project examples/ibex regress run --suite act4 --rvfi-trace \
  --out "$IBEX_WORK/act4-run" --no-index --json
rvw regress cosim "$IBEX_WORK/act4-run" --platform examples/ibex/rvw/platform.json \
  --out "$IBEX_WORK/act4-strict.json" --json
```

Use the ACT4 private virtual environment, its Ruby dependency and Sail 0.15.
The native run permits 500,000 cycles per ELF. A 50,000-cycle limit stops ten
large CSR sweeps before completion. The profile declares Ibex's fixed vectored
mtvec mode and 256-byte alignment. It also declares its implemented counters,
zero breakpoint mtval, read-only-zero MENVCFG FIOM and U-mode WFI when TW is
clear. The simulation devices bind machine software, timer and external IRQs.
Fast IRQs, NMI, debug, PMP and S-mode are not qualified.

| ACT4 group | ELFs | C1 passes |
| --- | ---: | ---: |
| I | 39 | 39 |
| M and Zmmul | 12 | 12 |
| Zca | 26 | 26 |
| Misalign | 9 | 9 |
| Zicsr and Zifencei | 7 | 7 |
| ExceptionsSm, ExceptionsU and ExceptionsZc | 6 | 6 |
| InterruptsSm | 14 | 14 |
| Sm | 27 | 27 |
| U | 8 | 8 |
| Total | 148 | 148 |

These are conclusive C1 program passes on the declared configuration. They do
not establish complete strict Spike agreement or architectural qualification.

| ACT4 reference comparison | Result |
| --- | --- |
| Strict Spike | 0 complete matches; 148 mismatches; zero synchronization and masks |
| Common first difference | Order 34, `csrr s0,mtvec`: Ibex `0x80000001`, Spike `0x0` |

The boot logic initializes mtvec from `boot_addr_i[31:8]` in vectored mode.
Spike starts mtvec at zero. The strict comparison stops at this first
difference. It does not verify the remaining ACT4 instruction stream.
Sail-generated self-checks and strict Spike agreement are separate results.
No CSR mask or reset synchronization was added to obtain a match.

The following smaller program isolates that reset-state difference:

```sh
mkdir -p "$IBEX_WORK/repro"
nice -n 15 riscv64-unknown-elf-gcc -march=rv32imc_zicsr_zifencei -mabi=ilp32 \
  -nostdlib -nostartfiles -T examples/ibex/rvw/link.ld -Wl,--build-id=none \
  examples/ibex/rvw/boot.S examples/ibex/rvw/mtvec-reset.S \
  -o "$IBEX_WORK/repro/mtvec-reset"
rvw --project examples/ibex regress run --suite mtvec-reset --rvfi-trace \
  --out "$IBEX_WORK/mtvec-reset-run" --no-index --json
rvw regress cosim "$IBEX_WORK/mtvec-reset-run" --platform examples/ibex/rvw/platform.json \
  --out "$IBEX_WORK/mtvec-reset-strict.json" --json
```
