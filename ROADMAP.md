# Roadmap

The plan for the RISC-V Workstation EDA tools. Tasks are in [TODO.md](TODO.md), under the same
areas. The project goal (core and EDA platform) is in `GOAL.md` of the parent workspace; this file
covers the EDA platform only.

- **Goal:** one integrated platform that replaces the commercial EDA stack for architecture, RTL
  design and verification, built on open-source tools and extended where they fall short.
  Synthesis, physical implementation and signoff are out of scope for now.
- **First user:** the BOOM port (`riscPrint/spinal-boom`). Tools start with BOOM and become generic:
  BOOM-specific parts stay in adapters and config.
- **Agents first:** every tool has a command line with JSON output, and `rvw mcp` exposes all of
  them to an AI agent, so an agent can develop a core without a person looking at a GUI.

**Area status:** none, exploring, in progress, usable (in daily use, gaps known), parity (matches or
beats the commercial tools). **Generic status:** BOOM-only, partly generic, generic (documented, works
on other designs), released.

State on 2026-10-24: phase 1 (regression, co-simulation, failure reports) and phase 2 (design
queries, coverage, generated checks, sim-to-formal, performance reports) are merged into `main` after
review and simplification; open items are in `TODO.md`. Phase 3 (lint/CDC,
sequential equivalence, IDE views, tool bundle, emulation) has not started.

## Areas

| ID | Area | Replaces | Open-source base | Ours so far | Status | Next |
|---|---|---|---|---|---|---|
| ARCH | Architecture exploration and virtual platforms | Arm Fast Models, Synopsys Platform Architect | gem5, QEMU, Spike, Sail | `Arch/` and `rvw arch`: native gem5 setup, project O3 descriptions, C1 ROI calibration and MCP; `rvw perf` | exploring | Event counters, measurement microbenchmarks, held-out fitting and drift checks |
| IDE | Design entry and IDE | Sigasi Studio, DVT IDE | VS Code, Verible, Metals (Scala) | SpinalBlocks; SpinalDB + `rvw query` | in progress | Cross-navigation in VS Code backed by the design database |
| SIM | Simulation and regression | Synopsys VCS, Cadence Xcelium, Siemens Questa; vManager | Verilator, Icarus Verilog, GHDL | RiscvSim (run contract, BOOM adapter); `rvw regress`; `rvw cov` | usable | Persistent simulation server (no per-run elaboration); other presets and ACT4 through RiscvSim |
| VER | Testbenches, VIP, co-simulation | UVM, Questa VIP, Synopsys VIP, Imperas ImperasDV | riscv-tests, ACT4, riscv-dv, TestRIG, Spike, Sail, cocotb | `rvw cosim` (Spike lockstep, Sail offline); riscv-tests/ACT4/VM suites in `rvw regress` | in progress | Cosim on ACT4, benchmarks and random programs (riscv-dv); interrupt stimulus; TestRIG |
| FV | Formal verification | Cadence JasperGold, Synopsys VC Formal, Siemens Questa Formal | SymbiYosys, Yosys, ABC, pono, avy, eqy, mcy, riscv-formal | SpinalChecks (FV 5); `rvw formal` (FV 7, xprop); proof exclusions and mcy in `rvw cov` (part of FV 6) | in progress | BOOM X candidates; TileLink rules; FV 2 (sequential equivalence), rest of FV 6 |
| LINT | Lint and clock-domain crossing | Synopsys VC SpyGlass, Siemens Questa CDC | Verible, Verilator lint, Yosys | none | none | Survey open CDC; checks Spinal can emit from clock-domain info |
| DBG | Debug and waveforms | Synopsys Verdi, Cadence SimVision, Questa Visualizer | GTKWave, Surfer | SpinalWaves, SpinalTrace, SpinalKonata, `rvw wave`, `rvw bundle`/`reduce`/`bisect`, `rvw perf` | usable | SpinalTrace model flag in RiscvSim; formal counterexample debugging; Surfer integration |
| EMU | Emulation and FPGA prototyping | Cadence Palladium and Protium, Synopsys ZeBu | Verilator (multithreaded), open FPGA flows | none | none | Decide: FPGA prototyping, faster simulation, or both |
| PLAT | One integrated platform | All of the above, as one product | VS Code | `rvw` CLI and `rvw mcp`; shared formats C1–C8; separate core projects with `rvw.toml` (integration in progress); VS Code extension with SpinalBlocks | in progress | Show regress/cov/perf results in VS Code; native tool bundle |

## Release status (2026-10-24)

