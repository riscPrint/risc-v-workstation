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
| `branch learn0` (cached: `cond`, `call`, `icall`, `ret`; default: `cond`) | upstream whitebox learn port: `pcOnLastSlice`, `taken`, `pcTarget`; cacheless: sequential prediction; cached: carried `ALIGNED_JUMPED` and `ALIGNED_JUMPED_PC` |
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

The cacheless `branches` run has 35658 typed commits and 35660 C2 records.
The typed counter reads the `trapAt` commit ports. C2 uses the upstream
completion-based scheduler, which can emit instructions before those ports fire.
The commit PCs equal the C2 prefix. The remaining records are at the tail.
See [the source analysis and native evidence](rvw/csim/RETIREMENT.md).
Performance reports retain this difference. No constant is added to either count.

Synthesis safety: run `rvwvexii.ProbeSafety` from the adapter classpath. It elaborates the
core with and without `ProbeTapPlugin` (probes off) and compares the Verilog SHA-256; it exits 1 when
they differ. Measured identical on 2026-11-13.

## Limits

- Compressed and FPU configurations have no validated trace mapping.
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
library with `RiscvSim/scripts/build-devices.py --out LIB` and set
`RVW_DEVICE_LIBRARY=LIB`. Leave `PYTHONHOME` and `PYTHONPATH` unset: the
library embeds both paths, and the launcher refuses them because native
identity cannot enumerate their inputs.
`rvw/devices64.json` supplies CLINT and PLIC regions and output-to-pin routes.
`rvw/clint64.json` is passed as raw JSON to preserve its 64-bit reset value.
The adapter ticks each model before MMIO on every sampled cycle. An explicit
IRQ schedule replaces device input levels for that run. Each run gets fresh
device handles. This path has no checkpoint binding or multi-hart claim.

`rvw/features64-devices.json` adds `device:clint`, so `rvw regress plan`
also selects the CLINT WFI family (`examples/privilege/spike-wfi.json`).
`prepare-suites.py --features rvw/features64-devices.json --out DIR` builds it
under `DIR/wfi-clint`; `rvw64-devices.toml` expects `../../rvw/out/suites64d`.
On 2026-11-13 the four programs (MSIP and MTIP wake-up, MIE clear and set)
passed C1 on `rv64imasu` with the CLINT model driving the pins. All four
matched Spike with `rvw regress cosim --allow-sync irq,mmio`: the Spike shim
has no CLINT state, so `mtime` loads and asserted `mip` bits take DUT values
(one or two synchronizations per program). Narrow MMIO stores now pass only
their own byte lanes to the device model; before, a 4-byte MSIP write carried
the replicated upper word and the model refused it.

The adapter serves `rvw.stimulus/1` files (`--stimulus-file`, suite option
`stimulus_file`). When the program stores a step to `stimulus_step`, the
next event drives the PLIC source level through DeviceApiV1 ABI 2
(`set_input`), and the adapter writes the step to `stimulus_ack` after
`settle_ticks`. A passing program that left events unserved becomes C1
`error`. `features64-devices.json` also declares `device:plic` and the SEIP
input (9), so the plan selects `plic` and `plic-delivery`. The PLIC stimulus
paths in `rvw64-devices.toml` are relative to the workstation root, and the
build directories are `cache_paths` entries so regress captures the files.

On 2026-11-13 all 12 PLIC programs (priority, tie, threshold claim, shared
contexts, gateway completion, enable changes; M- and S-context delivery with
global, local and threshold masking) passed C1. A fresh capture with declared
`rvw.external-interrupts/1` evidence resolves the earlier mailbox limitation.
All 12 complete traces match Spike strictly: 1,424 instructions, zero
synchronizations and no masks. The independent PLIC replay checks 36 pin
records, 123 accepted MMIO accesses, 30 claims, eight completions, 27 source
changes, 27 served acknowledgements and six interrupt-taken boundaries.
The six delivery programs each take one interrupt.

The retained evidence (historical counts and regeneration command in the example README) gives every ordered input/device
record with cycle and retirement boundary, plus ELF, RTL and trace hashes.
A missing acknowledgement gives a reference load mismatch. A wrong claim
value and a wrong pin level each fail the independent device check. These
negative controls do not earn a match. Earlier captures without this extension
remain inconclusive. Use the same device profile and stimulus files to capture
fresh evidence, then run `rvw cosim check --strict` with
`rvw/platform64-devices.json`. Rebuild the Spike shim with `Cosim/build.sh`:
this consumer needs shim version 8. The core source is unchanged.

| Family | Generated | Applicable | Run | C1 pass | C1 fail | Spike match | Finding |
|---|---:|---:|---:|---:|---:|---:|---:|
| PLIC | 6 | 6 | 6 | 6 | 0 | 6 | 0 |
| PLIC delivery | 6 | 6 | 6 | 6 | 0 | 6 | 0 |

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
| PMP (8 entries, 4-byte grain) | 394 | 394 | 394 | 394 | 0 | 394 | 0 |
| Ordering | 5 | 5 | 5 | 5 | 0 | 5 | 0 |
| Scheduled WFI | 6 | 6 | 6 | 6 | 0 | 6 | 0 |

