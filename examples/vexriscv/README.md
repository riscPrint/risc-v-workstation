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
## Counter event bindings

`HpmChecksPlugin` is an optional project plugin. It reconstructs the actual
64-bit `mcycle` and `minstret` storage from the CSR plugin read mappings.
Its independent reference counts core clock samples and last-stage `isFiring`
events. It does not derive events from observed counter deltas. RV32 low/high
software writes use masks. Unselected bits retain concurrent increment/carry.
The binding requires the existing writable machine counter interfaces and no
debug stopcount. It does not change the normal adapter configuration.

Set `RVW_HOME` and `VEXRISCV`. From `examples/vexriscv/rvw`, run:

```sh
"$RVW_HOME/scripts/with-lock.sh" vex "$RVW_HOME/scripts/with-lock.sh" sbt nice -n 10 sbt -batch \
  "runMain rvwvex.HpmChecksMain /tmp/vex-hpm-rtl"
```

The output contains assertions and an inserted-check report. Elaboration is
not a simulation campaign or architectural retirement proof. Programmable HPM
events, privilege filtering, interrupts and overflow campaigns remain open.

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
reset bits. The default capture selects only this CSR. This example has no debug module,
so debug-entry comparison is not available.

`rvw/tests/test_csr_capture.py` checks two consecutive CSR values in native RTL.
Native timing validation passed on 2026-11-13. The capture reads the single
actual RVFI slot. It does not establish timing for a core with multiple slots.
## Reverse replay on the live bridge

`rvw/checkpoint_port.py` implements the existing snapshot-port interface for
this probe. The native test builds a manifest, captures retirement 8, reverses
from instruction 15 to instruction 10, then compares the full saved state with
an independent from-reset checkpoint at instruction 10:

```sh
nice -n 10 rvw/.venv/bin/python -m pytest examples/vexriscv/rvw/tests/test_reverse_port.py -q
```

The existing `rvw sim checkpoint` and `rvw sim reverse-step` commands accept
that manifest. Each replay starts a new process and restores live state before
forward execution. Clock cycles, all exposed registers, RAM, pending bus
responses and the C2 prefix remain in the payload. The port has no C1 resume
publication and does not provide an interactive debugger session.

Use `RVW_VEX_LOCK=vex-NAME` with a private `VEXRISCV` copy when the shared
core lock is busy. The checkpoint launcher uses that lock name and bounds
native make jobs through the common launcher.

Native reverse validation found two missing synchronous register-file read
buffers in the first bridge inventory. The bridge now makes those buffers
explicit before state capture. It also checks the restored inventory before
execution. A fresh process port reports a stopped boundary before its first
restore. Full replayed state at retirement 10 matched an independent reset run
on 2026-11-13 with private core revision
`a62c145aa042a5de874344e0a7683bd7c8c8c870`.

## Arcilator and Verilator C1/C2 probe

`rvw/engine-probe.py` runs captured `VexTop` RTL through the generic scalar
model API. Generate the RTL with the normal private project build or use its
captured `rtl/VexTop.v`. Keep it beside the run identity. Select the matching
RV32IM smoke ELF. Install CIRCT with `scripts/install.sh --with-arcilator`.
Set `RVW_CIRCT` to that install. Source the native Verilator environment.

```sh
scripts/with-lock.sh vex-simsrv nice -n 10 rvw/.venv/bin/python \
  examples/vexriscv/rvw/engine-probe.py --backend arcilator \
  --rtl /path/to/VexTop.v --elf /path/to/smoke --out /path/to/new-arc --seed 7
scripts/with-lock.sh vex-simsrv nice -n 10 rvw/.venv/bin/python \
  examples/vexriscv/rvw/engine-probe.py --backend verilator \
  --rtl /path/to/VexTop.v --elf /path/to/smoke --out /path/to/new-verilator --seed 7
cmp /path/to/new-arc/rvfi.jsonl /path/to/new-verilator/rvfi.jsonl
```

The adapter writes C1 `result.json` and C2 `rvfi.jsonl`. A retired `tohost`
store determines pass or fail. Seeded bus-ready choices use the same sequence
on each engine. Memory responses have one-cycle latency. The probe refuses
traps and stores outside RAM. It has a cycle bound and no interrupt stimulus.
Its port names and address map stay in this example. Build errors and missing
tools return inconclusive. It does not replace the production Scala adapter.

On 2026-11-13, CIRCT `firtool-1.163.0` and Verilator 5.049 ran the captured
private VexRiscv RV32IM core at `a62c145aa042a5de874344e0a7683bd7c8c8c870`.
Both passed 17 retired instructions in 81 cycles with seed 7. Complete C2
files were byte-identical. This includes all observed fields, cycle numbers
and the end event. RTL SHA-256 was
`85901d3da9d45c0860bfa29a902d51fede05d2f7a53e85de805168e4f513a555`.
The two short runs do not establish a speed change, ISA correctness or BOOM
support. Medium/large BOOM, interrupts, CSR snapshots, waves, runtime effects
and native checkpoint support remain outside this probe.
## Native ISA co-simulation result

