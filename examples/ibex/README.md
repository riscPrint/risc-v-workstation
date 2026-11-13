# Ibex SystemVerilog project

This project uses lowRISC Ibex v2.1.0 at
`38c070939183cc10940b66c8e9e04eeca6b65470`. The source stays outside this
repository. No Ibex source file is changed. The configuration has two pipeline
stages, slow RV32M, RV32C, a flip-flop register file, no instruction cache,
no security mode and no PMP. U-mode is present. The boot vector is
`0x80000080`. RAM is 1 MiB at `0x80000000`. There are no MMIO devices.

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
options are errors. There is no wave capture or interrupt schedule.

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
| Initial strict Spike batch | 50 matches; ma_data differs under the default alignment-trap policy |
| Corrected ma_data platform | Complete strict match, 344 instructions, zero synchronization and masks |
| Committed gate control | Accept, 51 tests compared |
| Committed harness fault | Reject, 51 new failures; fault removed |
| Fast Python set | 3,098 passed, 4 skipped, 8,096 deselected |

The platform now enables misaligned scalar RAM accesses. A fresh full strict
batch uses that policy. The initial batch and the corrected single-test run
remain separate observations. The gate fault changes a completed pass to
failure in the harness. It does not change Ibex. To repeat it, change
`finish=read(a);` to `finish=read(a); if(finish==1) finish=3;`, commit, and run
the ISA suite in a new directory. Compare clean and fault run directories:

```sh
rvw regress gate --tier full --rvfi-trace --base "$IBEX_WORK/committed"   --cand "$IBEX_WORK/fault" --out "$IBEX_WORK/gate.json" --json
```
