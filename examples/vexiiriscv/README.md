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

`rv32imasu` adds A, S/U modes, Sv32 and eight PMP entries with 4-byte
regions. `rv64imasu` uses Sv39 and eight PMP entries with 16-byte regions.
Both keep one hart, one lane and cacheless fetch and LSU buses. They do not
implement Sv48, Sv57, H, pointer masking, PBMT or NAPOT page mappings.
The adapter services LR/SC and AMO commands on the native LSU bus. C2 retains
both observed AMO read and write effects. The RV64 profile uses `rvw64.toml`
and `rvw/run64.sh`. The launcher selects XLEN before constructing the driver.
A batch cannot mix XLEN values.

Use a private core copy. Set `VEXIIRISCV`, `RVW_HOME`, `RVW_VEX_LOCK` and
`RISCVSIM_WORK` as in the native setup. From this workstation checkout, also
pass `--source "$VEXIIRISCV"` to `rvw regress run`. The environment variable
alone does not override the regression source checkout.

`rvw/prepare-suites.py --out DIR` builds a selected Sv39 matrix, privilege
controls and the five supported single-hart ordering programs. It records
excluded MMU scenarios and their reasons. Update suite directories in a
project copy of `rvw64.toml` to `DIR/mmu`, `DIR/privilege` and `DIR/ordering`.
Use `rvw regress plan --features rvw/features64.json` to inspect requirements.

`rvw64-devices.toml` selects the optional DeviceApiV1 host binding. Build the
library with `RiscvSim/scripts/build-devices.py`. Set `RVW_DEVICE_LIBRARY`,
`PYTHONHOME` and `PYTHONPATH` from its output before running regressions.
`rvw/devices64.json` supplies CLINT and PLIC regions and output-to-pin routes.
`rvw/clint64.json` is passed as raw JSON to preserve its 64-bit reset value.
The adapter ticks each model before MMIO on every sampled cycle. An explicit
IRQ schedule replaces device input levels for that run. Each run gets fresh
device handles. This path has no checkpoint binding or multi-hart claim.

Current supervisor validation is in progress. No RTL pass count is claimed
for these new configurations until the C1 runs and strict Spike checks finish.
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
