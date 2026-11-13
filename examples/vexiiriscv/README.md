# VexiiRiscv project example

This folder holds the project files for an external
[VexiiRiscv](https://github.com/SpinalHDL/VexiiRiscv) checkout. It is the third
test core, beside BOOM and VexRiscv. Install the workstation as described in
[Bring your own core](../../docs/BRING_YOUR_OWN_CORE.md). Set `RVW_HOME` to that
installation. Keep the core outside the workstation repository.

## Setup

Pinned revisions:

| Repository | Revision |
|---|---|
| VexiiRiscv | `9f70315deb3390b283995c5b8f1bd38215ecf52b` (`dev`, 2026-10-31) |
| `ext/SpinalHDL` (submodule) | `de72faf6062206a89b445e5cc07e32ed982712c8` |
| `ext/rvls` (submodule) | `847ce99fd2b28a5c0ccb1ec2683311cf97a9fefc` |

```sh
git clone https://github.com/SpinalHDL/VexiiRiscv "$HOME/projects/VexiiRiscv"
cd "$HOME/projects/VexiiRiscv"
git checkout -b rvw-project 9f70315deb3390b283995c5b8f1bd38215ecf52b
git submodule update --init ext/SpinalHDL ext/rvls
cp "$RVW_HOME/examples/vexiiriscv/rvw.toml" rvw.toml
cp -R "$RVW_HOME/examples/vexiiriscv/rvw" rvw
unset VEXIIRISCV RVW_PROJECT RVW_CORE
export RVW_PYTHON="$RVW_HOME/rvw/.venv/bin/python"
export RVW_LOCK_PYTHON="$RVW_PYTHON"
export RISCV_TESTS_SOURCE=/path/to/riscv-tests
rvw/build-tests.sh
git add rvw.toml rvw
git commit -m 'Add workstation project files'
```

Use JDK 21, sbt, Verilator, a C++ compiler and make. The other submodules
(`NaxSoftware`, `riscv-isa-sim`) are not necessary.

VexiiRiscv needs its pinned SpinalHDL source. The released SpinalHDL 1.15.0
does not compile it: the SWD debug transport is missing, and
`SimBitVectorPimper.toBigInt` returns `Any`. `rvw/build.sbt` therefore compiles
`ext/SpinalHDL` from source and removes the 1.15.0 jars that RiscvSim and SpinalDB
declare. Run sbt with `'++2.13.14!'`, as the launchers do. The SpinalHDL build
defaults to Scala 2.12. The first build compiles SpinalHDL and takes about five
minutes. Builds run offline after the dependencies are in the local cache.
The adapter holds the `vex` lock (shared with the VexRiscv example) and the `sbt` lock.

## Run from the core project

```sh
rvw regress list
rvw regress run --suite isa --rvfi-trace --out rvw/out/isa --no-index --json
rvw regress gate --tier quick --base-rev 9f70315deb3390b283995c5b8f1bd38215ecf52b \
  --cand-rev HEAD --json
rvw/run.sh run --elf rvw/out/programs/smoke --out rvw/out/smoke \
  --seed 1 --mem-latency 0 --rvfi-trace --json
rvw cosim check --elf rvw/out/programs/smoke --trace rvw/out/smoke/rvfi.jsonl --json
rvw/run.sh run --elf rvw/out/isa/rv32ui-p-add --out rvw/out/konata --konata --json
rvw perf rvw/out/konata/konata.log
rvw query build --config rv32im
rvw query where PrivilegedPlugin_logic_harts_0_privilege
rvw query drivers PrivilegedPlugin_logic_harts_0_privilege
```

`quick` selects `add`, `beq`, `lw` and `sw`. `full` selects 49 aligned RV32UI/UM
ISA tests and two local programs. `rv32ui-p-ma_data` needs misaligned access
support and is excluded.

## Design

The default configuration is `rv32im`: `ParamSimple` defaults with `m` added. It
has machine mode only, one decode and one execute lane, cacheless native fetch
and LSU buses, no MMU, PMP, caches, FPU or debug unit. RAM is 16 MiB at
`0x80000000`. The reset PC is `0x80000000`. The upstream PMA map also has an I/O
region at `0x10000000`; the adapter refuses I/O accesses.

VexiiRiscv has no RVFI port. The C2 trace comes from the upstream
`VexiiRiscvProbe` and its `WhiteboxerPlugin`. These report the committed
register write, load, store and commit of each micro-op, and each trap, in
retirement order. `rvw/src/main/scala/rvwvexii/C2Backend.scala` turns these
events into C2 records:

- `rd` is the instruction's `rd` field when the core reported an integer write.
- `rs1`/`rs2` come from the instruction format. Their values come from a shadow
  register file that only the core's committed writes update.
- `mem_*` give the exact byte address and the access width (`aligned_mem` is
  false in the platform).
- `pc_next` is the pc of the next retirement, or the trap's xepc when a trap
  follows. The last record of a run uses the decoded fall-through target.
- A trap is a C2 trap event. Its `cause` comes from the probe. `tval` and xepc
  come from the trap state machine's registers, which `TrapTapPlugin` exposes.
  The plugin reads core registers and changes no behavior.

The bus models answer in request order after a fixed latency (`--mem-latency`),
or after zero to three seeded wait cycles. Interrupt schedules can drive MSIP,
MTIP and MEIP. Konata uses the upstream Konata backend. Its labels have no
disassembly (the rvls disassembler is not loaded). `--rvfi-check` and
`--soc-map` are refused.

## Measured results (2026-11-13, macOS arm64, Verilator 5.049)

- `rvw regress run --suite isa`: 49 pass, 0 fail, 0 skip. `--suite smoke`: 2 pass.
- `rvw cosim check` with Spike: 49 of 49 ISA traces and both smoke traces match.
- Seeded memory latency (seeds 3 and 7) on `lw`, `sb` and `div`: 6 pass, 6 match.
- Negative control: XOR changed to OR in `IntAluPlugin`. `rvw regress run` on
  `xor`, `xori` and `add` gave 1 pass and 2 fail. Cosim reported a mismatch at
  the first `xor` and the first `xori` (`rd_wdata`).
- `rvw query build`: 2006 signals, 224 registers, PDG, blocks and HGLDD exported.
  `where`, `drivers`, `search`, `hierarchy` and `path` work.
- Konata: `rvw perf` reads the log.

These checks do not prove full ISA, privileged-mode, interrupt, formal or
hardware correctness. They apply only to this configuration.

## Cached configuration

`rv32im_cached` adds the upstream fetch L1 and LSU L1 (64-byte lines, 2 ways x 32 sets =
4 KiB each; the LSU L1 is write-back) and the upstream predictor stack (`BtbPlugin` with RAS,
`GSharePlugin`). `rv32im` stays the default. `rvw/src/main/scala/rvwvexii/L1Buses.scala`
answers the native L1 buses: each refill returns one line, one memory word per cycle, after
the run's memory latency; a writeback burst is stored at once and answered after its last
beat. With an LSU L1 the cacheless responder serves the LSU I/O bus. The BTB, GShare and
RAS RAMs have simulation init content, so the example's `SpinalConfig` now inlines memory
init (`inlineRom = true`); configs without such RAMs give the same Verilog.

Measured 2026-11-13 (suite `isa-cached`, private core copy, `rvw cosim check` against Spike):
49 rv32ui/um-p programs pass and match at memory latency 0 and at seeded latency 0..3 (seed 7).

## Probes

`rvw/src/main/scala/rvwvexii/ProbeTapPlugin.scala` is the second user of
[SpinalProbes](../../SpinalProbes/README.md), after the VexRiscv example. It taps existing
signals only and adds nothing unless the run uses C1 `--probes`.

| Probe | Signals |
|-------|---------|
| `branch learn0` (`cond`) | upstream whitebox learn port: `pcOnLastSlice`, `taken`, `pcTarget`; predicted = `taken xor wasWrong` (no BTB or GShare: the sequential PC) |
| `counter` | cycles, retired (commit ports), branches, cond_branches, mispredicts (HPM 3), loads (HPM 4), stores (HPM 5), flushes |
| `csrWrite csr` | whitebox CSR access port with `writeDone` |
| `interruptTaken irq` | trap whitebox `trap && interrupt`, code, pending PC |
| `bus dbus`, `bus ibus` | `LsuCachelessPlugin` and `FetchCachelessPlugin` bus commands |
| `faultSite privilege` | `PrivilegedPlugin` privilege register |
| `pageWalk ptw response`, `walkResult ptw` | MMU refill state machine: PTE response in `RSP(level)`, then the refill port response (configs with an MMU) |

Results on VexiiRiscv `9f70315d`, seed 1, random memory timing, with the VexRiscv example's
`branches`, `memcsr` and `irqs` ELFs (`rv32im`) and three `rvw regress mmu build` Sv32
programs (`rv32imasu`):

- `branches`: 6001 branch events align one to one with C2 conditional branches
  (`--to bp-events`). 4853 direction misses, equal to the taken count (the core predicts
  not taken). `gshare.json` agrees on 20.1 %.
- `memcsr`: `--to bus` consistent (61 writes, 60 reads, no unretired read); `--to csr-writes`
  consistent (122 events, 122 values checked). VexiiRiscv does not strobe the CSR write port
  for the illegal `csrw satp`; VexRiscv does. Both are consistent with C2.
- `irqs` with the same `--irq-schedule` as VexRiscv: `--to interrupts` consistent (3 and 3).
- `--to fault-sites`: `PrivilegedPlugin_logic_harts_0_privilege` (2 bits). `--to counts`
  writes the calibration counts.
- Sv32 MMU (`--to mmu-walks`, then `rvw.regress.mmu_walk.check_c2` with
  `scenario_accesses`): a level-0 load walk and a level-0 PTE page fault are `consistent`
  with the independent walker (levels, PTE addresses, PTE data, result, PA). A level-1 store
  scenario failed in the program: its leaf maps a misaligned megapage (PA `0x80201000`), so
  the core's page fault is correct. The reference walker gives the same page fault, and the
  DUT walk record matches it. The scenario expectation was wrong, not the core.

Limit: the `retired` counter of `branches` is 35658; C2 has 35660. The last two commits share
the end cycle and are not counted. The cause in the sampling order is not established.

Synthesis safety: run `rvwvexii.ProbeSafety` from the adapter classpath. It elaborates the
core with and without `ProbeTapPlugin` (probes off) and compares the Verilog SHA-256; it exits 1 when
they differ. Measured identical on 2026-11-13.

## Limits

- Compressed, FPU and cached configurations have no validated trace mapping.
  The additional supervisor configurations below are experimental.
- No riscv-formal monitor. The probe is the only commit source.
- `rvw query` cannot see the `rvw_trap_*` tap signals. They are simulation-only.
- SpinalDB and RiscvSim are compiled against SpinalHDL 1.15.0 and run on the
  pinned SpinalHDL source. Binary compatibility is checked only by these runs.

## Adapter controls

From the workstation checkout, with the setup environment:

```sh
VEXIIRISCV=/path/to/VexiiRiscv nice -n 10 rvw/.venv/bin/python -m pytest \
  examples/vexiiriscv/rvw/tests -q --basetemp=/tmp/cw-vexii-pytest
```

`test_vexii_project.py` needs no Scala build. `test_adapter.py` builds and runs
the core.

## Native DPI co-simulation

The example can expose the same generic `riscvsim.LockstepDpi` mailbox and C++
client as VexRiscv. Set `RVW_COSIM_DPI=1` and use `rvw cosim live --lockstep`
with this example's `rvw/run.sh`. Set `RVW_VEX_LOCK=vex-cosim` with a private
`VEXIIRISCV` copy. Keep `RISCVSIM_WORK` inside that private worktree.
The default lock remains `vex`.

The probe supplies a retirement's next PC through the next observed commit.
This creates one retirement of lookahead. The adapter preserves that actual
PC. It does not replace it with a reference value. It buffers C2 events until
the unresolved retirement allows them to be published in cycle order. It
samples the core and probe before sending C2 through the native mailbox.
The final pending store and end record are sent before native simulation closes.

This flow reuses the generic DPI client, C2 validator, Spike checker and C5
report. Core signal bindings and the probe backend stay in this example.
The negative control uses `RVW_COSIM_FAULT_ORDER=1` to flip an observed GPR
writeback bit. The comparator reports the first difference at order 1. Because
of the stated lookahead, another instruction can already have retired in RTL.
This is not a claim that RTL stops before that additional retirement.

Run the native controls with the pinned private source environment:

```sh
nice -n 10 rvw/.venv/bin/python -m pytest examples/vexiiriscv/rvw/tests/test_lockstep_native.py examples/vexiiriscv/rvw/tests/test_lockstep_interrupts.py -q
```

The interrupt controls start with `mtval=7`. They require the actual captured
trap value to be zero, not a value fabricated by the adapter. They cover MSIP
and MTIP input schedules, handler execution and `MRET`. This configuration has
no per-retirement CSR snapshot or debug-module binding. Those capabilities
are not implied by a GPR/memory/trap match.

Native validation on 2026-11-13 used the three pinned source revisions in the
Setup table, with a private core copy and the `vex-cosim` lock. All 49 aligned
ISA programs passed. Spike matched all 49 complete C2 traces: 17,637 compared
instructions, with no synchronization and no applied masks. The DPI clean/fault
control passed. The two Scala backend tests passed. These results cover this
RV32IM configuration and the supplied programs. They do not qualify other cores
or configurations.

The ISA comparison helper accepts a selected core and platform:

```sh
rvw/.venv/bin/python examples/vexriscv/rvw/check-isa.py --core vexiiriscv --platform examples/vexiiriscv/rvw/platform.json jobs.jsonl summary.json
```

Both native interrupt controls also passed after adding an actual `mtval` CSR
read in each handler. The initial value was 7. Each handler read zero, executed
`MRET`, and completed with a Spike match. Both traces recorded input
assertion at cycle 200 and deassertion at cycle 220.

## Generated CSR catalog controls

`csr.json` selects machine `mscratch` and absent `sscratch` for the RV32IM
machine-only example. The scratch reset is unknown. Its first accepted software
write initializes the independent read model. The generated assembly covers
scratch read/write/set/clear behavior and the absent-CSR illegal-instruction trap.

The optional `rvwvexii.CsrChecksRuntime MODEL OUT none|read ELF...` installs
one native `csr.read` check. Build `MODEL` and assembly with `rvw formal csr`.
Compile the assembly with the example linker script. Run each ELF on Spike with
`--isa=rv32im_zicsr_zifencei --priv=m`. Run the native entry under `vex-csr`
and the sbt lock, with nice priority 10. Select a private `VEXIIRISCV` source
checkout with its pinned SpinalHDL dependencies. The slow regression is
`rvw/tests/formal/test_vexii_generated_checks.py`.

The wrapper checks accepted CSR reads against the last accepted write-channel
value. It observes `CsrAccessPlugin.bus` and never reads CSR RAM into expected
state. This is a transaction-storage check. Generated instruction programs also
check instruction-level read/modify/write semantics. The wrapper does not prove
that the CSR access unit decoded each instruction correctly by itself.

The runtime compiles Verilator with `--assert`, reports monitor firings, and
keeps injected read faults as `fail` in `rvw.checks-run/1`. No checked wrapper
is installed in the default adapter. This binding covers one storage word.
Full CSR RAM reset, lower modes, aliases, WARL policies, autonomous hardware
updates and broader catalog qualification remain open under #85.

On 2026-11-13 the current SpinalChecks and private pinned VexiiRiscv source
compiled with cached dependency jars. Both generated programs passed Spike and
native Verilator. The scratch program retired 49 instructions in 203 cycles.
The absent-supervisor-CSR program retired 26 instructions in 158 cycles.
Clean runs had zero firings. The seeded read fault fired the scratch read
checker and retained `fail`; the absent-CSR control stayed clean. Native runs
used `vex-csr`. Formal was NOT RUN. See [the native record](csr-native-results.json).
## Supervisor suite configuration

`rv32imasu` adds A, S/U modes, Sv32, nine ASID bits and eight PMP entries
with 4-byte regions. `rv64imasu` uses Sv39, 16 ASID bits and eight PMP entries with 16-byte regions.
Both keep one hart, one lane and cacheless fetch and LSU buses. They do not
implement Sv48, Sv57, H, pointer masking, PBMT or NAPOT page mappings.
`rvw32.toml` and `rvw/platform32.json` select the RV32 profile; `rvw64.toml`
and `rvw/platform64.json` select RV64.
The adapter services LR/SC and AMO commands on the native LSU bus. C2 retains
both observed AMO read and write effects. The RV64 profile uses `rvw64.toml`
and `rvw/run64.sh`. The launcher selects XLEN before constructing the driver.
A batch cannot mix XLEN values.

Use a private core copy. Set `VEXIIRISCV`, `RVW_HOME`, `RVW_VEX_LOCK` and
`RISCVSIM_WORK` as in the native setup. `RVW_VEX_LOCK` must differ from the
project file's `lock`: `rvw regress run` holds that lock, and an adapter that
asks for the same name waits for its own parent. From this workstation checkout, also
pass `--source "$VEXIIRISCV"` to `rvw regress run`. The environment variable
alone does not override the regression source checkout.

`rvw/prepare-suites.py --features rvw/features64.json --out DIR` asks
`rvw regress plan` which generated families apply to the declared features.
It builds each applicable family with its shared generator: the paging
matrix, fault walks and random programs for the declared satp mode, privilege
controls, PMP, scheduled WFI and the single-hart ordering programs. It writes
`DIR/selection.json` with generated, applicable and excluded counts and a
reason for each exclusion. `rvw/features32.json` selects the Sv32 set. The
project files expect `DIR` at `../../rvw/out/suites64` (or `suites32`) from
this folder; change the suite `dir` values for another location.

`rvw64-devices.toml` selects the optional DeviceApiV1 host binding. Build the
library with `RiscvSim/scripts/build-devices.py`. Set `RVW_DEVICE_LIBRARY`,
`PYTHONHOME` and `PYTHONPATH` from its output before running regressions.
`rvw/devices64.json` supplies CLINT and PLIC regions and output-to-pin routes.
`rvw/clint64.json` is passed as raw JSON to preserve its 64-bit reset value.
The adapter ticks each model before MMIO on every sampled cycle. An explicit
IRQ schedule replaces device input levels for that run. Each run gets fresh
device handles. This path has no checkpoint binding or multi-hart claim.

### Generated suites on RTL (2026-11-13)

Core `9f70315deb3390b283995c5b8f1bd38215ecf52b`, seed 1, memory latency 0,
Verilator 5.049. `rvw regress run --rvfi-trace`, then
`rvw regress cosim RUN --platform rvw/platform64.json` (strict) and
`rvw regress mmu report` for the page-walk check. "Generated" counts all
scenarios of the shared description; the satp-mode subset is in parentheses.

`rv64imasu` (Sv39):

| Family | Generated | Applicable | Run | C1 pass | C1 fail | Spike match | Finding |
|---|---|---|---|---|---|---|---|
| MMU matrix | 589 (147) | 145 | 145 | 143 | 2 | 143 | 2 |
| MMU fault walks | 84 (18) | 18 | 18 | 9 | 9 | 9 | 9 |
| MMU random programs | 8 (2) | 2 | 2 | 2 | 0 | 2 | 0 |
| Privilege controls (TVM/TW/TSR) | 30 | 30 | 30 | 30 | 0 | 30 | 0 |
| PMP (8 entries, 16-byte grain) | 264 | 264 | 264 | 264 | 0 | 264 | 0 |
| Ordering (LR/SC, AMO, AMO fault, FENCE, FENCE.I) | 5 | 5 | 5 | 5 | 0 | 5 | 0 |
| Scheduled WFI (MSIP/MTIP/MEIP pins) | 6 | 6 | 6 | 6 | 0 | 6 | 0 |

`rv32imasu` (Sv32):

| Family | Generated | Applicable | Run | C1 pass | C1 fail | Spike match | Finding |
|---|---|---|---|---|---|---|---|
| MMU matrix | 589 (142) | 140 | 140 | 138 | 2 | 138 | 2 |
| MMU fault walks | 84 (12) | 12 | 12 | 6 | 6 | 6 | 6 |
| MMU random programs | 8 (2) | 2 | 2 | 2 | 0 | 2 | 0 |
| Ordering | 5 | 5 | 5 | 5 | 0 | 5 | 0 |
| Scheduled WFI | 6 | 6 | 6 | 6 | 0 | 6 | 0 |

The two paging matrices exclude only the hardware A/D scenarios. Every C1
failure is one finding: the page walker reads PTEs that PMP denies (all
`walk-denied` and `walk-deny-level-*` programs). See
[the reproduction](findings/ptw-pmp/load.S). The DUT walk records confirm it:
each denied PTE read completes and the walk succeeds, where the reference
walker reports an access fault. Three RV64 and three RV32 scheduled-WFI
programs with the interrupt disabled read `mip` while the pin is asserted.
Spike has no input pins, so they match only with `--allow-sync irq` (one
synchronization each). All other matches are strict.

Not applicable from the declared features: Sv48/Sv57, NAPOT/PBMT, H,
pointer masking, Smepmp, Zacas, cache-block operations and two-hart families.
The RV64 CLINT WFI family needs `device:clint`, which only the device profile
declares; it was not run here. NMI, AIA, Sstc, state-enable and PLIC families
are not in the requirement catalog and need extensions or devices this core
does not have.

### Page-walk observations

C2 `mmu_walks` come from the MMU refill state machine (`WalkTap` and
`WalkCapture`): the start request, each PTE read on the walker's bus port and
the refill response. `rvw regress mmu report` compares them with the
independent Python walker:

| Profile | Family | Consistent | No reference access | C1 fail | Other |
|---|---|---|---|---|---|
| Sv39 | MMU matrix | 92 | 49 | 2 | 2 non-canonical: no walk record |
| Sv39 | Fault walks | 6 | 3 (fetch) | 9 | 0 |
| Sv32 | MMU matrix | 89 | 49 | 2 | 0 |
| Sv32 | Fault walks | 4 | 2 (fetch) | 6 | 0 |

The report keeps failed C1 runs inconclusive. A direct comparison of their
walk records gives `mismatch` for every denied load and store walk. The
checker cannot use random programs alone (it refuses a manifest without a
standalone level-zero scenario). Fetch walks have no reference access plan.
These checks do not cover TLB hits, fences without a walk, or hardware A/D.
The database launcher also honors `RVW_VEX_LOCK`. Use a private checkout and
set `RVW_VEX_LOCK=vex-vexii` for isolated extraction. This selects the core
lock; the shared sbt lock still serializes library compilation.

A fresh private extraction on 2026-11-13 retained 2006 signals and 224
non-pruned registers. It wrote PDG, SpinalBlocks and HGLDD artifacts.
`query where` and `query hierarchy` read the result. The database records
44 PDG warnings, including a mixed-width memory write and missing providers.
Dependency coverage remains partial. No new CPU simulation was run for this
extraction check. An initial 180-second compile limit expired; the cached
retry completed within its 240-second active limit.
### Hardware formal observer prototype

The opt-in `rvwvexii.FormalRvfi` elaboration uses a project-owned hardware plugin.
It is separate from the simulation probe. It is not qualified for ISA signoff.
See [the observer status](formal-observer.md) for the source pins, interface
limits and diagnostic instruction campaign.

Warm launches reuse a completed sbt classpath while source files, resources,
compiled classes and dependency jars retain their hashes. A cache miss runs
sbt under the shared lock. The launcher refuses to save a cache if sources
changed during compilation. `RISCVSIM_CP_CACHE` selects its file. The default
is `vexii-classpath.json` under `RISCVSIM_WORK`, or under the example's target
directory. Native RTL identity and C1 capture still run on every launch.
Set `RVW_CHECKS_ISA=1` on `rvwvexii.CsrChecksRuntime` to include all available
generated rules and write C1 records beside the check observations. The recorded
capture uses core revision `9b63f47fe559dbba7874af9196746412fa1294c1`.
It generated and bound 25 checks. Scratch passed with no firings. The absent-CSR
program fired `stream.valid_hold:PcPlugin_logic_harts_0_output` twice. Its C1
result is fail and its disposition remains open. One external fetch-command
check passed BMC through depth 4. No activation or unbounded proof was measured.
See [the record](checks-qualification.json). Set `RVW_CHECKS_FORMAL=1` as well
to emit formal RTL without simulating. This opt-in path keeps the default adapter.

## Security runs

`rvw/sec/` holds the project data for `rvw sec` native runs on this core: core
binding, case templates, IFT programs and policies, contract, campaign and
model pre-check manifests. See [its README](rvw/sec/README.md) and the
results in [`rvw/src/rvw/sec/README.md`](../../rvw/src/rvw/sec/README.md).
C2 memory addresses use the LSU's actual virtual address sampled when the
native bus accepts the request. An AMO's store half has a stale probe store id;
it binds to the latest hart command at its physical address. C2 `tval` uses
the core's own CSR write expression (`expendPc`, sign extension to XLEN). Micro-op tags bind that address to the probe's
physical load/store observation. A physical-address mismatch rejects the
binding. The adapter does not reconstruct this value from instruction operands
or take it from Spike. C1 `details.translated_addresses` retains both addresses
for requests where they differ. Completion still uses the physical store address.
Page-walk records are separate (see above).

The initial Sv39 run used zero ASID bits. Eight root/remap cases failed their
satp readback check because they request ASID 7. The rich profile now enables
16 ASID bits. Those initial setup failures do not establish a TLB defect.
