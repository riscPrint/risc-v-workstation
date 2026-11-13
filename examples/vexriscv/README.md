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

The core is RV32IM with M-only CSRs, simple instruction and data buses, 16 MiB of
RAM at `0x80000000`, and reset PC `0x80000000`. It has no caches, PMP, MMU or debug
unit. Supervisor CSRs, including SATP, are absent and trap on access. Interrupt inputs default to low. `--irq-schedule` can drive MSIP, MTIP
and MEIP. The adapter records changes in C2. See
[RiscvSim interrupt schedules](../../RiscvSim/README.md#interrupt-schedules). Misaligned data access traps.
The only configuration is `rv32im`.

The build compiles core sources in the adapter's own target directory.
It consumes the generic RiscvSim library through `ProjectRef`.
The library does not load a BOOM checkout. The database build uses SpinalDB through `ProjectRef`. Core build files
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

## Limit ownership

PMP/ECALL policy: [#11](https://github.com/riscPrint/risc-v-workstation/issues/11). RV32 architecture models: [#13](https://github.com/riscPrint/risc-v-workstation/issues/13). More-design validation: [#70](https://github.com/riscPrint/risc-v-workstation/issues/70).

Retained limit: The documented ISA, adapter and validation subset applies only to this example. It does not qualify other VexRiscv configurations.

## Cocotb component tests

The [cocotb example](cocotb/README.md) generates a small counter and the upstream
PMP address unit. It runs both with Icarus and Verilator through `rvw regress
cocotb`. The test bindings stay outside the generic library.

## SoC map

`soc.json` describes this example's simulation map and reference policies.
Run `rvw soc generate soc.json --out /tmp/vexriscv-soc --json` from this folder.
See the [format and limits](../../rvw/src/rvw/soc/README.md).
Pass `--soc-map DIR/sim-map.json` to `rvw/run.sh run` to use the generated RAM map.
The adapter saves the map and captures accepted instruction and data bus requests.

`isa.json` declares the adapter trace ISA and pins the opcode coverage source.
Extension versions remain null until verified. Use it with `rvw cov isa-check`
and `rvw cov functional --manifest`; see the coverage tool README. It does not
certify VexRiscv ISA compliance or change the adapter configuration.

## RTL event coverage

[The coverage example](rvw/coverage/README.md) samples typed fetch-interface
bins and a bounded request-to-response sequence. It uses plain VexTop RTL and
matching HGLDD. It also measures Scala attribution of native toggle points.
This interface exercise is separate from ISA regression coverage.

## Bounded RVFI checks

`formal/rvw.toml` selects the upstream riscv-formal `FormalSimple` RTL snapshot.
The snapshot has compressed instructions enabled. The checker uses RV32IC
for 2-byte PC alignment. It selects the 37 RV32I instruction checks and reg, pc_fwd, pc_bwd, liveness,
unique and causal. This snapshot is separate from the RV32IM simulation core.
Run it with native tools and a new output directory:

```sh
RISCV_FORMAL=/path/to/riscv-formal scripts/with-lock.sh vex nice -n 10 \
  rvw/.venv/bin/rvw --project examples/vexriscv/formal/rvw.toml \
  formal riscv --out /tmp/vex-formal --timeout 120 --json
```

Read each C3 row in `results.json`. A timeout is inconclusive. A bounded PASS
is not a full ISA proof. The C4 verdict cannot accept a core revision.
Liveness uses a bounded simple-bus environment, including no traps.
It counts accepted fetches and loads. Stores need no response. Responses must
consume an outstanding request and arrive at least one cycle after acceptance.
A response and a new request can occur in the same cycle. Overlapping fetches
remain legal. Each command stall and each gap between owed responses has at
most four cycles. Responses return in request order because neither bus has
transaction IDs. Response data stays arbitrary. These assumptions apply only
to liveness. They do not model coherent memory or prove adapter conformance.
The counters cover the runner's maximum 200-cycle bound. The native environment
regression checks response legality and wait bounds. It also covers overlap,
simultaneous acceptance and response, stores, and queue drain:

```sh
scripts/with-lock.sh vex nice -n 10 rvw/.venv/bin/python -m pytest \
  examples/vexriscv/formal/tests/test_environment.py -q
```
See the [formal guide](../../rvw/src/rvw/formal/README.md) for scope and Sail
arithmetic model generation. Measured results belong in issue #63.

## Architecture models

[Minor and TimingSimple descriptions](rvw/arch/README.md) select RV32IM,
uncached physical RAM and the RV32 benchmark runtime. The C1 adapter publishes
live retirement events for a project-owned fitting plan. These models show
trends. They do not reproduce the core's exact timing.

### Tagged fetch coverage example

From `rvw/`, run the following command with `RVW_HOME` and `VEXRISCV` set:

```sh
../../../scripts/with-lock.sh vex nice -n 10 sbt 'runMain rvwvex.CoverageExample /tmp/vex-tagged /tmp/vex-plan.json'
```

`CoverageExample` adds a tagged fetch-accept signal without changing VexRiscv
sources. It emits an exact-instance `rvw.rtl-plan/1`. Its event domain is
speculative. Fetch acceptance does not establish instruction retirement.
The example binds the design identity to the emitted RTL SHA-256.
Sample the declared signals before each rising edge. Run `rvw cov rtl` on the
plan and those samples. The exporter does not collect samples by itself.

The cosim platform declares M-only privilege, no PMP, zero PMP CSR reads, and
instruction-valued `mtval` on ECALL. The adapter uses the same choices.

### CSR model selection

`rvw formal csr --model examples/vexriscv/csr.json --out out/vex-csr`
selects M-only scratch access data from the pinned standard catalog. Run this
from the workstation root. The model declares unknown `mscratch` reset storage and absent
`sscratch`. The safe program first writes zero to establish a known value. It generates the existing independent monitor and assembly tests.
The optional project plugin `CsrChecksPlugin` binds actual `CsrRead` storage,
accepted `onRead`/`onWrite` callbacks, and CSR read/write data. It checks
`mscratch` after the first accepted full write. The normal adapter does not
install it. Generate `model.json` with the command above, then run:

```sh
cd examples/vexriscv/rvw
"$RVW_HOME/scripts/with-lock.sh" vex "$RVW_HOME/scripts/with-lock.sh" sbt nice -n 10 sbt -batch \
  "runMain rvwvex.CsrChecksMain /tmp/vex-csr-rtl /absolute/generated/model.json"
```

Set `RVW_HOME` and `VEXRISCV` first. The generated RTL contains CSR assertions.
The report lists inserted checks. Generation does not prove the core. The
binding checks accepted M-mode scratch accesses only. Denied instructions,
aliases, other catalog CSRs and privilege transitions still need bindings.

To generate a minimal RVFI wrapper from port data, set `RISCV_FORMAL` to the
upstream checkout. Run `rvw formal rvfi-generate formal/binding.json --out OUT`
from this directory. The generated wrapper has unconstrained bus inputs.
Review its environment before a formal campaign. The existing
`formal/rvw.toml` and `formal/wrapper.sv.in` retain their separate bus assumptions.
## Live checkpoint probe

Run the project-owned probe with `RVW_HOME`, `VEXRISCV` and the native tool
environment set. It holds the `vex` lock. Each command starts a separate JVM.

```sh
examples/vexriscv/rvw/checkpoint-probe.sh /path/to/smoke /tmp/vex-save /tmp/vex-state.json save 8
examples/vexriscv/rvw/checkpoint-probe.sh /path/to/smoke /tmp/vex-resume /tmp/vex-state.json restore 8
cmp /tmp/vex-save/rvfi.jsonl /tmp/vex-resume/rvfi.jsonl
```

The first run saves state after eight retired instructions and runs to `tohost`.
The second run resets an empty native instance, installs the saved live state,
and executes only the suffix. It restores the C2 prefix and counters too.
The comparison includes all C2 bytes, including cycle numbers. The probe uses
fixed single-cycle responses and no interrupts. It saves pending fetch and load
responses, sparse RAM and the complete exposed synchronous RTL state. It has a
5000-cycle limit. It does not implement the generic Python snapshot port or C1
publication. The general adapter's random memory latency, SoC capture, ROI,
wave and coverage modes are outside this probe.

Native validation on 2026-11-13 used core revision
`a62c145aa042a5de874344e0a7683bd7c8c8c870`, SpinalHDL 1.15.0 and Verilator.
`test_checkpoint_probe.py` passed with a checkpoint after retirement 8 in the
RV32IM smoke program. The complete resumed C2 file equalled the original.
The generic register/RAM fixture also passed. BOOM validation, random-latency
continuation, native `--savable` serialization and throughput measurements
remain open under #346. This probe does not close that issue.

## Spike bootstrap transfer probe

Build the matched shim with `Cosim/build.sh`. With the native environment and
`RVW_HOME` and `VEXRISCV` set, run:

```sh
nice -n 10 rvw/.venv/bin/python -m pytest examples/vexriscv/rvw/tests/test_spike_bootstrap.py -q
```

The test captures Spike after ten retirements, including a changed `mscratch`.
It reads all GPRs and the complete declared 64 KiB RAM image. A fresh VexRiscv
instance executes a bootstrap from reset, then jumps to the saved PC. The C2
trace starts at that transfer point. The test compares the continuation against
the original Spike instance through the final `tohost` store. The bootstrap
uses `0x80008000` and replaces the reset instruction with a direct jump.
Programs must not use those reserved bytes after transfer. Counter equivalence,
pre-fetch readback, C1 integration and fresh-Spike import remain open.

## Per-retirement CSR capture

The RV32IM adapter captures actual `mscratch` storage for its single RVFI slot.
The C2/2 header declares `capabilities: ["csr"]` and `csr_snapshot: ["0x340"]`.
Each retirement carries that snapshot. This does not declare FP capture.
The checker compares defined bits and reports any synchronization of unspecified
reset bits. No other CSR snapshot is claimed. This example has no debug module,
so debug-entry comparison is not available.

`rvw/tests/test_csr_capture.py` checks two consecutive CSR values in native RTL.
The wiring compiles. Native timing validation is still required before this
capture can support an RTL CSR comparison claim.
