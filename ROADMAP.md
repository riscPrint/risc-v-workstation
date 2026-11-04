# Roadmap

The plan for the RISC-V Workstation EDA tools. Tasks are in [TODO.md](TODO.md), under the same
areas. The project goal (core and EDA platform) is in `GOAL.md` of the parent workspace; this file
covers the EDA platform only.

- **Goal:** one integrated platform that replaces the commercial EDA stack for architecture, RTL
  design and verification, built on open-source tools and extended where they fall short.
  We extend the open engines themselves (formal, simulation, UVM, debug) until they match or
  beat the commercial ones: JasperGold and VC Formal (#294), VCS and Xcelium (#295), UVM
  (#296), Verdi (#297). Changes go upstream where possible.
  Synthesis, physical implementation and signoff are out of scope for now.
- **First user:** the BOOM port (`riscPrint/spinal-boom`). Tools start with BOOM and become generic:
  BOOM-specific parts stay in adapters and config.
- **Agents first:** every tool has a command line with JSON output, and `rvw mcp` exposes all of
  them to an AI agent, so an agent can develop a core without a person looking at a GUI.

**Area status:** none, exploring, in progress, usable (in daily use, gaps known), parity (matches or
beats the commercial tools). **Generic status:** BOOM-only, partly generic, generic (documented, works
on other designs), released.

State on 2026-11-04: the P1+P2 integration branch includes first increments for
lint/CDC, sequential equivalence, saved IDE views, native tool bundles, SSH farms,
remote caches and budgets. These extend the earlier regression, co-simulation,
query, coverage and formal tools. They do not establish commercial parity.
Native host qualification and core runtime checks remain open. Emulation has not started.

## Areas

| ID | Area | Replaces | Open-source base | Ours so far | Status | Next |
|---|---|---|---|---|---|---|
| ARCH | Architecture exploration and virtual platforms | Arm Fast Models, Synopsys Platform Architect | gem5, QEMU, Spike, Sail | `Arch/` and `rvw arch`: native gem5 setup, project O3 descriptions, C1 ROI calibration and MCP; native Linux reference image flow (RTL blocked); `rvw perf` | exploring; Bayesian fitting, repeat intervals and prediction ledger; native RTL event correlation pending | Event counters, measurement microbenchmarks, held-out fitting and drift checks |
| IDE | Design entry and IDE | Sigasi Studio, DVT IDE | VS Code, Verible, Metals (Scala) | SpinalBlocks; SpinalDB + `rvw query` | in progress | Cross-navigation in VS Code backed by the design database |
| SIM | Simulation and regression | Synopsys VCS, Cadence Xcelium, Siemens Questa; vManager | Verilator, Icarus Verilog, GHDL | RiscvSim (run contract, BOOM adapter); `rvw regress`; `rvw cov` | usable; C1/dashboard simulation rates; portable LR/SC outcomes; native HDL X/reset, timing and synthesized VHDL subsets; serial server and firmware loading; Linux devices pending | Persistent simulation server (no per-run elaboration); other presets and ACT4 through RiscvSim; extend open simulation to VCS/Xcelium class (#295); full open UVM (#296) |
| VER | Testbenches, VIP, co-simulation | UVM, Questa VIP, Synopsys VIP, Imperas ImperasDV | riscv-tests, ACT4, riscv-dv, TestRIG, Spike, Sail, cocotb | `rvw cosim` (Spike lockstep, Sail offline); riscv-tests/ACT4/VM suites in `rvw regress` | in progress (bounded Accellera UVM component suite; interrupt schedules; Sv39 and privilege campaigns; walk capture; BOOM runtime pending) | Cosim on ACT4, benchmarks and random programs (riscv-dv); interrupt stimulus; TestRIG |
| FV | Formal verification | Cadence JasperGold, Synopsys VC Formal, Siemens Questa Formal | SymbiYosys, Yosys, ABC, pono, avy, eqy, mcy, riscv-formal | SpinalChecks (FV 5); `rvw formal` (FV 7, xprop); proof exclusions and mcy in `rvw cov` (part of FV 6) | in progress (table-driven safety apps and pinned engine benchmark; guarded UNR and structural cones; solver cores and general liveness pending; Sail arithmetic slice and bounded top-port connectivity) | BOOM X candidates; TileLink rules; FV 2 (sequential equivalence), rest of FV 6; extend open engines to JasperGold/VC Formal class (#294) |
| LINT | Lint and clock-domain crossing | Synopsys VC SpyGlass, Siemens Questa CDC | Verible, Verilator lint, Yosys | `rvw lint`: native diagnostics and structural crossing inventory | in progress | Survey open CDC; checks Spinal can emit from clock-domain info |
| DBG | Debug and waveforms | Synopsys Verdi, Cadence SimVision, Questa Visualizer | GTKWave, Surfer | SpinalWaves, SpinalTrace, SpinalKonata, `rvw wave`, `rvw bundle`/`reduce`/`bisect`, `rvw perf` | usable ([#68](https://github.com/riscPrint/risc-v-workstation/issues/68) cross-core caller parity checked) | formal counterexample debugging; Surfer integration; extend open debug to Verdi class (#297) |
| EMU | Emulation and FPGA prototyping | Cadence Palladium and Protium, Synopsys ZeBu | Verilator (multithreaded), open FPGA flows | none | none | Decide: FPGA prototyping, faster simulation, or both |
| PLAT | One integrated platform | All of the above, as one product | VS Code | `rvw` CLI and `rvw mcp`; shared formats C1–C8; separate core projects with `rvw.toml` (integration in progress); VS Code extension with SpinalBlocks | in progress (saved regress/cov/perf VS Code views added; local macOS CI in progress; native qualification pending, #16 and #41) | Qualify native bundles and remote execution; extend saved result navigation |

## Release status (P1+P2 integration branch, 2026-11-04)

Project mode is implemented: install the workstation once, and keep each core's adapters and
settings in its own repository with a root `rvw.toml` (`--project`, `RVW_PROJECT` or upward
discovery). See the [bring-your-own-core guide](docs/BRING_YOUR_OWN_CORE.md).
The [agent setup](docs/AGENT_SETUP.md) and [architecture](docs/AGENT_ARCH.md)
playbooks include commands, checks and failure actions. A scratch VexRiscv
setup validated regression, both gate outcomes, Spike smoke, database queries
and MCP. RV32 architecture models use Minor or TimingSimple approximations.
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

Release cleanup removes machine paths and recorded review output. The release scan
in `rvw/tests/test_release_hygiene.py` checks tracked files and commit/tag metadata.
Its limits are in `rvw/README.md`. Current tool limits stay in tool READMEs.
Review results belong in issues and pull requests, not repository history.

## Where we are against commercial tools

An honest comparison, feature by feature. "Parity" means an agent or engineer can do the same job
with our tools; it does not mean every option of the commercial product exists. The numbers are on
BOOM `small` (2026-10-22, SpinalChecks 2026-10-23).

| Commercial product | Feature | Our equivalent | Level | Main gaps |
|---|---|---|---|---|
| Imperas ImperasDV | Lockstep co-simulation against a reference model | `rvw cosim` (Spike as a library, trace-driven; Sail as a second model) | usable | Compares integer state, memory, traps and privilege; C2 v2 adds Spike FP/flag and declared CSR snapshots. BOOM still exports v1. No vector, hypervisor, debug mode or multi-hart. BOOM: 173/174 riscv-tests match Spike (the other is a real core bug), 171/174 match Sail. |
| VCS / Xcelium / Questa (simulation) | Fast compiled simulation, waves, coverage | Verilator through RiscvSim | usable; serial server, cocotb and native HDL semantic subsets | Serial server is opt-in; standalone runs still elaborate per process. Icarus supports bounded four-state component tests; Verilator remains two-state. No full SystemVerilog testbench language. |
| Cadence vManager, Synopsys VC Execution Manager | Regression management, verdicts, history | `rvw regress` (suites, tiers, cache, known failures, `gate`, history, JUnit) | usable | Native SSH shards and static C3/C4 trend dashboards are first increments. No cluster scheduler, remote cancel acknowledgement, crash recovery or verification closure planner. |
| URG / IMC (coverage) | Code coverage merge, ranking, exclusions | `rvw cov merge/report/rank/select` | usable; exact-instance collection and database declaration mapping added | FSM coverage gated at Verilator 5.052; nested HGLDD leaf mapping and explicit denominator scopes; whole-core Scala mapping remains partial. |
| Functional coverage (SV covergroups) | Cover groups and holes | `rvw cov functional` over RVFI traces (declarative groups) | in progress; Spinal tag export, semantic RVFI bins and closure candidates added | Typed project-defined RTL bins and bounded sequences; automatic sample collection remains adapter-owned. |
| Synopsys Verdi, Cadence SimVision | Waveform debug, active driver tracing | Surfer + SpinalWaves (typed waves), SpinalTrace (dynamic dependency trace), `rvw wave` (CLI) | in progress | No integrated GUI with tracing across waves, source and schematic; no what-if editing of a trace. |
| Verdi debug apps, root-cause analysis | Automatic triage of a failure | `rvw bundle` (last instructions, pipeline snapshot, wave window, SpinalTrace causes, replay), `rvw reduce`, `rvw bisect` | usable (ELF/IRQ reduction) | Historical bisect attempt blocked by adapter API; SpinalTrace on BOOM needs a short window. Strong for agent use, weaker for interactive use. |
| Verdi nTrace / nSchema, Sigasi, DVT | Design navigation: drivers, loads, paths, hierarchy | SpinalDB + `rvw query` (drivers, loads, fan-in/out, paths, hierarchy, hardware diff) | usable for Spinal | Spinal designs only (no general SystemVerilog parser); no clock-domain reasoning. |
| Sigasi / DVT block diagrams | Diagrams of the design | SpinalBlocks (web and VS Code) | usable | Database export; cross-core caller parity checked [#44](https://github.com/riscPrint/risc-v-workstation/issues/44); wave cross-navigation remains [#24](https://github.com/riscPrint/risc-v-workstation/issues/24). |
| Konata-like pipeline viewers (vendor-specific) | Pipeline visualization and performance analysis | SpinalKonata, Konata viewer, `rvw perf` text reports | usable | Stall causes need more probe events; BOOM's probe counts predicated-off commits. |
| JasperGold Superlint, VC Formal AutoChecks / FXP | Checks generated from the design | SpinalChecks (stream handshakes, index ranges, legal states, progress, TileLink bursts); `rvw formal xprop` | in progress; source dispositions set, runtime pending #5; wider local use gates, CSR/HPM access models and subset register-map imports | Far fewer check kinds; no connectivity, CSR or deadlock apps; index checks fire even when the value is unused. BOOM: 516 checks (484 inserted, 32 waived); 24 stream checks have source-backed dispositions; runtime triage remains [#5](https://github.com/riscPrint/risc-v-workstation/issues/5). |
| Jasper state swarm, VC Formal sim-based init | Proof started from a simulation state | `rvw formal from-sim` | in progress | Works on BOOM to depth 16 in ~3 min; no swarm of start points, no automatic depth search. |
| JasperGold / VC Formal engines | Deep proofs: abstraction, engine portfolios, proof grid | SymbiYosys engines (`rvw formal bmc`, engine portfolio option) | in progress: width-checked cuts, safety templates, checked contract composition and unsigned bound mining | No RAM refinement, relational invariant mining or multi-machine runs (FV 1). |
| Jasper COV / UNR, VC Formal FCA | Proof coverage, unreachability | `rvw cov prove` (proven-unreachable exclusions with a vacuity check), `rvw cov mutate` (mcy) | in progress | Structural cone reports available; solver proof cores and property activation remain open. Bounded BOOM RocketALU mutation reviewed. |
| Jasper SEC, VC Formal SEQ | Sequential equivalence | `rvw formal equiv` (eqy, ABC scorr/PDR; advisory dsec) | first increment; revision export in review | Exported RTL only; no BOOM equivalence claim. FV 2 epic: tested project-driven module export, nonzero latency, state encoding and blackbox contracts remain. |
| Jasper C2RTL, VC Formal DPV | Arithmetic against a C model | `SpinalChecks/c2rtl/` | small unsigned combinational units | FV 3; sequential and FP models pending. |
| Jasper SPV, VC Formal FSV | Information flow / security | none | none | FV 4. |
| SpyGlass, Questa CDC / Lint | Lint and CDC | `rvw lint` (Verilator, Verible, SpinalDB structural CDC/RDC) | first increment | No protocol proof, metastability analysis or signoff. Structural results remain findings or inconclusive. |
| Palladium, Protium, ZeBu | Emulation and prototyping | none | none | Phase 3. |
| Arm Fast Models, Platform Architect | Virtual platforms, architecture exploration | `rvw arch` (native gem5, calibrated against the RTL), Spike, `rvw perf` | exploring; Bayesian search, repeated measurements, event correlations and prediction ledger | RV64 O3 and RV32IM Minor/TimingSimple; native event mappings and broader workload validation remain. |
| (no commercial equivalent) | Agent interface over the whole flow | `rvw mcp`: 64 built-in MCP tools (see [reference](docs/COMMAND_REFERENCE.md)), background jobs, cancel | usable | — |

Summary: for the daily loop an agent needs (run, judge, compare with a reference, triage, query the
design, measure coverage, simple formal checks) the open tools are usable today. Deep formal (FV 1–4),
protocol-level CDC signoff, emulation and an integrated debug GUI remain open.

## Components

Every tool in this repository. "For BOOM" is what it does for the core today; "Generic" is how far it
is from being usable on other designs.

| Component | Path | Area | For BOOM | Generic goal | Generic status |
|---|---|---|---|---|---|
| RiscvSim | `RiscvSim/` | SIM, VER | `RiscvSim/boom/run.sh`: build / run / run-many; result JSON, RVFI trace, waves with cycle windows, Konata, coverage, replay | The run contract (C1) and RVFI trace (C2) for any Spinal RISC-V core | opt-in serial persistent regression batches; generic build isolated from BOOM; C2/2 multi-hart writer; bounded two-hart word-atomic/litmus fixture with observers and fault checks (native coherent core coverage pending) |
| VexRiscv example | `examples/vexriscv/` | SIM, VER, IDE | Independent second-core check | External core with C1/C2, regression, Spike and SpinalDB | core-owned project validated; ISA startup cosim mismatch recorded |
| rvw regress | `rvw/src/rvw/regress/`, `rvw/configs/boom.toml` | SIM, VER | Suites (riscv-tests, ACT4, VM, benchmarks, random-timing stress, elaboration), tiers, verdict, `gate`, known failures; quick tier 173/173 | Regression for any core with a C1 adapter and complete C8 inputs | generic config; HDL four-state/timing and GHDL/Yosys subset; external BOOM project validated; C4 /2 dirty outcomes and unchanged-RTL reuse verified; waiver, signature, stored-folder and metric reviews remain experimental (#2, #4) |
| rvw farm | `rvw/src/rvw/farm/` | SIM, PLAT | Native SSH shards, C3/C4 static dashboard | Any core with a C1 adapter and matching native identity | native SSH; host-confirmed cancel, cooperative host reservations, resumed cache transfer and history trends; closure planning pending |
| Accellera UVM component suite | `Uvm/`, `rvw/src/rvw/sim/uvm.py` | SIM, VER | Pinned library; bounded TL-UL and load observation checks | Native SV UVM agents and scoreboards | experimental; no-DPI subset with per-run conformance evidence; full CPU VIP, RAL and C1 integration pending (#296) |
| rvw cosim | `rvw/src/rvw/cosim/`, `Cosim/` | VER | Spike lockstep 173/174, Sail 171/174 on riscv-tests | Any core writing C2 traces, platform in project JSON | C2 v2 Spike state checks and live adapter launch; DUT v2 capture pending |

| rvw bundle / reduce / bisect / wave | `rvw/src/rvw/{bundle,reduce,bisect,wave,runs}/`, `RiscvSim/boom/debug.toml` | DBG | Failure report, reduction, bisection; root-caused the `lsu.scala:1241` assertion | Any core with a C1 adapter and a debug config | generic (BOOM in config) |
| SpinalDB + rvw query | `SpinalDB/`, `rvw/src/rvw/query/` | IDE, PLAT | BOOM design database in ~1 min; queries in under a second | Any Spinal design, built by its project's adapter | generic library; external BOOM project build validated |
| rvw lint | `rvw/src/rvw/lint/` | LINT | Register-boundary inventory; no signoff | Native lint and CDC/RDC for domain-aware designs | generic; pinned Verible, bounded synchronizer/protocol topology, reconvergence and declared reset order; protocol and analog proof unrun |
| rvw soc | `rvw/src/rvw/soc/` | PLAT | Versioned SoC maps and deterministic software exports | Project-owned JSON, existing Spike platform reader, CMSIS-SVD register subset | generic; runtime maps, harness request capture and strict IP-XACT register import; full bridge verification pending |
| rvw cov | `rvw/src/rvw/cov/` | SIM, FV | Coverage merge, ranking, RVFI functional coverage, change-based selection, proof exclusions, mcy | Any Verilator design / RISC-V core | generic; partial Scala attribution; pinned opcode plans, retirement sequences, typed RTL bins and guarded proof cones |
| SpinalChecks + rvw formal | `SpinalChecks/`, `rvw/src/rvw/formal/` | FV | 516 generated checks (24 fire, untriaged); BMC from a riscv-tests state; xprop | Any Spinal design within the supported clock and state model | generic libraries; opt-in sampled multi-clock/async-reset BMC; bounded first-witness X sweep and native parent-context Icarus replay; TileLink/AXI4 protocol checks and reference traffic; BOOM triage pending |
| rvw workloads | `rvw/src/rvw/workloads/` | ARCH | Pinned RV64GC kernel ELFs and reference checks | Open application sets and optional licensed SPEC through the same manifest | generic first increment; Linux applications, sampling restore and SPEC runtime qualification pending (#282) |
| Arch + rvw arch | `Arch/`, `rvw/src/rvw/arch/` | ARCH | Project O3 descriptions, native setup, same-ELF C1 calibration and MCP | One RV64 O3 or RV32IM in-order hart with the bare-metal ROI runtime | generic runner; project SoC topology, interval observations, held-out event fitting, compatibility preflight, Linux reference flow and bounded speed-only DSE; RTL correlation pending |
| SpinalKonata + rvw perf | `SpinalKonata/`, `rvw/src/rvw/perf/` | DBG, ARCH | BOOM probe adapter; text reports on `large` benchmarks | Any design that tags pipeline events; any Kanata log | generic cause/replay events and commit kinds; BOOM probe mapping documented, not wired |
| C model datapath checks | `SpinalChecks/c2rtl/` | FV | No core binding | C references against RTL | unsigned 1–4-bit combinational truth tables; SBY depth 1; sequential and FP pending |
| rvw CLI + MCP project selection | `rvw/`, `docs/BRING_YOUR_OWN_CORE.md` | PLAT | Explicit `--core boom` compatibility; background MCP jobs | Install once; core-owned `rvw.toml` and adapters; `--project`, `RVW_PROJECT`, upward discovery | project interface documented; external BOOM validated, BOOM and VexRiscv projects validated |
| Workstation installer | `scripts/install.sh` | PLAT | Core install; optional native tools; check and dry-run modes | Separate core projects on macOS and Linux | package-manager setup; manual native bundle workflow added; host qualification and offline dependencies open (#71) |
| rvw init | `rvw/src/rvw/init/` | PLAT | Core project scaffolding | Safe core-owned setup files | Spinal/sbt scaffold with optional build wiring, reviewed linker map and query entry; native adapter mapping pending |
| rvw doctor | `rvw/src/rvw/doctor/` | PLAT | Setup diagnostics and explicit installer forwarding | Version, project, adapter and gate preflight checks | optional GUI probes and bounded C2/reference smoke checks; full C1 conformance pending |
| SpinalWaves | `SpinalWaves/` | DBG | Spinal types and source locations in Surfer (port of Tywaves) | Any Spinal design | partly generic: database reader and pinned fork package; WASM migration and interactive checks pending |
| SpinalTrace | `SpinalTrace/` | DBG | Traces a value back to Spinal statements; CLI and GUI (port of ChiselTrace) | Any Spinal design | partly generic; database reader; accuracy status in CLI and GUI |
| SpinalBlocks | `SpinalBlocks/` | IDE | Block diagrams; web host and VS Code feature | Any Spinal design | generic extractor; database export; legacy BOOM entry removed after cross-core caller parity |
| VS Code extension | `vscode/` | PLAT | SpinalBlocks, saved result views and integrated indexed debug session; GUI performance and trace parity pending | One extension, one feature per tool | generic saved-data views; no run identity validation or verdict generation |

Core-side tools that stay in `spinal-boom` for now: the BoomSim harness
and BOOM's Konata probe. The gem5 automation moved here (`Arch/`) on 2026-10-24.

## Integration

- **Shared formats:** C1 (run result), C2 (RVFI trace), C3 (suite results), C4 (verdict), C5
  (failure bundle), C6 (design database), C7 (MCP tools), C8 (input capture, result generations, threat
  model), C9 (native architecture models) in `docs/PLATFORM_CONTRACTS.md`.
- **Design database:** SpinalDB writes the dependency graph, the block JSON and HGLDD from one run;
  SpinalBlocks can consume database exports; legacy extraction remains for parity checks (#44). SpinalTrace and SpinalWaves consumer integration remains #69.
- **Cross-navigation:** waveform signal ↔ block diagram ↔ Scala source ↔ dependency trace (not built).
- **One host:** the VS Code extension hosts SpinalBlocks; waves (Surfer), Konata and SpinalTrace's
  GUI are separate apps.
- **Agent interface:** built-in MCP tools are listed in [the command reference](docs/COMMAND_REFERENCE.md). Init, SoC commands and some CLI actions have no MCP tool.
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
  needs today. Extend the open engines (Yosys/SBY, ABC, pono, rIC3, avy, EBMC, Verilator and
  others) until they match or beat JasperGold, VC Formal, VCS, Xcelium and Verdi; build a full
  open UVM flow (#294–#297). Measure this with head-to-head benchmarks.
- Deterministic work is code; agents reach it through MCP.
- Private native bundle definitions pin source revisions and archives per host.
  Native qualification and full offline dependency packaging remain open. No Docker requirement.
- SpinalHDL first; other HDLs later.

## Limit ownership

Open work stays with the tool README owners: [debug integration #24](https://github.com/riscPrint/risc-v-workstation/issues/24),
[simulation performance #14](https://github.com/riscPrint/risc-v-workstation/issues/14),
[coverage attribution #42](https://github.com/riscPrint/risc-v-workstation/issues/42),
[deeper formal #21](https://github.com/riscPrint/risc-v-workstation/issues/21),
[lint/CDC #22](https://github.com/riscPrint/risc-v-workstation/issues/22),
[emulation #23](https://github.com/riscPrint/risc-v-workstation/issues/23),
[regression farm #25](https://github.com/riscPrint/risc-v-workstation/issues/25) and
[architecture fitting #12](https://github.com/riscPrint/risc-v-workstation/issues/12).
Other formal gaps remain [sequential equivalence #18](https://github.com/riscPrint/risc-v-workstation/issues/18),
[datapath checks #19](https://github.com/riscPrint/risc-v-workstation/issues/19),
[security #20](https://github.com/riscPrint/risc-v-workstation/issues/20),
[proof coverage #62](https://github.com/riscPrint/risc-v-workstation/issues/62),
[CSR checks #85](https://github.com/riscPrint/risc-v-workstation/issues/85) and
[connectivity #107](https://github.com/riscPrint/risc-v-workstation/issues/107).
The IDE scope remains an owner decision in [#77](https://github.com/riscPrint/risc-v-workstation/issues/77).

Retained limit: old BOOM measurement counts above describe their dated runs.
They are not current qualification totals. Parent Track 2 counts are a workspace
summary outside this repository. Use these component rows and tool scope for this
integration branch. No claim of parity, complete capture or complete verification
follows from a component's usable status.