The RV32 PMP run generated 394 applicable programs. All 394 passed C1 and
matched Spike in strict replay, with zero synchronizations. The completed RTL
capture was retained from the interrupted worker. The resumed comparison used
a rebuilt Spike shim. See the per-program hashes and results (historical counts and regeneration command in the example README).
This covers standard PMP accesses, locks, priority and MPRV. It does not cover
page-table accesses by the walker.

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
declares; see the device binding below (4/4 match). NMI, AIA, Sstc and state-enable need extensions this profile does not have.
The device profile declares PLIC and runs its two families as recorded above.

The 19 denied-walk failures have one confirmed core cause: PTE reads bypass PMP.
See [the per-program triage, directed Spike reproduction and wave window](findings/ptw-pmp/README.md).
The fetch-fault reference-plan gap is fixed. No failed run becomes a pass.

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
It generated and bound 25 checks. Both scratch and absent-CSR programs passed
with zero firings after the source-reviewed PC hold cancellation binding.
The original two PC valid-hold firings were tool false positives. The PC offer
can be withdrawn on registered hold. See the retained [wave windows](checks-evidence/pc-hold-wave.json).
Set `RVW_CHECKS_WAVE=1` to retain waves from this runtime. Runs use seed 17.
One external fetch-command check passed BMC through depth 4 in the earlier
capture. No activation or unbounded proof was measured.
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

## Interrupt-driven UART echo

`rvw/live-devices.json` defines the RAM, UART FIFO, CLINT and PLIC map. The adapter
uses `LiveDevices` for this map. It connects software, timer and external levels
to the real core interrupt inputs. The existing DeviceApiV1 map remains available.
A request must select one device map. Live MMIO regions must match the project
PMA regions. Device state is fresh for each run.

Run `rvw/programs/device-echo.S` with `--soc-map rvw/live-devices.json` and fixed
memory latency zero. The program enables the UART FIFO and RX interrupt. It
claims the PLIC source, drains five bytes, echoes `echo\n`, and completes the
claim. It also services CLINT software and timer interrupts before reporting
pass through `tohost`.

The native control is `rvw/tests/test_live_devices.py`. Set private
`VEXIIRISCV`, `RVW_VEX_LOCK=vex-simsrv`, `RVW_SBT_LOCK=sbt-simsrv` and
`RISCVSIM_WORK` before running it. This example does not require a plugin
library. OS boot and native checkpoint restore need separate checks.
## Catalog-backed CSR bank readback

`csr-bank.json` selects nine machine CSRs from the pinned catalog: `mscratch`,
`mtval`, `mepc`, `mtvec`, `misa`, `mvendorid`, `marchid`, `mimpid` and `mhartid`.
The model declares reset values, static read/write masks and project IDs.
`CsrBankPlugin` checks accepted reads against independent software-write state.
It uses the CSR interface, so it can check RAM-backed storage without guessing
register names. This project binding accepts one unshifted M-mode view per
32-bit bank. It rejects aliases and other widths. The generic bank model keeps
its broader support.

Generate the trap-free programs with:

```sh
rvw/.venv/bin/python examples/vexiiriscv/rvw/csr-bank-programs.py \
  examples/vexiiriscv/csr-bank.json --out /tmp/vexii-csr-bank
```

Compile each `.S` with RV32IM/Zicsr, the ILP32 ABI and
`examples/vexriscv/rvw/programs/link.ld`. Pass the generated `model.json` and
ELFs to `rvwvexii.CsrChecksRuntime`. Set `RVW_CHECKS_ISA=1` to retain all
available checks. The main accepts both the original scalar model and this
bank model. Keep the source build in a private core copy under `vex-csr` and
`sbt-csr`. The recorded run used cached pinned dependency jars and private core
classes. It did not rebuild those dependencies.

The harness does not install a trap handler. It can therefore test `mtvec` and
`mepc` without the general generator's trap-control setup. Unexpected traps
fail by timeout. It tests legal aligned software writes, set and clear for four
RAM-backed CSRs, and constant reads for five CSRs. It does not test denied
accesses, illegal WARL inputs or lower modes. The general generator still
rejects models that conflict with its own trap setup.

All nine native RTL programs passed at seed 17, with 33 generated and bound
checks and zero firings. Eight programs passed on Spike. The `marchid` program
failed because the project declares 46 and the installed Spike returns 5.
This is a reference configuration difference. It is retained as a failure.
The `mscratch` read-corruption control fired only `csr.read:mscratch`, 15 times.
See [the measured record](csr-bank-native-results.json).

Trap observations invalidate expected `mepc` and `mtval` state. A later complete
software write makes the bank known again. This is software readback evidence.
It does not check trap-update values, all CSR fields, dynamic AIA semantics,
shared aliases, hardware/software update races or whole-core equivalence.

## Stimulus verification plan

[The project plan](verification-plan.json) binds the measured integer,
operand, native-counter and probe evidence. Run it from the workstation root:

```sh
rvw plan status examples/vexiiriscv/verification-plan.json --json
```

The saved status (historical counts and regeneration command in the example README) comes from real native results.
It retains unobserved add classes, native counter holes, missing retirement
pairs. It also records the tested instruction injection hook. Source path aliases are
for display. Raw runs remain in the worker checkout. Missing raw runs on a
clean checkout become explicit evidence holes. The plan covers these bounded
stimulus samples. It does not qualify the whole core or grant C4 acceptance.

## OpenSBI and bounded Linux startup

`rvw/opensbi/prepare.py` builds a reset ELF, DTB and supervisor test payload.
Supply an OpenSBI `fw_jump.bin` built for `rv64ima_zicsr_zifencei`, ABI `lp64`,
`FW_TEXT_START=0x80200000`, `FW_JUMP_ADDR=0x80400000` and an empty
`FW_JUMP_FDT_OFFSET=`. This preserves the DTB address from the reset prelude.
The sample uses OpenSBI revision `bd613dd92113f683052acfb23d9dc8ba60029e0a`.
Build it from a private checkout with the supplied UART/CLINT configuration:

```sh
rvw/.venv/bin/python examples/vexiiriscv/rvw/opensbi/build.py \
  --source /path/to/private/opensbi --out /tmp/new-opensbi-build \
  --llvm-prefix /path/to/llvm/bin
```

The builder uses `FW_OPTIONS=1` to suppress boot diagnostics.
It records configuration, platform-source and firmware hashes. The firmware
uses the project-owned single-hart UART/CLINT platform. Linux receives the
generated DTB. Use `platform/rvw/firmware/fw_jump.bin` from the build directory.
Apple's Clang has no RISC-V backend. Homebrew LLVM and LLD supply the tested build path.

```sh
rvw/.venv/bin/python examples/vexiiriscv/rvw/opensbi/prepare.py \
  --firmware /path/to/fw_jump.bin --out /tmp/new-vexii-boot
examples/vexiiriscv/rvw/run64.sh run --config rv64imasu \
  --elf /tmp/new-vexii-boot/reset.elf \
  --boot-payloads /tmp/new-vexii-boot/payloads.json \
  --soc-map /tmp/new-vexii-boot/devices.json --out /tmp/new-vexii-run \
  --seed 1 --mem-latency 0 --max-cycles 10000000 --wall-timeout 600 --rvfi-trace --json
```

The supervisor payload prints `S`. It calls the SBI base extension. It checks
the return code and specification version 2.0. It reports through `tohost`.
Preparation records hashes for the reset ELF, firmware, payload and DTB. Supply `--kernel /path/to/Image` to place a Linux image at the firmware
jump address. That variant uses 128 MiB RAM and an early-console command line.
Select `--config rv64imacsu_linux` for bounded Linux execution.
This profile ignores the bare-metal `tohost` convention. It cannot earn a
program pass from a Linux memory store. Preparation reserves the first 4 MiB
for reset code and firmware. Use a 600-second
wall limit for bounded Linux execution. No initramfs is included.

The standard C1 launcher cannot save or restore Verilator and harness state.
The separate boot-slice harness below supplies a live bridge path.
The loader captures boot bytes before compilation. Replay starts from reset
and needs the original inputs. The VexRiscv checkpoint sample does not qualify VexiiRiscv restore.

The native OpenSBI control passed at cycle 304,429 with 126,162 retirements.
It observed 14 supervisor instructions and a supervisor ecall. The C2 parser
accepted the complete trace. The firmware reported no PMP configuration warning.
See [the boot sample](rvw/opensbi/results.json) for hashes and source identity.
Live restore through the standard C1 launcher remains open. The boot-slice
harness below has a separate short-run equality check.

The 600-second Linux sample retired 1,726,669 instructions. Supervisor mode
accounted for 1,597,511 of them. It observed 15 MMU walks and 328,491 translated
memory addresses. The last PC was `0xffffffff8021296e` in supervisor mode.
UART output was empty. C1 ended with a wall-clock timeout. This does not
establish a completed Linux boot. See [the prefix sample](rvw/opensbi/linux-results.json).
The Linux run did not capture C2. The generic DTB firmware attempts also
exceeded their bounds. The passing SBI control uses the fixed-map platform.


### Detailed family results (2026-11-13)

The matrix and ordering rows below split the retained RTL campaign. They are
subsets of the aggregate rows above. Do not add them to those totals.
The detailed table uses separate pass, fail and known-finding dispositions.
A known finding is never a pass. Raw C1 failures remain in the aggregate table.
Not run means applicable minus run. Generated programs outside applicability
are excluded, not failed. Superpage rows are subsets of the translation row.
The aligned superpage rows exclude level-0 4 KiB pages.
The eight random privilege runs were captured in #1128. All eight match Spike
strictly with zero synchronizations and no masks. Each crosses 32 seeded
M/S/U transitions, traps, delegation and returns. The planner selects these
families, and `prepare-suites.py` now builds them under `random-privilege`.
The project files select all four ELFs per XLEN with `--suite random-privilege`.