On 2026-11-13, the private core at
`a62c145aa042a5de874344e0a7683bd7c8c8c870` passed all 49 aligned ISA programs.
`rvw cosim check` matched all 49 complete traces against Spike: 41 RV32UI
programs and 8 RV32UM programs, with 17,735 compared instructions in total.
The run used `rv32im`, seed 1, fixed memory latency 0 and a 200,000-cycle limit.
It used the declared `rvw/platform.json` settings without added CSR masks.
Each trace synchronized the unspecified initial `mscratch` value once.
No counter, MMIO or interrupt synchronization was applied in this campaign.
`rv32ui-p-ma_data` remains excluded because this configuration traps on
misaligned data access. These results cover this configuration and these ELFs.

Use a private core copy for concurrent native work. Set `VEXRISCV` to that
copy. Set `RVW_VEX_LOCK=vex-cosim` for the normal run launcher. Set
`RISCVSIM_WORK` to a directory in the private worktree to keep native build
outputs there. The default lock remains `vex`.

For a `run-many` JSONL manifest with absolute `elf` and `out` paths, set
`rvfi_trace` to true, `mem_latency` to 0 and `max_cycles` to 200000 in each job.
Run the manifest, then compare every saved trace:

```sh
examples/vexriscv/rvw/run.sh run-many --manifest jobs.jsonl --jobs 1 --json
rvw/.venv/bin/python examples/vexriscv/rvw/check-isa.py jobs.jsonl summary.json
```

The comparison script saves every original C5 report, its input identity and
its exit code. It returns failure for an empty campaign, an incomplete trace,
a mismatch or missing evidence.

## Whole-core four-state reset probe

Run the captured core Verilog with native Icarus:

```sh
scripts/with-lock.sh vex-simsrv nice -n 10 rvw/.venv/bin/python \
  examples/vexriscv/rvw/four-state-probe.py --rtl /path/to/VexTop.v \
  --elf /path/to/smoke --out /path/to/new-four-state-run
```

The testbench applies X on reset for two falling edges. It then applies a
known asserted reset for five falling edges and runs the smoke ELF from RAM.
A retired `tohost` store of 1 is required. The script records the RTL, ELF and
testbench hashes, Icarus version, cycle bound, return code and X observations.
It checks unknown RVFI validity after reset, instruction/control fields,
selected register values and memory values selected by active byte masks.
Unused memory read/write data fields are counted separately.

On 2026-11-13, Icarus 14.0 devel at `s20251012-154-g50ca27fdf` completed
17 instructions in 60 cycles on the same captured RTL used by the Arcilator
probe. It observed two reset windows with unknown retirement outputs, zero
unknown values in the checked active retirement fields, and 16 unknown
inactive memory-data observations. A second test injected X into
`rvfi_rd_wdata`. The checker rejected that run. Both native tests passed.

These inactive unknowns are unselected RTL values. They do not establish
X-pessimism. Ordinary Icarus procedural `if` semantics can be X-optimistic.
This probe does not implement pessimistic X propagation or compare all binary
concretizations. It shows recovery after the explicit known reset for this
program. It does not prove that arbitrary reset release or unknown state is
safe. BOOM, gate-level timing and a production four-state C1 adapter remain
outside this probe.
## Native DPI lockstep

Set `RVW_COSIM_DPI=1` to expose the generic DPI mailbox and link its C++ client
into the Verilator harness. Run `rvw cosim live --lockstep` with `rvw/run.sh`
as the simulator command. Keep `--rvfi-trace` enabled. Each C2 record blocks
until Spike checks it. The end record is sent before the native model closes.

`rvw/tests/test_lockstep_native.py` passed on 2026-11-13 with the private core
revision recorded above. The clean six-instruction program matched completely.
`RVW_COSIM_FAULT_ORDER=1` flipped bit 0 of the observed GPR writeback at order 1.
Spike reported the first `rd_wdata` difference at that order. The saved C2
prefix contained only orders 0 and 1. This is an explicit adapter fault. It does
not claim to test every RTL fault. Both controls default to off.

Run the overhead probe with the native environment, private core and lock set:

```sh
rvw/.venv/bin/python examples/vexriscv/rvw/measure-lockstep.py rvw/out/dpi-overhead
```

The probe warms both paths, then alternates two baseline runs and two checked
runs. Both paths use the same DPI-enabled RTL, fixed memory latency and trace
capture. It saves `details.execution_s` from C1. This time includes adapter and
artifact work but excludes model setup. Startup time is not a DPI throughput
measurement. Interrupt synchronization has a separate validation scope.

Measured on 2026-11-13 on the shared macOS arm64 host, with the private core
revision above, SpinalHDL 1.15.0 and Verilator 5.049:

| Measured pair | Baseline execution | DPI checked execution |
|---|---:|---:|
| 1 | 1.826 s | 10.178 s |
| 2 | 3.178 s | 27.198 s |

Each run retired 6,006 instructions in 24,026 cycles. All four measured traces
matched Spike completely. Total checked execution time divided by total
baseline execution time was 7.47. These measurements were refreshed after
the post-edge CSR sampling change. The first baseline and checked runs were
excluded as cache warmups. Each trial starts a fresh native process and includes
its own execution-time JIT work. This is adapter overhead for this loop on a
shared host with other active workers. It is not a stable host benchmark,
a universal slowdown factor or a measurement of hardware speed.

## Native interrupt synchronization

