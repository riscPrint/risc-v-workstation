# NaxRiscv project example

Current RV32 timing limit: the corrected final window model meets the criterion
on 6 of 15 nonzero RTL changes and 15 of 24 total pairs. Training/held-out
IPC MAE is 7.31%/9.08%. Earlier stage scores remain historical.
See [the corrected study](../../rvw/src/rvw/ooo/README.md#corrected-resource-study-window)
and [PR #1252](https://github.com/riscPrint/risc-v-workstation/pull/1252).
Structure-size decisions still need RTL measurements.


This folder holds the project files for an external
[NaxRiscv](https://github.com/SpinalHDL/NaxRiscv) checkout. NaxRiscv is an
out-of-order RISC-V core written in SpinalHDL. This example tests the generic
out-of-order tools on a small native RTL target. Install the workstation as described in
[Bring your own core](../../docs/BRING_YOUR_OWN_CORE.md). Set `RVW_HOME` to that
installation. Keep the core outside the workstation repository. The adapter
does not change NaxRiscv's source.

## Configuration and result summary

The default remains `rv32imasu`. The extra RV64 configs use the same pinned
core and SpinalHDL sources. All numbers below are RTL simulation results.
They do not qualify hardware or a whole core.

| Evidence | RV32 default | RV64 machine | RV64 M/S/U, Sv39 |
|---|---|---|---|
| Named config | `rv32imasu` | `rv64ima` | `rv64imasu` |
| riscv-tests | 59 C1 passes, 59 strict matches | 85 C1 passes, 85 strict matches | 85 C1 passes, 85 strict matches |
| ACT4 instruction profile | 69 C1 passes, 69 strict matches | 98 C1 passes, 98 strict matches | 98 C1 passes, 98 strict matches |
| Generated supervisor campaign | NOT RUN here | Not applicable to M-only mode | 179 programs: 163 C1 passes, 16 failures; 157 strict matches and 6 IRQ-synchronized matches |
| Native MMU observations | NOT RUN here | No MMU | 135 bound files; 26 bounded walks consistent, 109 inconclusive |
| Probe and top-down results | Retained RV32 study below | NOT RUN | Three benchmarks; retirement counts agree; orphan-event warnings remain |
| Generated OoO rules | Nine rules, 59 ISA passes, zero firings | NOT RUN | Nine rules, three benchmark passes, zero firings |
| Timing evidence | Separate retained RV32 calibration and delta studies | NOT RUN | Three unfitted parameter-transfer comparisons; IPC error -10.99% / -0.02% / +11.58% |

The supervisor campaign retains 14 MPRV permission failures and two
noncanonical-address failures. PMP, ASIDs, hardware A/D updates, H and
multi-hart shootdown are absent or excluded. The benchmark matches need
explicit counter synchronization. Standard privileged ACT4, C/F/D configs
and translated benchmark timing are NOT RUN. Read the detailed
[supervisor results](rvw/supervisor/README.md) and
[RV64 tool results](#rv64-out-of-order-tools) before reusing these counts.

## Setup

Pinned revisions:

| Repository | Revision |
|---|---|
| NaxRiscv | `9f452d50560d02fb391bc8039f5453c54e0911af` (`main`, 2026-01-23) |
| `ext/SpinalHDL` (submodule) | `c362657003fa178350d6955055867e9ab363c44a` |
| `ext/rvls` (submodule) | `db0e5acbc941e4bef416c151dc19c47574a80f3b` |

```sh
git clone https://github.com/SpinalHDL/NaxRiscv "$HOME/projects/NaxRiscv"
cd "$HOME/projects/NaxRiscv"
git checkout -b rvw-project 9f452d50560d02fb391bc8039f5453c54e0911af
git submodule update --init ext/SpinalHDL ext/rvls
cp "$RVW_HOME/examples/naxriscv/rvw.toml" rvw.toml
cp -R "$RVW_HOME/examples/naxriscv/rvw" rvw
export RVW_PYTHON="$RVW_HOME/rvw/.venv/bin/python"
export RISCV_TESTS_SOURCE=/path/to/riscv-tests
rvw/build-tests.sh
```

Use JDK 21, sbt, Verilator, a C++ compiler and make. The other submodules
(`NaxSoftware`, `riscv-isa-sim`) are not necessary. To keep the core checkout
clean, set `NAXRISCV` to it and run the project from a copy of this folder.

## Private worker layout

Create the pinned private clone with the setup commands above. Set `RVW_HOME`
to your workstation checkout. The old `saviour` scratch workers were deleted.
Build outputs are local to the new checkout.

```sh
export RVW_HOME=/path/to/risc-v-workstation
export NAXRISCV="$HOME/projects/NaxRiscv"
export RISCVSIM_WORK="$RVW_HOME/examples/naxriscv/rvw/target/work"
export RVW_NAX_LOCK=nax-dbg
export RVW_NAX_SBT_LOCK=sbt-dbg
export RVW_SPINAL_SOURCE="$NAXRISCV/ext/SpinalHDL"
```

`run.sh` selects Scala 2.12.18 and the pinned SpinalHDL source. Use `nice -n 15`
for new jobs. Keep each native run to a few minutes. Keep planted bugs in this
private core. The normal adapter does not patch a core checkout.

## SpinalHDL and Scala versions

NaxRiscv pins its own SpinalHDL source (`ext/SpinalHDL`) and declares Scala
2.12.18. That SpinalHDL revision does not compile with Scala 2.13 (two errors in
`lib/.../tilelink/Decoder.scala`), and it lacks several members that the
SpinalHDL 1.15.0 release has. The example therefore uses the pinned toolchain
as it is:

- `rvw/build.sbt` compiles the NaxRiscv sources (without its sandboxes, ASIC and
  tile-link demo generators) with Scala 2.12.18 against `ext/SpinalHDL`.
- The workstation libraries take the source axis of
  `scripts/sbt/SpinalAxis.scala`: `run.sh` sets `RVW_SPINAL_SOURCE` to
  `ext/SpinalHDL` and runs sbt with `'++2.12.18!'`. RiscvSim, SpinalProbes,
  SpinalTrace and SpinalWaves compile against that source, into their own
  `target/spinal-source-c362657003fa/` directories.
- The build fails at load time when `RVW_SPINAL_SOURCE` names another checkout.

Generic changes this needed (all version-neutral; the release axis still compiles):

- The axis itself and a `project/spinal-axis.sbt` line in each library build.
- `scala-collection-compat` on both axes; Scala 2.13-only calls replaced by forms
  that compile on 2.12 (`Map.from`, `Regex.matches`, `Double.isFinite`,
  `dropRightInPlace`, an escaped quote in an interpolated string, a path-dependent
  `flatMap`).
- `SpinalCompat` objects in RiscvSim, SpinalWaves and SpinalChecks for members
  that this SpinalHDL revision lacks: `SpinalSimConfig._waveFilePrefix`,
  `MemReadAsyncWrite`, `Axi4Config.withAxi3`, the tile-link sim
  `MemoryAgent.blockSize` and `TransactionC.beat`. Each states its fallback.
- `ScopeStatement.on` returns `Unit` in this revision; `spinalprobes.Probe`
  no longer uses its result.
- Verilator 5.052 removed the `WData` type name used by the pinned wrapper.
  The launcher maps it to `EData`, which is the same 32-bit word type.
  The alias also compiles with 5.049. This build setting does not qualify assertions.
- The pinned SpinalHDL Verilator wrapper constructs the model before it sets the
  handle that `sc_time_stamp()` reads. Verilator 5.049 reads the time during
  construction and the process crashes. `run.sh` adds `-CFLAGS -DVL_TIME_CONTEXT`
  to `SPINAL_VERILATOR_FLAGS`, so Verilator reads its own context time. SpinalHDL
  1.15.0 has a null check instead.

  This workaround does not validate HDL assertions. A native probe with the
  installed Verilator 5.049 returns `$time == 0` with `VL_TIME_CONTEXT`, even
  when the old callback reports time 17. The old wrapper does not advance
  `VerilatedContext` time. Assertions guarded by `noAssertAtTimeZero` can then
  remain disabled. The [native probe](../../RiscvSim/tests/repro/verilator-context-time/README.md)
  has the source and command. Use a null-safe callback in the SDK or a compatible
  Verilator before validating assertions on this axis. The basic C1 smoke
  result does not establish assertion coverage.

- SpinalDB selects its API shim directory through `SpinalAxis.apiSources`:
  `scala-spinal-legacy/` for this SpinalHDL revision. The legacy shim declares
  the missing port and operator types (`MemReadAsyncWrite`, `Repeat`,
  `VerilogValues`) as types that are never instantiated, so their cases never
  match. `PhaseDeviceDefault`, `ObfuscateConfig` and
  `preventMemToBlackboxTranslation` have stated fallbacks.

SpinalChecks now compiles on this axis through version-specific API shims.
See the SpinalChecks README for the fallback behavior.

## Run from the core project

```sh
rvw regress list
rvw regress run --suite isa --rvfi-trace --out rvw/out/isa --no-index --json
rvw/run.sh run --elf rvw/out/isa/rv32ui-p-add --out rvw/out/add --seed 1 --mem-latency 0 --rvfi-trace --json
rvw cosim check --elf rvw/out/isa/rv32ui-p-add --trace rvw/out/add/rvfi.jsonl --json
rvw query build --config rv32imasu
rvw query path integer_RfAllocationPlugin_logic_push_physicalRdNew_0 CommitPlugin_logic_commit_continue_1
rvw query export blocks.json rvw/out/nax-blocks.json
```

From the workstation checkout, also pass `--source "$NAXRISCV"` to
`rvw regress run`. `quick` selects `add`, `beq`, `lw` and `sw`. `full` selects
the 59 ISA programs (rv32ui-p without `ma_data`, rv32um-p, rv32ua-p) and two
local programs. The adapter holds the `nax` lock (`RVW_NAX_LOCK`); its sbt
compile holds `sbt-nax` (`RVW_NAX_SBT_LOCK`). Use private names with a private
checkout.

## Measured results (2026-11-13, macOS arm64, Verilator 5.049)

- Build: elaboration 2.4 s, Verilator model 8 to 10 s. The first sbt compile of
  the pinned SpinalHDL and NaxRiscv takes about 2 minutes.
- `rvw regress run --suite isa`: 59 pass, 0 fail, 0 skip. 86,309 cycles and
  24,801 retired instructions in total (IPC 0.29 on these short, trap-heavy
  tests with cold caches). `--suite smoke`: 2 pass.
- `rvw cosim check` with Spike: all 59 ISA traces and both smoke traces match:
  24,801 + 28 instructions, 177 + 1 traps, no synchronization, no applied masks.
- Random memory timing (seeds 3 and 7, zero to three wait cycles per refill) on
  `lw`, `sb`, `div`, `amoadd_w`, `lrsc` and `fence_i`: 12 pass, 12 match.
- The ISA negative control and three-register fault sample are reported below.
- `rvw/build-db.sh rv32imasu rvw/out/nax.db`: 17 s (elaboration 3.3 s,
  extraction 6.0 s). 30 components, 8278 signals, 1482 registers, 154 memories,
  10,826 assignments, 17,363 dependency edges. PDG, SpinalBlocks and HGLDD
  artifacts written; 50 warnings (mixed-width memory writes are not modelled in
  the PDG). `info`, `search`, `drivers`, `fanin`, `path`, `hierarchy` and `regs`
  answer; for example `rvw query path integer_RfAllocationPlugin_logic_push_physicalRdNew_0
  CommitPlugin_logic_commit_continue_1` finds the free-list path through the
  commit stage. `rvw query export blocks.json` writes 24 module diagrams for
  SpinalBlocks.

These checks do not prove full ISA, privileged-mode, interrupt, MMU, formal or
hardware correctness. They apply only to this configuration.

## Design

The configuration `rv32imasu` is the upstream `naxriscv.Gen` configuration
without RVC, FPU or debug: RV32IMA, M/S/U modes, Sv32 MMU, two-wide decode,
dispatch and commit, two ALUs and one shared execution unit (multiply, divide,
branch, CSR, environment call), Lsu2 with 16-entry load and store queues, a
64-entry ROB, BTB and GShare predictors, and 64-byte-line instruction and data
caches. Smaller decode widths are not used upstream.

NaxRiscv has no RVFI port. The C2 trace comes from the upstream
`naxriscv.platform.NaxriscvProbe`, the same probe that NaxRiscv's own
regression uses with rvls. The build generates an integration-owned
`CommitProbe` from that pinned source. `rvw/src/main/scala/rvwnax/C2Backend.scala` turns its
events into C2 records:

- Without `--probes`, `insn` comes from the adapter's architectural memory
  image: the ELF plus every committed store. With `--probes`, the adapter
  retains the micro-op and privilege at ROB allocation. It can capture
  instructions fetched through a virtual address.
- `rd` is the instruction's `rd` field when the probe reported an integer
  write. `rs1`/`rs2` values come from a shadow register file that only committed
  writes update.
- `mem_*` give the byte address and access width from committed memory
  operations. With `--probes`, C2 uses the LSU virtual address. Committed
  memory and tohost use the observed physical address.
- `pc_next` is the PC of the next retirement, or xepc when a trap follows.
  With `--probes`, the adapter samples the privileged unit's trap EPC and
  actual TVAL CSR write. Without probes, it retains the older ROB-based EPC
  capture. The generated supervisor campaign requires probes.
- `TapPlugin` exposes the privilege register to simulation. It reads one core
  register and changes no behavior.

The adapter drives the native refill buses: `FetchL1Bus` (one line refill at a
time), `DataMemBus` (line reads in request order, line write-backs) and
`LsuPeripheralBus` (no device: every access answers with an error). RAM is
16 MiB at `0x80000000`. Responses come after a fixed latency (`--mem-latency`)
or after zero to three seeded wait cycles. `tohost` is detected from committed
stores, because the data cache is write-back.

## Out-of-order probes

`rvw/src/main/scala/rvwnax/ProbeTapPlugin.scala` binds SpinalProbes to existing
NaxRiscv signals. It adds hardware only under C1 `--probes`.
`rvwnax.ProbeSafety` elaborates the core with and without the plugin, probes
off, and compares the Verilog SHA-256: identical (`e89079a7...`).

| Probe | Signals |
|-------|---------|
| `topdown_*` counters | commit mask, `CommitPlugin` execute-time and commit-time reschedules, ROB allocation (`robToPc.valid`) and `ptr.empty`; the OoO model's partition predicates |
| `rob_alloc_lines`, `rob_occupancy`, `reschedule_execute`, `reschedule_commit`, `reschedule_commit_trap` | `CommitPlugin` pointers and reschedule ports (`reschedule_commit_trap` counts the `trap` bit, which non-trap flushes such as `satp` writes also set) |
| `freelist_alloc`, `freelist_free` | integer `RfAllocationPlugin` allocator pop mask and push ports |
| `iq_occupancy`, `iq_full_cycles` | `DispatchPlugin` issue queue `usage` bits |
| `lq_occupancy`, `sq_occupancy`, `lq_full_cycles`, `sq_full_cycles` | `Lsu2Plugin` load/store queue free trackers |
| `icache_refills`, `dcache_refills`, `dcache_writebacks` | the refill buses at the core boundary |
| `branch learn` (`cond`, `first-prediction`), `branches`, `cond_*` | `BranchContextPlugin` learn port (committed branches in commit order); prediction = the branch's dispatch-time `BRANCH_EARLY` context |

```sh
rvw/build-bench.sh            # riscv-tests benchmarks, RV32IM, with Arch/bench
rvw/run.sh run --elf rvw/out/bench/median.riscv --out rvw/out/probe/median --probes --rvfi-trace --mem-latency 0 --json
rvw perf topdown rvw/out/probe/median/probe-events.jsonl --c2 rvw/out/probe/median/rvfi.jsonl --result rvw/out/probe/median/result.json
rvw probes convert rvw/out/probe/median/probe-events.jsonl --to bp-events --c2 rvw/out/probe/median/rvfi.jsonl --out bp.jsonl
rvw csim compare-rtl rvw/probes/gshare.json --trace rvw/out/probe/median/rvfi.jsonl --events bp.jsonl
rvw probes convert rvw/out/probe/median/probe-events.jsonl --to counts --c1 rvw/out/probe/median/result.json --c2 rvw/out/probe/median/rvfi.jsonl --out counts.json
```

Measured on 2026-11-13 (`--mem-latency 0`). Every run passed, and Spike matched
every complete trace. Top-down columns are percent of commit slots (2 per
cycle); `retiring` equals the C2 retirement count in every run. The branch
columns compare the RTL direction prediction with `rvw/probes/gshare.json`
(a 16384-counter gshare; see its approximations); events align one to one with
the C2 conditional branches.

| Program | Cycles | Retired | IPC | Retiring | Bad spec. | Back end | Front end | Cond. branches | RTL MPKI | gshare MPKI | Agreement |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| median | 18,061 | 10,653 | 0.590 | 29.5 | 20.1 | 49.5 | 0.9 | 3,562 | 96.5 | 59.0 | 83.2 % |
| qsort | 293,449 | 226,061 | 0.770 | 38.5 | 15.0 | 46.5 | 0.1 | 60,980 | 62.0 | 59.2 | 85.1 % |
| towers | 8,880 | 7,273 | 0.819 | 41.0 | 9.7 | 47.0 | 2.4 | 331 | 23.0 | 14.6 | 80.4 % |
| vvadd | 5,220 | 6,490 | 1.243 | 62.2 | 6.3 | 28.2 | 3.4 | 1,064 | 7.6 | 7.9 | 99.4 % |
| multiply | 38,207 | 54,296 | 1.421 | 71.1 | 2.8 | 25.7 | 0.5 | 6,764 | 5.1 | 4.7 | 99.5 % |
| rsort | 210,339 | 364,958 | 1.735 | 86.8 | 1.8 | 11.4 | 0.1 | 17,457 | 0.6 | 0.4 | 99.5 % |
| spmv | 986,710 | 1,557,480 | 1.578 | 78.9 | 2.8 | 18.3 | 0.0 | 144,180 | 6.5 | 5.8 | 97.9 % |
| memcpy | 25,375 | 31,185 | 1.229 | 61.4 | 1.5 | 36.3 | 0.7 | 7,014 | 1.4 | 1.0 | 99.7 % |
| dhrystone | 144,337 | 206,224 | 1.429 | 71.4 | 1.4 | 26.9 | 0.2 | 28,312 | 3.0 | 2.8 | 99.8 % |

Other counters: mean ROB occupancy 11 (median) to 32 (memcpy) of 64; mean
issue-queue occupancy 2.3 to 13.3; the RTL `cond_mispredicts` count stays
within 3 to 15 of the commit-time non-trap flush count; `branches` equals the
model's `branches` count on the eight calibrated programs. `freelist_free` minus
`freelist_alloc` ends at 31 or 32 on every program (the reset fill of the free
list, less registers still allocated in flight).

Limits: the top-down predicates are the model's simple commit-slot partition,
not the hardware top-down method. The Kanata follow-up below now binds reused
ROB IDs and bulk flushes. No TLB probe: the benchmarks run in M-mode without
translation. The `gshare` study is unqualified.

## Out-of-order timing model

`rvw/arch/ooo.json` retains the initial description. The revised default is
`rvw/arch/ooo-measured.json`. See the measured delta study below for current
trust limits. Both describe the same base RTL configuration for the workstation's
trace-driven OoO model (`rvw ooo`): two-wide fetch, rename and commit, 64 ROB
entries, 32 issue-queue entries, 16 load and 16 store entries, 64 physical
registers, speculative load issue, buffered stores, and shared components for NaxRiscv's GShare
(16384 counters), 512-entry BTB and 16 KiB 4-way I$ and D$. Latencies, the
branch penalty and front-end delays are timing approximations, not extracted
values. `rvw/arch/calibrate.py RUNS OUT` builds the calibration plan from the
probe runs above, maps the RTL `branches` counter to the model's `branches`
event, fits branch penalty and load latency on the training programs only
(`rvw arch ooo-fit`) and scores the held-out programs. Fetch latency stays at
3. The calibration plan allows 5,000,000 cycles, including `spmv`.

```sh
rvw ooo rvw/arch/ooo-measured.json rvw/out/probe/median/rvfi.jsonl --json
python3 rvw/arch/calibrate.py rvw/out/probe rvw/out/calib
rvw ooo rvw/arch/ooo-measured.json rvw/out/probe/spmv/rvfi.jsonl --max-cycles 5000000 --json
```

### Initial correlation

This table records the earlier description. The current memory-model follow-up
below reports the revised description and its mixed results.

Measured on 2026-11-13 (results: [`rvw/arch/results-2026-11-13.json`](rvw/arch/results-2026-11-13.json)).
Training: median, qsort, multiply. Held out: towers, vvadd, rsort, memcpy,
dhrystone. `spmv` exceeds the model's 1,000,000-cycle budget and is left out.
Round 1 used four-entry fetch and decode buffers; round 2 uses eight, a change
chosen on the training programs only (multiply went from -31.7 % to -12.4 %).
Selected: branch penalty 6, fetch latency 3, load latency 2. Top-down columns
are percent retiring / bad speculation / back end / front end.

| Program | Split | RTL IPC | Model IPC | IPC error | Round 1 | RTL top-down | Model top-down |
|---|---|---:|---:|---:|---:|---|---|
| median | training | 0.590 | 0.671 | +13.7 % | +14.9 % | 29/20/49/1 | 34/22/44/1 |
| qsort | training | 0.770 | 0.641 | -16.9 % | -12.7 % | 39/15/46/0 | 32/22/46/0 |
| multiply | training | 1.421 | 1.245 | -12.4 % | -31.7 % | 71/3/26/0 | 62/3/34/1 |
| towers | held out | 0.819 | 0.755 | -7.8 % | -5.1 % | 41/10/47/2 | 38/8/53/0 |
| vvadd | held out | 1.243 | 1.055 | -15.1 % | -26.6 % | 62/6/28/3 | 53/5/42/1 |
| rsort | held out | 1.735 | 1.371 | -21.0 % | -30.2 % | 87/2/11/0 | 69/0/31/0 |
| memcpy | held out | 1.229 | 0.705 | -42.7 % | -42.6 % | 61/2/36/1 | 35/1/64/0 |
| dhrystone | held out | 1.429 | 0.888 | -37.9 % | -40.3 % | 71/1/27/0 | 44/11/44/1 |

Mean absolute IPC error: 14.3 % on training, 24.9 % held out (maximum 42.7 %).
The `branches` event matches exactly on every program (Pearson r = 1). Only
towers is inside the 10 % IPC budget; `sufficient_coverage` is false (one event
family). The model is too slow on high-IPC memory-heavy code: its back-end share
on memcpy is 64 % against 36 % in RTL. Candidate causes at this early stage, not tested in that campaign: the
single load/store port and in-order store issue of the model against NaxRiscv's
Lsu2, and component cache latency added on every access. This is the first
out-of-order RTL correlation of the model; it is not a fidelity verdict.

## Generated checks

`checks.generate.json` selects the design database (bus checks) and
`rvw/micro-checks.json` (`rvw.micro-checks/1`), which binds the generic
microarchitecture templates to NaxRiscv signal names:

| Rule | Template | NaxRiscv signals |
|---|---|---|
| `lq_free_bound`, `sq_free_bound` | `counter_bounds` (16) | `Lsu2Plugin_logic_{lq,sq}_tracker_free` |
| `branch_context_bound` | `counter_bounds` (16) | `BranchContextPlugin_logic_ptr_occupancy` |
| `rob_conservation` | `rob_pointers` (64; two-lane steps) | commit allocation/free pointers and accepted transfers |
| `int_freelist_ghost` | `freelist_ghost` (64; two allocation/free lanes) | accepted allocation tags and free events |
| `sq_forward_youngest` | `store_forward_window` (16) | load-stage hits, selected store and age-window pointers |
| `fetch_refill_cmd`, `dcache_refill_cmd`, `peripheral_cmd` | `pipeline` (valid/payload stable while stalled) | the refill and peripheral command streams |

```sh
rvw checks generate --all --project . --out rvw/out/checks
RVW_NAX_CHECKS=$PWD/rvw/out/checks/queues rvw regress run --suite isa --rvfi-trace --out rvw/out/isa-checks --no-index
```

`RVW_NAX_CHECKS` selects a check model: the adapter compiles the generated
monitors and binds into the Verilator model, with each `assert(e);` turned into
one firing line, and writes `checks-run.json` (`rvw.checks-run/1`) per run. A
pass with any firing becomes `fail`; a run whose output was not captured is an
error, never a pass. `TapPlugin` adds the constant `rvw_checks_active` wire for
the counter-bound enables.

Initial six-rule baseline on 2026-11-13: `rvw checks generate --all` bound six rules
(`complete: false` overall: no stream contracts, no CSR model, and the bus
generator has no checker for NaxRiscv's FetchL1/DataMem/peripheral bus types;
each instance is listed with that reason). The ISA suite with the check model:
59 pass, 59 reports captured, 0 firings. Negative control
(`rvw/micro-checks-control.json`, load-queue free count at most 8):
`rv32ui-p-add` fails with 1,004 firings of `control_lq_free_le_8`.

The current project declares nine rules. The follow-up native ISA run has
59 passes, 59 captured reports and zero firings across all nine rules. Each
new rule also caught its private planted bug with seed 1. See the wide-check
follow-up and `rvw/plants/check-results.json` for the counts and limits.

The ghost model checks allocation/free event consistency. It does not observe
the allocator RAM state, so it cannot establish complete free-list state
conservation. The ROB rule checks pointer movement for two-lane transfers.
The forwarding-window rule checks selection within the declared window, not
forwarded byte data. Full recovery is still unbound. SpinalChecks compiles
its library and test sources on both API axes. Four naming/elaboration tests
pass on each axis. Other compiled Scala tests did not run.

## Limits

- The default configuration has the 59-test ISA result. The IQ16 variant has
  only the measured `memcpy` run.
- No RVC, FPU, interrupt schedules, devices or riscv-formal monitor.
  `--irq-schedule`, `--rvfi-check` and `--soc-map` are refused.
- Native C1 `--konata` is refused. Convert the probe stream with `--to kanata`.
- Unseeded directed-check firings remain unresolved. Fixed-seed controls use 1.
- Store-buffer drain, forwarded byte checks and full recovery checks remain open.
- SpinalChecks has compile support on the legacy axis. Native qualification
  remains separate from compilation.
- `rvw query build` sets `NAXRISCV` to the project root. Keep the project files in
  the NaxRiscv checkout, or call `rvw/build-db.sh rv32imasu rvw/out/nax.db` with
  `NAXRISCV` set.

## Memory-model follow-up (2026-11-13)

The description now uses speculative load issue, buffered stores and one shared
load/store/multiply/divide/CSR issue port. Lsu2 can feed a ready store before an
older load completes. The old model made every store wait for all older memory
operations. Buffered stores remove that wait and count cache service without
adding it to store execution latency. This is an approximation: stores update
cache state at issue, and the model has no finite store buffer or drain.

The saved RTL counters separate two cases. `memcpy` has 1,009 data-cache refills
and 2,982 full-store-queue cycles. `dhrystone` has 28 refills and 6,942 full-store-queue
cycles. The new model has 1,007 and 27 demand misses, respectively. These close
counts do not validate refill latency. With the other settings held fixed,
buffered stores reduce `memcpy` from 33,751 to 31,252 model cycles and `dhrystone`
from 172,514 to 170,721. Thus this policy explains part of the gap. It does not
explain all of it. Memory replay events remain approximate.

Training-only selection chose branch penalty 8 and load latency 2. Mean absolute
IPC error is **20.7% on training**, worse than the earlier 14.3%. It is **13.0%
on the original five held-out programs**, down from 24.9%. With `spmv` added,
it is **12.4% across six held-out programs**. No held-out result selected a
parameter. The calibration plan now sets a 5,000,000-cycle budget. `spmv`
finishes in 1,087,327 model cycles, against 986,710 RTL cycles.

| Program | Split | IPC error |
|---|---|---:|
| median | training | +35.0% |
| qsort | training | -1.5% |
| multiply | training | +25.7% |
| towers | held out | +21.5% |
| vvadd | held out | +20.2% |
| rsort | held out | +3.6% |
| memcpy | held out | -7.2% |
| dhrystone | held out | -12.3% |
| spmv | held out | -9.3% |

[Saved counts, trace hashes and ablation](rvw/arch/memory-results-2026-11-13.json).
This is mixed timing evidence, not a model fidelity pass. The earlier table
records the previous description and remains for comparison.

## Wide-check follow-up (2026-11-13)

The project now binds nine rules. `rob_conservation` checks the two-entry
allocation and free steps, including flushed entries. `int_freelist_ghost`
keeps a free-tag mask from allocate and free events. It needs no DUT mask.
`sq_forward_youngest` checks the youngest matching older store in the wrapping
store-queue window. It is active only for loads and does not check byte data.

The ISA run has 59 passes, 59 captured check reports and zero firings of all
nine rules. Private core mutations fired each new target rule: 29 ROB
conservation firings, 135 free-list firings and 2 forwarding firings. Other
rules can also fire after corruption. The fixed-seed controls use seed 1. The directed positive control passes with
zero firings and 331 complete Spike matches. An unseeded clean directed run
fired other rules. Its cause remains unresolved. The forwarding control uses
[`rvw/plants/forward-control.S`](rvw/plants/forward-control.S). The first
free-list mutation did not build because a bound signal was removed. The
first forwarding program did not fire the intended rule. Neither attempt is
counted as a successful control.

[`rvw/plants/check-results.json`](rvw/plants/check-results.json) records the
results and limits. Apply `rvw/plants/planted-bugs.patch` only to a private
pinned NaxRiscv checkout. `RVW_NAX_PLANT=rob|freelist|forward` selects one bug.
Use the private `nax-dbg` and `sbt-dbg` locks. These are simulation controls,
not formal proofs or core qualification.

## Kanata pipeline follow-up (2026-11-13)

The probe stream now exports instruction lifetimes with reused ROB IDs.
`Rn` marks ROB allocation, `Ds` dispatch, `Is` issue, `Ex` operand read one
cycle after issue, and `Wb` completion. Commit and flush are terminal Kanata
records. A reschedule flushes each younger live entry in entry order. Numeric
ROB indices do not define age across wraparound.

```sh
rvw/run.sh run --elf rvw/out/isa/rv32ui-p-add --out rvw/out/pipeline --seed 1 --mem-latency 0 --probes --rvfi-trace --json
rvw probes convert rvw/out/pipeline/probe-events.jsonl --to kanata --out rvw/out/pipeline/pipeline.log
rvw perf rvw/out/pipeline/pipeline.log --result rvw/out/pipeline/result.json --queue-stage Ds --issue-stage Is --head-stage Wb --in-order-retirement
```

Open the log in Konata, or drag it into the Konata viewer. The native C1
`--konata` option remains refused; this path converts the probe stream.
`rvw/probes/add.kanata` (historical counts and regeneration command in the example README) is a measured sample.
It contains 718 instruction lifetimes, 501 retirements and 210 flushed
instructions. All 501 retired PCs and cycles match C2. Spike matches the 501
instructions and 3 trap events. Seven instructions remain open at `tohost`.
There are 32 orphan events for IDs that are not live, zero stale-ID closures
and no unknown flush anchor. The warnings remain visible in `rvw probes check`.

RiscvSim now records inclusive sampling bounds. With these bounds, `rvw perf`
uses all 1,003 cycles and reports the same 501 retirements as C1. Old streams
without bounds keep their observed event window. `Ex` is an operand-read
marker, not a measured execution latency for every functional unit. See
[`rvw/probes/pipeline-results.json`](rvw/probes/pipeline-results.json).

## Functions and issue-queue comparison (2026-11-13)

`rv32imasu-iq16` changes `dispatchSlots` from 32 to 16. It keeps the 64-entry
ROB and all other settings. The project emits `topdown_cycle` samples beside
the aggregate counters. `rvw perf topdown ... --elf ELF` reports functions.
Retired slots use each instruction's C2 PC. Lost slots use the next retiring
function. This is time attribution, not a causal stall trace.

```sh
rvw perf topdown rvw/out/run/probe-events.jsonl --c2 rvw/out/run/rvfi.jsonl --elf rvw/out/bench/memcpy.riscv --result rvw/out/run/result.json --json
rvw perf topdown-compare rvw/perf/iq32.json rvw/perf/iq16.json --json
```

Both configurations passed `memcpy` with seed 1 and zero refill wait cycles.
Spike matched all 31,185 instructions in each complete trace. Most retired
instructions map to `main`: 31,027 of 31,185. The function report places the
added back-end slots there.

| Issue entries | Cycles | IPC | Queue push blocked | Main back-end slots |
|---|---:|---:|---:|---:|
| 32 | 25,375 | 1.229 | 5,731 | 17,723 |
| 16 | 28,999 | 1.075 | 11,187 | 24,883 |

The smaller queue adds 3,624 cycles and 7,160 back-end slots in `main`.
`iq_push_blocked` measures the exact dispatch condition: a valid dispatch
stage with the queue push port not ready. The queue waits for its oldest
line. Its aggregate `iq_full_cycles` counter stays at zero in both runs.
Data-cache refills stay at 1,009. These observations support dispatch/issue
window pressure as the reason for most of the added time in this pair.
The counters can overlap other stalls. They do not add to a cycle budget.
Store-queue-full cycles fall from 2,982 to zero as dispatch slows.

[`rvw/perf/results.json`](rvw/perf/results.json) records the counters and limits.
The saved reports are `iq32.json`, `iq16.json` and `iq-diff.json` in that folder.
An attempted 32-entry ROB with a 32-entry issue queue failed elaboration on
the pinned core. Its pointer-width error is recorded and that configuration
is not offered. The IQ16 variant has only this benchmark result. It has no
59-test ISA or generated-check qualification.

## ISA negative control and register faults (2026-11-13)

A private integer ALU mutation flips result bit zero. On `rv32ui-p-add` with
seed 1, Spike finds the first wrong architectural write at order 1, PC
`0x80000050`: `li ra, 0` writes 1. Spike expects 0. The earlier boot jump
matches. No masks or synchronization hide the error. The native trace later
ends on an assertion at cycle 381. Co-simulation stops at the first mismatch;
it does not claim a complete mutant-trace match.

With the mutation disabled, the golden run passes and matches all 501
instructions and 3 trap events. The private mutation is in `rvw/plants/isa-negative.patch`. Set
`RVW_NAX_PLANT=alu` only for that control. The project captures this environment
variable in its input identity.

`rvw fault` also applied three seed-1 bit flips at cycle 150, one each in
`CommitPlugin_logic_ptr_alloc`, `CommitPlugin_logic_ptr_commit` and
`CommitPlugin_logic_ptr_free`. All three have explicit applied receipts and
are classified as detected by existing native assert/fail statuses. There are
zero not-injected or inconclusive cases. The sample covers three of 21
bit/cycle positions in that declared one-cycle window. It is not safety or
broad diagnostic-coverage qualification. No watchdog was declared.

See [`rvw/plants/negative-control.json`](rvw/plants/negative-control.json),
[`rvw/plants/fault-results.json`](rvw/plants/fault-results.json) and the commands
in [`rvw/plants/README.md`](rvw/plants/README.md). The saved adapter fixes the
native seed and memory wait across golden and faulty runs. The earlier seed-7
sample touched only the free pointer and is recorded separately.

## Independent nine-declaration rerun

[The independent rerun](checks-nine-rerun.json) uses a separate clean pinned
core copy. All 59 ISA programs pass. Each program captures nine compiled
checks with zero firings. The regenerated declarations and monitor/bind hashes
are retained. The run uses seed 1, zero memory latency and one simulation worker.
This result supersedes the six-rule coverage limit for this campaign. Native
activation remains unmeasured. It does not establish allocator RAM-state
conservation, forwarded byte-data correctness, full recovery or core qualification.

## One-structure RTL matrix

`rvw/arch/matrix.py OUT [VARIANT ...]` runs six fixed programs on the
base, IQ16, ROB128, LQ8 and SQ8 configurations. Each variant changes one
argument of upstream `Config.plugins`. No new core-source edit is needed.
The script resumes completed runs. It requires passing C1 results and
complete Spike matches before it records a sample. It retains RTL top-down
fractions and probe counts. Use the private worker environment above and
run the script with `rvw/.venv/bin/python` from the workstation root.
The adapter runs at `nice -n 10`. Do not enable fault plants or generated
negative checks for this campaign.

Keep PATH stable across the campaign. Set all tool directories before the
first native run. For example, add RISC-V GCC and the workstation venv before
both benchmark builds and native runs:

```sh
export PATH="/opt/homebrew/opt/riscv-gnu-toolchain/bin:$RVW_HOME/rvw/.venv/bin:$PATH"
```

The first base and IQ16 runs in this campaign missed the warm cache.
Their old receipts used these two PATH prefixes. The new launch omitted
them. Both the explicit PATH field and the full environment digest changed.
The namespace stayed at `native-inputs-v29`. Resolved tool records and
emitted RTL hashes stayed equal. The full environment hash does not reveal
any other inherited variable changes. See
[the identity comparison](rvw/arch/cache-identity-results.json).
`rvw/arch/cache-diff.py OLD_C1 NEW_C1` repeats this check.

The collector keeps PATH in its identity because descendant tool lookup
is not fully pinned. Removing that check would weaken cache validity.
This campaign found environment invalidation, not a failed cache lookup.
It used one stable new identity for all 30 runs. Five first-run receipts
record native cache misses. The owner authorized the fifth build after
the original four-build limit was reached. The other 25 runs hit the cache.

The retained matrix (historical counts and regeneration command in the example README) has 30 passing runs and
30 complete Spike matches. Each uses seed 1 and zero added memory wait.
Counter synchronization remains explicit in the Spike receipts. The full
C1/C2/probe captures stay under `$RUN_ROOT/<variant>/<program>`; the retained
file gives their hashes. The private fault-control edits were present
with all plants disabled. This is simulation evidence on six programs.
It is not ISA or whole-core qualification for the variants.


## Measured delta study (2026-11-13)

The earlier frozen model meets the delta criterion on only two of 15 nonzero RTL changes. All nine zero changes match. Structure-size choices still need RTL measurements. Use the model to select experiments and inspect possible bottlenecks. The current results do not qualify design decisions for Apple M-series or Zen 5 class cores.

Thirty RTL runs pass. Thirty complete traces match Spike, with counter
synchronization recorded. Six programs run at seed 1 with zero added memory
wait. The variants change only dispatch slots (32 to 16), ROB entries
(64 to 128), load entries (16 to 8) or store entries (16 to 8).
The existing private fault controls stay disabled.

### RTL IPC and slot partition

R, S, B and F are percent retiring, bad speculation, back end and front end.
These are project-bound commit-slot predicates. They are not hardware
top-down counters or independent causal budgets.

| Variant | Program | RTL IPC | R / S / B / F (%) |
|---|---|---:|---|
| base | median | 0.590 | 29.5 / 20.1 / 49.5 / 0.9 |
| base | qsort | 0.770 | 38.5 / 15.0 / 46.5 / 0.1 |
| base | multiply | 1.421 | 71.1 / 2.8 / 25.7 / 0.5 |
| base | towers | 0.819 | 41.0 / 9.7 / 47.0 / 2.4 |
| base | vvadd | 1.243 | 62.2 / 6.3 / 28.2 / 3.4 |
| base | memcpy | 1.229 | 61.4 / 1.5 / 36.3 / 0.7 |
| iq16 | median | 0.580 | 29.0 / 19.9 / 50.2 / 0.9 |
| iq16 | qsort | 0.766 | 38.3 / 14.8 / 46.8 / 0.1 |
| iq16 | multiply | 1.417 | 70.8 / 2.9 / 25.8 / 0.5 |
| iq16 | towers | 0.814 | 40.7 / 8.4 / 48.5 / 2.4 |
| iq16 | vvadd | 1.141 | 57.0 / 6.0 / 33.9 / 3.1 |
| iq16 | memcpy | 1.075 | 53.8 / 1.5 / 44.1 / 0.6 |
| rob128 | median | 0.590 | 29.5 / 20.1 / 49.5 / 0.9 |
| rob128 | qsort | 0.770 | 38.5 / 15.0 / 46.5 / 0.1 |
| rob128 | multiply | 1.421 | 71.1 / 2.8 / 25.7 / 0.5 |
| rob128 | towers | 0.819 | 41.0 / 9.7 / 47.0 / 2.4 |
| rob128 | vvadd | 1.243 | 62.2 / 6.3 / 28.2 / 3.4 |
| rob128 | memcpy | 1.229 | 61.4 / 1.5 / 36.3 / 0.7 |
| lq8 | median | 0.584 | 29.2 / 20.0 / 50.0 / 0.9 |
| lq8 | qsort | 0.768 | 38.4 / 14.9 / 46.7 / 0.1 |
| lq8 | multiply | 1.421 | 71.0 / 2.8 / 25.7 / 0.5 |
| lq8 | towers | 0.808 | 40.4 / 8.9 / 48.3 / 2.3 |
| lq8 | vvadd | 1.207 | 60.4 / 6.1 / 30.3 / 3.3 |
| lq8 | memcpy | 1.131 | 56.5 / 1.4 / 41.4 / 0.7 |
| sq8 | median | 0.590 | 29.5 / 20.1 / 49.5 / 0.9 |
| sq8 | qsort | 0.768 | 38.4 / 14.9 / 46.7 / 0.1 |
| sq8 | multiply | 1.421 | 71.1 / 2.8 / 25.7 / 0.5 |
| sq8 | towers | 0.783 | 39.2 / 8.9 / 49.7 / 2.3 |
| sq8 | vvadd | 1.243 | 62.2 / 6.3 / 28.2 / 3.4 |
| sq8 | memcpy | 1.095 | 54.7 / 1.4 / 43.3 / 0.6 |


### Fixed-calibration IPC changes

Each value is percent change from the base IPC. Both descriptions use one
base-only fit across all four variants. The revised fit uses median, qsort
and multiply. It selects branch penalty 10 and load latency 2 from six
candidates. No variant or held-out result enters selection. The new
description is [ooo-measured.json](rvw/arch/ooo-measured.json).
The initial description stays in [ooo.json](rvw/arch/ooo.json).

A result is outside the criterion when its sign differs or its error exceeds
half the measured change. Zero measured changes have no relative error.
The criterion uses exact signs. Small nonzero losses remain explicit.

| Variant | Program | Measured (%) | Initial model (%) | Revised model (%) | Revised criterion |
|---|---|---:|---:|---:|---|
| iq16 | median | -1.682 | -0.007 | -0.155 | outside |
| rob128 | median | +0.000 | +0.000 | +0.000 | within |
| lq8 | median | -1.057 | +0.000 | +0.000 | outside |
| sq8 | median | +0.000 | +0.000 | +0.000 | within |
| iq16 | qsort | -0.617 | -0.017 | -0.276 | outside |
| rob128 | qsort | +0.000 | +0.000 | +0.000 | within |
| lq8 | qsort | -0.359 | +0.000 | +0.000 | outside |
| sq8 | qsort | -0.294 | +0.000 | +0.000 | outside |
| iq16 | multiply | -0.303 | -0.026 | -0.088 | outside |
| rob128 | multiply | +0.000 | +0.000 | +0.000 | within |
| lq8 | multiply | -0.021 | +0.000 | +0.000 | outside |
| sq8 | multiply | +0.000 | +0.000 | +0.000 | within |
| iq16 | towers | -0.627 | -0.137 | -0.860 | within |
| rob128 | towers | +0.000 | +0.000 | +0.000 | within |
| lq8 | towers | -1.388 | -0.096 | -0.108 | outside |
| sq8 | towers | -4.393 | -0.109 | -0.054 | outside |
| iq16 | vvadd | -8.244 | -0.184 | -7.976 | within |
| rob128 | vvadd | +0.000 | +0.000 | +0.000 | within |
| lq8 | vvadd | -2.902 | -0.023 | +0.000 | outside |
| sq8 | vvadd | +0.000 | +0.000 | +0.000 | within |
| iq16 | memcpy | -12.497 | -0.004 | -5.890 | outside |
| rob128 | memcpy | +0.000 | +0.000 | +0.000 | within |
| lq8 | memcpy | -7.988 | -4.330 | -3.490 | outside |
| sq8 | memcpy | -10.902 | -3.516 | -2.602 | outside |

| Variant | Initial outside criterion | Revised outside criterion |
|---|---:|---:|
| iq16 | 6/6 | 4/6 |
| rob128 | 0/6 | 0/6 |
| lq8 | 5/6 | 6/6 |
| sq8 | 3/6 | 3/6 |

The initial model has 14 wrong deltas. The revision has 13.
IQ16 improves on towers and vvadd. LQ8 worsens by one pair. The store-queue
loss remains too small in the model. This is mixed delta evidence despite
the better absolute IPC fit.

### Mechanisms and remaining gaps

The RTL issue queue reuses whole age-ordered lines after wakeup.
The generic compacting policy now represents this constraint and one
registered reuse cycle. The front end now has a generic fetch-block limit.
The RTL uses one 8-byte block per cycle. The old description could fetch
instructions from two adjacent blocks in one cycle.

Training probe pairs show one-cycle ALU, two-cycle branch/jump and
four-cycle store completion. Observed load hits take four cycles.
The revised project also declares the existing 16-entry return stack
and shared ALU/branch ports. The fitted load execution delay remains two
cycles, plus component service. It is an effective timing parameter,
not an extracted pipeline latency.

The [per-pair mechanism record](rvw/arch/mechanism-results.json) gives
both top-down partitions and counter values for every pair.
The [stage-pair counts](rvw/arch/latency-results.json) retain the training
observations. Stage-pair capture is partial. These counts support timing
priors, not complete pipeline qualification.

The earlier frozen policy has no finite store drain. Buffered stores release their model
queue slot at commit. The RTL can retain stores until drain. Wrong-path
load/issue occupancy, speculative predictor repair and exact LSU replay
also remain approximate. These gaps can change capacity deltas even when
the committed instruction stream is equal. Counter changes support these
mechanism hypotheses; they do not isolate every cause.

### Base-fit regression

Mean absolute IPC error, in percent:

| Description | Training (3) | Original held-out (5) | Extended held-out (6) |
|---|---:|---:|---:|
| Buffered baseline | 20.74 | 12.98 | 12.36 |
| IPC objective only | 18.77 | 12.34 | 12.60 |
| Compacting queue only | 20.74 | 13.08 | 12.47 |
| RTL structure priors | 19.94 | 14.45 | 12.34 |
| Fetch alignment and base-only fit | 10.67 | 7.56 | 7.47 |


The queue-only and structure-prior rows are intermediate trials.
Their engine hashes are retained. They are not a controlled one-field
sweep of the final engine.

The earlier buffered-store update changed branch overlap, memory ordering,
port sharing and fit settings together. Its training regression cannot be
attributed to buffered stores alone. The old objective minimized cycle
error, although the reported metric was IPC error. IPC-only refitting
helps the original held-out set but slightly worsens the extended set.
The final structural correction improves both held-out set means.
Individual regressions remain: revised memcpy error is -8.15%, against
-7.16% before. Towers remains +20.34%.

Calibration inputs, candidates and all sample errors (historical counts and regeneration command in the example README)
retain these distinctions. The branch-count event family matches retired
counts. It does not validate predictor miss timing. Event coverage remains
insufficient for a fidelity verdict.

### Sensitivity rank agreement

The model uses local plus/minus 12.5% changes. This keeps compacting issue
capacities aligned to whole rename lines. RTL steps halve queues or double
the ROB. IPC is instruction-pooled over the six programs. The comparison
uses absolute elasticity to account for the different step sizes.

| Structure | RTL pooled IPC change (%) | RTL absolute elasticity | Model local sensitivity |
|---|---:|---:|---:|
| issue_entries | -1.617 | 0.03234 | 0.01549 |
| store_entries | -1.112 | 0.02224 | 0.00000 |
| load_entries | -0.952 | 0.01904 | 0.00000 |
| rob_entries | +0.000 | 0.00000 | 0.00000 |


RTL ranks IQ, SQ, LQ, then ROB. The model ranks IQ first and ties the other
three. Kendall tau-b is 0.707: three concordant pairs, zero discordant pairs
and three unresolved model ties. This is partial rank agreement.
Local sensitivity does not establish the order of large capacity changes.

The [sensitivity record](rvw/arch/sensitivity-results.json) and
[rank check](rvw/arch/rank-results.json) retain the trial sizes and method.
Raw traces and builds stay outside versioned source. Compact receipts and
hashes are retained. Results cover short RV32IMA programs on one pinned
small OoO core. FP, vectors, operating-system workloads, larger cores,
native model throughput and physical hardware are not qualified here.


### Resource timing study

All stages use the same base-only fitted parameters. The five corrected
stages share one engine, including common recovery fixes. The historical
baseline uses the earlier engine. Compare mechanisms against the current
engine baseline as well as the historical result. No variant result selects
parameters. The 30 RTL runs and 30 complete Spike matches are reused. No RTL
variant was rebuilt. Calibration uses three training and six held-out programs.
A pair meets the criterion only when its sign matches and its error is no
more than half the measured change. Exact zero changes retain their sign check.

| Policy | Within / 24 | Nonzero within / 15 | Training MAE (%) | Held-out MAE (%) | Same-step rank tau-b |
|---|---:|---:|---:|---:|---:|
| Historical baseline | 11 | 2 | 10.67 | 7.47 | 0.667 |
| Current engine baseline | 11 | 2 | 10.67 | 7.47 | 0.667 |
| Wrong-path occupancy | 15 | 6 | 7.15 | 9.11 | 0.667 |
| Plus finite store drain | 15 | 6 | 7.31 | 9.11 | 1.000 |
| Plus memory-order window | 15 | 6 | 7.31 | 9.08 | 1.000 |
| Plus cache-response retry | 10 | 1 | 9.46 | 9.55 | 1.000 |

Rejected guarded-fetch attempts, before the final occupancy policy:

| Attempt | Within / 24 | Nonzero within / 15 | Training MAE (%) | Held-out MAE (%) |
|---|---:|---:|---:|---:|
| Issue-time guard | 9 | 0 | 57.46 | 48.69 |
| Rename-time guard | 10 | 1 | 51.05 | 40.55 |

Rank uses pooled cycles and the same large steps as RTL. This is separate
from the earlier local-sensitivity tau-b of 0.707 with three unresolved ties.
Better rank does not establish correct change sizes.
Read delta and absolute-error changes separately. A lower training error
or a better rank does not qualify a design decision. Both absolute-error
splits remain explicit for every policy.

| Structure change | Direction matches / 6 | Within size criterion / 6 | Use for a design decision |
|---|---:|---:|---|
| IQ 32 to 16 | 6 | 3 | Measure RTL |
| ROB 64 to 128 | 6 | 6 | Measure RTL |
| LQ 16 to 8 | 2 | 2 | Measure RTL |
| SQ 16 to 8 | 5 | 4 | Measure RTL |

The structure table uses the memory-order window policy, with the
cache-response retry experiment disabled. No structure is qualified for
general direction and size predictions.
IQ, LQ and SQ still need RTL measurements. ROB doubling has no measured effect
on these six programs. Those zero results do not validate ROB shrinkage or
larger programs. Use the model to choose experiments and inspect pressure.

Wrong-path work uses a deterministic committed-mix proxy. The existing Spike
redirect capture cannot supply dynamic gshare paths. The policy has no nested
prediction, wrong-path register dependencies or speculative cache traffic.
Committed frontend lookahead remains optimistic. Stores now retain queue
slots until bounded cache acceptance. Final store visibility after retirement
is outside the measured region.

The cache-response experiment holds a missed load's queue line and readmits the younger
window through finite capacity. Exact probe-driven replay remains **open**.
The RTL reschedule counters mix branches, traps and LSU causes. They cannot
identify a typed LSU retry window. The five-cycle penalty stays fixed; it is
not inferred from those totals. A long cache response is only a retry proxy.
Do not claim that all cache misses require an RTL replay.

The resource configuration is [ooo-resource.json](rvw/arch/ooo-resource.json).
It enables occupancy, finite drain and the memory-order retry window.
It leaves the historical cache-response retry heuristic disabled. Typed RTL
retry evidence was absent in that historical study. New directed evidence
and policy results are below. That separate experiment is retained as
[ooo-retry-experimental.json](rvw/arch/ooo-retry-experimental.json). The original
[ooo-measured.json](rvw/arch/ooo-measured.json) stays as the frozen baseline.
The [model README](../../rvw/src/rvw/ooo/README.md) contains each stage's
24-pair table. Retained JSON files beside these configurations contain all
pair hashes, absolute errors, model events and rank inputs. Two rejected
fetch-guard policies are retained with their large regressions.

Run `resource-study.py CALIBRATION_PLAN DELTA_PLAN CONFIG NEW_OUTPUT` with the
workstation Python to repeat a stage from saved captures. The script runs the
existing calibration and delta commands. It performs no fit and starts no RTL
or Spike process. Retain `summary.json`; keep raw captures outside Git.

## Typed LSU retry smoke

[The retry receipt](retry-results.json) retains capture hashes, live-ID checks,
retry-to-completion histograms and a complete Spike match. The retire probe
count equals C1 `instret`. Cache retry uses the explicit LSU response.
The mini core declares four zero-valid retry probes because it has no
rejected LSU attempts. Zero activation is not exercised retry behavior.
Only the NaxRiscv cache cause activates in these two short runs. Other
causes still need directed captures. Completion spans include queue and
service time. They are not isolated replay penalties.

Historical `rvw/arch/calibration-results.json`: {"stages":{"entries":5},"selection":{"id":4,"score":0.053335279427832255},"candidates":{"records":6},"selection_basis":"base training only: median, qsort, multiply; IPC and branch-count objective","limits":{"records":5}}.
Raw records are no longer tracked. Regenerate outside the repository:
`python3 rvw/arch/calibrate.py rvw/out/probe RUN_ROOT`. Use the pinned inputs and options from [PR #1212](https://github.com/riscPrint/risc-v-workstation/pull/1212).

Historical `rvw/arch/matrix-results.json`: {"samples":{"records":30,"statuses":{"pass":30}},"variants":{"entries":5},"limits":{"records":5}}.
Raw records are no longer tracked. Regenerate outside the repository:
`python3 rvw/arch/retain-matrix.py RUN_ROOT OUTPUT`. Use the pinned inputs and options from [PR #1206](https://github.com/riscPrint/risc-v-workstation/pull/1206).

Historical `rvw/probes/add.kanata`: {}.
Raw records are no longer tracked. Regenerate outside the repository:
`rvw probes convert rvw/out/pipeline/probe-events.jsonl --to kanata --out RUN_ROOT/add.kanata`. Use the pinned inputs and options from [PR #1127](https://github.com/riscPrint/risc-v-workstation/pull/1127).
## Directed retry observations and typed timing

`rvw/programs/retry-directed.S` is a short base-configuration program. It
exercises all four retry causes. It passes in 363 cycles with 40 retirements.
All 40 instructions match Spike. The six typed retry records have live IDs.
[The profile](rvw/arch/retry-profile-results.json) retains the observations
and capture hashes. The memory-order event occurs at cycle 106. Its inclusive
flush occurs at 112. The same PC restarts at rename at 113. A stale completion
at 108 does not measure recovery. The tap now records local LSU attempts as
stage `Ls` as well as the existing pipeline stages.

`rvw/arch/retry-profile.py CAPTURE NEW_OUTPUT` repeats extraction. Its local
attempt intervals include service waiting. Zero added local cost is an
assumption. It is not a measured zero overhead. One memory-order restart
sample is not a stable cross-program latency. The model uses its own cause
detection. Captured dynamic retry rows do not enter a prediction.

The [typed window experiment](rvw/arch/typed-replay-results.json) keeps one
base-only cost profile across all variants. It meets the criterion on 15/24
pairs, including 6/15 nonzero changes. Training MAE is 7.31%. Extended held-out
MAE is 9.05%. [Local cache retry](rvw/arch/typed-cache-results.json) lowers
held-out MAE to 7.52%, but meets only 12/24 pairs and 3/15 nonzero changes.
It loses IQ multiply, IQ memcpy and LQ memcpy. It therefore stays disabled.
Improved absolute IPC alone does not meet the activation rule.

The optional costs are in [ooo-typed.json](rvw/arch/ooo-typed.json).
The rejected cache candidate remains in
[ooo-typed-cache.json](rvw/arch/ooo-typed-cache.json). Local retry uses the LSU
return path and does not need an IQ slot. A dependent wrong-path branch
cannot prevent that return. Exact local cost isolation, cache retry predicate
agreement and broad replay accuracy remain open.

The optional `replay_at_commit` experiment separates that seven-cycle span.
The model predicts the wait for the violating load to reach the ROB head.
The base capture supplies one cycle from flush to rename. A targeted schedule
changes an older instruction's latency by 30 cycles. Predicted commit waiting
also changes by 30 cycles, with the restart cost held fixed. This is a
mechanism check. Full matrix and absolute-error results remain separate.

## Security runs

`rvw/sec/` holds `rvw sec` project data. It runs cases through `rvw/run.sh` with the
C1-run case adapter. Results: [`FINDINGS.md`](FINDINGS.md) and `rvw/sec/README.md`.
## Absolute-error mechanism check

[The per-program diagnosis](rvw/arch/absolute-diagnosis.md) separates the
historical occupancy, drain and retry effects. It also tests the new
commit-controlled recovery. This policy reduces held-out MAE to 8.82%, but
meets only 14/24 deltas and 5/15 nonzero changes. LQ8 towers leaves the size
criterion. The earlier 7.47% held-out mean is not restored.

The missing commit wait now has a mechanism instead of a fixed seven-cycle
charge. This fixes one source of compensation in the cost. It does not fix
all prediction errors. Local cache retry reaches 7.29% held-out MAE, but only
11/24 deltas meet the criterion. Cache retry remains disabled. No individual
variant receives a different parameter value.


## Extra RV64 configurations

| Config | XLEN | Modes | Translation | ISA |
|---|---:|---|---|---|
| `rv32imasu` (unchanged default) | 32 | M/S/U | Sv32 | IMA, Zicsr, Zifencei |
| `rv64ima` | 64 | M | Bare | IMA, Zicsr, Zifencei |
| `rv64imasu` | 64 | M/S/U | Sv39 | IMA, Zicsr, Zifencei |

Both RV64 configs use the pinned upstream `Config.plugins` parameters.
No core source change is needed. Sv39 physical addresses remain 32 bits.
The M-only static translator uses its public 64-bit physical-width parameter.
See [the elaboration findings](FINDINGS.md).
PMP, compressed instructions and floating point are absent.
Use a private pinned checkout and private locks:

```sh
export NAXRISCV="$SAVIOUR/wt/.nax/nax64/NaxRiscv"
export RVW_NAX_LOCK=nax-nax64 RVW_NAX_SBT_LOCK=sbt-nax64
export RISCV_TESTS_SOURCE="$SAVIOUR/ref/riscv-tests"
examples/naxriscv/rvw/build-tests.sh 64
nice -n 10 rvw --project examples/naxriscv regress run --suite isa64 \
  --config rv64ima --source "$NAXRISCV" --rvfi-trace --jobs 4 \
  --no-index --out "$RUN_ROOT/isa-rv64ima"
nice -n 10 rvw regress cosim "$RUN_ROOT/isa-rv64ima" \
  --platform examples/naxriscv/rvw/platform-rv64ima.json
```

Repeat with `rv64imasu` and `platform-rv64imasu.json` for Sv39.
The suite excludes `ma_data`, which requires misaligned data support.
The remaining UI, UM and UA tests keep their self-checks.
The build generates an integration-owned `CommitProbe` from the pinned
upstream observer. It guards the absent S interrupt pin for M-only RTL.
It reads wire values through `SimEncoding.longBits` because the pinned
SpinalHDL rejects 64-bit UInt `.toLong` calls. Commit events and their
ordering keep the upstream implementation. No generated source is committed.
Strict comparison has no synchronization or output mask.
Keep full results outside Git.


RV64 ISA results on 2026-11-13, seed 1, zero added memory wait:

| Config | UI / UM / UA | C1 pass | Complete strict Spike match | Cycles | Instructions |
|---|---|---:|---:|---:|---:|
| `rv64ima` | 53 / 13 / 19 | 85 | 85 | 107,393 | 33,733 |
| `rv64imasu` | 53 / 13 / 19 | 85 | 85 | 107,772 | 33,648 |

Both comparisons have zero synchronization and no output masks.
These are physical-memory ISA tests. They do not qualify Sv39 translation,
interrupts or a whole core. C/F/D configurations are NOT RUN.


## RV64 ACT4

| Config | Selected / built | C1 pass | Complete strict Spike match |
|---|---:|---:|---:|
| `rv64ima` | 98 / 98 | 98 | 98 |
| `rv64imasu` | 98 / 98 | 98 | 98 |

Both runs use the [RV64 instruction profile](rvw/act4-rv64/README.md).
The signatures use machine mode. S/U, standard Sm and Sv39 ACT4 are NOT RUN.
Both comparisons have zero synchronization and no output masks.
Use `NAX_ACT4_OUT` for the external build output. The existing RV32 suite
and defaults are unchanged.
## Debug support on the legacy axis

| Capability | Exact scope |
|---|---|
| Build axis | `RVW_SPINAL_SOURCE=$NAXRISCV/ext/SpinalHDL`, selected with Scala 2.13.14; the libraries also declare a 2.12.18 cross-build |
| Database consumers | The prior measured `rv32imasu` database contains PDG, HGLDD and 24 module diagrams. These measurements were not repeated for the trace task. |
| Memory API | The compatibility layer has no `MemReadAsyncWrite` in the old API. It does not invent such ports. Mixed-width memory writes remain unmodelled in the PDG. |
| Causal accuracy | Artifact export does not establish a complete dynamic chain. Source locations, memory modelling and clock-domain limits remain explicit. |
| Retirement binding | C2 comes from the upstream commit probe. There is no native RVFI port. A packed two-lane formal binding must not be treated as a simulation signal binding. |

## Cross-core sizing guidance

The [current cross-core table](../../rvw/src/rvw/ooo/README.md#current-cross-core-results)
compares this matrix with ooo-mini. It separates the 15/24 typed immediate
result from the 14/24 commit-controlled result. Use the model to rank
candidates. Measure the top few on RTL before choosing a structure size.

The typed and commit policy receipts retain compact summaries below 20 KB.
They retain every delta and per-program absolute error, input hashes and
selected mechanism counters. Full model events stay outside Git. Regenerate
full reports with workstation Python from the repository root:

```sh
rvw/.venv/bin/python examples/naxriscv/rvw/arch/resource-study.py CALIBRATION_PLAN DELTA_PLAN examples/naxriscv/rvw/arch/ooo-typed.json NEW_TYPED_OUTPUT
rvw/.venv/bin/python examples/naxriscv/rvw/arch/resource-study.py CALIBRATION_PLAN DELTA_PLAN examples/naxriscv/rvw/arch/ooo-typed-cache.json NEW_TYPED_CACHE_OUTPUT
rvw/.venv/bin/python examples/naxriscv/rvw/arch/resource-study.py CALIBRATION_PLAN DELTA_PLAN examples/naxriscv/rvw/arch/ooo-commit-replay.json NEW_COMMIT_OUTPUT
rvw/.venv/bin/python examples/naxriscv/rvw/arch/resource-study.py CALIBRATION_PLAN DELTA_PLAN examples/naxriscv/rvw/arch/ooo-commit-cache.json NEW_COMMIT_CACHE_OUTPUT
```

`CALIBRATION_PLAN` and `DELTA_PLAN` point to the saved frozen capture plans.
The receipts retain their hashes. Keep new output directories outside Git.
Use each receipt's recorded engine revision for a historical reproduction.
These commands do not rebuild RTL or select parameters from variant results.


## RV64 supervisor suites

The [supervisor campaign](rvw/supervisor/README.md) supplies capability
selection, external corpus preparation, C1 suite entries, scheduled inputs
and native page-walk observations for `rv64imasu`. It keeps the base project
and its RV32 default unchanged. The measured MMU failures are in
[FINDINGS.md](FINDINGS.md#rv64-sv39-functional-findings).


## RV64 out-of-order tools

Measured on `rv64imasu` on 2026-11-13. These three RV64IM programs run in
M-mode with translation disabled. Seed 1 and zero added memory wait apply.
They pass their RTL self-checks. Each complete Spike comparison uses only
two counter synchronizations for the benchmark's cycle reads. Strict
comparison differs at `mcycle`. These are not strict architectural matches.
There is no output mask. MMIO, CSR and IRQ synchronization are disabled.

| Program | RTL cycles | Retired | RTL IPC | Model cycles | Model IPC | IPC error | Counter synchronizations |
|---|---:|---:|---:|---:|---:|---:|---:|
| median | 19,185 | 12,651 | 0.65942 | 21,553 | 0.58697 | -10.99% | 2 |
| multiply | 40,136 | 55,393 | 1.38013 | 40,144 | 1.37986 | -0.02% | 2 |
| memcpy | 22,235 | 28,674 | 1.28959 | 19,928 | 1.43888 | +11.58% | 2 |

The existing [resource model](rvw/arch/ooo-resource.json) is used without
RV64 fitting. C2 supplies XLEN 64 to the instruction decoder. The model has
two-wide fetch, rename and commit, three issue ports, 64 ROB entries,
32 IQ entries, 64 integer physical registers, and 16 load and store entries.
It has two ALU ports and one shared execution port. Cache geometry, GShare,
BTB and RAS settings stay as described in that file. The constant operation
latencies, branch recovery, front-end delay, store drain and replay costs
remain approximations. The RV32 fit has prior exposure to these benchmark
families. This is a parameter-transfer check. It is not a new held-out fit.
IPC uses the full C1/C2 program interval, not the benchmark ROI counters.
IPC error is `100 * (model IPC / RTL IPC - 1)`.
No translated benchmark timing or structure-size decision is qualified.

| Program | Probe check | C2 / retiring slots | Top-down check | Captured rules / firings | Orphan-event warnings |
|---|---|---:|---|---:|---:|
| median | clean | 12,651 / 12,651 | checked | 9 / 0 | 1,280 |
| multiply | clean | 55,393 / 55,393 | checked | 9 / 0 | 512 |
| memcpy | clean | 28,674 / 28,674 | checked | 9 / 0 | 69 |

The build exposes 55 registered probes. `rvw probes check --validate --c2`
checks event fields and retirement counts. It reports the orphan events as
warnings. It does not prove every pipeline-ID relationship. `rvw perf
topdown` checks that retiring slots equal C1 and C2 retirements. Its other
slots use the project's commit-slot partition. Function attribution assigns
lost slots by time. These results do not prove a unique stall cause.

The nine generated queue, pointer, free-list and forwarding rules compile
into the RTL model. Native output capture sees zero firings in each run.
The Sv39 config has 32 physical address bits, so the 32-bit refill bindings
retain the full physical address. The M-only 64-bit physical-width config
was not checked by this run. RV64 negative controls and whole-core formal
proofs were NOT RUN. Zero firings cover only these exercised rules and runs.

Use a private pinned core and the private locks from the setup above. Keep
`RUN_ROOT` outside Git. The riscv-tests source pin is
`d7e86f701b929b5d801f8cda1a4871ab05f452bb`. Its `isa` and `env` sources are
unchanged. Build and run the programs once with the same model:

```sh
export NAX_BENCH_ELFS="$RUN_ROOT/bench64"
export NAX_BENCH_RUN="$RUN_ROOT/bench64-rtl"
nice -n 10 make -s -C Arch/bench SRC="$RISCV_TESTS_SOURCE/benchmarks" \
  BARE_CC=riscv64-unknown-elf-gcc MARCH=rv64im ABI=lp64 \
  BUILD="$NAX_BENCH_ELFS" BENCHES='median multiply memcpy'
rvw --project examples/naxriscv checks generate --all --out "$RUN_ROOT/checks64" --json
export RVW_NAX_CHECKS="$RUN_ROOT/checks64/queues"
python - <<'PYMANIFEST'
import json, os
from pathlib import Path
rows = [dict(config='rv64imasu', elf=str(Path(os.environ['NAX_BENCH_ELFS'])/(n+'.riscv')),
             out=str(Path(os.environ['NAX_BENCH_RUN'])/n), seed=1, mem_latency=0,
             max_cycles=1000000, wall_timeout=120, probes=True, rvfi_trace=True)
        for n in ('median', 'multiply', 'memcpy')]
(Path(os.environ['RUN_ROOT'])/'bench64-jobs.jsonl').write_text(
    '\n'.join(json.dumps(r) for r in rows)+'\n')
PYMANIFEST
nice -n 10 examples/naxriscv/rvw/run.sh run-many \
  --manifest "$RUN_ROOT/bench64-jobs.jsonl" --jobs 1 --persistent
nice -n 10 python examples/naxriscv/rvw/arch/rv64-study.py \
  --runs "$NAX_BENCH_RUN" --elf-dir "$NAX_BENCH_ELFS" \
  --out "$RUN_ROOT/bench64-analysis"
```

The helper runs the existing probe, top-down, timing-model and Spike tools.
It checks their outcomes and prints the IPC table. Full consumer reports
stay in the external output directory. The model configuration SHA256 is
`c8ed44308b842f120a5106d4a4fccbd1a2b99b9b7393b3486a59eab57ce879d2`.

## Benchmark regression tier

The `bench` tier is off in `quick` and `full`. It selects median, vvadd and
multiply. C1 self-checks must pass. The gate compares cycles for the full run of
these fixed instruction streams. Project `core.perf_tolerance` is 0.01.
The tolerance is an allowed increase in cycles. It is not host timing noise.

Recorded baseline: MacBookPro, 2026-11-13, default config, seed 1, added memory
latency 0. These are RTL simulation counts. They are not physical core scores.

| Program | Instructions | Cycles | IPC | Cycle tolerance |
|---|---:|---:|---:|---:|
| median | 10653 | 18061 | 0.589834 | 1% |
| vvadd | 6490 | 5220 | 1.243295 | 1% |
| multiply | 54296 | 38207 | 1.421101 | 1% |

Use a fresh external `RUN_ROOT`. The link path must not exist.
Set the project's source environment and private locks as described above.

```sh
nice -n 15 rvw workloads run --project "$PROJECT" --source "$RISCV_TESTS" --out "$RUN_ROOT"
mkdir -p "$PROJECT/rvw/out"
ln -s "$RUN_ROOT" "$PROJECT/rvw/out/bench"
nice -n 15 rvw regress gate --project "$PROJECT" --tier bench --jobs 1 --base-rev "$BASE" --cand-rev "$CANDIDATE"
```

The gate measures both committed revisions. The table is a dated reference;
it is not a substitute for the gate's baseline capture. Use `--perf-tolerance`
to override the project policy explicitly. Keep all generated results out of Git.


## RV32 scratch CSR selection

`csr.json` selects only `mscratch` from the pinned CSR catalog for RV32.
Its reset value is unknown. Generated assembly writes the register before
it checks a read. U-mode and S-mode access must trap because `mscratch` is
an M-mode CSR. Field access entries do not grant lower-mode CSR access.

Generate the monitor and assembly with:

Use `rvw csr show` / `rvw checks generate` for CSR selection data (`formal csr` CLI subcommand was trimmed).

This selection is input data. Generation does not show that the monitor is
bound to RTL or that the program passed on the core. It does not cover RV64,
other CSRs or privileged ISA compliance.