| Profile | Family | Generated | Applicable | Run | Pass and match | Fail | Known finding | Not run |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Vexii RV32 | Accessed/dirty (Svade) | 16 | 2 | 2 | 2 | 0 | 0 | 0 |
| Vexii RV32 | TLB/ASID and fences | 40 | 10 | 10 | 10 | 0 | 0 | 0 |
| Vexii RV32 | Translation matrix beyond walk levels | 533 | 128 | 128 | 126 | 0 | 2 | 0 |
| Vexii RV32 | lrsc | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| Vexii RV32 | amo | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| Vexii RV32 | amo-fault | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| Vexii RV32 | fence | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| Vexii RV32 | fence-i | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| Vexii RV32 | Aligned superpages | 10 | 1 | 1 | 1 | 0 | 0 | 0 |
| Vexii RV32 | Misaligned superpages | 10 | 1 | 1 | 1 | 0 | 0 | 0 |
| Vexii RV32 | random privilege | 4 | 4 | 4 | 4 | 0 | 0 | 0 |
| Vexii RV64 | Accessed/dirty (Svade) | 16 | 2 | 2 | 2 | 0 | 0 | 0 |
| Vexii RV64 | TLB/ASID and fences | 40 | 10 | 10 | 10 | 0 | 0 | 0 |
| Vexii RV64 | Translation matrix beyond walk levels | 533 | 133 | 133 | 131 | 0 | 2 | 0 |
| Vexii RV64 | lrsc | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| Vexii RV64 | amo | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| Vexii RV64 | amo-fault | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| Vexii RV64 | fence | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| Vexii RV64 | fence-i | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
| Vexii RV64 | Aligned superpages | 10 | 2 | 2 | 2 | 0 | 0 | 0 |
| Vexii RV64 | Misaligned superpages | 10 | 2 | 2 | 2 | 0 | 0 | 0 |
| Vexii RV64 | random privilege | 4 | 4 | 4 | 4 | 0 | 0 | 0 |
| Vexii RV64 | reset | 3 | 3 | 3 | 3 | 0 | 0 | 0 |

[The family record](family-results.json) retains the random run identities and
names every matrix subset member. Matrix generated counts span all four satp
modes. The A/D generated count includes hardware-update cases. These profiles
use Svade, so only the two fault-on-clear A/D cases per profile apply.
Hardware A/D updates are not tested. TLB/ASID and fence programs check
architectural results; they do not observe internal TLB hits.

The RV64 reset binding now runs all three programs with retained RAM.
Cold reset uses a fetch loop. Warm reset uses a load loop. Local reset uses a
store loop. Each program drives three five-clock pulses after a 64-clock
mailbox delay. All three pass and match Spike strictly: 507 instructions,
zero synchronizations and no masks. The independent reference resets its
processor and retains only its own memory state. Each load/store delay window
contains 11 retired accesses before assertion. Reset samples check M privilege
and inactive bus requests. Cold, warm and local select the same main pin on
this single-hart core. Separate SoC reset domains and device resets are not
covered. The project declares `harness:reset-events` only for this RV64 profile.
## Instruction injection hook

[The core-side injection sample](rvw/testrig/README.md) binds the instruction
request/response port from project data. Its matching feed passes strict Spike
comparison. Its deliberately changed feed produces the expected mismatch.
The stimulus plan now links the passing native port run. This is a declared
evidence link for the tested hook, not whole-core or live TestRIG qualification.

## Reviewed findings

[The consolidated findings](FINDINGS.md) include suite and generated-check
observations. Identify the 19 reviewed denied-walk failures with:

```sh
rvw regress cosim RUN --platform rvw/platform64.json --findings known-findings.json --json
```

Use `platform32.json` for RV32. Exact reviewed traces report `known_finding`
with ID `VEXII-PTW-PMP-001`. They remain outside pass and match counts.
Changed traces or failure reasons require review. C1 still records failure.

## Repeated reset on RTL

[The reset record](reset-results.json) retains identities, all nine pulse
receipts and the activity counts. Build with:

```sh
rvw privilege build examples/vexiiriscv/rvw/reset64.json --out rvw/out/suites64/reset --json
rvw regress run --project examples/vexiiriscv/rvw64.toml --source "$VEXIIRISCV" --suite reset-cold,reset-warm,reset-local --jobs 1 --rvfi-trace --out RUN --no-index --json
rvw regress cosim RUN --platform examples/vexiiriscv/rvw/platform64.json --json
```

Run from the workstation root. Set private `RVW_VEX_LOCK` and `RVW_SBT_LOCK`
as described above. `prepare-suites.py` also builds the reset family.
`reset64.json` owns pulse timing, the pin name, activity and state expectations.
The initial native attempt timed out because sampling callbacks stop during
reset. Reset control now uses raw clock edges. Bus queues, reservations and
probe bookkeeping clear on assertion. RAM is retained. Native and reference
execution agree across all three restarts. The reference checks each retired
mailbox request, delay, pulse length and state receipt before applying reset.

| Generated | Applicable | Run | Pass and strict match | Fail | Known finding | Not run |
|---:|---:|---:|---:|---:|---:|---:|
| 3 | 3 | 3 | 3 | 0 | 0 | 0 |

