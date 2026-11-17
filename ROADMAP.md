# Roadmap

## Purpose and scope

Build open tools that match or beat commercial EDA tools for out-of-order RISC-V cores.
Extend open engines where they fall short. Send changes upstream where possible.
This plan covers tools only. It does not require BOOM or another core to add a feature.
Use an existing capable design or a sealed tool-owned target to test a tool.
Keep core names, signals and configuration in adapters.

The toolset is agent-led. Each required operation needs a CLI, MCP access and machine-readable output.
An agent must get a checked answer without a GUI. GUI work is optional later work.
PPA, emulation, FPGA and physical power or electromagnetic side channels are out of scope.
Timing, cache and speculation side-channel verification remains in scope.

The owner froze the source plan on 2026-11-04. This roadmap gives that plan seven milestones.
A cell is one numbered acceptance test, such as D01.c1. A receipt records checked test evidence.
A protocol defines a shared rule used by several cells. A milestone groups phases. It does not remove a cell, a comparator or a required child.
Start phases permit engineering. Acceptance phases permit closure only after required receipts pass.
No new runtime qualification follows from this document.

Read the current-state table first. Then select a milestone and follow its cell links.
Use [acceptance.md](docs/roadmap/acceptance.md) for all 357 cells and their exact rules.
Use [protocols.md](docs/roadmap/protocols.md) for shared rules, phase exits, release tiers, method designs and planning counts.
Use [commercial-features.md](docs/roadmap/commercial-features.md) for all 405 feature entries and issue ownership.
Use [organisation.md](docs/roadmap/organisation.md) for owner tasks that do not gate tool acceptance.
[TODO.md](TODO.md) keeps tasks under the existing areas and marks each issue with its milestone.

A runtime predecessor needs an earlier accepted receipt. A sealed interface supplies a schema only.
A context link supplies no acceptance evidence. A family link includes all of its children.
Missing, failed, not-run, unsupported and inconclusive results stay separate.
Never report an unearned pass, match or accept. A finite census does not establish a population claim.
The category table fixes one primary measure per category. Secondary measures cannot rescue it.
All exact correctness, capacity, depth and refusal controls still apply.

### Performance goal query
The tools answer whether a supplied design approaches an exact Zen 5 or M-series system. No candidate must reach the goal for the tools to pass. For identical completed useful work j, compute the ratio of measured comparator core cycles to candidate RTL cycles for each useful work item at the specified clock scenario. Missing counters mean unavailable cycles; the qualified time-only route remains usable with its explicit evidence class. Counter acquisition and semantic checks are mandatory in D36.c4. Do not infer cycles from GHz and time. Freeze CPU, firmware, OS, affinity, memory, libraries, compiler, flags, full input, outputs and region of interest. Test two compiler versions. Keep portable and equal-budget tuned builds separate. Cross-ISA IPC is diagnostic.
The query tests adjusted lower 95% R bounds of 0.90 overall and 0.80 per class. Classes are integer/branch, FP/scientific, memory, system/application, vector/SIMD, ML inference and media/crypto. Use the label QUALIFIED-EQUAL-CLASS with equal-class weights as the primary supported headline until D22.c2 qualifies natural deployment weights. Then publish both, with deployment weights frozen before outcomes. No defensible deployment weights means no deployment-weighted headline. Report `goal_shortfall=max(0,1-R)`, missing weight and each class regression.
For clock scenario f, rerun fixed-ns external delays at 0.5 times, 1 time and 1.5 times and bracket crossings. Report cycles, modeled elapsed time as cycles divided by the assumed clock frequency, measured comparator time and useful throughput separately. Queries test upper latency ratio 1.10 overall and 1.25 per class and lower throughput ratio 0.90 overall and 0.80 per class. Concurrency levels 1, 2, 4 and 8 are separate supported cells. Each conditional-time export says: "Clock is an input assumption; candidate elapsed time is modeled."
A latency contract covers frontend/redirect, rename, issue, RF/bypass, operations, commit/recovery, caches, translation, forwarding and external memory. Missing or idealized structure latency makes the affected result unconstrained. D36 owns the acceptance tests for this service. Query thresholds here are user hypotheses, not tool acceptance or core outcomes.
Plan 20 stochastic endpoint families per category and 380 in total before the complete endpoint census. Plan 899 independent agent-task clusters per stratum and 225 then 899 workload families per class. The planning section in protocols.md defines power checks and the required finite-census or substitute labels when a frame is too small.

## Where we are now

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

### Supported scope

[README.md](README.md) states current supported and experimental features.
[PLATFORM_CONTRACTS.md](docs/PLATFORM_CONTRACTS.md) defines C1 through C9 and the C8 threat model.
Tool README files own current limits. The release hygiene scan rejects machine paths and credentials.
Keep review output and runtime evidence outside repository history, in issues, PRs and receipt stores.

## Milestones

Issue state was checked on 2026-11-17. The 213 live issues include 211 with
frozen-plan milestone owners. Issues #722 and #723 have no assignment in that
plan. The owner must assign their acceptance scope before they gate a milestone.
Closed issue assignments remain historical in the detail ledger. Closure does
not establish acceptance. All 357 acceptance cells remain requirements.