Project mode is implemented: install the workstation once, and keep each core's adapters and
settings in its own repository with a root `rvw.toml` (`--project`, `RVW_PROJECT` or upward
discovery). See the [bring-your-own-core guide](docs/BRING_YOUR_OWN_CORE.md).
The [agent setup](docs/AGENT_SETUP.md) and [architecture](docs/AGENT_ARCH.md)
playbooks include commands, checks and failure actions. A scratch VexRiscv
setup validated regression, both gate outcomes, Spike smoke, database queries
and MCP. The architecture flow stops for this RV32 in-order core.
BOOM as an external
project passed the five-test committed gate (accept, `instret_overflow` still failing), a full Spike
trace match, and SpinalDB and SpinalChecks elaboration. A second core, VexRiscv
(`examples/vexriscv/`, RV32IM), passes 49 ISA tests and 2 programs, matches Spike on a smoke trace
and builds a design database, with no change to generic code. It differs from Spike on absent PMP
CSR access and on `mtval` for `ecall`. Its separate `rvw.toml` project now passes
41 aligned RV32UI tests and a four-test committed gate with equal RTL hashes.
Project-selected Spike smoke and database build/navigation work. Known limits are
in `examples/vexriscv/README.md`. Open tasks are in `TODO.md`.

## Supported scope

The supported and experimental features are listed in the "Status" section of
`README.md`. C8 defines the review rule and threat model. BOOM run identity uses
the hash of generated Verilog. Missing evidence cannot earn a gate acceptance.

Release cleanup removes machine paths and recorded review output. The path check
in `rvw/tests/test_release_hygiene.py` checks tracked text files. Current limits
stay in tool READMEs. Git history retains past reports.

## Where we are against commercial tools

An honest comparison, feature by feature. "Parity" means an agent or engineer can do the same job
with our tools; it does not mean every option of the commercial product exists. The numbers are on
BOOM `small` (2026-10-22, SpinalChecks 2026-10-23).

| Commercial product | Feature | Our equivalent | Level | Main gaps |
|---|---|---|---|---|
| Imperas ImperasDV | Lockstep co-simulation against a reference model | `rvw cosim` (Spike as a library, trace-driven; Sail as a second model) | usable | Compares integer registers, memory, traps, privilege; not FP registers, `fflags` or unread CSR state. No vector, hypervisor, debug mode or multi-hart. BOOM: 173/174 riscv-tests match Spike (the other is a real core bug), 171/174 match Sail. |
| VCS / Xcelium / Questa (simulation) | Fast compiled simulation, waves, coverage | Verilator through RiscvSim | usable | Single machine; each process re-elaborates BOOM (15–25 s); no 4-state simulation; no SystemVerilog testbench language. |
| Cadence vManager, Synopsys VC Execution Manager | Regression management, verdicts, history | `rvw regress` (suites, tiers, cache, known failures, `gate`, history, JUnit) | usable | One machine; no farm/cluster dispatch; no web dashboard or trend charts. |
| URG / IMC (coverage) | Code coverage merge, ranking, exclusions | `rvw cov merge/report/rank/select` | usable | Line/branch/toggle/user only; FSM coverage off (crashes Verilator 5.049); mapping to Scala lines is partial (44k of 1.34M BOOM points). |
| Functional coverage (SV covergroups) | Cover groups and holes | `rvw cov functional` over RVFI traces (declarative groups) | in progress | Instruction-level groups only; no covergroups inside the RTL. |
| Synopsys Verdi, Cadence SimVision | Waveform debug, active driver tracing | Surfer + SpinalWaves (typed waves), SpinalTrace (dynamic dependency trace), `rvw wave` (CLI) | in progress | No integrated GUI with tracing across waves, source and schematic; no what-if editing of a trace. |
| Verdi debug apps, root-cause analysis | Automatic triage of a failure | `rvw bundle` (last instructions, pipeline snapshot, wave window, SpinalTrace causes, replay), `rvw reduce`, `rvw bisect` | usable | Bisect not yet run on real core history; SpinalTrace on BOOM needs a short window. Strong for agent use, weaker for interactive use. |
| Verdi nTrace / nSchema, Sigasi, DVT | Design navigation: drivers, loads, paths, hierarchy | SpinalDB + `rvw query` (drivers, loads, fan-in/out, paths, hierarchy, hardware diff) | usable for Spinal | Spinal designs only (no general SystemVerilog parser); no clock-domain reasoning. |
| Sigasi / DVT block diagrams | Diagrams of the design | SpinalBlocks (web and VS Code) | usable | Not yet backed by the design database; no cross-navigation to waves. |
| Konata-like pipeline viewers (vendor-specific) | Pipeline visualization and performance analysis | SpinalKonata, Konata viewer, `rvw perf` text reports | usable | Stall causes need more probe events; BOOM's probe counts predicated-off commits. |
| JasperGold Superlint, VC Formal AutoChecks / FXP | Checks generated from the design | SpinalChecks (stream handshakes, index ranges, legal states, progress, TileLink bursts); `rvw formal xprop` | in progress | Far fewer check kinds; no connectivity, CSR or deadlock apps; index checks fire even when the value is unused. BOOM: 516 checks (484 inserted, 32 waived); 24 stream checks fire and are not yet triaged (likely legal Chisel `Decoupled` drops). |
| Jasper state swarm, VC Formal sim-based init | Proof started from a simulation state | `rvw formal from-sim` | in progress | Works on BOOM to depth 16 in ~3 min; no swarm of start points, no automatic depth search. |
| JasperGold / VC Formal engines | Deep proofs: abstraction, engine portfolios, proof grid | SymbiYosys engines (`rvw formal bmc`, engine portfolio option) | exploring | No cut points or automatic abstraction, no multi-machine runs (FV 1). |
| Jasper COV / UNR, VC Formal FCA | Proof coverage, unreachability | `rvw cov prove` (proven-unreachable exclusions with a vacuity check), `rvw cov mutate` (mcy) | in progress | No proof-core / cone-of-influence reports; mutation not yet run on a BOOM unit. |
| Jasper SEC, VC Formal SEQ | Sequential equivalence | none (eqy and ABC available, not wired) | none | FV 2. |
| Jasper C2RTL, VC Formal DPV | Arithmetic against a C model | none | none | FV 3. |
| Jasper SPV, VC Formal FSV | Information flow / security | none | none | FV 4. |
| SpyGlass, Questa CDC / Lint | Lint and CDC | none | none | Phase 3. |
| Palladium, Protium, ZeBu | Emulation and prototyping | none | none | Phase 3. |
| Arm Fast Models, Platform Architect | Virtual platforms, architecture exploration | `rvw arch` (native gem5, calibrated against the RTL), Spike, `rvw perf` | exploring | Out-of-order RV64 cores only; IPC comparison, no fitting yet. Next: event counters, microbenchmarks, fitting. |
| (no commercial equivalent) | Agent interface over the whole flow | `rvw mcp`: 48 MCP tools, background jobs, cancel | usable | — |