## Final generated-family audit

[The audit](suite-family-audit.json) lists every selected family and every
planner exclusion for the RV32 and RV64 supervisor profiles and VexRiscv
M-only profile. All applicable families have retained RTL numbers. The reset
results are fresh. The other rows reuse the named earlier captures. The
superpage subsets were checked against the retained per-program comparisons.
No program outside the declared profiles gets execution credit.

Hardware A/D updates, Sstc and other timer extensions, cache-block operations,
Zacas, H, other satp modes, pointer masking, NAPOT/PBMT and multi-hart families
remain excluded where the required core or harness capability is absent.
MTIP pin and CLINT WFI tests do not establish Sstc support. Each exclusion has
its exact missing-capability reason in the audit. Not run is zero within each
applicable family. Excluded programs remain visible in the generated count.

The audit also includes the CLINT/PLIC RV64 feature plan. Its four WFI and
12 PLIC/delivery programs keep the documented device/reference limits.
Repeated reset with live devices is excluded until a device reset contract
exists. The main-pin reset result does not qualify that combination.

## Cached probe measurements

`rv32im_cached` keeps one lane and machine mode. It adds 4 KiB instruction
and data L1 caches, GShare, BTB and a four-entry RAS. The default remains
`rv32im`. Core sources are unchanged. With probes enabled, all 49 selected
aligned RV32UI/UM programs passed and matched complete Spike traces at
seed 7 and memory latency 0. [The ISA record](rvw/csim/isa-measured.json)
retains input and RTL hashes.

[CacheProbes](rvw/src/main/scala/rvwvexii/CacheProbes.scala) taps physical
instruction lookups, refill beats, fills and invalidation. It records data
access hit/miss, refill, victim eviction, writeback bursts and flush
completion. Its data-cache flush cleans dirty lines and retains tags. Retired
instruction accesses have separate refill-attribution semantics.

The cache sweep completed 3,344 C2 instructions in 20,738 cycles. Its data
cache emitted 769 accesses, 513 misses, 513 fills, 449 evictions and 512
writeback bursts. All 769 data accesses agreed with the component model.
Miss-rate error was zero. RTL recorded one data-cache clean. The model
omits that clean and records 449 writebacks, a count error of -63.
The independent checker was consistent on all four measured programs. It checked 12 early-restart instruction hits in
the cache sweep against exact returned words.

The predictor study describes the selected GShare, BTB and RAS stack. Its
conditional, call and return measurements are recorded in
[the predictor study](rvw/csim/README.md). It uses the actual carried
prediction. `wasWrong` also includes target errors and cannot supply the
predicted direction by itself. The model remains approximate.

`rvw perf` has a commit-stage view and inferred refill/recovery spans. Its
clock window matches C1. The retirement-count difference remains visible.
See [the event-boundary explanation](rvw/csim/RETIREMENT.md). The frozen
three-program timing study reports inconclusive accuracy. Its held-out IPC
errors were +81.54 percent on `branches` and +210.26 percent on the `nop`
cache sweep. No timing fit or fidelity claim is made.

See [the performance record](rvw/csim/perf-measured.json) and
[the commands](rvw/csim/README.md). These results cover selected native
simulation cases. They do not qualify cache coherence, other configs or
physical hardware.

## RV64 ISA profiles

`rvw64m.toml` selects the extra `rv64ima` machine-mode config. It has no MMU,
PMP, cache, compressed instructions or FPU. `rvw64.toml` selects the existing
`rv64imasu` supervisor config with Sv39. Both use the pinned private core
source. `rvw.toml` and its RV32 default are unchanged.

Build the RV64 UI, UM and UA physical-memory ELFs with `rvw/build-tests64.sh`.
Set `RISCV_TESTS_SOURCE` to the external riscv-tests checkout. Then run:

```sh
rvw --project examples/vexiiriscv/rvw64m.toml regress run --suite isa-rv64 \
  --source "$VEXIIRISCV" --rvfi-trace --no-index --out rvw/out/rv64m-isa
rvw regress cosim rvw/out/rv64m-isa \
  --platform examples/vexiiriscv/rvw/platform64m.json
```

Use `rvw64.toml` and `platform64.json` for the supervisor config. Set
`RVW_VEX_LOCK=vex-suites-adapter` and `RVW_SBT_LOCK=sbt-suites`. The regression
holds `vex-suites`. Use at most four simulations. The suite omits only
`rv64ui-p-ma_data`, which requires misaligned data accesses. It retains
unaligned access fault controls in the generated suites. C/F/D are outside
these two profiles. The C2 FPU mapping remains unqualified.

Measured on 2026-11-13: each profile has 85 C1 passes and 85 complete strict
Spike matches: UI 53, UM 13 and UA 19. Both comparisons use zero
synchronizations and zero masks. The record includes each ELF, C1 and C2
SHA-256 in [the RV64 ISA results](rvw/rv64/isa-results.json). No core source
was changed. The source revision is the Setup table's pinned revision.

