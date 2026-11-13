# NaxRiscv project example

This folder holds the project files for an external
[NaxRiscv](https://github.com/SpinalHDL/NaxRiscv) checkout. NaxRiscv is an
out-of-order RISC-V core written in SpinalHDL. It is the first out-of-order core
in the workstation that builds in seconds: the light RTL target for the tools that
are specific to out-of-order execution. Install the workstation as described in
[Bring your own core](../../docs/BRING_YOUR_OWN_CORE.md). Set `RVW_HOME` to that
installation. Keep the core outside the workstation repository. The adapter
does not change NaxRiscv's source.

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
- The pinned SpinalHDL Verilator wrapper constructs the model before it sets the
  handle that `sc_time_stamp()` reads. Verilator 5.049 reads the time during
  construction and the process crashes. `run.sh` adds `-CFLAGS -DVL_TIME_CONTEXT`
  to `SPINAL_VERILATOR_FLAGS`, so Verilator reads its own context time. SpinalHDL
  1.15.0 has a null check instead.

- SpinalDB selects its API shim directory through `SpinalAxis.apiSources`:
  `scala-spinal-legacy/` for this SpinalHDL revision. The legacy shim declares
  the missing port and operator types (`MemReadAsyncWrite`, `Repeat`,
  `VerilogValues`) as types that are never instantiated, so their cases never
  match. `PhaseDeviceDefault`, `ObfuscateConfig` and
  `preventMemToBlackboxTranslation` have stated fallbacks.

SpinalChecks does not compile on this axis yet.

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
- No negative control was run.
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
regression uses with rvls. `rvw/src/main/scala/rvwnax/C2Backend.scala` turns its
events into C2 records:

- The probe does not report the instruction word. `insn` comes from the
  adapter's architectural memory image: the ELF plus every committed store.
- `rd` is the instruction's `rd` field when the probe reported an integer
  write. `rs1`/`rs2` values come from a shadow register file that only committed
  writes update.
- `mem_*` give the exact byte address and the access width, from the probe's
  load and store commits.
- `pc_next` is the pc of the next retirement, or xepc when a trap follows. xepc
  is the ROB pc (from the probe's own table) of the latest commit-time
  reschedule with `trap` set. A `satp` write also reschedules with `trap` set
  without a trap, so only the latest one counts.
- `TapPlugin` exposes the privilege register to simulation. It reads one core
  register and changes no behavior.

The adapter drives the native refill buses: `FetchL1Bus` (one line refill at a
time), `DataMemBus` (line reads in request order, line write-backs) and
`LsuPeripheralBus` (no device: every access answers with an error). RAM is
16 MiB at `0x80000000`. Responses come after a fixed latency (`--mem-latency`)
or after zero to three seeded wait cycles. `tohost` is detected from committed
stores, because the data cache is write-back.

## Limits

- One configuration. No RVC, FPU, interrupts schedules, devices, Konata or
  riscv-formal monitor (`--irq-schedule`, `--konata`, `--rvfi-check` and
  `--soc-map` are refused).
- Generated checks need SpinalChecks on the source axis; not available yet.
- `rvw query build` sets `NAXRISCV` to the project root. Keep the project files in
  the NaxRiscv checkout, or call `rvw/build-db.sh rv32imasu rvw/out/nax.db` with
  `NAXRISCV` set.