Summary: for the daily loop an agent needs (run, judge, compare with a reference, triage, query the
design, measure coverage, simple formal checks) the open tools are usable today. Deep formal (FV 1–4),
lint/CDC, emulation and an integrated debug GUI are not yet built.

## Components

Every tool in this repository. "For BOOM" is what it does for the core today; "Generic" is how far it
is from being usable on other designs.

| Component | Path | Area | For BOOM | Generic goal | Generic status |
|---|---|---|---|---|---|
| RiscvSim | `RiscvSim/` | SIM, VER | `RiscvSim/boom/run.sh`: build / run / run-many; result JSON, RVFI trace, waves with cycle windows, Konata, coverage, replay | The run contract (C1) and RVFI trace (C2) for any Spinal RISC-V core | generic library; external BOOM adapter validated |
| VexRiscv example | `examples/vexriscv/` | SIM, VER, IDE | Independent second-core check | External core with C1/C2, regression, Spike and SpinalDB | core-owned project validated; ISA startup cosim mismatch recorded |
| rvw regress | `rvw/src/rvw/regress/`, `rvw/configs/boom.toml` | SIM, VER | Suites (riscv-tests, ACT4, VM, benchmarks, random-timing stress, elaboration), tiers, verdict, `gate`, known failures; quick tier 173/173 | Regression for any core with a C1 adapter and complete C8 inputs | generic config; external BOOM project validated; C4 /2 dirty outcomes and unchanged-RTL reuse verified |
| rvw cosim | `rvw/src/rvw/cosim/`, `Cosim/` | VER | Spike lockstep 173/174, Sail 171/174 on riscv-tests | Any core writing C2 traces, platform in project JSON | generic platform config; external BOOM project trace matched |
| rvw bundle / reduce / bisect / wave | `rvw/src/rvw/{bundle,reduce,bisect,wave,runs}/`, `RiscvSim/boom/debug.toml` | DBG | Failure report, reduction, bisection; root-caused the `lsu.scala:1241` assertion | Any core with a C1 adapter and a debug config | generic (BOOM in config) |
| SpinalDB + rvw query | `SpinalDB/`, `rvw/src/rvw/query/` | IDE, PLAT | BOOM design database in ~1 min; queries in under a second | Any Spinal design, built by its project's adapter | generic library; external BOOM project build validated |
| rvw cov | `rvw/src/rvw/cov/` | SIM, FV | Coverage merge, ranking, RVFI functional coverage, change-based selection, proof exclusions, mcy | Any Verilator design / RISC-V core | generic; partial Scala attribution |
| SpinalChecks + rvw formal | `SpinalChecks/`, `rvw/src/rvw/formal/` | FV | 516 generated checks (24 fire, untriaged); BMC from a riscv-tests state; xprop | Any Spinal design within the supported clock and state model | generic libraries; module X sweep and native Icarus replay; external BOOM checks elaborated |
| Arch + rvw arch | `Arch/`, `rvw/src/rvw/arch/` | ARCH | Project O3 descriptions, native setup, same-ELF C1 calibration and MCP | One RV64 O3 hart with the bare-metal ROI runtime | generic runner; BOOM preset data in projects |
| SpinalKonata + rvw perf | `SpinalKonata/`, `rvw/src/rvw/perf/` | DBG, ARCH | BOOM probe adapter; text reports on `large` benchmarks | Any design that tags pipeline events; any Kanata log | generic; BOOM still uses its own probe |
| rvw CLI + MCP project selection | `rvw/`, `docs/BRING_YOUR_OWN_CORE.md` | PLAT | Explicit `--core boom` compatibility; background MCP jobs | Install once; core-owned `rvw.toml` and adapters; `--project`, `RVW_PROJECT`, upward discovery | project interface documented; external BOOM validated, BOOM and VexRiscv projects validated |
| Workstation installer | `scripts/install.sh` | PLAT | Core install; optional native tools; check and dry-run modes | Separate core projects on macOS and Linux | package-manager setup; native bundle remains open |
| SpinalWaves | `SpinalWaves/` | DBG | Spinal types and source locations in Surfer (port of Tywaves) | Any Spinal design | partly generic: needs the Tywaves fork of Surfer |
| SpinalTrace | `SpinalTrace/` | DBG | Traces a value back to Spinal statements; CLI and GUI (port of ChiselTrace) | Any Spinal design | partly generic |
| SpinalBlocks | `SpinalBlocks/` | IDE | Block diagrams; web host and VS Code feature | Any Spinal design | partly generic: BOOM entry point in the extractor |
| VS Code extension | `vscode/` | PLAT | Hosts SpinalBlocks | One extension, one feature per tool | generic |