`rvw/features64m.json` selects LR/SC, AMO, FENCE, FENCE.I and scheduled WFI.
It excludes MMU, PMP, lower-mode privilege controls and AMO fault programs.
The machine `ordering` suite selects the four applicable ordering ELFs.
An exploratory run also executed the PMP-dependent AMO-fault ELF and failed.
That result is outside machine applicability. It is retained in the run log.

The [fresh walker replay](rvw/rv64/walk-replay.json) rechecks retained Sv39
DUT captures with the current independent walker. It does not rerun RTL.
The matrix has 92 consistent, 2 mismatching and 51 inconclusive cases.
Fault walks have 9 consistent and 9 mismatching cases. Both random cases
have no supported access plan and remain inconclusive. The 11 mismatches
are the documented page-walk PMP defect. A consistent walk is separate
from a self-check pass or a complete strict Spike match.

[The retained supervisor counts](rvw/rv64/generated-results.json) separate
456 strict matches, 11 PMP-walk failures and 3 strict IRQ differences.
The three IRQ differences require `--allow-sync irq`. They are not strict
matches. [Fresh strict IRQ replay](rvw/rv64/irq-replay.json) retains the same
three differences. [Fresh machine ordering](rvw/rv64/ordering-results.json)
has four strict matches and the excluded AMO-fault failure described above.