The DPI adapter samples the trap, RVFI record and CSR snapshot before it sends
any C2 event. This prevents a transport call from advancing simulation time
between those signal reads. RVFI order continuity remains mandatory.

The native MSIP and MTIP controls initialize `mtval` to zero. Each asserts its
input at cycle 200 and deasserts it at cycle 220. The handler checks the actual
`mcause`, disables the interrupt, sets `mepc`, executes `MRET` and reports through
`tohost`. The controls require complete Spike matches and actual C2 input,
trap, handler and return records. Run them with the private native environment:

```sh
nice -n 10 rvw/.venv/bin/python -m pytest examples/vexriscv/rvw/tests/test_lockstep_interrupts.py -q
```

The pinned core retains `mtval` on interrupt entry. Its CSR plugin writes that
register on exceptions only. Negative controls set `mtval=7` before the same
MSIP and MTIP inputs. Spike expects zero at the interrupt trap; RTL reports 7.
The comparator must report that mismatch. No CSR mask or fabricated trap value
is used. Zero initialization is an explicit positive-control precondition.
These controls do not establish general interrupt correctness or remove the
retained-`mtval` limit.

Native validation on 2026-11-13 passed all four controls. The two positive
runs each matched 50 instructions, one interrupt trap and a complete trace.
The two negative runs each stopped at the interrupt trap with `tval`: expected
0, actual 7. Input deassertion at cycle 220 was present in both complete traces.
The core revision was `a62c145aa042a5de874344e0a7683bd7c8c8c870`.

## Native history bisect

The [history recipe](rvw/history/README.md) executes real historical
`VexTop.scala` revisions with captured per-revision project adapters. Native
`rvw bisect` identified the expected M/S/U-to-M-only change at `6c891a76`.
Both adjacent endpoints were checked. The older configuration passed the
supervisor-CSR compatibility program. The newer configuration deliberately
failed that old expectation. C1 records the selected adapter and source hashes.
This is a known compatibility transition, not a new core bug or BOOM result.
## Full machine CSR capture

Set `RVW_VEX_CSR_FULL=1` to capture every readable machine CSR in this adapter's
CSR mapping. The C2 header declares the exact address set. Each retirement
contains every declared value. The probe reads actual mapped CSR fields and
fills unmapped bits with zero, as the core's CSR read path does. It does not
copy expected values from Spike. The default remains the validated `mscratch`
capture. The setting is part of project inputs and replay.

The set includes machine status, ISA, interrupt enable and pending state,
trap vector, scratch, exception PC, cause, trap value, both RV32 halves of
cycle and retirement counters, and the four machine identity registers.

This is a capture capability. Full machine-CSR equivalence with Spike is not
claimed. The core has unspecified reset storage for `mepc`, `mcause` and
`mtval`, different identity and trap-vector reset values, and a cycle counter driven by RTL clocks.
The current reference snapshot comparison checks exact values and will expose
these differences. No broad mask or reference-state overwrite is added.

Run the native timing and inventory test with the private core environment:

```sh
nice -n 10 rvw/.venv/bin/python -m pytest examples/vexriscv/rvw/tests/test_csr_capture.py examples/vexriscv/rvw/tests/test_full_csr_capture.py -q
```

Native validation on 2026-11-13 passed the default and full-capture tests.
The full test checked all 17 declared machine CSR addresses over 17 retirements.
It checked consecutive `mscratch` writes of 7 and 9 without a read between them.
It also checked `mtvec`, `mepc` and `mtval` write/read timing and the four actual
identity values. For this no-trap program, every snapshot had `mcycle=cycle`
and `minstret=order+1`. Both high counter halves were captured. Counter rollover
and software counter writes were not exercised. The RVFI record is sampled at
the firing edge; CSR storage is sampled after that edge settles.

## Native build profile measurements

The [profile campaign](rvw/profiles/README.md) runs flat, ccache cold/warm,
2-thread, 4-thread, hierarchical and compiler PGO capture/reuse builds on the
same captured core. All eight passed the seeded smoke with complete C2 bytes
equal to the independent Arcilator reference. The README includes build time,
execution/trace time, child-process RSS, cache counters and a build-time chart.
These short samples qualify the profile plumbing. They do not qualify a
runtime speed improvement or a BOOM preset. Defaults remain unchanged.
## Sail adjudication

Set `RVW_VEX_CSR_CAPTURE=0` to capture C2/1 for the common GPR, memory and trap
scope. This setting does not remove fields from an existing trace. It selects
a fresh native capture and is recorded in project inputs and replay. The
default remains CSR capture. Sail cannot observe the default CSR snapshots;
that input must remain inconclusive rather than being silently downgraded.

The platform selects `sail_reference_isa=rv32im_zicsr_zifencei`. Sail rejects
counter and MMIO reads. This profile has no CLINT time source. Spike keeps its
separate declared reference ISA. Both effective instruction selections are
checked. Sail uses M-only privilege, zero usable PMP entries, read-only MISA.M
and direct trap vectors. Native PMP controls checked actual zero reads and
ignored writes against both references.

