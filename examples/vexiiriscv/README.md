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

The only configuration is `rv32im`: `ParamSimple` defaults with `m` added. It
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

- One configuration. Compressed, atomic, FPU, supervisor, MMU and cache
  configurations need more trace mapping (RVC `rd` decoding, LR/SC and AMO
  effects, I/O accesses).
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