Historical `plic-results.json`: {"seed":1,"memory_latency":0,"counts":{"generated":12,"applicable":12,"run":12,"c1_pass":12,"c1_fail":0,"spike_match":12,"finding":0,"inconclusive":0},"instructions":1424,"event_counts":{"pins":36,"mmio":123,"source":27,"ack":27,"claim":30,"complete":8,"taken":6},"rows":{"records":12},"negative_controls":{"records":3,"statuses":{"mismatch":1,"error":2}},"reference":{"shim_version":8},"isa":"rv64ima_zicsr_zifencei"}.
Raw records are no longer tracked. Regenerate outside the repository:
`rvw regress run --project examples/vexiiriscv/rvw64-devices.toml --suite plic-contexts,plic-disabled,plic-gateway,plic-priority,plic-threshold-claim,plic-tie,plic-delivery-m-0-global,plic-delivery-m-0-local,plic-delivery-m-0-threshold,plic-delivery-s-1-global,plic-delivery-s-1-local,plic-delivery-s-1-threshold --rvfi-trace --out RUN_ROOT; rvw regress cosim RUN_ROOT --platform examples/vexiiriscv/rvw/platform64.json`. Use the pinned inputs and options from [PR #1147](https://github.com/riscPrint/risc-v-workstation/pull/1147).

Historical `pmp32-results.json`: {"scope":"VexiiRiscv RV32 supervisor PMP programs on RTL; strict Spike replay","date":"2026-11-13","core_dirty":false,"profile":"rv32imasu","seed":1,"mem_latency":0,"generator_config":{"entries":4},"platform":"rvw/platform32.json","counts":{"generated":394,"applicable":394,"run":394,"c1_pass":394,"c1_fail":0,"spike_match":394,"finding":0,"inconclusive":0},"allow_sync":{"records":0},"compared_instructions":26798,"rows":{"records":394}}.
Raw records are no longer tracked. Regenerate outside the repository:
`rvw regress run --project examples/vexiiriscv/rvw32.toml --suite pmp --rvfi-trace --out RUN_ROOT; rvw regress cosim RUN_ROOT --platform examples/vexiiriscv/rvw/platform32.json`. Use the pinned inputs and options from [PR #1111](https://github.com/riscPrint/risc-v-workstation/pull/1111).

Run-output JSON files with `summary_only` contain historical counts only.
They are not inputs to `rvw plan`, `rvw evidence`, or coverage merging.
Regenerate full records outside the repository before using those tools.

Historical `verification-status.json`: {"status":"reported","features":{"records":7,"statuses":{"reported_closed":4,"open":3}},"notes":{"records":2},"unassigned_requirements":{"records":0},"summary":{"features":7,"reported_closed":4,"open":3,"holes":5082,"unassigned_requirements":0}}.
Raw records are no longer tracked. Regenerate outside the repository:
`rvw plan status examples/vexiiriscv/verification-plan.json --json`. Use the pinned inputs and options from [PR #1145](https://github.com/riscPrint/risc-v-workstation/pull/1145).

## RV32 and RV64 evidence

| Check | RV32 | RV64 |
|---|---|---|
| Default | `rv32im` remains the default | Extra `rv64ima` M and `rv64imasu` Sv39 profiles |
| riscv-tests | 49 strict matches per existing M and MSU profile | 85 strict matches per M and MSU profile |
| ACT4 reduced-CSR instruction boot | 58 strict matches | 98 strict matches |
| ACT4 standard supervisor boot | 270 failures at missing `mhpmevent3` | 302 failures at the same missing CSR; zero body retirements |
| Native generated checks | Existing RV32 qualification | 25 checks, zero firings on two CSR programs; both traces match Spike strictly |
| Formal ISA | Existing RV32 results remain separate | ADDW, SLLIW and MULW at 32 cycles remain inconclusive |
| Divider pair | Existing RV32 results remain separate | 42 versus 138 case-window cycles, with strict Spike checks on both sides |

See [the complete RV32/RV64 table](../../docs/INTEGRATION_GUIDE.md#vexiiriscv-rv32-and-rv64-status)
for generated-family counts and synchronization limits. The
[tool record](rvw/rv64/TOOLS.md) separates coverage, probes, catalog metadata,
formal attempts and timing evidence. The [RV64 ACT4 supervisor record](rvw/act4-64su/README.md)
keeps its standard-boot failure and minimal reproduction. The
[machine ACT4 record](rvw/act4-64m/README.md) has all 98 strict matches.

No upstream core source was changed. C/F/D suite qualification and whole-core
ISA proof remain open. The mapped RTL security harness and CSR bank remain
RV32-only. The new security C1 adapter handles the RV64 pair.
The standalone `rvw/run64.sh` default remains `rv64imasu`. Select
`--config rv64ima` or the `rvw64m.toml` project for the machine profile.
## Boot slices in a fresh process

The project `rvw/boot-slices.sh` uses the live Spinal register and memory bridge.
It saves a single-clock cacheless RV64 supervisor model at an exact cycle.
It also saves RAM, devices, pending bus replies, the LR/SC reservation and
retirement counters. It does not replay from reset. It uses fixed one-cycle
bus replies. It does not start the upstream C2 probe or write a trace or wave.

Set `RVW_HOME` to this checkout. Set `VEXIIRISCV` to a private pinned core copy.
Source the native tool environment. Keep all output outside the repository:

```sh
rvw/boot-slices.sh RESET_ELF PAYLOADS_JSON DEVICES_JSON RUN_A CHECKPOINT_ZIP fresh 1000
rvw/boot-slices.sh RESET_ELF PAYLOADS_JSON DEVICES_JSON RUN_B CHECKPOINT_ZIP restore 2000
```

The stop cycle is cumulative. Each output directory must be new. The checkpoint
is replaced after each successful slice. An incomplete write has the suffix
`.partial`. Keep the source inputs for the identity check on restore. Set
`RVW_BOOT_WORK` to reuse the native build between processes. The launcher uses
private `vex-linux` and `sbt-linux` locks and nice priority 10.

Run `rvw/tests/test_boot_slices.py` from this example with the private core
selected to compare fresh and resumed console output, retirements, final RTL
state and RAM. A slice result has status `bounded`. It does not claim a Linux
boot or shutdown. C2 capture, wave windows and Spike sampling are not yet bound
to this harness. Checkpoints are trusted same-build data, not portable images.
Set `RVW_BOOT_SECONDS=600` for a wall-time slice. The harness checks this limit
every 1,024 cycles and saves the state at the next settled boundary. It excludes
compilation from this limit. Restore with a stop cycle above the saved cycle.

The native equality check used VexiiRiscv `9b63f47fe559dbba7874af9196746412fa1294c1`
and SpinalHDL `de72faf6062206a89b445e5cc07e32ed982712c8`.
It selected `rv64imacsu_linux`. It split at cycle 1,000 and ended at cycle 2,000.

| Check | Straight run | Fresh-process restore |
|---|---|---|
| Final cycles | 2,000 | 2,000 |
| Retired instructions | 441 | 441 |
| UART output | `KKK` | `KKK` |
| Final RTL registers and memories | Equal | Equal |
| Final RAM, pending bus replies and devices | Equal | Equal |

The test compares the complete final state and RAM entries, not only counts.
It took 274.42 seconds including three launcher invocations and native builds.
These short slices are correctness evidence. They are not boot throughput
measurements. A completed Linux boot remains unproved by this check.

## Minimal Linux workload and shutdown

The [Linux recipe](rvw/linux/README.md) builds a static init and a built-in
initramfs from pinned Linux v6.6.60. Init prints `RVW_LINUX_USERSPACE` and calls
power-off. The `--resumable` preparation profile uses 32 MiB RAM, a 1 MHz
simulation clock and a syscon power-off register. Build OpenSBI with `--linux`
for the matching clock and SBI reset device. The standard preparation map is
preserved when `--resumable` is absent.

```sh
rvw/.venv/bin/python examples/vexiiriscv/rvw/opensbi/build.py \
  --source OPENSBI_SOURCE --out "$RUN_ROOT/opensbi" --llvm-prefix LLVM_BIN --linux
examples/vexiiriscv/rvw/linux/build.sh LINUX_SOURCE "$RUN_ROOT/kernel"
rvw/.venv/bin/python examples/vexiiriscv/rvw/opensbi/prepare.py \
  --firmware "$RUN_ROOT/opensbi/platform/rvw/firmware/fw_jump.bin" \
  --kernel "$RUN_ROOT/kernel/arch/riscv/boot/Image" --resumable --out "$RUN_ROOT/inputs"
RVW_BOOT_SECONDS=600 SPINAL_VERILATOR_FLAGS='-CFLAGS -O3' \
  examples/vexiiriscv/rvw/boot-slices.sh "$RUN_ROOT/inputs/reset.elf" \
  "$RUN_ROOT/inputs/payloads.json" "$RUN_ROOT/inputs/devices.json" \
  "$RUN_ROOT/slice-1" "$RUN_ROOT/boot.zip" fresh 100000000
```

Set the compiler, linker, GNU sed, Flex and Bison paths as described in the
recipe. Keep sources, build trees and run directories outside the repository.
Restore into a new output directory with `restore` in place of `fresh`.
The stop cycle is cumulative. Each successful slice replaces the checkpoint.

| Native check | Cycles | Instructions retired | Wall seconds | Instructions/s |
|---|---:|---:|---:|---:|
| Current ISA properties, minimal kernel, first bounded slice | 3,201,024 | 1,171,289 | 600.94 | 1,949.09 |
| Fresh-process continuation of an earlier Linux checkpoint | 65,536 additional | 19,218 additional | 16.49 | 1,165.26 |

The current first slice printed ISA and ELF capabilities `acim`. It retired
129,728 machine instructions and 1,041,561 supervisor instructions. It had no
user retirements. Its final PC was `0xffffffff8005ef86`, in
`should_skip_region` in `memblock.c`. The last trap was supervisor ecall cause
9 at `0xffffffff800041d0`. The driven interrupt levels were zero. It stopped
at the harness wall limit. This is memory-setup progress, not evidence of a
core hang. Userspace and shutdown remain unproved by this first slice. The
continuation row uses a different earlier kernel image and is restore evidence.
It is not a paired throughput comparison.

The native run used the source pins from the boot-slice equality check above.
The Linux pin is `9b5aad3a7498c261116a0251fe57f14ba9c4c6cf`. OpenSBI is pinned
to `bd613dd92113f683052acfb23d9dc8ba60029e0a`. The kernel Image is about 2 MiB.
On this case-insensitive macOS filesystem, Linux's case-clashing network and
litmus files mark the checkout dirty. This profile does not compile those files.

The live UART now supports the FIFO and loopback discovery accesses that the
Linux 8250 driver uses. The current DTB ISA properties work with legacy ISA
fallback disabled. The power-off model latches only its configured command.
The native device and RAM tests passed all 10 checks. Six fast recipe and debug
conversion tests passed. A diagnostic C1 view produced an `rvw bundle` without
a trace or wave. It reports the missing evidence and remains inconclusive for
C1 replay and regression acceptance. See the recipe for the exact commands.

The first measured launcher applied nice priority twice and ran at niceness
20. The long-run profile corrects that increment and defaults to optimization
level 3 with one Verilator thread. No trace or wave was written for these boot slices.

## Dependency debug measurements

The database entry resolves its device map from `RVW_ADAPTER` when no simulator
JVM property exists. `rvw/build-db.sh` selects the pinned SpinalHDL source axis.
Set `RVW_VEX_LOCK=vex-trace`, `RVW_SBT_LOCK=sbt-trace` and `RVW_NICE=15` for a
private trace build. The adapter records the wave time of cycle one through
`SimSession.runCtl`.

| Private RV32IM check | Measured result |
|---|---|
| Database | 4 components; 2,000 signals; 3 memories; 1,785 assignments; 291 conditions; 2,403 edges |
| Elaboration / extraction | 11.6 s / 16.2 s |
| PDG / blocks / HGLDD | 2.1 s / 1.5 s / 5.8 s; stored gzip sizes 99,351 / 50,721 / 57,997 bytes |
| Instrumented smoke | 100 cycles; 18 retirements; 48.3 s model setup |
| FST window | Cycles 10 to 40; 27,602 bytes |

The cold source build took 465 s before the missing device-map property stopped
elaboration. The corrected warm database command took 66 s. These results cover
extraction and one short simulation. They do not establish complete causal
attribution, GUI rendering or other configurations.

## Extra floating-point profiles

The FP attempt uses private core revision
`9b63f47fe559dbba7874af9196746412fa1294c1`. It has no tracked source changes.
This differs from the older integer profile pin in the Setup table.

| Config | ISA | Mode | Default change | Verification state |
|---|---|---|---|---|
| `rv32imafc` | RV32IMAFC | M | None | Adapter compiled; RTL qualification pending |
| `rv64imafdc` | RV64IMAFDC | M | None | Adapter compiled; RTL qualification pending |

Use `rvw32fp.toml` or `rvw64fp.toml`. Set `RVW_FPU_RUN_ROOT` outside the
repository. Set the private core and lock environment as in the setup above.
Use `RVW_VEX_LOCK=vex-fpu`, `RVW_SBT_LOCK=sbt-fpu` and `RVW_NICE=15`.
`rvw/fpu/build-tests.sh 32` builds F/C; `64` builds F/D/C. Select `fp-isa`
with `rvw regress run --rvfi-trace --jobs 2`. Compare with the matching
`rvw/platform32fp.json` or `platform64fp.json` using `rvw regress cosim`.
The C2/2 capture includes FP destinations, fcsr and mstatus. Their native
retirement timing still needs strict Spike validation. No FP match is claimed.