The example's declared ECALL `mtval=0x73` is an exact platform policy. Raw Sail
writes zero. The comparator checks the exact declared event value and records
`ecall_tval` in `recent_quirks`. It does not take arbitrary trap bits from RTL.
Sail's internal CSR state is not fabricated. A later `mtval` read is refused
until an independent full CSR write or another trap restores common state.
The reference report states this limit. This is not a raw, unmodified-Sail
trap-value match or a full machine CSR equivalence claim.

After native `run-many` with the selected capture, save both reference reports:

```sh
rvw/.venv/bin/python examples/vexriscv/rvw/check-isa.py --adjudicate jobs.jsonl adjudication.json
```

On 2026-11-13, all 49 aligned ISA programs passed natively. Each complete
C2/1 trace matched Spike and Sail 0.15 under the stated profile: 17,735
instructions per reference, zero synchronizations and no applied bit masks.
Sail recorded the exact ECALL policy quirk once per program. The reports retain
both references and their captured input identities. They do not vote away a
disagreement. Native controls also checked a changed GPR result, a refused
post-ECALL `mtval` read and an independent overwrite that restores comparison.

A separate zero-ECALL-value profile was also checked on the real `add` trace.
Both references reported the actual `0x73` trap value as a mismatch against
zero. The declared policy is therefore part of these results, rather than a
claim of standard zero-valued ECALL behavior.

## Native instruction and IRQ reduction

[The reduction recipe](rvw/reduction/README.md) runs the existing `rvw reduce`
instruction and IRQ modes on captured whole-core RTL. Native trials reduced
eight replaceable instruction slots to one and six removable IRQ events to
one. Both have a passing empty control and a fresh failing confirmation.
C1 and complete C2 files are validated for every reported trial. These are
deliberate failing fixtures. They do not identify a new core defect.
## Native RVVI round trip

The native round-trip test exports real VexRiscv C2 to RVVI-TEXT 0.5 and imports
it again. The `rvw.c2` STATE extension preserves fields that this RVVI subset
does not express directly. The test requires equality of all decoded C2
records, including source metadata, IRQ/trap events and CSR values. It does
not require identical JSON whitespace or claim an independent check from a
format conversion.

On 2026-11-13, both native controls passed: the default one-CSR capture and the
full 17-CSR capture. Each had nine retirements and an actual ECALL trap. The
restored default trace matched Spike with the same instruction count as the
original. The restored full-CSR trace retained the same real reference-model
differences as the original. Neither conversion turned those differences into
a match. The importer also rejects contradictions in RVVI timing, hart, order,
mode, parameters and IRQ NET data against the saved C2 state.

```sh
nice -n 10 rvw/.venv/bin/python -m pytest examples/vexriscv/rvw/tests/test_rvvi_native.py -q
```

The current generic harness has no DMI endpoint. This VexRiscv configuration
has no debug unit. Debug-halt comparison with the reference Debug Module path
was NOT RUN. A format round trip does not establish debug support.

## Native server lifecycle controls

`rvw/tests/test_server.py` under this example runs a cycle timeout and a
failing ELF before repeated passing ELFs. It compares the passing C2 bytes
with a fresh process and a persistent batch. `rvw/tests/test_server_cancel.py`
observes retirement in a second ELF before it cancels the launcher. Both
use the private `RVW_VEX_LOCK` setting. C1 records the native JVM PID, which
the tests check after teardown. See
[the generic limits](../../RiscvSim/README.md#native-server-teardown-observation)
and [the native sample](rvw/server-lifecycle.json). These controls do not
establish complete device reset coverage or a thread count between requests.
### CSR and HPM monitor execution

`rvw/tests/formal/test_vex_generated_checks.py` runs generated `mscratch` and
absent-`sscratch` programs, plus `csr-check-events.S`, on Spike and native
VexRiscv with the CSR and HPM plugins installed. Select a private external
checkout with `VEXRISCV`. Set `RVW_VEX_CHECKS_LOCK` to its private lock name.
Source the native tool environment first. Run the slow module directly:

```sh
rvw/.venv/bin/python -m pytest rvw/tests/formal/test_vex_generated_checks.py -q
```

The native entry is `rvwvex.CsrChecksRuntime model.json OUT MODE ELF...`.
Modes are `none`, `csr`, `hpm` and `hpm_read`. The last three modes seed observation faults.
They leave core storage and program instructions intact. A seeded run succeeds
only when the required monitor fires. Its `rvw.checks-run/1` report retains
status `fail`. A clean run requires program success and zero firing checks.
The driver also requires executed scratch and counter instructions. Each
native invocation has a 110-second limit in the slow test. Missing tools or
external sources cause a skip, which supplies no execution evidence.

The counter program writes both RV32 halves, crosses low-half wraparound and
reads user aliases from M mode. Its Spike reference enables Zicntr. This is
an M-only, no-debug example. It does not qualify privilege filters, programmable
HPM events, AIA behavior, general CSR aliases or physical hardware.

The HPM binding compares machine and user-alias read responses against its
independent expected counter. It checks both RV32 halves. `hpm_read` corrupts
only the observed read response. It must fire all four read monitors during
the counter program. Clean execution requires all nine CSR/HPM monitors to
remain clear. The program must execute at least eight counter-half reads.
These aliases are exercised from M mode. Lower-mode counter-enable rules
and programmable event selectors remain outside this example.

## Cached configurations

Two extra configs use the upstream caches. Neither changes the core sources; both live in
`rvw/src/main/scala/rvwvex/CachedConfig.scala`. `rv32im` stays the default.

| Config | Plugins | Suite |
|--------|---------|-------|
| `rv32im_cached` | `rv32im` with `IBusCachedPlugin` and `DBusCachedPlugin` (`GenFullNoMmu` caches: 4 KiB, 32-byte lines, 1 way; write-through data cache, no allocation on a store miss), `StaticMemoryTranslatorPlugin` (0xF0000000 and up uncached) | `isa-cached` |
| `rv32ima_linux` | the same caches with LR/SC and AMOs, `MmuPlugin` (Sv32, 4-entry port TLBs), M/S/U CSRs | `isa-linux` |

`DBusCachedPlugin` does not feed the RVFI memory fields. `CachedFormalPlugin` rebuilds them
at write-back from the plugin's stage values (address, masks, store data, load word in its
lanes, the AMO result and SC success). `CachedBuses` answers the cache buses: one
outstanding refill per bus, one word per cycle after the run's memory latency; data-cache
writes are single words without a response. The cached configs accept bare RAM only (no
`--soc-map`). Build `rv32ua-p` ELFs with `rvw/build-tests.sh` (it now builds `ua` too).
Compare `rv32ima_linux` traces with `--platform rvw/platform-linux.json` (M/S/U, RV32IMA).

