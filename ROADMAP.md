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

Dated audit state on 2026-11-13: the push added native core adapters, persistent simulation,
probes, component models, generated checks, bounded formal flows, VIP and agent tools.
The [audit](docs/status/2026-11-13/ISSUES.md) records reported evidence and remaining work.
Its corrected collection covers 865 merged PR bodies through 16:37:04 UTC.
The [owner summary](docs/status/2026-11-13/SUMMARY.md) gives the dated limits.
Selected later cache-security (#1255) and RV64 ACT4 (#1257) updates are cited below.
The [integration guide](docs/INTEGRATION_GUIDE.md) records measured HDL subsets.
Real core RTL, seeded fixtures, reference models and unit tests have different scopes.
The audit Linux attempt timed out. A later minimal Linux boot completed, as recorded below.
ACT4 standard supervisor bodies remain unqualified. No area earns parity.
Emulation has not started. This document update ran no simulation, build or proof.

## Reconciliation with main on 2026-11-17

Sources were read at main `7009b61b`.
The tables below retain the dated audit scope. This table supersedes older limits
for the named slices only. Results were read from committed sources, not rerun.
No whole-core qualification or commercial parity follows from these results.

| Slice | Reported result | Remaining limit and exact source |
|---|---|---|
| Linux boot | Two minimal VexiiRiscv kernel recipes reach the userspace marker and power-off. The recipe without optional crypto boot tests takes 38,946,382 cycles and retires 13,854,575 instructions. | No C2 or wave in these boot slices. Replay and regression acceptance remain inconclusive. [Boot record](docs/INTEGRATION_GUIDE.md#boot-an-os-on-your-core). |
| Checkpoint restore | Straight and fresh-process runs reach 2,000 cycles and 441 retirements with equal full state, RAM and `KKK` UART output. | Short same-build equality check. General portable restore remains open. [Core record](examples/vexiiriscv/README.md#minimal-linux-workload-and-shutdown). |
| VexiiRiscv floating point | RV32 and RV64 have 110 and 236 strict machine ACT4 matches. Across ISA, ACT4 and directed tests, 484 runs strictly match. | Separate flags-only probes fail FS Dirty on both widths. Supervisor FP and OS context switches remain unqualified. [FP record](examples/vexiiriscv/README.md#extra-floating-point-profiles). |
| NaxRiscv RV64 ACT4 | Both selected targets have 98 C1 passes and 98 complete strict matches each. | Standard Sm, S/U and Sv39 ACT4 remain NOT RUN. [ACT4 record](docs/ACT4.md#naxriscv-rv64-instruction-profile). |
| Ibex | 51 ISA C1 passes and strict matches. All 148 ACT4 runs pass C1 but differ first at reset mtvec. | No strict ACT4 match or whole-core qualification. [Ibex record](examples/ibex/README.md#result-scope). |
| Frozen non-BOOM rerun | At source `f94b3a3b18a64f1bfd361115fc978c3848e12798`, slow Python has 7,964 passes, one failure and 203 skips. Released Scala has 519 passes. | Native Spike PLIC disagreement remains. Old Scala has six failures, five cancellations and two native crashes or aborts. SMP regression lacks captured inputs. This does not qualify later main. [Suite record](docs/status/2026-11-13/FULL_SUITE.md). |
| Paired security | Adapters reject differing executed model identities. Expanded Vex campaign inputs were added. | No new native campaign qualification. [Security contract](docs/contracts/sec.md). |
| CSR selections | RV32 scratch selections exist for NaxRiscv and OoO Mini. | RTL binding and native runs remain open (#1505). [CSR limits](rvw/src/rvw/csr/README.md). |
| Sampled RTL | `rvw sample` selects BBV points and checks checkpoint replay through a project adapter. | Initial scope is single-hart RV32IM M-mode physical RAM. Cached adapters and long-workload estimates remain unqualified. [Sample limits](rvw/src/rvw/sample/README.md). |

## Areas

These rows describe the audit cutoff. Apply the later slice updates above.

| ID | Area | Replaces | Open-source base | Ours so far | Status | Next |
|---|---|---|---|---|---|---|
| ARCH | Architecture exploration and virtual platforms | Arm Fast Models, Synopsys Platform Architect | gem5, QEMU, Spike, Sail | Measured component/probe comparisons and the 30-run NaxRiscv capacity matrix (#1206). Corrected final window model meets only 6/15 nonzero deltas (#1252). | exploring | Use RTL for structure-size decisions. Separate absolute IPC fit, delta accuracy and rank agreement. |
| IDE | Design entry and IDE | Sigasi Studio, DVT IDE | VS Code, Verible, Metals (Scala) | Slang, GHDL and FIRRTL front ends; HDL diagrams; semantic queries; corrected imported aliases and source coverage locators. | in progress | Check native editor use, source locations and unseen designs. Keep stripped-comment and ambiguous-source gaps visible. |
| SIM | Simulation and regression | Synopsys VCS, Cadence Xcelium, Siemens Questa; vManager | Verilator, Icarus Verilog, GHDL | Persistent servers, device reset, thread variants, replay reduction, OpenSBI supervisor control and bounded Linux execution. | usable | Complete Linux boot and trace capture. Qualify live checkpoint/device bindings, second-machine replay and repeated throughput controls. |
| VER | Testbenches, VIP, co-simulation | UVM, Questa VIP, Synopsys VIP, Imperas ImperasDV | riscv-tests, ACT4, riscv-dv, TestRIG, Spike, Sail, cocotb | Strict device-input replay, 12 PLIC matches, ACT4 instruction campaigns, privilege/MMU suites and native Python/SV verification subsets. | in progress | Resolve standard CSR bootstrap compatibility. Execute privileged bodies. Retain independent device evidence and complete test denominators. |
| FV | Formal verification | Cadence JasperGold, Synopsys VC Formal, Siemens Questa Formal | SymbiYosys, Yosys, ABC, pono, avy, eqy, mcy, riscv-formal | Shared CSR data, triggered generated checks, bounded helper groups, real module equivalence and restricted datapath proofs. | in progress | Resolve six current activation misses and new stream failures. Qualify reset/observer semantics and full-core scope. |
| LINT | Lint and clock-domain crossing | Synopsys VC SpyGlass, Siemens Questa CDC | Verible, Verilator lint, Yosys | Reset crossings, typed CDC generation, SDC checks, HDL domain import and VS Code diagnostics. | in progress | Qualify real design crossings and reset order. Run the pinned commercial comparison. |
| DBG | Debug and waveforms | Synopsys Verdi, Cadence SimVision, Questa Visualizer | GTKWave, Surfer | Indexed waves, transactions, replay, real DMI slices, portable inputs, reused-ID Kanata and native UART/per-hart reduction. | usable | Check interactive navigation, debug deviations, trace recovery and replay identities. Keep native and architectural state distinct. |
| EMU | Emulation and FPGA prototyping | Cadence Palladium and Protium, Synopsys ZeBu | Verilator (multithreaded), open FPGA flows | No emulation or FPGA qualification in the collected PRs. | none | Owner decides the scope of #23. Do not infer emulation from faster simulation. |
| PLAT | One integrated platform | All of the above, as one product | VS Code | MCP effects/profiles/workflows, one CSR API, weakest-input plan summaries, farm native history/budgets and CI report wiring. | in progress | Add installer IDs for llvm-mca, MCY and kubectl. Qualify clean installs, cluster execution and CI runtime tiers. Local committed farm gates accept/accept/reject (#1163). |

## Dated release measurements (2026-11-04)

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
with our tools; it does not mean every option of the commercial product exists. Historical BOOM numbers below are on
BOOM `small` (2026-10-22, SpinalChecks 2026-10-23). Current scope follows the
2026-11-13 audit and dry-run reports. No head-to-head commercial comparison ran.

| Commercial product | Feature | Our equivalent | Level | Main gaps |
|---|---|---|---|---|
| Imperas ImperasDV | Lockstep co-simulation against a reference model | `rvw cosim` (Spike as a library, trace-driven; Sail as a second model) | usable | Historical BOOM: 173/174 Spike and 171/174 Sail matches. Twelve fresh PLIC traces match with ordered device evidence. V/H capture, full CSR state and multi-hart reference scope remain open. |
| VCS / Xcelium / Questa (simulation) | Fast compiled simulation, waves, coverage | Verilator through RiscvSim; persistent servers, device plugins, Arcilator comparison and bounded HDL backends | usable | Persistent Vex runs and bounded native HDL semantics work. Linux timed out at 600 seconds with no C2. Live checkpoint restore and broader device bindings remain open. |
| Cadence vManager, Synopsys VC Execution Manager | Regression management, verdicts, history | `rvw regress` (suites, tiers, cache, known failures, `gate`, history, JUnit) | usable | Native SSH crash/cancel and budget controls ran. Committed VexRiscv farm gates accept a repeat and a changed passing revision and reject the planted fault (#1163). Kubernetes runtime and multi-user scheduling remain open. |
| URG / IMC (coverage) | Code coverage merge, ranking, exclusions | `rvw cov merge/report/rank/select` | usable | Real HDL source reports work. Chisel links 6562/9716 points; VHDL links 2777/57336. Unmapped points remain. Mapping is not coverage closure. |
| Functional coverage (SV covergroups) | Cover groups and holes | `rvw cov functional`, source reports, probe goals and smoke closure candidates | in progress | ACT4 reports keep observed and qualified populations separate. All 270 standard supervisor cases fail in bootstrap. RTL bins need project sampling and complete denominators. |
| Synopsys Verdi, Cadence SimVision | Waveform debug, active driver tracing | Surfer + SpinalWaves (typed waves), SpinalTrace (dynamic dependency trace), `rvw wave` (CLI) | in progress | Indexed waves and transaction joins exist. Live GUI cross-navigation and complete source/trace joins remain unqualified. |
| Verdi debug apps, root-cause analysis | Automatic triage of a failure | `rvw bundle` (last instructions, pipeline snapshot, wave window, SpinalTrace causes, replay), `rvw reduce`, `rvw bisect` | usable | Native UART and per-hart reduction ran. Second-machine replay, full checkpoint state and general history bisection remain open. |
| Verdi nTrace / nSchema, Sigasi, DVT | Design navigation: drivers, loads, paths, hierarchy | SpinalDB + `rvw query`; Yosys/slang, GHDL and FIRRTL imports | usable | SpinalDB plus Yosys/slang, GHDL and FIRRTL imported real core subsets. Lowered graphs, ambiguous source spans and incomplete aliases limit semantic navigation. |
| Sigasi / DVT block diagrams | Diagrams of the design | SpinalBlocks (web and VS Code) | usable | HDL diagram exports ran. Viewer rendering and wave/source cross-navigation remain unqualified in the dry runs. |
| Konata-like pipeline viewers (vendor-specific) | Pipeline visualization and performance analysis | SpinalKonata, Konata viewer, `rvw perf` text reports | usable | BOOM, Vexii and Nax probe slices ran. Nax orphan events and BOOM SFB endpoint difference remain. Larger OoO causal attribution needs explicit probes. |
| JasperGold Superlint, VC Formal AutoChecks / FXP | Checks generated from the design | SpinalChecks, `rvw checks plan`, shared CSR data and `rvw formal xprop` | in progress | Generated Vex/Vexii checks ran. Six current activation misses and new backpressure failures remain. One dated BOOM ID is unmapped. Zero firings alone do not show activation. |
| Jasper state swarm, VC Formal sim-based init | Proof started from a simulation state | `rvw formal from-sim`, `swarm`, `depth-search` | in progress | Selected-state and finite-depth campaigns exist. Reset reachability, full state transfer and witness reconstruction remain open. |
| JasperGold / VC Formal engines | Deep proofs: abstraction, engine portfolios, proof grid | SymbiYosys engines (`rvw formal bmc`, engine portfolio option) | in progress | Real RTL portfolios ran, but 37 later ISA attempts add zero proofs. RAM contracts, restrictions and whole-core scale remain limits. |
| Jasper COV / UNR, VC Formal FCA | Proof coverage, unreachability | `rvw cov prove` (proven-unreachable exclusions with a vacuity check), `rvw cov mutate` (mcy) | in progress | Guarded exclusions and mutation controls exist. Solver-core attribution, vacuity and real-core activation need separate evidence. |
| Jasper SEC, VC Formal SEQ | Sequential equivalence | `rvw formal equiv` (eqy, ABC scorr/PDR; advisory dsec) | in progress | Extracted module and RAM/vector FIFO comparisons ran. General retiming, automatic state mapping and unrestricted whole-core equivalence remain open. |
| Jasper C2RTL, VC Formal DPV | Arithmetic against a C model | `SpinalChecks/c2rtl/` | in progress | Vexii split-multiplier word-operator composition closes with trusted $mul semantics (#1199). Nax unsigned 32-bit helper transaction certificate closes (#1215). Optional IPC division by zero fails on core RTL (#1170). Signed wrappers and integrated core writeback remain open. |
| Jasper SPV, VC Formal FSV | Information flow / security | `rvw formal security`; `rvw sec` dynamic campaigns and model checks | in progress | Two-copy bounded and mapped IFT slices ran. PMP metadata export is fixed (#1180). Starting-byte isolation passes at depth 16, but attempted-access reach times out (#1221). Deeper observation/initialization failures and physical leakage remain open. |
| SpyGlass, Questa CDC / Lint | Lint and CDC | `rvw lint` (Verilator, Verible, SpinalDB structural CDC/RDC) | in progress | Structural CDC/RDC and bounded digital fixtures exist. 2507 SoC findings remain. No analog metastability signoff or commercial comparison ran. |
| Palladium, Protium, ZeBu | Emulation and prototyping | none | none | No emulation or FPGA qualification. Owner decides #23. |
| Arm Fast Models, Platform Architect | Virtual platforms, architecture exploration | `rvw arch` (native gem5, calibrated against the RTL), Spike, `rvw perf` | exploring | Nax has 30 RTL/Spike matched runs. Corrected final window delta success is 6/15 nonzero and 15/24 total (#1252). Held-out IPC MAE is 9.08%. The original #1218 result remains 2/15. BOOM historical slice remains 258 RTL cycles versus 96 model cycles. |
| (no commercial equivalent) | Agent interface over the whole flow | `rvw mcp`: 348 tools from generated `rvw mcp --list --json`; profiles, effects, jobs and cancel | usable | Generated discovery listed 348 tools in the 2026-11-17 review. Core profile had 22 at #1075. Schema tests do not run handlers. llvm-mca, MCY and kubectl inventory IDs remain open. |

The measured daily loop supports run, judge, compare, triage, query and coverage work.
Deep formal, CDC signoff, full protocol qualification, emulation and integrated GUI
acceptance remain open. A usable tool does not qualify all cores or configurations.

## Components

These rows describe the audit cutoff. Apply the later slice updates above.

Every tool and major command family. The core column includes BOOM and example cores.
Generic status names the strongest reported evidence slice. It does not qualify the whole
family. Later audit updates supersede earlier entries. Tool READMEs retain detailed limits.

| Component | Path | Area | For BOOM and example cores | Generic goal | Generic status |
|---|---|---|---|---|---|
| RiscvSim | `RiscvSim/` | SIM, VER | `RiscvSim/boom/run.sh`: build / run / run-many; result JSON, RVFI trace, waves with cycle windows, Konata, coverage, replay | The run contract (C1) and RVFI trace (C2) for any Spinal RISC-V core | partly generic; ran on real core RTL (BOOM small, VexRiscv and VexiiRiscv). BOOM daily loop has 173 passes plus one known failure across 174; Spike matches 173/174 and unchanged gate accepts (#1246). Linux, restore, optional suites and wider presets remain unqualified. |
| VexRiscv example | `examples/vexriscv/` | SIM, VER, IDE | Independent second-core check | External core with C1/C2, regression, Spike and SpinalDB | generic; ran on real core RTL. 49 aligned ISA traces match. Cancellation-aware rerun gives 49 passes and zero firings (#893). Interrupt mtval and six ACT4 MEPC failures remain. |
| rvw regress | `rvw/src/rvw/regress/`, `rvw/configs/boom.toml` | SIM, VER | BOOM small daily loop (2026-11-13): quick tier 173 pass and one known instret_overflow failure across 174; unchanged committed gate accepts (#1246) | Regression for any core with a C1 adapter and complete C8 inputs | partly generic; ran on real core RTL. Seeded random and generated capability-selected suites added. Native production campaigns remain separate from Spike self-checks (#388, #795). |
| rvw farm | `rvw/src/rvw/farm/` | SIM, PLAT | Native SSH shards, C3/C4 static dashboard | Any core with a C1 adapter and matching native identity | partly generic; ran on real core RTL (VexRiscv). Committed 49-cell gates accept/accept/reject; queue costs are recorded (#1163). Eight-test ranking misses the fault; safe fallback runs all 49 (#1090). Kubernetes has offline schema validation, no cluster execution (#1172). |
| Accellera UVM component suite | `Uvm/`, `rvw/src/rvw/sim/uvm.py` | SIM, VER | Pinned library; bounded TL-UL and load observation checks | Native SV UVM agents and scoreboards | partly generic; ran on real core RTL (VexRiscv); seeded RTL protocol matrix is separate. Nested-task data checking is repaired. Installed Verilator still fails the unchanged covergroup requirement at seeds 1/2/3 (#1183). No full UVM qualification. |
| rvw cosim | `rvw/src/rvw/cosim/`, `Cosim/` | VER | Dated BOOM measurement (2026-10-22/23): Spike lockstep 173/174, Sail 171/174 on riscv-tests | Any core writing C2 traces, platform in project JSON | generic; ran on real core RTL. Historical BOOM counts: 173/174 Spike, 171/174 Sail. Fresh PLIC: 12 matches with ordered evidence. Four BOOM FP/CSR matches need aligned initial FCSR. V/H capture and whole campaign scope remain open. |
| rvw bundle / reduce / bisect / wave | `rvw/src/rvw/{bundle,reduce,bisect,wave,runs}/`, `RiscvSim/boom/debug.toml` | DBG | Failure report, reduction, bisection; root-caused the `lsu.scala:1241` assertion | Any core with a C1 adapter and a debug config | partly generic; ran on real core RTL. Indexed wave and portable session features added (#429, #517). Native history/reduction slices ran (#714, #769). Live integrated GUI acceptance remains open. |
| rvw debug | `rvw/src/rvw/debug/` | DBG | OpenOCD campaign, native DMI/JTAG client, pinned baseline E-Trace decoder and exact C2 PC comparison | Single-hart RV64 debug profile; machine-mode encoder ingress | partly generic; ran on real core RTL. Vex DMI/JTAG, OpenOCD and four ingress cases ran (#896/#914). Five target deviations, target+4 breakpoint stop and trace recovery remain open. |
| SpinalDB + rvw query | `SpinalDB/`, `rvw/src/rvw/query/` | IDE, PLAT | Dated BOOM measurement (2026-10-22/23): BOOM design database in ~1 min; queries in under a second | Any Spinal design, built by its project's adapter | generic within supported subsets; ran on real core RTL imports. Spinal, slang, GHDL and FIRRTL navigation and source coverage ran. Conservative lowered graphs and ambiguous source locations remain limits. |
| rvw lint | `rvw/src/rvw/lint/` | LINT | Register-boundary inventory; no signoff | Native lint and CDC/RDC for domain-aware designs | partly generic; ran on seeded RTL fixture. Real-core static inventory also exists: 2507 SoC CDC/RDC findings and 100 active OoO Mini findings with 159 unresolved temporaries (#1195/#1251). No lint, CDC or analog metastability signoff. |
| rvw soc | `rvw/src/rvw/soc/` | PLAT | Versioned SoC maps and deterministic software exports | Project-owned JSON, existing Spike platform reader, CMSIS-SVD register subset | partly generic; ran on real core RTL (VexRiscv and Stepper). Native CPU/DMA, debug and UART slices exist. Stepper protocol/decode cover fabric only; five consumers and automatic native preparation remain open (#1248). |
| rvw cov | `rvw/src/rvw/cov/` | SIM, FV | Coverage merge, ranking, RVFI functional coverage, change-based selection, proof exclusions, mcy | Any Verilator design / RISC-V core | partly generic; ran on real core RTL. Solver, sequence, event and code guidance paths added (#431, #452, #468, #740). Evidence sealing and replay do not create new coverage credit (#643, #686). |
| SpinalChecks + rvw formal | `SpinalChecks/`, `rvw/src/rvw/formal/` | FV | Dated BOOM measurement (2026-10-22/23): 516 generated checks (dated run; 24 fire, source dispositions set; runtime triage #5); BMC from a riscv-tests state; xprop | Any Spinal design within the supported clock and state model | partly generic; ran on real core RTL. Vexii 51-program cancellation rerun has zero firings. Across 82 checks, 63 activate and 13 have conditional unreachability results. Six current misses and new backpressure failures remain (#1171). Full-core proof remains open. |
| ComponentSims | `ComponentSims/` | ARCH | Native actual-path branch direction studies | ChampSim/CBP-class components; no imported engine code yet | partly generic; ran on real core RTL events (VexRiscv, VexiiRiscv; BOOM small earlier). Cached Vexii has 769 matching data-access outcomes and 9001 declared predictor events. Model writebacks are 449 versus 512 observed (#1219). Approximate BOOM parameters and general timing fidelity remain limits. |
| rvw workloads | `rvw/src/rvw/workloads/` | ARCH | Pinned RV64GC kernel ELFs and reference checks | Open application sets and optional licensed SPEC through the same manifest | partly generic; reference model only (Spike/Sail/Python). Pinned workload builds and Spike/QEMU checks do not run a core. Full RTL workload-class, Linux and licensed SPEC qualification remain separate. |
| Arch + rvw arch | `Arch/`, `rvw/src/rvw/arch/` | ARCH | Project O3 descriptions, native setup, same-ELF C1 calibration and MCP | One RV64 O3 or RV32IM in-order hart with the bare-metal ROI runtime | partly generic; ran on real core RTL inputs (NaxRiscv). Thirty passing runs and complete Spike matches cover six programs and four variants (#1206). Corrected final-window delta success is 6/15 nonzero and 15/24 total (#1252). Absolute fit and rank agreement do not qualify delta accuracy. |
| Own core timing model | `rvw/src/rvw/ooo/` | ARCH | Generic trace-driven OoO kernel with C2 input | Measured C1/C2 timing and project structure comparisons | partly generic; ran on real core RTL inputs (NaxRiscv). Corrected final window stage meets 6/15 nonzero and 15/24 total deltas; training/held-out IPC MAE is 7.31%/9.08% (#1252). The original #1218 result is 2/15. Exact replay and structure-size decisions still need RTL. |
| SpinalKonata + rvw perf | `SpinalKonata/`, `rvw/src/rvw/perf/` | DBG, ARCH | BOOM probe adapter; text reports on `large` benchmarks | Any design that tags pipeline events; any Kanata log | partly generic; ran on real core RTL. BOOM/Vexii/Nax probes, topdown, ELF function and configuration reports exist. BOOM SFB endpoint differs by one; Nax orphan events and causal scope remain open. |
| C model datapath checks | `SpinalChecks/c2rtl/` | FV | No core binding | C references against RTL | partly generic; ran on real core RTL extracts. Vexii word-operator multiplier composition closes with trusted $mul semantics (#1199). Nax unsigned 32-bit helper transaction certificate closes (#1215). Signed conversion, later requests, core writeback and production FPU qualification remain open. |
| rvw CLI + MCP project selection | `rvw/`, `docs/BRING_YOUR_OWN_CORE.md` | PLAT | Explicit `--core boom` compatibility; background MCP jobs | Install once; core-owned `rvw.toml` and adapters; `--project`, `RVW_PROJECT`, upward discovery | generic; ran on real core RTL project adapters. The 2026-11-17 inventory has 348 tools. Effects, profiles and workflow schema tests do not qualify native handlers; three installer IDs remain missing. |
| Agent benchmark | `rvw/src/rvw/agent_bench/` | PLAT | Agent outcome measurement | Core-independent fixture runner | partly generic; unit tests only. Misleading evidence and external MCP runner added (#809, #817). Native repair acceptance and scored LLM trials remain NOT RUN (#830). |
| Workstation installer | `scripts/install.sh` | PLAT | Core install; optional native tools; check and dry-run modes | Separate core projects on macOS and Linux | partly generic; unit tests only. Pinned inventory and native flags added (#665, #672, #772). Untested Linux recipes remain unqualified (#685). |
| rvw init | `rvw/src/rvw/init/` | PLAT | Core project scaffolding | Safe core-owned setup files | partly generic; ran on real core RTL (Stepper). Mapped CPU, probes, security, ISA and pyuvm bindings run in finite scopes. Exact-cycle instruction checks pass; depth 22 stays inconclusive. Five SoC consumers and independent newcomer repeat remain open (#1248). |
| rvw doctor | `rvw/src/rvw/doctor/` | PLAT | Setup diagnostics and explicit installer forwarding | Version, project, adapter and gate preflight checks | partly generic; unit tests only. Mapped evidence and replay checks added (#787, #834). Full native doctor campaigns remain NOT RUN (#834). |
| SpinalWaves | `SpinalWaves/` | DBG | Spinal types and source locations in Surfer (port of Tywaves) | Any Spinal design | partly generic; unit tests only. Typed wave and database paths remain bounded. Live viewer acceptance is not established by the new saved-data views. |
| SpinalTrace | `SpinalTrace/` | DBG | Traces a value back to Spinal statements; CLI and GUI (port of ChiselTrace) | Any Spinal design | partly generic; unit tests only. Wave driver and cause queries added (#429). Exact native and interactive workflow scope must remain explicit. |
| SpinalBlocks | `SpinalBlocks/` | IDE | Block diagrams; web host and VS Code feature | Any Spinal design | partly generic; ran on real core RTL. HDL database diagram export added (#688). Complete source semantics and interactive cross-navigation remain open. |
| VS Code extension | `vscode/` | PLAT | SpinalBlocks, saved result views and integrated indexed debug session; GUI performance and trace parity pending | One extension, one feature per tool | partly generic; unit tests only. Navigation, results, cosim, coverage, formal, lint, architecture and pipeline views added (#845 through #870). Live VS Code checks did not run. |
| SpinalProbes / rvw probes | `SpinalProbes/`; `rvw/src/rvw/probes/` | ARCH, DBG | Optional simulation probes and consumer conversion. No additional BOOM acceptance. | Optional simulation probes and consumer conversion. | partly generic; ran on real core RTL. BOOM and example streams ran. Nax orphan events, BOOM SFB endpoint and full consumer bindings remain open. |
| rvw sec | `rvw/src/rvw/sec/` | VER | Dynamic simulation security experiments and contract suites. No additional BOOM acceptance. | Dynamic simulation security experiments and contract suites. | partly generic; ran on real core RTL (VexRiscv, VexiiRiscv and Stepper in separate scopes). Cached Vex contract/flow positive and constant-time controls run (#1255). Stepper flow checks 42 cycles (#1248). Cached Vexii, TLB channels, all-operand and physical security remain unqualified. |
| rvw fault | `rvw/src/rvw/fault/`; `RiscvSim/` | VER | Fault plans, native public-access injection and C2 classification. No additional BOOM acceptance. | Fault plans, native public-access injection and C2 classification. | partly generic; ran on real core RTL. BOOM/Vex/Nax selected register flips ran. Missing outcomes remain inconclusive; no hardware reliability claim. |
| rvw bugmem | `rvw/src/rvw/bugmem/` | DBG | Store failure patterns and find similar reports. No additional BOOM acceptance. | Store failure patterns and find similar reports. | partly generic; unit tests only. Native cause ranking and repair acceptance remain unqualified. |
| SpinalSoc / rvw soc compose | `SpinalSoc/`; `rvw/src/rvw/soc/` | PLAT | Compose map-driven peripheral SoCs and generate software data. No additional BOOM acceptance. | Compose map-driven peripheral SoCs and generate software data. | partly generic; ran on real core RTL (VexRiscv, VexiiRiscv SMP, Stepper). Stepper fabric protocol/decode close limited scopes; five other consumers remain inconclusive (#1248). Vex CDC/RDC has 2507 findings (#1195). No complete SoC qualification. |
| rvw vip / protocol families | `rvw/src/rvw/vip/`; `Uvm/vip/` | VER | Protocol agents, RTL controls and optional external-model contracts. No additional BOOM acceptance. | Protocol agents, RTL controls and optional external-model contracts. | partly generic; ran on seeded RTL fixture. Repaired SV fixtures pass their declared matrix. Physical protocols and four inert external model stubs remain open. |
| rvw uvm / CPU and RAL families | `rvw/src/rvw/uvm/`; `Uvm/` | VER | Project benches, RAL and CPU verification sequences. No additional BOOM acceptance. | Project benches, RAL and CPU verification sequences. | partly generic; ran on real core RTL (VexRiscv and Stepper). Stepper live pyuvm/Spike checks 15 smoke and 80 composed-hello retirements (#1229). Other protocols and architectural observations need bindings. |
| rvw lsp | `rvw/src/rvw/lsp/` | IDE | Database-backed language navigation and an editor client. No additional BOOM acceptance. | Database-backed language navigation and an editor client. | partly generic; unit tests only. Live editor latency, safe edits and complete semantic joins remain unqualified. |
| rvw plan | `rvw/src/rvw/plan/` | PLAT | Roll up project verification evidence and trends. No additional BOOM acceptance. | Roll up project verification evidence and trends. | partly generic; unit tests only. Native example reports are inputs to unit-tested summaries. Weakest-input rules do not grant coverage closure or C4 acceptance. |
| rvw agent guide | `rvw/src/rvw/agent/` | PLAT | Expose the agent playbook through CLI and MCP. No additional BOOM acceptance. | Expose the agent playbook through CLI and MCP. | partly generic; unit tests only. CLI/MCP guide and schema walks are tested. New-core native workflow qualification is separate. |
| rvw evidence | `rvw/src/rvw/evidence/` | PLAT | Index original cross-tool evidence and dependencies. No additional BOOM acceptance. | Index original cross-tool evidence and dependencies. | partly generic; unit tests only. Hash and dependency joins have unit tests. Native multi-tool workflow acceptance remains open. |
| Standard device plugins | `rvw/src/rvw/sim/`; `RiscvSim/` | SIM | Device models, live input wiring and device-aware checkpoints. No additional BOOM acceptance. | Device models, live input wiring and device-aware checkpoints. | partly generic; ran on real core RTL. Live Vexii devices and OpenSBI control ran. Linux timed out; checkpoint restore remains absent. |
| Arcilator adapter | `rvw/src/rvw/sim/`; `RiscvSim/` | SIM | Alternate native engine and controlled comparison with Verilator. No additional BOOM acceptance. | Alternate native engine and controlled comparison with Verilator. | partly generic; ran on real core RTL. One warmed native sample ran; repeated controlled throughput and full engine semantics remain open. |
| slang front end | `rvw/src/rvw/query/` | IDE | Build a database from elaborated SystemVerilog. No additional BOOM acceptance. | Build a database from elaborated SystemVerilog. | partly generic; ran on real core RTL. SERV and core import subsets have native receipts. Full SystemVerilog, includes and semantic source joins remain open. |
| GHDL front end | `rvw/src/rvw/query/` | IDE | Build a database from the supported VHDL synthesis subset. No additional BOOM acceptance. | Build a database from the supported VHDL synthesis subset. | partly generic; ran on real core RTL. NEORV32 whole-core and UART import subsets ran. Tool/plugin identities and complete source semantics remain limits. |
| FIRRTL/CIRCT front end | `rvw/src/rvw/query/` | IDE | Build a database from Chisel-generated FIRRTL through CIRCT. No additional BOOM acceptance. | Build a database from Chisel-generated FIRRTL through CIRCT. | partly generic; ran on real core RTL. riscv-mini and Queue import subsets ran. Reviewed firtool lowering and complete source joins remain limits. |
| rvw checks | `rvw/src/rvw/checks/` | FV | Generate project checks and report connected qualification gaps. No additional BOOM acceptance. | Generate project checks and report connected qualification gaps. | partly generic; ran on real core RTL. Activation gaps, new stream failures and the missing BOOM historical ID remain. |
| Farm service and workflows | `rvw/src/rvw/farm/` | PLAT | Queue work, plan shards and retain recovery and cost evidence. No additional BOOM acceptance. | Queue work, plan shards and retain recovery and cost evidence. | partly generic; ran on real core RTL (VexRiscv). Persistent local queue, crash/cancel, budgets and committed C4 gate controls ran (#1163/#1189). Kubernetes runtime remains NOT RUN. |
| Debug Module campaign commands | `rvw/src/rvw/debug/` | DBG | Reference Debug Module, DMI/JTAG drivers and trace campaigns. No additional BOOM acceptance. | Reference Debug Module, DMI/JTAG drivers and trace campaigns. | partly generic; ran on real core RTL. Real Vex DMI/JTAG and OpenOCD slices ran. Physical JTAG, five target deviations and trace recovery remain open. |
| Native HDL project scaffolds | `rvw/src/rvw/init/` | PLAT | Generate mapped external-core projects and launchers. No additional BOOM acceptance. | Generate mapped external-core projects and launchers. | partly generic; ran on real core RTL (Stepper, PicoRV32, riscv-mini, NEORV32). Stepper has 50 strict ISA matches. Reviewed add/lw/sw exact cycles pass with activation; trace-selected depth 22 stays inconclusive. Flow completes; five SoC consumers remain open (#1248). |
| Agent trial and evidence benchmark | `rvw/src/rvw/agent_bench/` | PLAT | Score fixture tasks and run bounded external MCP client trials. No additional BOOM acceptance. | Score fixture tasks and run bounded external MCP client trials. | partly generic; unit tests only. Native repair acceptance and scored LLM trials remain NOT RUN. |
| MCP profiles and tool catalog | `rvw/src/rvw/mcp/` | PLAT | Authenticated sessions, profile filtering and common result envelopes. No additional BOOM acceptance. | Authenticated sessions, profile filtering and common result envelopes. | partly generic; unit tests only. 348 tools in generated discovery on 2026-11-17. Schema smoke runs no handlers; three native installer IDs remain open. |
| Cacheless multi-hart example | `examples/smp/` | SIM | Run two to eight external VexiiRiscv harts with simulation RAM and devices. No additional BOOM acceptance. | Run two to eight external VexiiRiscv harts with simulation RAM and devices. | partly generic; ran on real core RTL. N=2..8 cacheless runs and one-line cached two-hart handoff ran. In-simulation SV bind and full coherence remain open. |
| rvw memory | `rvw/src/rvw/memory/` | VER | Serialized and axiomatic memory observation checks and concurrent campaigns. No additional BOOM acceptance. | Serialized and axiomatic memory observation checks and concurrent campaigns. | partly generic; ran on real core RTL. Remaining scope is in [the family audit](docs/status/2026-11-13/NEW_TOOLS.md). |
| rvw privilege | `rvw/src/rvw/privilege/` | VER | Project-owned privilege and interrupt programs with independent observation checks. No additional BOOM acceptance. | Project-owned privilege and interrupt programs with independent observation checks. | partly generic; ran on real core RTL (VexRiscv RV32IM, VexiiRiscv RV32/RV64 supervisor). Native PMP, random, privilege and main-pin reset families run. Three fresh RV64 reset traces strictly match across nine pulses (#1188). Unsupported extensions and separate reset domains remain open. |
| rvw verification-plan | `rvw/src/rvw/verification_plan/` | VER | Versioned extension and environment-control verification plans. No additional BOOM acceptance. | Versioned extension and environment-control verification plans. | partly generic; unit tests only. Plan generation has unit tests. Environment controls, native obligation coverage and closure remain unqualified. |
| VexiiRiscv example | `examples/vexiiriscv/` | SIM, VER | RV32/RV64 C1/C2, probes and database | RV32/RV64 C1/C2, probes and database | partly generic; ran on real core RTL (RV32/RV64). RV64 M/MSU each have 85 strict ISA matches (#1237). RV64 machine ACT4 has 98 strict matches; 302 supervisor bodies fail bootstrap (#1257). RV32 supervisor retains 270 blocked bodies. One shared compatibility cause; no privileged-body qualification. |
| NaxRiscv example | `examples/naxriscv/` | SIM, VER, ARCH | OoO RV32IMA/Sv32 adapter, pinned Spinal axis and probes | OoO RV32IMA/Sv32 adapter, pinned Spinal axis and probes | partly generic; ran on real core RTL (RV32IMA). 59 riscv-tests, 69 ACT4 strict matches, nine monitored declarations and a 30-run capacity matrix (#1167/#1205/#1206). Activation and whole-core qualification remain open. |
| PicoRV32 example | `examples/picorv32/` | SIM, VER, IDE | Mapped Verilog C1/C2 and Yosys queries | Mapped Verilog C1/C2 and Yosys queries | partly generic; ran on real core RTL. ACT4 has 50 passes/strict matches and one FENCE destination-state failure (#1205). Misaligned-JAL monitor counterexample remains. |
| OoO mini example | `examples/ooo-mini/` | SIM, FV | Small core integration and bounded formal experiments | Small core integration and bounded formal experiments | partly generic; ran on real core RTL (RV32IM). 50 ISA and three directed strict matches. Default has eight SV binds and 19 Scala monitors with zero firings. Four sampled faults, coverage, lint and committed reject/repair-accept controls exist (#1245/#1251). ISA proof, 100 lint findings, 159 unresolved candidates and ROB16 SV binds remain open. |
| rvw csr | `rvw/src/rvw/csr/` | VER, FV | Shared pinned CSR data for generators and checks | Shared pinned CSR data for generators and checks | partly generic; unit tests only. Native WARL, privilege and autonomous-update qualification remain open. |

| ACT4 and stimulus campaigns | `rvw/src/rvw/regress/`; `docs/ACT4.md` | VER | Capability-selected ACT4 builds, riscv-dv campaigns and instruction feeds | Project-owned profiles and independently checked C1/C2 campaigns | partly generic; ran on real core RTL. RV32 instruction passes: Vex 52/58, Vexii 58/58, Nax 69/69, Pico 50/51. RV64 machine adds 98/98 strict matches. Standard supervisor boot blocks 270 RV32 and 302 RV64 bodies (#1257). BOOM ACT4 remains NOT RUN. |
| MMU campaigns | `rvw/src/rvw/regress/`; `examples/mmu/` | VER | Generate and check translation, PMP and page-walk observations | Project-declared translation modes and independent observed walks | partly generic; ran on real core RTL. RV32 PMP has 394 strict matches. Nineteen PMP-denied walks remain findings. IOMMU and other modes retain reference-only slices. |
| SystemC/TLM example | `RiscvSim/examples/systemc/`; `RiscvSim/src/main/cpp/TlmMemory.h` | SIM | Multi-initiator memory and RTL bridge example; no BOOM binding | Generic blocking TLM memory transport | partly generic; ran on seeded RTL fixture. Native SystemC/Verilator controls ran. Effects occur at call time; timing annotation is not complete CPU/device timing. |

Core-side tools that stay in `spinal-boom` for now: the BoomSim harness
and BOOM's Konata probe. The gem5 automation moved here (`Arch/`) on 2026-10-24.

## Integration

- **Shared formats:** C1 (run result), C2 (RVFI trace), C3 (suite results), C4 (verdict), C5
  (failure bundle), C6 (design database), C7 (MCP tools), C8 (input capture, result generations, threat
  model), C9 (native architecture models) in `docs/PLATFORM_CONTRACTS.md`.
- **Design database:** SpinalDB writes the dependency graph, the block JSON and HGLDD from one run;
  SpinalBlocks can consume database exports; legacy extraction remains for parity checks (#44). SpinalTrace and SpinalWaves have database readers; complete consumer workflow qualification remains #69.
- **Cross-navigation:** waveform signal ↔ block diagram ↔ Scala source ↔ dependency trace (saved-data joins exist; complete live GUI acceptance remains open).
- **One host:** the VS Code extension hosts SpinalBlocks; waves (Surfer), Konata and SpinalTrace's
  GUI are separate apps.
- **Agent interface:** built-in MCP tools are listed in [the command reference](docs/COMMAND_REFERENCE.md). Generated discovery (`rvw mcp --list --json`) listed 348 tools in the 2026-11-17 review.
  Profiles, effect declarations and workflow sets have schema tests. Handler execution
  is separate evidence. The command reference can lag current discovery.
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
- SpinalHDL first; Verilog/SystemVerilog, Chisel/FIRRTL and VHDL have measured
  adapter subsets. Full language support remains open.

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
2026-11-13 snapshot. No claim of parity, complete capture or complete verification
follows from a component's usable status.

Current limit owners also include ACT4 and bootstrap (see `docs/ACT4.md`), generated-check activation
(#5, #85), SoC ingress (#134), MMU and interrupt campaigns (#84, #131, #158), UVM/VIP
(#296), memory/coherence (#90, #128, #363), and native CI/install (#40, #41).
The [open list](TODO.md) gives current issue scope. No-issue work needs owner scope
assignment before it can become a closure target.

Source disagreements remain visible: the ComponentSims README says no native RTL
comparison has run and no adapter writes `rvw.bp-events/1`. The audit records native
Vex/Vexii/BOOM event comparisons. This update follows the scoped audit receipts.
It does not claim RTL model fidelity. Early NEW_TOOLS entries call security/fault
fixture-only, debug/privilege reference-only and GHDL/FIRRTL unit-only. Later audit
updates and READMEs describe native slices. Use the later scoped records, not the
early family labels. These source files were not changed here.
