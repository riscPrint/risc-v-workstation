# VexRiscv project example

This folder is a copy of the project files for an external VexRiscv checkout.
Install the workstation as described in
[Bring your own core](../../docs/BRING_YOUR_OWN_CORE.md). Set `RVW_HOME` to that
installation. Keep the core outside the workstation repository.

## Setup

From this folder, copy the project files into the core repository:

```sh
git clone https://github.com/SpinalHDL/VexRiscv "$HOME/projects/VexRiscv"
git -C "$HOME/projects/VexRiscv" checkout -b rvw-project baf7dc82f855eddaf5b0a20a6802c526f127e38a
cp rvw.toml "$HOME/projects/VexRiscv/rvw.toml"
cp -R rvw "$HOME/projects/VexRiscv/rvw"
cd "$HOME/projects/VexRiscv"
unset VEXRISCV RVW_PROJECT RVW_CORE
export RVW_PYTHON="$RVW_HOME/rvw/.venv/bin/python"
export RVW_LOCK_PYTHON="$RVW_PYTHON"
export RISCV_TESTS_SOURCE=/path/to/riscv-tests
rvw/build-tests.sh
git add rvw.toml rvw
git commit -m 'Add workstation project files'
```

Use JDK 21, sbt, Verilator, a C++ compiler and make. The build uses cached sbt
1.10.7, Scala 2.13.14 and SpinalHDL 1.15.0. It runs offline. The RISC-V compiler
default is `riscv64-unknown-elf-` on `PATH`.
Set `RISCV_PREFIX` to use another prefix. Build outputs are ignored by Git.
The adapter holds the `vex` lock through JVM exit. Scala builds also hold the
`sbt` lock. Native builds use at most four jobs and run with `nice`.

## Run from the core project

```sh
rvw regress list
rvw regress run --suite isa --filter '^rv32ui-p-' --rvfi-trace \
  --out rvw/out/rv32ui --no-index --json
rvw regress gate --tier quick --base-rev baf7dc82f855eddaf5b0a20a6802c526f127e38a \
  --cand-rev HEAD --json
rvw/run.sh run --elf rvw/out/programs/smoke --out rvw/out/smoke \
  --seed 1 --mem-latency 0 --rvfi-trace --json
rvw cosim check --elf rvw/out/programs/smoke \
  --trace rvw/out/smoke/rvfi.jsonl --json
rvw query build --config rv32im
rvw query info --json
rvw query where rvfi_rd_wdata --json
rvw query drivers rvfi_rd_wdata --json
```

`quick` selects `add`, `beq`, `lw` and `sw`. `full` selects 49 aligned RV32UI/UM
ISA tests and two local programs. `rv32ui-p-ma_data` requires misaligned access
support and is excluded. Gate acceptance covers only the selected tests.
Commit the workstation changes before the gate. A dirty harness cannot earn
acceptance. The gate selects core revisions through `VEXRISCV`; leave it unset
for normal use. The adapter defaults to its own core checkout.

## Design and limits

The core is RV32IM with M/S/U CSRs, simple instruction and data buses, 16 MiB of
RAM at `0x80000000`, and reset PC `0x80000000`. It has no caches, PMP, MMU or debug
unit. SATP stays bare. Interrupt inputs stay low. Misaligned data access traps.
The only configuration is `rv32im`.

The build compiles core sources and the generic RiscvSim sources in the adapter's
own target directory. This avoids the bundled BOOM `ProjectRef` in RiscvSim's
build. The database build uses SpinalDB through `ProjectRef`. Core build files
and core Scala sources are unchanged.

The smoke program matches Spike. The platform JSON declares absent PMP CSRs as
zero on reads with ignored writes. It declares ECALL `mtval=0x73`. The adapter
preserves those values. The comparator checks these exact outcomes. Wrong values
still mismatch. Full PMP behavior is outside this example because it has no PMP. The external project check passed
41 aligned RV32UI tests and a four-test committed gate with equal RTL hashes.
These simulator checks do not establish formal or hardware correctness.

RVFI uses upstream `FormalPlugin`. Trap events read actual CSR storage. Trace
capture checks order continuity but has no riscv-formal monitor. `--rvfi-check`
and Konata are refused. Completion requires a retired `tohost` store. ELF32,
the reset entry and RAM bounds are checked. The adapter loads captured ELF bytes.
Fixed memory latency applies to fetches and loads. Without it, the recorded seed
selects waits from zero to three cycles. Stores have no response channel.

Database extraction uses the same `VexTop` configuration. It captures the core
and adapter source roots. PDG, block and HGLDD exports are enabled. Export them with
`rvw query export pdg pdg.json`, `rvw query export blocks blocks.json.gz` and
`rvw query export hgldd VexTop.dd`. Navigation uses the direct graph. It remains
partial evidence: graph edges show possible structural influence. They do not
show the active cause in a cycle. The default PDG naming phase adds probe wires,
so its HGLDD requires the database RTL. For a plain simulation VCD, use a
separate database built with `rvw/build-db.sh rv32im plain/design.db --no-pdg`.
Keep that RTL separate from the PDG-named RTL. The launcher accepts the shared
SpinalDB options after `OUT`. These checks do not prove full ISA, privileged-mode,
interrupt, formal or hardware correctness.

## Adapter controls

From the workstation checkout:

```sh
VEXRISCV=/path/to/VexRiscv nice -n 10 rvw/.venv/bin/python -m pytest \
  examples/vexriscv/rvw/tests -q --basetemp=/tmp/cw-vex-pytest
rm -rf /tmp/cw-vex-pytest
```