Measured 2026-11-13 with the private core copy, seed 1 or 7, `rvw cosim check` against Spike:

| Config | Programs | Memory latency | Runs | Spike | Compared instructions |
|--------|----------|----------------|------|-------|-----------------------|
| `rv32im_cached` | 49 rv32ui/um-p | 0 | 49 pass | 49 match | 17,735 |
| `rv32im_cached` | 49 rv32ui/um-p | seeded 1..4 | 49 pass | 49 match | 17,735 |
| `rv32ima_linux` | 59 rv32ui/um/ua-p | 0 | 59 pass | 59 match | 24,919 |
| `rv32ima_linux` | 59 rv32ui/um/ua-p | seeded 1..4 | 59 pass | 59 match | 24,919 |

The 49 programs took 58,603 cycles on `rv32im_cached` at latency 0.
`rv32ui-p-ma_data` stays excluded: these configs trap on misaligned data access.

## Probes

`rvw/src/main/scala/rvwvex/ProbePlugin.scala` attaches
[SpinalProbes](../../SpinalProbes/README.md) to existing VexRiscv signals. It changes no core
source and adds no hardware unless the run uses C1 `--probes`.

| Probe | Signals |
|-------|---------|
| `branch vex_static` | write-back firing, `BRANCH_CTRL != INC`; predicted = `BRANCH_DO xor BRANCH_COND_RESULT` (STATIC prediction) |
| `stage D/X/M/W`, `flush *_remove`, `retire wb` | stage `isValid`, `removeIt`, write-back `isFiring`; one ID per instruction that leaves decode |
| `stall` (evidence `inferred`) | stage `haltItself` and `haltByOther`, split by instruction class; an empty decode stage is `fetch/empty` |
| `counter` | cycles, retired, branches, mispredicts (HPM 3), loads (HPM 4), stores (HPM 5), wait and flush cycles |
| `interruptTaken irq` | registered CSR jump strobe with `mcause` and `mepc` |
| `bus ibus`, `bus dbus` | accepted `iBus`/`dBus` commands (`cmd.fire`): address; data bus also write, data, mask, size |
| `csrWrite csr` | `csrMapping.onAnyWrite` strobe (the plugin's `writeEnable`), instruction bits 31..20, `writeDataSignal` |

Results on VexRiscv `baf7dc82` (core sources), `rv32im` config, seed 1, random memory timing:

```sh
examples/vexriscv/rvw/run.sh run --elf rvw/out/programs/branches --out RUN --probes --rvfi-trace
rvw probes convert RUN/probe-events.jsonl --to bp-events --c2 RUN/rvfi.jsonl --out RUN/bp.jsonl
rvw csim compare-rtl rvw/probes/btfn.json --trace RUN/rvfi.jsonl --events RUN/bp.jsonl
```

- `branches` (35659 instructions, 195928 cycles): 9002 branch events, 6001 conditional.
  `btfn.json` agrees with the core on all 6001 directions (3355 misses each).
  `gshare.json` (1024 entries, 10 history bits) agrees on 44.3 % and misses 1199 times
  (33.6 MPKI against the core's 94.1).
- `rvw probes convert --to kanata` then `rvw perf` gives IPC 0.182, with an exact cycle
  and instret match to `result.json`; 160269 cycles have an empty decode stage (inferred
  `fetch/empty`).
- `irqs` with `--irq-schedule '1:0x0,2000:0x80,2200:0x0,4000:0x800,4200:0x0,6000:0x80,6200:0x0'`:
  `--to interrupts` finds 3 probe events and 3 C2 interrupts, consistent. `--to counts` and
  `--to hpm` give the counter totals (3 HPM bindings).
- `memcsr` (382 instructions, 1855 cycles): `--to bus` is consistent: 61 bus writes match the
  61 retired C2 stores one to one by bytes and values, and 60 bus reads cover the 60 loads with
  no unretired read. `--to csr-writes` is consistent: 123 write events, 122 retired CSR writes,
  122 values checked from C2 operands. One event is the write strobe of the illegal
  `csrw satp`, which then traps (C2 trap event, cause 2). `--to hpm` gives 60 loads and
  61 stores. `rvw cosim check` against Spike matches, with the per-slot `mscratch` snapshot
  on all 382 steps.
- Fault sites: `Probe.faultSite("mscratch", ...)` gives `CsrPlugin_mscratch` (32 bits) through
  `--to fault-sites`. `rvw fault plan --sites` (flip, stuck1, window 100:1700, 4 samples,
  seed 7) and `rvw fault run` on `memcsr`: 4 of 4 injected, 4 `silent_corruption` (the
  program reads `mscratch` back and does not check it).
- OoO calibration: `--to counts` for `branches` (training) and `smoke` (held out), with
  `rvw/probes/ooo/vex-inorder.json` and `event-map.json`. `rvw arch ooo-calibrate` reports
  `retired` and `branches` equal to the probe counters. Mispredicts on `branches`: model
  7854, core 4855 (the model predicts the sequential PC; the core uses static BTFN). IPC
  error 224.5 % and 105.2 % (the core's fetch is slow). Accuracy stays `inconclusive`
  (two samples).
- No cache probes: this config has no caches (`IBusSimplePlugin`, `DBusSimplePlugin`), so the
  cache observer has no input. A cached config would change the bus type that the other
  example tools drive.

The first BTFN comparison found one disagreement at the loop exit. The C2 trace converter
wrote the fall-through as the target of a not-taken branch, so the model's BTFN rule saw
a forward branch. The converter now writes the decoded target (see `docs/contracts/csim.md`).

Synthesis safety: run `rvwvex.ProbeSafety` from the adapter classpath. It elaborates the
core with and without `ProbePlugin` (probes off) and compares the Verilog SHA-256; it exits 1 when
they differ. Measured identical on 2026-11-13.

## Live UART, CLINT and PLIC

`live-devices.json` supplies uncached MMIO regions, UART input bytes and the
interrupt routes. The generic Scala harness models UART RX and TX, its 16-byte
RX FIFO, CLINT MSIP/MTIME/MTIMECMP and one PLIC context. The adapter connects
MSIP, MTIP and MEIP to the real core pins. Each run gets fresh device state.

`rvw/programs/device-echo.S` enables all three interrupts. Its handlers clear
MSIP, move the timer deadline, claim the UART source, echo the RX bytes and
complete the PLIC claim. It reports success only after all three handlers run.
The native test requires C2 traps for all three causes and exact echoed bytes.
Run it with the private core and native environment:

```sh
RVW_HOME=$PWD VEXRISCV=/path/to/private/VexRiscv RVW_VEX_LOCK=vex-simsrv \
  nice -n 10 rvw/.venv/bin/python -m pytest \
  examples/vexriscv/rvw/tests/test_live_devices.py -q
```

C1 captures the map and `details.device_output`. No IRQ schedule is used for
this test. UART baud timing, modem inputs, multi-hart PLIC contexts remain unsupported. The checkpoint harness can save
these device models at a settled boundary.

Native sample on 2026-11-13: both echo runs passed at 4,079 cycles with 868
retirements. Both traces contain MSIP, MTIP and MEIP traps and have the same
SHA-256. The intervening no-RX control reached its 20,000-cycle limit and
produced no UART output. See [the recorded sample](rvw/live-device-results.json).
The sample used a direct captured JVM launch after compiling the adapter in
an isolated directory. The standard launcher test was cancelled in the sbt
queue. This sample does not qualify device snapshots.

## FreeRTOS RTL boot and resume

The [FreeRTOS payload](rvw/freertos/README.md) builds a pinned V11.2.0 kernel.
It runs two tasks with timer-driven delays on this M-mode RTL configuration.
The project checkpoint harness now saves UART, CLINT and PLIC state with RTL,
RAM, pending bus responses and the C2 prefix. Restore runs in a fresh process.
This is a real RTOS workload. It does not establish Linux or OpenSBI support.
## Connected generated check campaign

Build ISA ELFs with `rvw/build-tests.sh`. Use a private `VEXRISCV` checkout.
Run `rvw/.venv/bin/python examples/vexriscv/rvw/qualify-checks.py --out NEW_DIR`
from the workstation root with the native environment active. The runner uses
locks `vex-csr` and `sbt-csr`, nice priority 10 and a 240-second timeout.
It excludes the misaligned-data test, as the existing aligned ISA suite does.

The optional `RVW_CHECKS_ISA=1` runtime installs all available SpinalChecks
rules plus the existing scratch and HPM bindings. It compiles assertions with
Verilator `--assert`. It writes `c1_N.json` and `run_N.json` per completed ELF.
C1 `details.checks` records generated, bound, fired and unbound counts per kind.
Any firing or program failure prevents a clean runtime result. The separate
summary keeps NOT RUN formal counts null and retains incomplete campaigns.
A failing assertion can stop the simulator before a C1 report is written.
The campaign then records incomplete execution. This is not a passing run.

`checks.generate.json` also selects database stream and bus generators.
Pass `--checks` to the database builder to write `checks.json` beside `vex.db`. Stream contracts
and clock declarations require review before their bindings can be complete.
VexiiRiscv and the stub SoC have generation manifests with their own expected
database paths. Missing captures remain explicit. No connected three-design
qualification result is claimed from these manifests alone.

On 2026-11-13 the native checked campaign completed all 49 aligned ISA programs.
It inserted 57 checks. Eleven internal fetch `stream.valid_hold` checks fired
8,768 times. All 49 C1 results stayed `fail`. No check was waived or disabled.
The other 46 checks had zero firings. Source inspection identifies cancellable
fetch offers as the likely contract mismatch. This classification is inferred
from `Fetcher.scala` flush/halt logic and `IBusSimplePlugin.scala` response
discard logic. Cancellation was not independently traced. These findings stay
open until a cancellation-aware binding establishes the correct obligations.
The native regression verifies that the findings retain failure status.

The external instruction and data command ports have explicit stable contracts.
Their generated bindings passed Verilator elaboration. Run `rvw/checks-formal.py`
with `--rtl`, `--generated` and `--out` to prepare separate assertions. Run the
resulting `regress.toml` with `rvw formal regress MANIFEST --out NEW_DIR --jobs 3`.
Eight native SBY properties passed through depth 6 with two reset clocks. They
cover four packed command checks. No unbounded proof or activation evidence was
obtained. Other design inputs remain arbitrary. The native run used a private
Scala compile with cached dependency jars to avoid the shared sbt queue.
See [the recorded summary](checks-qualification.json) for counts and limits.

## FST failure windows on the live server

The example records its sampled wave clock in C1 and has a minimal project
debug configuration. Generic RiscvSim uses FST. `rvw bundle --sim-server PATH`
can request the failure window from the same JVM that produced the failure.
The test `rvw/tests/test_live_fst_bundle.py` requires the original session and
RTL hash, an FST artifact and the bundle's selected VCD window.

The native sample reproduced a deliberate tohost failure at cycle 9,023.
It requested cycles 8,923 through 9,043. The same process and session supplied
`wave.fst`, and the bundle produced `wave-window.vcd` with no notes. This is a
fixture, not a newly found core defect. See [the sample](rvw/live-fst-results.json).
The cancellation-aware rerun on 2026-11-13 completed the same 49 aligned ISA
programs. All 49 software and C1 results passed. All 57 checks remained bound,
with zero firings and no waivers or disables. The recognizer reads standard
Stream gate and registered-flush assignments. Three custom equations have
exact project cancellation bindings with source and wave evidence. See
[the triage](checks-evidence/README.md) and [the current counts](checks-qualification.json).
This rerun did not run formal. It does not qualify other designs or inputs.

## Debug Module and trace ingress configurations

Three additive configurations sit beside `rv32im`. They use the same adapter.

| Config | Adds |
|---|---|
| `rv32im_dmi` | CSR plugin official debug support and the SpinalHDL `DebugModule`, with its DMI bus on top-level `dmi_*` ports |
| `rv32im_jtag` | The same Debug Module behind the upstream `EmbeddedRiscvJtag` DTM, on top-level `jtag_*` pins |
| `rv32im_trace` | `TraceIngressPlugin`: an E-Trace encoder ingress port (`trace_*`) from the write-back stage and the trap CSRs |

Build the loop program, then run the compliance suite. rvw starts the simulation
through the profile's `dmi_process` command:

```sh
examples/vexriscv/rvw/debug/build.sh
rvw debug suite --profile examples/vexriscv/rvw/debug/profile-dmi.toml --out /tmp/vex-debug
```

For JTAG, start the simulation, then point the TAP checks, the suite or OpenOCD and
GDB at its port. The session serves one client at a time and ends after 300 s
without a client:

```sh
examples/vexriscv/rvw/run.sh run --config rv32im_jtag --elf examples/vexriscv/rvw/out/programs/debug-loop \
  --out /tmp/vex-jtag --mem-latency 0 --max-cycles 2000000000 \
  --debug jtag:0 --debug-binding examples/vexriscv/rvw/debug/binding.json &
port=$(cat /tmp/vex-jtag/debug-port)
rvw debug tap --port "$port" --out /tmp/vex-tap
rvw debug suite --profile examples/vexriscv/rvw/debug/profile-jtag.toml --port "$port" --out /tmp/vex-jtag-suite
rvw debug interop --port "$port" --elf examples/vexriscv/rvw/out/programs/debug-loop --out /tmp/vex-interop
```

Trace ingress from a real run, checked against C2 (see the debug README,
"Trace ingress from a core"):

```sh
examples/vexriscv/rvw/run.sh run --config rv32im_trace --elf rvw/out/programs/smoke --out /tmp/vex-trace \
  --mem-latency 0 --rvfi-trace --trace-ingress examples/vexriscv/rvw/trace/ingress-binding.json
rvw debug ingress-check --ingress /tmp/vex-trace/te_ingress.csv --rvfi /tmp/vex-trace/rvfi.jsonl \
  --elf rvw/out/programs/smoke --out /tmp/vex-ingress
```

Measured on 2026-11-13 (VexRiscv `a62c145a`, SpinalHDL 1.15.0, Verilator 5.049,
OpenOCD 0.12.0+dev-00519, GDB 18.1):

| Campaign | Result |
|---|---|
| `debug suite`, `rv32im_dmi` | 34 pass, 5 fail, 45 unsupported or skipped |
| `debug tap`, `rv32im_jtag` | 9 of 9 pass |
| `debug suite`, `rv32im_jtag` | 33 pass, 5 fail, 1 inconclusive (`abs.busy_collision`: JTAG is too slow to see busy) |
| `debug interop`, `rv32im_jtag` | load, register and memory writes, `stepi` and `stepi` over a jump pass; software and hardware breakpoints stop at `target + 4`; the watchpoint is refused (execute-only triggers) |

The five failures are the same over DMI and JTAG. See the debug README, "Core hooks".
The late breakpoint stop is not explained yet: the suite's dpc checks pass, and
OpenOCD logs failed program-buffer memory reads at low addresses.

These configurations change the RTL. Their results do not qualify `rv32im`.
The debug configurations keep `TrapProbePlugin`, so a debug entry or `dret` can
appear as a trap event in C2. Use them for debug sessions, not for C2 regression.

## Scala DSL property campaign

`rvw/src/main/scala/rvwvex/CoreProperties.scala` binds 34 assertions and two
covers beside the example elaboration. It observes the four pipeline stages,
PC transfers, instruction and data command buses, RVFI writes and trap CSRs.
It does not change upstream sources. Use a private core copy and private locks.
Set `RVW_HOME` to this workstation checkout. Set `VEXRISCV` to the private copy.
From `examples/vexriscv/rvw`, generate the RTL and DSL statements:

```sh
"$RVW_HOME/scripts/with-lock.sh" sbt-sva nice -n 10 sbt -batch \
  'runMain rvwvex.CoreProperties /tmp/vex-properties/rtl'
```

From the workstation root, prepare and run the checks:

```sh
rvw/.venv/bin/python examples/vexriscv/rvw/core-properties.py \
  --rtl /tmp/vex-properties/rtl --out /tmp/vex-properties/jobs --depth 12
rvw formal regress /tmp/vex-properties/jobs/regress.toml \
  --jobs 3 --timeout 20 --proof-cache /tmp/vex-properties/cache \
  --out /tmp/vex-properties/proof-1 --json
rvw formal regress /tmp/vex-properties/jobs/regress.toml \
  --jobs 3 --timeout 20 --proof-cache /tmp/vex-properties/cache \
  --out /tmp/vex-properties/proof-2 --json
scripts/with-lock.sh vex-sva nice -n 10 rvw/.venv/bin/python \
  examples/vexriscv/rvw/core-properties-sim.py --rtl /tmp/vex-properties/rtl \
  --out /tmp/vex-properties/sim examples/vexriscv/rvw/out/isa/rv32ui-p-add
rvw cov merge add=/tmp/vex-properties/sim/rv32ui-p-add/coverage.dat \
  --source-root /tmp/vex-properties/sim --json
```

Pass all 49 aligned ISA ELFs to the simulation script for the full example
campaign. Exclude dump files and `rv32ui-p-ma_data`. Compile once for the whole
list. Each program starts a fresh native process with initialized memory.
C1 records assertion counts and ELF/RTL hashes. Cover counts record sampled
hits. They are not RTL toggle coverage. Formal writes C3 and JUnit.
Read [the measured table](property-results.md) for the exact observations.

The simulation memory model returns ordered responses with one pending request
per bus. It stops on a nonzero `tohost` store. It has no interrupt stimulus.
Formal assumes two initial reset clocks and leaves other inputs arbitrary.
A bounded pass does not prove later behavior. Assertion pass counts include
false antecedents. Finite simulation reports each matched antecedent. Separate formal cover jobs
report bounded antecedent reachability. DSL source locations are retained in C1
and C3. Complete transitive source closure remains uncertified. The fetched-instruction identity and eventual retirement or
flush property is not implemented in this campaign. No liveness proof is claimed.

## Single-file failing-run replay

`rvw/replay.json` supplies the portable adapter command and source-input roots.
It keeps core bindings in project data. With a conclusive failing C1/C2 run:

```sh
rvw replay-pack failed-run --recipe examples/vexriscv/rvw/replay.json --out failure.rvw
rvw replay failure.rvw --out new-reproduction --lock vex-simsrv
```

The archive contains the ELF, stimulus/options, a from-reset trace checkpoint
and offline Git source bundles with patches and declared extra inputs.
The target still needs JDK 21, Scala dependencies, Verilator and native build
tools. `JAVA_HOME` and `PATH` bind to that target's configured tools.
Live-state cross-machine restore is outside this command.

The native sample rebuilt the captured core and adapter sources in a new
location. It reproduced fail code 3 at cycle 9,023 with 2,005 retirements.
All sixteen checks passed. The trace checkpoint was cycle 4,500. The archive
was about 33.6 MB. This is local relocation evidence. Native execution on a
second machine was NOT RUN. See [the sample](rvw/replay-results.json).

## Security runs

`rvw/sec/` holds the project data for `rvw sec` native runs on this core: core
binding, case templates, IFT programs and policies, contract, campaign and
model pre-check manifests. See [its README](rvw/sec/README.md) and the
results in [`rvw/src/rvw/sec/README.md`](../../rvw/src/rvw/sec/README.md).
