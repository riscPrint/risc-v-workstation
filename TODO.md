# TODO

Open tasks for the areas in [ROADMAP.md](ROADMAP.md). Current limits are in each tool README.
Git history retains completed reviews.

## Release preparation

Done: portable paths, neutral fixtures and removal of recorded history.
The tracked-text path test guards the release tree.

## Gate acceptance

Done: C4 `/2` separates test outcomes from acceptance. Dirty work cannot earn accept.

## Second core (2026-10-24)

Done: External VexRiscv project: regression, committed gate, Spike smoke and database queries.

- [ ] Resolve the VexRiscv/Spike absent-PMP CSR behavior and ECALL `mtval=0x73` mismatch
  before claiming ISA-suite cosim matches. The adapter preserves both observations.

## Agent playbooks (2026-10-24)

Done: [new-core setup](docs/AGENT_SETUP.md) and [architecture](docs/AGENT_ARCH.md) playbooks.
A scratch VexRiscv setup passed the four-test regression and committed gate,
Spike smoke, database queries and MCP. Architecture stops at the RV32/in-order
guard.

## Project mode and second core (2026-10-24)

Done: Install once. Select a core-owned `rvw.toml` with discovery, `--project` or `RVW_PROJECT`.

- [ ] Generic gaps found by VexRiscv: RiscvSim's build loads BOOM's sbt `ProjectRef`; store helpers
  assume 8-byte bus lanes; the Spike setup fixes privilege modes to `MSU` and misaligned accesses to
  trap; the shared driver does not check the ELF XLEN.

- [ ] Cosim on VexRiscv: per-core setting for absent PMP CSRs and `mtval` on `ecall` (Spike writes 0,
  VexRiscv writes the instruction bits).

- [ ] Move BOOM's project files into `spinal-boom` (needs the core agent and the owner).

## Simplification (2026-10-24)

Done: RTL identity and shared input handling are in place. Old mutation results remain observations.

- [ ] Owner decisions still open: support policy for old formats (pre-C8 run sets, designdb `/1`–`/19`,
  legacy resume), retiring the mkdir lock, removing public features (MCP plugins, SDK 1.x, PDG tables,
  `sample_raw`), SpinalChecks stream de-duplication.

- [ ] Optional later: drop the generic `input_commands`/`input_verilator_toolchain` fields once every
  adapter supplies a complete RTL identity.

## Security: Java CVE-2026-91403 (2026-10-23)

Done: Use a patched JDK 21. Host-specific patch records remain outside this repository.

- [ ] At the next JDK update, move to an OpenJDK 21 build that includes the fix (owner's preferred
  source; any build from the OpenJDK source works) and drop the in-place patch.

## Core bugs found by the tools (not fixed here; for `spinal-boom`)

- [ ] `minstret`: after `csrwi minstret,0`, BOOM reads 1 where Spike reads 0 (`rv64mi-p-instret_overflow`,
  found by `rvw cosim`).

- [ ] BOOM's RVFI `mode` reports the new privilege on traps and xRETs (`rvfi.scala`, `r.mode := io.prv`);
  allowed by the `mode_after_change` platform key until fixed.

- [ ] `lsu.scala:1241` assertion (upstream BOOM v4): a cache probe between two loads to the same word
  makes the older load retry after the younger one succeeded. Likely fix: restore the younger load's
  order-failure replay. See `rvw/src/rvw/bundle/README.md`.

- [ ] Possible X-propagation in FpPipeline (`io_dgen_valid`, `io_wakeups_0_valid`) and the ITLB
  (`io_ptw_req_valid`): confirm with a 4-state replay.

- [ ] Rocket `TLArbiter` port (`mshrs.scala:719`) re-arbitrates a stalled A request at the
  Chisel/Spinal boundary (waived in `SpinalChecks/boom/waivers.txt`); decide whether to change it.

- [ ] SpinalChecks (after the stream coverage fix; BOOM `small`, seed 1, 58 programs): two newly
  inserted checks fire. Triage each (core bug or over-strict check); do not waive without a reason.
  - `stream.valid_hold:tile.core.xcpt_pc_req`: 46 firings in six programs, first at cycle 655 in
    `rv64ui-p-jalr` (valid drops while stalled).
  - `stream.payload_stable:arbiter.ups_0_a`: 2 firings in `qsort.riscv`, first at cycle 13001.
  - `rv64ui-p-ma_data` fails with code 668 in the SpinalChecks suite run (both before and after the fix).

- [ ] SpinalChecks (with child-master coverage; BOOM `small`, seed 1, 58 programs): 516 checks,
  484 inserted, 32 waived; **24 fire** (all `stream.valid_hold` / `stream.payload_stable`; no TileLink check).
  Likely cause for most: BOOM came from Chisel, whose `Decoupled` allows `valid` to drop before `ready`
  (only `Irrevocable` forbids it); BOOM's kill/flush queues drop entries on purpose. Decide per stream in the
  core: mark legal drops (with the reason) in `SpinalChecks/boom/`, or fix a real protocol bug. Program results are unchanged (57/58;
  `rv64ui-p-ma_data` code 668).

## ARCH: architecture exploration and virtual platforms

Done: Native gem5 tools, project O3 data and same-ELF C1 calibration.