Each of the 211 mapped live issues appears in one list below. The two unassigned issues are listed above.
The detailed issue map retains the frozen owners.
Issues can need cells in several milestones. The listed milestone owns the issue's final planned tool outcome. Whole-engine and scale issues close after their full comparisons.
An issue's earlier engineering work can start sooner when its cells permit it.
M7 tracks the disposition of deferred issues #23 and #51 and organisation issues #37 and #39. These issues do not gate tool acceptance.
Assign each mapped issue to the milestone that accepts its main deliverable. Early source-specific ledger cells do not set that milestone.
Category closure below means its fixed primary capability gate. Final release closure also needs all other cells and the M7 audits.

### M1: Seal sources and methods

Seal the source scope, identities, independent expectations and statistical methods before implementation results can influence them.

Phases: P00 through P02. Dependencies: none.

Main deliverables: Platform and trust: source sealing, verdict identities, import checks, statistical validation and route rules. IDE: frontend semantics. Workloads: eligibility and behavior frames. Agents: safe transport and budgets.

Exit: every cell assigned to these acceptance phases and every required child must pass. Use the exact phase exits in [protocols.md](docs/roadmap/protocols.md). Accept zero mandatory audit corruptions. Qualify complete-gate joint power at least .80.

Acceptance cells: [M1: Seal sources and methods](docs/roadmap/acceptance.md#m1-seal-sources-and-methods).

Issues (9): [#1](https://github.com/riscPrint/risc-v-workstation/issues/1), [#15](https://github.com/riscPrint/risc-v-workstation/issues/15), [#34](https://github.com/riscPrint/risc-v-workstation/issues/34), [#52](https://github.com/riscPrint/risc-v-workstation/issues/52), [#76](https://github.com/riscPrint/risc-v-workstation/issues/76), [#79](https://github.com/riscPrint/risc-v-workstation/issues/79), [#370](https://github.com/riscPrint/risc-v-workstation/issues/370), [#371](https://github.com/riscPrint/risc-v-workstation/issues/371), [#372](https://github.com/riscPrint/risc-v-workstation/issues/372).

### M2: Build checked semantic foundations

Build and check the semantic foundations. Establish trustworthy event accounting, ISA obligations, reference state and proof methods.

Phases: P03 through P05. Dependencies: M1 and all earlier runtime predecessors named by each cell.

Main deliverables: Performance: exact causal accounting and PMU mapping. Verification: ISA and scalar references. Formal: application semantics, prototype certificates and refinement targets. Debug: capture and source maps. Platform: native packages and reproducible builds.

Exit: every cell assigned to these acceptance phases and every required child must pass. Use the exact phase exits in [protocols.md](docs/roadmap/protocols.md). Category 2, [D03.c1](docs/roadmap/acceptance.md#D03c1): Require unattributed cycle fraction at most 2% against independently checked full-run event accounting. Category 5, [D09.c2](docs/roadmap/acceptance.md#D09c2): Require checked conclusive obligations per total core-hour lower ratio at least 1.10 against each Siemens Questa Processor / OneSpin and Axiomise formalISA on the complete pinned architectural-proof frame. Category 17, [D32.c1](docs/roadmap/acceptance.md#D32c1): Require bit-identical reproducible build count at least 2 per supported host against the pinned package matrix and source-to-binary hashes.

Acceptance cells: [M2: Build checked semantic foundations](docs/roadmap/acceptance.md#m2-build-checked-semantic-foundations).

Issues (111): [#5](https://github.com/riscPrint/risc-v-workstation/issues/5), [#8](https://github.com/riscPrint/risc-v-workstation/issues/8), [#10](https://github.com/riscPrint/risc-v-workstation/issues/10), [#11](https://github.com/riscPrint/risc-v-workstation/issues/11), [#17](https://github.com/riscPrint/risc-v-workstation/issues/17), [#29](https://github.com/riscPrint/risc-v-workstation/issues/29), [#33](https://github.com/riscPrint/risc-v-workstation/issues/33), [#40](https://github.com/riscPrint/risc-v-workstation/issues/40), [#42](https://github.com/riscPrint/risc-v-workstation/issues/42), [#43](https://github.com/riscPrint/risc-v-workstation/issues/43), [#48](https://github.com/riscPrint/risc-v-workstation/issues/48), [#49](https://github.com/riscPrint/risc-v-workstation/issues/49), [#54](https://github.com/riscPrint/risc-v-workstation/issues/54), [#55](https://github.com/riscPrint/risc-v-workstation/issues/55), [#64](https://github.com/riscPrint/risc-v-workstation/issues/64), [#65](https://github.com/riscPrint/risc-v-workstation/issues/65), [#66](https://github.com/riscPrint/risc-v-workstation/issues/66), [#75](https://github.com/riscPrint/risc-v-workstation/issues/75), [#77](https://github.com/riscPrint/risc-v-workstation/issues/77), [#80](https://github.com/riscPrint/risc-v-workstation/issues/80), [#82](https://github.com/riscPrint/risc-v-workstation/issues/82), [#83](https://github.com/riscPrint/risc-v-workstation/issues/83), [#84](https://github.com/riscPrint/risc-v-workstation/issues/84), [#85](https://github.com/riscPrint/risc-v-workstation/issues/85), [#87](https://github.com/riscPrint/risc-v-workstation/issues/87), [#90](https://github.com/riscPrint/risc-v-workstation/issues/90), [#91](https://github.com/riscPrint/risc-v-workstation/issues/91), [#93](https://github.com/riscPrint/risc-v-workstation/issues/93), [#95](https://github.com/riscPrint/risc-v-workstation/issues/95), [#96](https://github.com/riscPrint/risc-v-workstation/issues/96), [#97](https://github.com/riscPrint/risc-v-workstation/issues/97), [#98](https://github.com/riscPrint/risc-v-workstation/issues/98), [#99](https://github.com/riscPrint/risc-v-workstation/issues/99), [#100](https://github.com/riscPrint/risc-v-workstation/issues/100), [#102](https://github.com/riscPrint/risc-v-workstation/issues/102), [#104](https://github.com/riscPrint/risc-v-workstation/issues/104), [#109](https://github.com/riscPrint/risc-v-workstation/issues/109), [#111](https://github.com/riscPrint/risc-v-workstation/issues/111), [#112](https://github.com/riscPrint/risc-v-workstation/issues/112), [#114](https://github.com/riscPrint/risc-v-workstation/issues/114), [#122](https://github.com/riscPrint/risc-v-workstation/issues/122), [#123](https://github.com/riscPrint/risc-v-workstation/issues/123), [#127](https://github.com/riscPrint/risc-v-workstation/issues/127), [#128](https://github.com/riscPrint/risc-v-workstation/issues/128), [#129](https://github.com/riscPrint/risc-v-workstation/issues/129), [#131](https://github.com/riscPrint/risc-v-workstation/issues/131), [#133](https://github.com/riscPrint/risc-v-workstation/issues/133), [#134](https://github.com/riscPrint/risc-v-workstation/issues/134), [#136](https://github.com/riscPrint/risc-v-workstation/issues/136), [#137](https://github.com/riscPrint/risc-v-workstation/issues/137), [#138](https://github.com/riscPrint/risc-v-workstation/issues/138), [#139](https://github.com/riscPrint/risc-v-workstation/issues/139), [#140](https://github.com/riscPrint/risc-v-workstation/issues/140), [#141](https://github.com/riscPrint/risc-v-workstation/issues/141), [#143](https://github.com/riscPrint/risc-v-workstation/issues/143), [#144](https://github.com/riscPrint/risc-v-workstation/issues/144), [#146](https://github.com/riscPrint/risc-v-workstation/issues/146), [#147](https://github.com/riscPrint/risc-v-workstation/issues/147), [#148](https://github.com/riscPrint/risc-v-workstation/issues/148), [#149](https://github.com/riscPrint/risc-v-workstation/issues/149), [#151](https://github.com/riscPrint/risc-v-workstation/issues/151), [#152](https://github.com/riscPrint/risc-v-workstation/issues/152), [#153](https://github.com/riscPrint/risc-v-workstation/issues/153), [#154](https://github.com/riscPrint/risc-v-workstation/issues/154), [#155](https://github.com/riscPrint/risc-v-workstation/issues/155), [#156](https://github.com/riscPrint/risc-v-workstation/issues/156), [#157](https://github.com/riscPrint/risc-v-workstation/issues/157), [#158](https://github.com/riscPrint/risc-v-workstation/issues/158), [#159](https://github.com/riscPrint/risc-v-workstation/issues/159), [#161](https://github.com/riscPrint/risc-v-workstation/issues/161), [#162](https://github.com/riscPrint/risc-v-workstation/issues/162), [#163](https://github.com/riscPrint/risc-v-workstation/issues/163), [#164](https://github.com/riscPrint/risc-v-workstation/issues/164), [#165](https://github.com/riscPrint/risc-v-workstation/issues/165), [#166](https://github.com/riscPrint/risc-v-workstation/issues/166), [#168](https://github.com/riscPrint/risc-v-workstation/issues/168), [#169](https://github.com/riscPrint/risc-v-workstation/issues/169), [#170](https://github.com/riscPrint/risc-v-workstation/issues/170), [#171](https://github.com/riscPrint/risc-v-workstation/issues/171), [#172](https://github.com/riscPrint/risc-v-workstation/issues/172), [#174](https://github.com/riscPrint/risc-v-workstation/issues/174), [#175](https://github.com/riscPrint/risc-v-workstation/issues/175), [#176](https://github.com/riscPrint/risc-v-workstation/issues/176), [#177](https://github.com/riscPrint/risc-v-workstation/issues/177), [#179](https://github.com/riscPrint/risc-v-workstation/issues/179), [#181](https://github.com/riscPrint/risc-v-workstation/issues/181), [#186](https://github.com/riscPrint/risc-v-workstation/issues/186), [#188](https://github.com/riscPrint/risc-v-workstation/issues/188), [#189](https://github.com/riscPrint/risc-v-workstation/issues/189), [#190](https://github.com/riscPrint/risc-v-workstation/issues/190), [#192](https://github.com/riscPrint/risc-v-workstation/issues/192), [#193](https://github.com/riscPrint/risc-v-workstation/issues/193), [#194](https://github.com/riscPrint/risc-v-workstation/issues/194), [#195](https://github.com/riscPrint/risc-v-workstation/issues/195), [#196](https://github.com/riscPrint/risc-v-workstation/issues/196), [#197](https://github.com/riscPrint/risc-v-workstation/issues/197), [#199](https://github.com/riscPrint/risc-v-workstation/issues/199), [#201](https://github.com/riscPrint/risc-v-workstation/issues/201), [#202](https://github.com/riscPrint/risc-v-workstation/issues/202), [#204](https://github.com/riscPrint/risc-v-workstation/issues/204), [#205](https://github.com/riscPrint/risc-v-workstation/issues/205), [#207](https://github.com/riscPrint/risc-v-workstation/issues/207), [#209](https://github.com/riscPrint/risc-v-workstation/issues/209), [#212](https://github.com/riscPrint/risc-v-workstation/issues/212), [#215](https://github.com/riscPrint/risc-v-workstation/issues/215), [#216](https://github.com/riscPrint/risc-v-workstation/issues/216), [#361](https://github.com/riscPrint/risc-v-workstation/issues/361), [#363](https://github.com/riscPrint/risc-v-workstation/issues/363), [#375](https://github.com/riscPrint/risc-v-workstation/issues/375), [#376](https://github.com/riscPrint/risc-v-workstation/issues/376), [#377](https://github.com/riscPrint/risc-v-workstation/issues/377).

### M3: Qualify references and transfer

Qualify independent references, adapters, workloads and agent tasks. Prove the required ordering and SMT properties before later consumers use them.

Phases: P06 through P07. Dependencies: M2 and all earlier runtime predecessors named by each cell.

Main deliverables: Architecture: detailed and interval models, exact rare events and method selection. Verification: whole-system anchors, ordering, coherence and SMT. Agents: verified campaigns and recovery. Platform: documentation answers, unseen-core transfer and compact labels. Security: relational comparison.

Exit: every cell assigned to these acceptance phases and every required child must pass. Use the exact phase exits in [protocols.md](docs/roadmap/protocols.md). Category 9, [D17.c15](docs/roadmap/acceptance.md#D17c15): Require checked proof-closure-time upper ratio at most 0.90 against each qualified JasperGold ordering and coherence flow. Category 13, [D25.c3a](docs/roadmap/acceptance.md#D25c3a): Require adjusted median total verified campaign-time upper ratio at most 0.75 against shell-plus-upstream, the strongest qualified coding agent and every required commercial EDA agent per provider. Category 15, [D29.c7](docs/roadmap/acceptance.md#D29c7): Require mandatory task-answer error count exactly zero against independent expected documentation and status answers on every host, language and task class. Category 16, [D30.c3](docs/roadmap/acceptance.md#D30c3): Require sealed unseen-core transfer count at least 2 against the independent adapter obligation inventory, with distinct language and generator ancestries. Category 18, [D33.c2](docs/roadmap/acceptance.md#D33c2): Measure seconds per conclusive checked contract with a paired geometric mean. Require the adjusted candidate-to-comparator upper ratio at most 0.90 against both JasperGold Security Path Verification and Cycuity Radix.

Acceptance cells: [M3: Qualify references and transfer](docs/roadmap/acceptance.md#m3-qualify-references-and-transfer).

Issues (46): [#18](https://github.com/riscPrint/risc-v-workstation/issues/18), [#19](https://github.com/riscPrint/risc-v-workstation/issues/19), [#20](https://github.com/riscPrint/risc-v-workstation/issues/20), [#21](https://github.com/riscPrint/risc-v-workstation/issues/21), [#26](https://github.com/riscPrint/risc-v-workstation/issues/26), [#31](https://github.com/riscPrint/risc-v-workstation/issues/31), [#35](https://github.com/riscPrint/risc-v-workstation/issues/35), [#38](https://github.com/riscPrint/risc-v-workstation/issues/38), [#58](https://github.com/riscPrint/risc-v-workstation/issues/58), [#60](https://github.com/riscPrint/risc-v-workstation/issues/60), [#61](https://github.com/riscPrint/risc-v-workstation/issues/61), [#62](https://github.com/riscPrint/risc-v-workstation/issues/62), [#63](https://github.com/riscPrint/risc-v-workstation/issues/63), [#72](https://github.com/riscPrint/risc-v-workstation/issues/72), [#78](https://github.com/riscPrint/risc-v-workstation/issues/78), [#103](https://github.com/riscPrint/risc-v-workstation/issues/103), [#107](https://github.com/riscPrint/risc-v-workstation/issues/107), [#119](https://github.com/riscPrint/risc-v-workstation/issues/119), [#124](https://github.com/riscPrint/risc-v-workstation/issues/124), [#125](https://github.com/riscPrint/risc-v-workstation/issues/125), [#142](https://github.com/riscPrint/risc-v-workstation/issues/142), [#145](https://github.com/riscPrint/risc-v-workstation/issues/145), [#173](https://github.com/riscPrint/risc-v-workstation/issues/173), [#184](https://github.com/riscPrint/risc-v-workstation/issues/184), [#198](https://github.com/riscPrint/risc-v-workstation/issues/198), [#200](https://github.com/riscPrint/risc-v-workstation/issues/200), [#203](https://github.com/riscPrint/risc-v-workstation/issues/203), [#208](https://github.com/riscPrint/risc-v-workstation/issues/208), [#210](https://github.com/riscPrint/risc-v-workstation/issues/210), [#211](https://github.com/riscPrint/risc-v-workstation/issues/211), [#351](https://github.com/riscPrint/risc-v-workstation/issues/351), [#352](https://github.com/riscPrint/risc-v-workstation/issues/352), [#353](https://github.com/riscPrint/risc-v-workstation/issues/353), [#354](https://github.com/riscPrint/risc-v-workstation/issues/354), [#355](https://github.com/riscPrint/risc-v-workstation/issues/355), [#356](https://github.com/riscPrint/risc-v-workstation/issues/356), [#357](https://github.com/riscPrint/risc-v-workstation/issues/357), [#358](https://github.com/riscPrint/risc-v-workstation/issues/358), [#359](https://github.com/riscPrint/risc-v-workstation/issues/359), [#360](https://github.com/riscPrint/risc-v-workstation/issues/360), [#362](https://github.com/riscPrint/risc-v-workstation/issues/362), [#364](https://github.com/riscPrint/risc-v-workstation/issues/364), [#365](https://github.com/riscPrint/risc-v-workstation/issues/365), [#366](https://github.com/riscPrint/risc-v-workstation/issues/366), [#367](https://github.com/riscPrint/risc-v-workstation/issues/367), [#369](https://github.com/riscPrint/risc-v-workstation/issues/369).

### M4: Integrate engines and durable workflows

Integrate full simulation semantics, UVM, restore, coverage and durable regression workflows. Keep every result bound to its inputs and checked generation.

Phases: P08 through P10. Dependencies: M3 and all earlier runtime predecessors named by each cell.

Main deliverables: IDE: incremental elaboration and generator feedback. Simulation: four-state execution, full UVM and complete restore. Coverage: exact merge and revision exchange. Regression: controller recovery and requirements closure. Formal: deep engine comparison and proof-grid support.

Exit: every cell assigned to these acceptance phases and every required child must pass. Use the exact phase exits in [protocols.md](docs/roadmap/protocols.md). Category 8, [D15.c5](docs/roadmap/acceptance.md#D15c5): Require adjusted checked-result-time upper ratio at most 0.90 against each JasperGold and VC Formal at equal core-hours.

Acceptance cells: [M4: Integrate engines and durable workflows](docs/roadmap/acceptance.md#m4-integrate-engines-and-durable-workflows).

Issues (30): [#14](https://github.com/riscPrint/risc-v-workstation/issues/14), [#16](https://github.com/riscPrint/risc-v-workstation/issues/16), [#22](https://github.com/riscPrint/risc-v-workstation/issues/22), [#28](https://github.com/riscPrint/risc-v-workstation/issues/28), [#32](https://github.com/riscPrint/risc-v-workstation/issues/32), [#41](https://github.com/riscPrint/risc-v-workstation/issues/41), [#45](https://github.com/riscPrint/risc-v-workstation/issues/45), [#46](https://github.com/riscPrint/risc-v-workstation/issues/46), [#57](https://github.com/riscPrint/risc-v-workstation/issues/57), [#71](https://github.com/riscPrint/risc-v-workstation/issues/71), [#132](https://github.com/riscPrint/risc-v-workstation/issues/132), [#160](https://github.com/riscPrint/risc-v-workstation/issues/160), [#167](https://github.com/riscPrint/risc-v-workstation/issues/167), [#178](https://github.com/riscPrint/risc-v-workstation/issues/178), [#180](https://github.com/riscPrint/risc-v-workstation/issues/180), [#182](https://github.com/riscPrint/risc-v-workstation/issues/182), [#187](https://github.com/riscPrint/risc-v-workstation/issues/187), [#191](https://github.com/riscPrint/risc-v-workstation/issues/191), [#213](https://github.com/riscPrint/risc-v-workstation/issues/213), [#214](https://github.com/riscPrint/risc-v-workstation/issues/214), [#217](https://github.com/riscPrint/risc-v-workstation/issues/217), [#296](https://github.com/riscPrint/risc-v-workstation/issues/296), [#335](https://github.com/riscPrint/risc-v-workstation/issues/335), [#344](https://github.com/riscPrint/risc-v-workstation/issues/344), [#345](https://github.com/riscPrint/risc-v-workstation/issues/345), [#346](https://github.com/riscPrint/risc-v-workstation/issues/346), [#347](https://github.com/riscPrint/risc-v-workstation/issues/347), [#348](https://github.com/riscPrint/risc-v-workstation/issues/348), [#350](https://github.com/riscPrint/risc-v-workstation/issues/350), [#378](https://github.com/riscPrint/risc-v-workstation/issues/378).

### M5: Close wide capability and category benefits

Close wide-design capability and the main category benefit comparisons. Check representative workload behavior and the soundness of accepted verdicts.

Phases: P11 through P12. Dependencies: M4 and all earlier runtime predecessors named by each cell.

Main deliverables: Architecture: blind Zen 5 and M-series cycle prediction. IDE and debug: complete-answer throughput. Simulation: wide and manycore capacity, commercial rate comparison. Stimulus: coverage benefit. Workloads: executed representative corpus. Trust: field-escape audits. Design loop: checked retained decisions.

Exit: every cell assigned to these acceptance phases and every required child must pass. Use the exact phase exits in [protocols.md](docs/roadmap/protocols.md). Category 1, [D01.c12](docs/roadmap/acceptance.md#D01c12): Require blind cycle-prediction median absolute error at most 5% per system and class against measured Zen 5 and M-series anchors. Category 3, [D06.c4](docs/roadmap/acceptance.md#D06c4): Require checked complete-answer throughput lower ratio at least 1.10 against each Sigasi, DVT and required native-generator recipe in every language child. Category 4, [D07.c6](docs/roadmap/acceptance.md#D07c6): Require adjusted checked-rate lower ratio at least 1.10 against both VCS and Xcelium in every design and state stratum. Category 7, [D14.c5](docs/roadmap/acceptance.md#D14c5): Require checked new obligations per total core-hour lower ratio at least 1.10 against every strongest qualified industrial stimulus recipe under CC27. Category 10, [D19.c4](docs/roadmap/acceptance.md#D19c4): Require checked complete-answer throughput lower ratio at least 1.10 against each Verdi, Verisium Debug and SimVision in every required root-cause stratum. Category 11, [D20.c2b](docs/roadmap/acceptance.md#D20c2b): Require an adjusted upper bound of at most 5% for unrepresented behavior weight in every workload class against the sealed D20.c4 behavior inventory, using executed and calibrated full anchors. Category 14, [D28.c5](docs/roadmap/acceptance.md#D28c5): Require zero mandatory soundness escapes and a complete natural-frame finite escape rate of at most .01 against two independent retrospective verdict audits. Keep the powered population upper bound of at most .01 separate. Category 19, [D35.c3](docs/roadmap/acceptance.md#D35c3): Require adjusted allocated-core-hour cost per checked retained decision upper ratio at most 0.90 against each required pinned gem5, PMU, native simulation and debug recipe.

Acceptance cells: [M5: Close wide capability and category benefits](docs/roadmap/acceptance.md#m5-close-wide-capability-and-category-benefits).

Issues (7): [#24](https://github.com/riscPrint/risc-v-workstation/issues/24), [#27](https://github.com/riscPrint/risc-v-workstation/issues/27), [#74](https://github.com/riscPrint/risc-v-workstation/issues/74), [#150](https://github.com/riscPrint/risc-v-workstation/issues/150), [#183](https://github.com/riscPrint/risc-v-workstation/issues/183), [#294](https://github.com/riscPrint/risc-v-workstation/issues/294), [#297](https://github.com/riscPrint/risc-v-workstation/issues/297).

### M6: Prove scale and complete the design loop

Complete scale, fast references, regression management and compiler integration. Close the prospective design loop with all costs and transfer limits.

Phases: P13 through P15. Dependencies: M5 and all earlier runtime predecessors named by each cell.

Main deliverables: Simulation: prospective and distributed scale. References: fast independent semantics and complete commercial comparison. Regression: closure-task throughput and farm comparisons. Workloads: fresh intake, response transfer and sampling. Compilers: scheduling and verified native changes. Design loop: final contracts and recommendations.

Exit: every cell assigned to these acceptance phases and every required child must pass. Use the exact phase exits in [protocols.md](docs/roadmap/protocols.md). Category 6, [D11.c6](docs/roadmap/acceptance.md#D11c6): Require adjusted end-to-end checked-rate lower ratio at least 1.10 against both ImperasDV and Siemens Questa Verification IP for RISC-V in every scalar, floating-point, vector, hypervisor and concurrent-state stratum. Category 12, [D24.c9](docs/roadmap/acceptance.md#D24c9): Require an adjusted checked closure-task throughput lower ratio of at least 1.10 against each vManager, IMC and Verdi Planner at each allocation.

Acceptance cells: [M6: Prove scale and complete the design loop](docs/roadmap/acceptance.md#m6-prove-scale-and-complete-the-design-loop).

Issues (4): [#25](https://github.com/riscPrint/risc-v-workstation/issues/25), [#59](https://github.com/riscPrint/risc-v-workstation/issues/59), [#282](https://github.com/riscPrint/risc-v-workstation/issues/282), [#295](https://github.com/riscPrint/risc-v-workstation/issues/295).

### M7: Audit the full release

Audit natural results, whole-feature scope and dependency closure. Release only the category and frame claims that the complete evidence permits.

Phases: P16 through P18. Dependencies: M6 and all earlier runtime predecessors named by each cell.

Main deliverables: Trust: natural-result audit, contract audit, whole-vendor feature audit and final evaluator. Design loop: full dependency audit. Platform: supported release claims with every open gate visible.

Exit: every cell assigned to these acceptance phases and every required child must pass. Use the exact phase exits in [protocols.md](docs/roadmap/protocols.md). D27.c3 must reject every missing or stale mandatory predecessor. No partial tier can claim full workstation closure.

Acceptance cells: [M7: Audit the full release](docs/roadmap/acceptance.md#m7-audit-the-full-release).

Issues (4): [#23](https://github.com/riscPrint/risc-v-workstation/issues/23), [#37](https://github.com/riscPrint/risc-v-workstation/issues/37), [#39](https://github.com/riscPrint/risc-v-workstation/issues/39), [#51](https://github.com/riscPrint/risc-v-workstation/issues/51).

## The 19 categories

Each row fixes the primary measure, comparator and bound. The milestone closes this primary; M7 audits the full category contract.

| Category | Fixed primary measure, comparator and number | Owning cell | Milestone |
|---|---|---|---|
| 1. Architecture exploration and performance modeling | Require blind cycle-prediction median absolute error at most 5% per system and class against measured Zen 5 and M-series anchors. | [D01.c12](docs/roadmap/acceptance.md#D01c12) | M5 |
| 2. Microarchitecture performance analysis | Require unattributed cycle fraction at most 2% against independently checked full-run event accounting. | [D03.c1](docs/roadmap/acceptance.md#D03c1) | M2 |
| 3. RTL design productivity and HDL/IDE support | Require checked complete-answer throughput lower ratio at least 1.10 against each Sigasi, DVT and required native-generator recipe in every language child. | [D06.c4](docs/roadmap/acceptance.md#D06c4) | M5 |
| 4. Simulation speed and scale | Require adjusted checked-rate lower ratio at least 1.10 against both VCS and Xcelium in every design and state stratum. | [D07.c6](docs/roadmap/acceptance.md#D07c6) | M5 |
| 5. ISA compliance and architectural verification | Require checked conclusive obligations per total core-hour lower ratio at least 1.10 against each Siemens Questa Processor / OneSpin and Axiomise formalISA on the complete pinned architectural-proof frame. | [D09.c2](docs/roadmap/acceptance.md#D09c2) | M2 |
| 6. Co-simulation and reference models | Require adjusted end-to-end checked-rate lower ratio at least 1.10 against both ImperasDV and Siemens Questa Verification IP for RISC-V in every scalar, floating-point, vector, hypervisor and concurrent-state stratum. | [D11.c6](docs/roadmap/acceptance.md#D11c6) | M6 |
| 7. Stimulus generation and coverage closure | Require checked new obligations per total core-hour lower ratio at least 1.10 against every strongest qualified industrial stimulus recipe under CC27. | [D14.c5](docs/roadmap/acceptance.md#D14c5) | M5 |
| 8. Formal verification | Require adjusted checked-result-time upper ratio at most 0.90 against each JasperGold and VC Formal at equal core-hours. | [D15.c5](docs/roadmap/acceptance.md#D15c5) | M4 |
| 9. Microarchitectural verification | Require checked proof-closure-time upper ratio at most 0.90 against each qualified JasperGold ordering and coherence flow. | [D17.c15](docs/roadmap/acceptance.md#D17c15) | M3 |
| 10. Debug and root cause | Require checked complete-answer throughput lower ratio at least 1.10 against each Verdi, Verisium Debug and SimVision in every required root-cause stratum. | [D19.c4](docs/roadmap/acceptance.md#D19c4) | M5 |
| 11. Workloads and benchmarks | Require an adjusted upper bound of at most 5% for unrepresented behavior weight in every workload class against the sealed D20.c4 behavior inventory, using executed and calibrated full anchors. | [D20.c2b](docs/roadmap/acceptance.md#D20c2b) | M5 |
| 12. Regression management, CI and scale | Require an adjusted checked closure-task throughput lower ratio of at least 1.10 against each vManager, IMC and Verdi Planner at each allocation. | [D24.c9](docs/roadmap/acceptance.md#D24c9) | M6 |
| 13. Agent integration | Require adjusted median total verified campaign-time upper ratio at most 0.75 against shell-plus-upstream, the strongest qualified coding agent and every required commercial EDA agent per provider. | [D25.c3a](docs/roadmap/acceptance.md#D25c3a) | M3 |
| 14. Correctness and trust of verdicts | Require zero mandatory soundness escapes and a complete natural-frame finite escape rate of at most .01 against two independent retrospective verdict audits. Keep the powered population upper bound of at most .01 separate. | [D28.c5](docs/roadmap/acceptance.md#D28c5) | M5 |
| 15. Usability, install and docs | Require mandatory task-answer error count exactly zero against independent expected documentation and status answers on every host, language and task class. | [D29.c7](docs/roadmap/acceptance.md#D29c7) | M3 |
| 16. Generality across cores and HDLs | Require sealed unseen-core transfer count at least 2 against the independent adapter obligation inventory, with distinct language and generator ancestries. | [D30.c3](docs/roadmap/acceptance.md#D30c3) | M3 |
| 17. Open-source readiness | Require bit-identical reproducible build count at least 2 per supported host against the pinned package matrix and source-to-binary hashes. | [D32.c1](docs/roadmap/acceptance.md#D32c1) | M2 |
| 18. Security and microarchitectural side-channel verification | Measure seconds per conclusive checked contract with a paired geometric mean. Require the adjusted candidate-to-comparator upper ratio at most 0.90 against both JasperGold Security Path Verification and Cycuity Radix. | [D33.c2](docs/roadmap/acceptance.md#D33c2) | M3 |
| 19. Performance-analysis and design-loop tooling | Require adjusted allocated-core-hour cost per checked retained decision upper ratio at most 0.90 against each required pinned gem5, PMU, native simulation and debug recipe. | [D35.c3](docs/roadmap/acceptance.md#D35c3) | M5 |

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
| Verdi debug apps, root-cause analysis | Automatic triage of a failure | `rvw bundle` (last instructions, pipeline snapshot, wave window, SpinalTrace causes, replay), `rvw reduce`, `rvw bisect` | usable | Native UART and per-hart reduction ran. `wave why-run` uses an explicit project without also selecting the C1 bundled core (#1502). Second-machine replay, full checkpoint state and general history bisection remain open. |
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
| rvw debug | `rvw/src/rvw/debug/` | DBG | OpenOCD campaign, native DMI/JTAG client, pinned baseline E-Trace decoder and exact C2 PC comparison | Single-hart RV64 debug profile; machine-mode encoder ingress | partly generic; ran on real core RTL. Vex DMI/JTAG, OpenOCD and four ingress cases ran (#896/#914). The target progress callback reports final comparison results and profile skips (#1507). Load/store address reference tests now cover declared match types and prefix effects (#1503). Five target deviations, target+4 breakpoint stop, the full RTL trigger matrix and trace recovery remain open. |
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

Keep C1 run results, C2 retirement traces, C3 suites, C4 verdicts, C5 bundles, C6 design databases,
C7 MCP, C8 capture and generations, and C9 architecture models in one versioned contract.
Update [PLATFORM_CONTRACTS.md](docs/PLATFORM_CONTRACTS.md) with any format change.
SpinalDB supplies dependency, block and source identities. Preserve legacy extraction while semantic parity differs.
SpinalTrace, SpinalWaves and SpinalBlocks must join the same design generation. A name match alone cannot join evidence.

Keep project paths relative to `rvw.toml`. Use `--project`, `RVW_PROJECT` or upward discovery.
Keep bundled BOOM examples for explicit legacy selection. Generic libraries must not select a core implicitly.
The CLI and MCP use deterministic code for deterministic work. See [COMMAND_REFERENCE.md](docs/COMMAND_REFERENCE.md).
Generated MCP discovery listed 348 tools in the 2026-11-17 review.
Discovery and schema tests do not qualify handlers. The command reference can lag discovery.
Existing GUI hosts remain optional consumers. They cannot supply missing machine evidence.

Alpha, Beta, Qualified and Full apply separately to each category and frame.
The full tier predicates and required receipt sets are in [protocols.md](docs/roadmap/protocols.md).
A schema interface never supplies a final producer result. A substitute receipt closes only its named route.
Print the actual scope, comparison, finite or population class, unsupported claims and open gates.

## Decisions

| Date | Owner decision |
|---|---|
| 2026-10-20 | Keep the core and tools in separate repositories. This repo owns the tool roadmap and task list. |
| 2026-10-21 | Use one Python command and one MCP server. Use shared formats and core-owned adapters. |
| 2026-11-04 | Freeze the source plan and write it as a readable implementation plan. |
| 2026-11-04 | Judge tool capabilities only. Keep studies, maintainers, community, legal work, publication and named-person tasks in the organisation appendix. |
| 2026-11-04 | Use CLI, MCP and machine-readable output first. GUI work is optional. |
| 2026-11-04 | Defer PPA, emulation, FPGA and physical power or EM side channels. Keep digital timing, cache and speculation verification. |
| 2026-11-04 | Do not require a sponsor or maintainer withdrawal drill. |
| Owner direction | Plan full tool ambition. Extend open formal, simulation, SystemVerilog UVM, coverage and debug engines. Resources cannot reduce acceptance scope. |

The owner will supply Kubernetes scale-out capacity and outside compute. Keep desktop use native.
Pinned cluster execution shares C1 through C9 and needs the same independent checks.
Keep the SPEC adapter required. A user may supply a licensed SPEC corpus. Use open substitutes for the default flow.
Commercial access and publication approval are owner tasks. The named technical comparisons remain required for capability claims.
Keep machine-wide locks and process-group cancellation. Keep native package revisions pinned.
Missing evidence must return an error, `inconclusive` or `no_checks` as the contract requires.

## Limit ownership

Tool README files own current limits. The issue map assigns every open issue to one milestone.
The cell owner roles and shared rules define future acceptance work. An issue closure is not a receipt.
All existing feature-specific limits remain until their required cells pass.

## Optional later work

GUI layout, mouse and keyboard interaction, visual cross-probing and interactive studies can follow the agent interface.
Retain existing viewers as optional tools. Do not make their UI a capability gate.
PPA, synthesis and physical signoff, emulation, FPGA prototyping, power leakage and EM leakage need a later owner plan.
Issues #23 and #51 stay open as explicit deferrals. They do not block this tool plan.