Core-side tools that stay in `spinal-boom` for now: the BoomSim harness, the riscv-formal harness
and BOOM's Konata probe. The gem5 automation moved here (`Arch/`) on 2026-10-24.

## Integration

- **Shared formats:** C1 (run result), C2 (RVFI trace), C3 (suite results), C4 (verdict), C5
  (failure bundle), C6 (design database), C7 (MCP tools), C8 (input capture, result generations, threat
  model) in `docs/PLATFORM_CONTRACTS.md`.
- **Design database:** SpinalDB writes the dependency graph, the block JSON and HGLDD from one run;
  SpinalBlocks, SpinalTrace and SpinalWaves still elaborate on their own.
- **Cross-navigation:** waveform signal ↔ block diagram ↔ Scala source ↔ dependency trace (not built).
- **One host:** the VS Code extension hosts SpinalBlocks; waves (Surfer), Konata and SpinalTrace's
  GUI are separate apps.
- **Agent interface:** every tool through `rvw mcp`.
- **Core projects:** installed workstation and separate core repository; project
  paths resolve against `rvw.toml`; core-owned adapters use workstation Scala
  libraries through `RVW_HOME` and offline sbt. Existing bundled BOOM paths stay
  available for explicit legacy selection.

## Decisions

- This repository keeps its own `AGENTS.md`, `ROADMAP.md` and `TODO.md` for the EDA
  platform; the parent workspace keeps the core track.
- One Python command (`rvw`, a subcommand per tool) and one MCP server; shared formats
  fixed in `docs/PLATFORM_CONTRACTS.md`. Cores plug in through a run adapter (C1) and an RVFI trace (C2).
- Tools never report an unearned pass, match or accept; missing evidence is
  `inconclusive`.
- One machine-wide OS file lock (`scripts/with-lock.sh`, `rvw.common.lock`) for heavy
  jobs; process trees are stopped as a group on timeout or cancel.
- Build open replacements for all commercial formal features (FV), not only what BOOM
  needs today.
- Deterministic work is code; agents reach it through MCP.
- The platform ships as pinned native binaries per OS, with no Docker requirement.
- SpinalHDL first; other HDLs later.