- [ ] Measure which issue-queue model best represents BOOM. The default data preserve
  the old fallback-unit overlap for historical comparison. `large-disjoint.json`
  is an explicit alternative. Do not treat either as validated cycle accuracy.

- [ ] Broaden architecture models beyond one RV64 O3 hart. Add in-order and RV32 runtime support.

- [ ] Add RTL event counters (`mhpmcounter`s mapped to gem5 stat names).

- [ ] Measurement microbenchmarks, fitting on held-out workloads, nightly drift check, MCP tools.

- [ ] QEMU as a fast reference for Linux/OpenSBI images; Linux toolchain and Buildroot image.

## IDE: design entry and IDE

Done: SpinalBlocks diagrams and SpinalDB navigation.

- [ ] Cross-navigation in VS Code backed by `rvw query where`/`drivers`.

- [ ] SpinalBlocks, SpinalTrace and Surfer read their inputs from the design database instead of
  elaborating again.

- [ ] Check SpinalBlocks and SpinalDB on designs other than BOOM (VexRiscv, NaxRiscv).

- [ ] Decide what the IDE needs beyond VS Code + Metals (navigation from Verilog names to Scala, lint,
  diagrams).

## SIM: simulation and regression

Done: C1 simulation, suites, regression gates and coverage.

- [ ] Persistent simulation server so `run.sh` does not re-elaborate BOOM for every process (15–25 s).

- [ ] Run medium/large/mega/giga, ACT4 and the VM tests through `run.sh`; add timer/external interrupt
  stimulus options.

- [ ] Run the `full` tier; record the `lsu.scala:1241` stress failure as a known failure; time a cold
  `gate` against an older revision.

- [ ] `rvw cov`: finish Scala attribution through HGLDD; restore FSM coverage on a fixed Verilator.

- [ ] Farm/cluster dispatch for regressions; a results dashboard (results already in C3/JUnit).

## VER: testbenches, VIP and co-simulation

Done: Spike lockstep and Sail offline comparison.

- [ ] Cosim on ACT4, the benchmarks and random programs (riscv-dv, pygen or pre-generated).

- [ ] Compare FP registers and `fflags` (extend C2 or the shim).

- [ ] TestRIG: an RVFI-DII adapter so TestRIG can inject instructions and compare against Sail.

- [ ] riscv-vector-tests once vector support starts.

## FV: formal verification

Done: Generated checks, bounded proof, simulation-state proof and proof exclusions.

- [ ] Resolve the BOOM X-propagation candidates; per-module X sweep command; 4-state replay of xprop
  counterexamples.

- [ ] SpinalChecks: gate index checks by use; Flow rules; per-clock-domain checks; unique ids for
  components built in loops.

- [ ] **FV 6. Proof coverage:** proof-core / cone-of-influence reports; mutation on a BOOM unit
  (exclusions and mcy flow exist in `rvw cov`).

- [ ] **FV 2. Sequential equivalence:** wire eqy partitions into ABC `dsec`/`scorr`, with register pairing.

- [ ] **FV 8. Counterexample debugging:** replay with edited inputs through Yosys `sim`; Surfer, SpinalTrace and SpinalWaves views.

- [ ] **FV 4. Information flow:** port CellIFT's taint pass to a Yosys plugin; contract shadow logic for out-of-order cores.

- [ ] **FV 3. Arithmetic vs a C model:** EBMC/hw-cbmc flow (e.g. FPU against SoftFloat).

- [ ] **FV 1. Deeper proofs:** engine portfolios across machines, cut points, abstraction, memories as arrays.

- [ ] **FV 9.** Full SVA through yosys-slang; regression runner over SymbiYosys jobs.

- [ ] Generic riscv-formal harness for any Spinal core with RVFI (today in `spinal-boom/formal/`).

- [ ] RISC-V spec from Sail: generate riscv-formal's per-instruction checks from Sail's SystemVerilog backend.

## LINT: lint and clock-domain crossing

- [ ] Survey open lint and CDC tools (Verible, Verilator lint, Yosys-based CDC research) against
  SpyGlass and Questa CDC.

- [ ] Have Spinal emit CDC checks from its clock-domain information.

## DBG: debug and waveforms

Done: Typed waves, dependency traces, Konata, bundles, reduction and bisection.

- [ ] RiscvSim `--spinaltrace` model flag, replacing the `RiscvSim/boom-spinaltrace` prototype.

- [ ] `rvw bisect` on a real BOOM regression.

- [ ] SpinalWaves: remove or upstream the dependency on the Tywaves fork of Surfer.

- [ ] `rvw perf`: separate predicated-off commits in BOOM's probe; more events to explain load-head waits.

## EMU: emulation and FPGA prototyping

- [ ] Decide the approach: FPGA prototyping, faster simulation, or both.

## PLAT: one integrated platform

Done: Installer, CLI, MCP, shared formats and separate core projects.

- [ ] Resolve the open tool findings and validate the release before tagging.

- [ ] Show regress, coverage and perf results in the VS Code extension; add SpinalWaves, SpinalTrace and
  Konata views.

- [ ] Native tool bundle: pinned binaries per OS (macOS arm64, Linux x86-64/arm64) for Verilator, Spike,
  Sail, QEMU, gem5, oss-cad-suite and a RISC-V GCC; no Docker.

## Architecture model scope

Core projects choose queue models, event counters and fitting targets.
`examples/boom/arch/` is a demonstration. It is not a tuned BOOM model.
