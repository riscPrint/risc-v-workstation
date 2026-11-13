# PR source ledger

Snapshot collected at 2026-11-13T07:16:42.340567+00:00. PR merge window starts at 2026-11-13T00:00:00Z. This is a reading audit. No tests, builds, simulations or proofs ran for this report. Local personal paths in quoted source text are omitted. Raw JSON retains the source. PR bodies report the evidence. Their artifacts were not independently rerun.

Full PR bodies follow. Text in these sections is source material, not a new acceptance claim.

## PR 382

[#382](https://github.com/riscPrint/risc-v-workstation/pull/382). Merged: 2026-11-13T01:29:12Z.

Title: feat(formal): extract mapped deletion-minimal solver cores

Audit evidence label: unit tests only.

## Summary
Add `rvw formal proof-core` and `formal_proof_core` MCP. Extract named Z3 UNSAT cores, reduce constraints, retain solver queries, bind stable property and requirement IDs, and resolve design signals with SpinalDB.

Scope is one supplied SMT query. Direct SBY/AIGER extraction, full obligation joins and assumption adequacy remain open. This does not authorize exclusions or establish an unbounded RTL proof.

## Testing
- Solver-core tests: 6 passed, 0 skipped, including native Z3.
- Required fast set: 759 passed, 4977 deselected.
- No full Python suite, BOOM build, simulation, long formal job or CI wait.

## Issues
Refs: #62

Roadmap notes: Named SMT solver-core extraction and source lookup are available. Automatic SBY/AIGER query export and complete requirement obligations remain open.


## PR 383

[#383](https://github.com/riscPrint/risc-v-workstation/pull/383). Merged: 2026-11-13T01:38:35Z.

Title: fix(cosim): validate and audit platform choices

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Reject unknown platform settings and schema versions. Report the selected legal policies and all masks used by a comparison, even when recent history is empty or full. Add a native RV32IM, M-only, no-PMP reference test for absent PMP access and ECALL mtval. Preserve the current VexRiscv example's M/S/U configuration because its adapter enables those modes.

Roadmap notes: Platform policy validation and mask reporting are extended. Split accesses, independent partial effects, PMP geometry and translation campaigns remain open. The RV32 test is reference evidence. No VexRiscv DUT match is claimed.

## Testing

- Targeted policy and reset tests: 71 passed, 0 skipped.
- Fast set: 759 passed, 4974 deselected, 0 skipped.
- Built the native Spike shim against the installed headers and libraries.
- NOT RUN: BOOM or VexRiscv builds/simulations, full Python suite, Sail campaigns, CI.

## Issues

Refs: #8, #11. The larger checklist scopes remain open.


## PR 384

[#384](https://github.com/riscPrint/risc-v-workstation/pull/384). Merged: 2026-11-13T01:32:02Z.

Title: feat(formal): generate project CSR verification artifacts

Audit evidence label: ran on seeded RTL fixture.

## Summary

Generate CSR monitors, optional project-bound SBY jobs, directed M-mode assembly and functional coverage groups from `rvw.csr/1`. Add CLI/MCP access, scratch-register examples and a seeded Spinal fixture with four mutations. Preserve both the solver-core command and CSR command during rebase.

This is a bounded increment. Full standard M/S catalog, aliases, privilege transitions, autonomous updates, general side effects, real-core bindings and compliance campaigns remain open.

## Testing

- CSR and command-reference tests: 16 passed, 0 skipped. Native Icarus accepts legal observations and detects four injected faults. These tests use a Verilog observation fixture, not the Spinal fixture.
- Fast set before rebase: 759 passed, 4978 deselected.
- Fast set after rebase: 759 passed, 4991 deselected, 0 skipped.
- NOT RUN: Spinal compile, SBY proof, assembly build, C1 execution, Spike comparison, BOOM simulations, full Python suite.

## Issues

Refs: #85

Roadmap notes: Add bounded project-owned CSR artifact generation. Retain the open compliance and real-core binding gaps.


## PR 385

[#385](https://github.com/riscPrint/risc-v-workstation/pull/385). Merged: 2026-11-13T02:02:07Z.

Title: feat(memory): check serialized multi-hart observations

Audit evidence label: unit tests only.

## Summary
Add per-hart ELF input preparation and an independent serialized byte checker under `rvw memory`. Keep capture order, retirement order and memory acceptance serialization separate. Add CLI/MCP entries and shared-format documentation.

## Testing
Twelve targeted contract and command-reference Python tests passed, with no skips. The fast Python set passed: 759 tests, no skips. The same set passed after the final rebase: 759 passed, no skips.

NOT RUN: Spike, RTL, BOOM builds, full Python suite. This change does not supply a production multi-hart adapter or a general multi-hart architectural reference.

## Issues
Refs: #90. Production multi-image loading and independent architectural execution remain open.

Roadmap notes: memory verification now has pinned per-hart ELF input preparation and a C2/2 serialized byte/reference checker. Sample consistency is separate from RVWMO proof.


## PR 386

[#386](https://github.com/riscPrint/risc-v-workstation/pull/386). Merged: 2026-11-13T01:40:19Z.

Title: feat(sim): isolate persistent regression workers

Audit evidence label: unit tests only.

## Summary

Use isolated serial simulation servers for parallel regression workers. Default the RiscvSim backend to persistent mode, with an explicit opt-out. Skip the redundant pre-build process and retain its startup budget. Retry missing results in fresh processes after a worker crash. Cancel worker groups before leaving the pool. Record generated RTL identity in session metadata.

Roadmap notes: #14 now has default RiscvSim regression selection and isolated parallel workers. Direct persistent run-many remains serial. Native device/monitor/coverage reset checks, native cancellation and long-lived resource measurements remain open.

## Testing

- Targeted Python runner and worker tests: 14 passed, 0 skipped.
- Fast set after rebase: 759 passed, 0 skipped, 4996 deselected.
- Bounded generic Scala ServerSpec under the sbt lock: 9 passed, 0 skipped. This uses fixture adapters, not native core simulation.
- The pool cancellation test starts a real sleeping child process and checks that its process group stops after a peer raises.
- git diff --check passed.
- NOT RUN: VexRiscv native pool/reset/cancellation tests, BOOM, full Python suite, long resource tests, GitHub CI.

## Issues

Refs: #14. This increment does not close the issue. It does not add live checkpoints or prove adapter reset equivalence.


## PR 387

[#387](https://github.com/riscPrint/risc-v-workstation/pull/387). Merged: 2026-11-13T03:44:44Z.

Title: feat(formal): add per-output equivalence contracts and mcp

Audit evidence label: unit tests only.

## Summary

Add signed per-output latency maps, output renames and the formal_equiv MCP tool. Run separate closed output partitions. Prove state encoding changes through output behavior without state equality assumptions.

## Testing

Native test_equiv.py: 22 passed, 0 skipped. Required fast set before rebase: 759 passed. Rebase retains the other worker's solver core tool and documentation. Required fast set after rebase: 759 passed, 4982 deselected.

NOT RUN: BOOM builds, BOOM proofs, full Python suite, long formal runs. Blackbox contracts, generated clocks, memory maps and counterexample replay remain open.

## Issues

Refs: #18.

Roadmap notes: Add per-output signed latency alignment, output matching, state encoding fixture proof and equivalence MCP support. Keep FV 2 partial for blackboxes, generated clocks, internal dependency partitions and mapped replay.


## PR 388

[#388](https://github.com/riscPrint/risc-v-workstation/pull/388). Merged: 2026-11-13T01:34:18Z.

Title: feat(regress): run seeded riscv-dv campaigns through spike

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Add `rvw regress random` and `regress_random`. Generate pinned upstream pygen programs, compile them with project-owned ISA, ABI, runtime and linker settings, run them through the existing C1 regression runner, compare C2 through the public Spike API, and measure functional coverage only after a complete passing comparison. Record seeds, commands, hashes and separate generation, compiler, adapter, trace and reference failures.

Add `scripts/install.sh --with-riscv-dv` and its check mode. Install source outside the repository. Add `[stimulus] random_settings` project selection. Keep the existing integer ALU profile explicit. No cosim platform code changes.

## Testing

- Targeted random, launcher, project and command reference tests: 49 passed. Two final runtime/hash tests are included in the random subset: 16 passed.
- Post-rebase fast set: 759 passed, 5009 deselected, zero skips.
- Native pinned external install and dependency check: passed.
- Native RV32 pygen seed 376, 20 instructions, two runs: equal source SHA-256 `b4ec00130cb33bd8a415f2bd2773b4b284a78cb38bee74cf2eef5013cb00fe77`.
- Native RV32 GCC compile with the initialization runtime: passed.
- NOT RUN: BOOM or VexRiscv simulation, native Spike campaign, DUT seeded-bug negative control, full Python suite, CI. The brief forbids heavy core jobs. Fixture negative controls reject partial matches, mismatches, missing traces and failed C1 runs.

## Issues

Refs: #376, #48

Keep both issues open. Native DUT campaigns, random branch/memory/privilege constraints, TestRIG core injection hooks and broader source campaigns remain. The new command is an explicit random campaign entry point, not an automatic `run --tier random` expansion. C1 ELF replay is retained, but generator-level reduction and cross-host deterministic replay are not qualified.

Roadmap notes: Seeded pinned riscv-dv generation, compilation, C1 dispatch, Spike qualification and full-trace functional coverage now share a CLI/MCP command. Native generation and compilation were checked. DUT execution and payload-only closure evidence remain unverified. Do not mark #376 or #48 complete.


## PR 389

[#389](https://github.com/riscPrint/risc-v-workstation/pull/389). Merged: 2026-11-13T02:37:47Z.

Title: feat(formal): extend connection tables and proof reports

Audit evidence label: ran on seeded RTL fixture.

## Summary

Add project CSV/JSON/TOML connection tables with condition, delay and inversion. Add reverse input-influence checks for declared destinations and every top output. Report outputs with no required source declaration.

Run bounded or unbounded value-transfer campaigns with separate activation witnesses. Bind required internal source, destination and condition signals through Yosys flatten/expose without driver cuts. Check top-port types and exact internal RTL names/widths. Retain source/transformed hashes and bindings. Missing required structural paths cannot be replaced by value proofs. Check and retain each child result's proof kind. Forbidden activation must witness distinct legal source values sampled with the condition and delay.

Expose connectivity through MCP and integrate its structural results with SoC map/bridge checks. Internal forbidden influence, inouts and real mapped-DUT integration remain open. Source RTL assumptions restrict proofs. No design acceptance is implied.

Roadmap notes: project connection tables, reverse checks across top outputs, required internal observations and optional unbounded connection contracts are implemented. SoC checks can include the same structural table. Internal forbidden influence still requires a state-coupling backend. Real bridge transaction pairing and whole-core evidence remain open.

## Testing

- Initial connectivity suite: 51 passed, 0 skipped, including native Yosys/SBY/Yices bounded and unbounded small-fixture runs.
- SoC integration, bridge and connection-table checks: 42 passed, 0 skipped.
- Internal backend/campaign checks: 7 passed, 0 skipped. Includes correct, wrong, delayed and internal-destination fixtures and width refusal.
- Post-rebase top-port native checks: 4 passed, 38 deselected, 0 skipped.
- Post-guard native proof-kind check: 1 passed, 6 deselected. Latest table/graph regression: 33 passed, 20 deselected.
- Distinct-source activation regression: 4 native cases passed, 0 skipped. The fixed-source case failed before the fix.
- Post-rebase fixed/free-source native spot checks: 2 passed, 2 deselected.
- Final post-rebase table/graph/reference tests: 36 passed, 20 deselected, 0 skipped.
- Final post-rebase fast set: 809 passed, 6163 deselected, 0 skipped.
- NOT RUN: BOOM builds, core simulations, full Python suite, long formal campaigns, real bridge traffic, GitHub CI waits.

## Issues

Refs: #107, #134. Internal forbidden influence and real mapped-DUT integration remain open.


## PR 390

[#390](https://github.com/riscPrint/risc-v-workstation/pull/390). Merged: 2026-11-13T01:58:06Z.

Title: feat(soc): check concurrent register hardware side effects

Audit evidence label: unit tests only.

## Summary

Extend paired device register checks with expanded write masks and independent hardware clear/set observations. Apply software effects, hardware clear, then hardware set. Failed software accesses still permit observed hardware updates.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_soc_bridge.py -q`: 27 passed, 0 skipped.
- Fast set: 759 passed, 5128 deselected, 0 skipped.
- NOT RUN: Scala tests, BOOM simulation, real-device campaigns, full Python suite.

## Issues

Refs: #142

Roadmap notes: Paired register observations now cover concurrent hardware updates. Real-device bindings, multiple bus masters and behavior between samples remain open.


## PR 391

[#391](https://github.com/riscPrint/risc-v-workstation/pull/391). Merged: 2026-11-13T01:43:24Z.

Title: feat(formal): reduce counterexamples and export replay benches

Audit evidence label: ran on seeded RTL fixture.

## Summary
Reduce counterexample prefixes and input changes through exact-property Yosys replay. Keep first input values and all assumptions. Retain each trial and report the check budget. Export a portable replay model and testbench. Add SpinalDB driver and fan-in analysis through the query API. Extend CLI and MCP.

Reduction is greedy. Assumption reduction, a solver what-if proof with internal pins, and native typed Spinal source/viewer navigation remain open. No proof verdict is earned by replay or exported simulation files.

Rebase resolution: keep all concurrent documentation additions. Keep X-propagation, minimization and testbench flags together. Regenerate the command reference.

## Testing
- Counterexample tests: 17 passed, 0 skipped, including native Yosys reduction and generated Icarus compile/run.
- Required fast set after rebase: 759 passed, 5102 deselected.
- No full suite, BOOM build or simulation, long formal run, GUI navigation or CI wait.

## Issues
Refs: #60

Roadmap notes: Exact-property greedy counterexample reduction, simulation export and query driver analysis are available. Native captured Spinal viewer validation and assumption reduction remain open.


## PR 392

[#392](https://github.com/riscPrint/risc-v-workstation/pull/392). Merged: 2026-11-13T01:59:11Z.

Title: feat(arch): extend ooo timing and saved calibration

Audit evidence label: unit tests only.

## Summary
Add committed-path branch recovery with a predictor interface, per-class issue limits, integer physical-register pressure, and traced address disambiguation with store forwarding. Add project-owned effective-configuration snapshot checks and cancellable OoO MCP jobs.

Add saved C1/C2 calibration, held-out overlap checks, explicit missing/zero event errors, correlations, budget comparisons and separate exclusive prediction scores. Bind all captured inputs by hash. Keep accuracy inconclusive and report local timestamp limits.

Core elaboration exporters, cache/TLB timing, wrong-path work, replay, memory dependence prediction, semantic event-map qualification, five-workload RTL calibration, later C2 comparison, later event scoring and three-repeat native speed qualification remain open. No issue is closed.

Roadmap notes: the own-core model supports bounded branch/memory/port/register timing and effective snapshot comparison. Saved calibration and prediction evidence has CLI/MCP support. RTL accuracy and native speed are unqualified.

## Testing
45 focused OoO and command-reference tests passed. Final rebased fast set: 759 passed, 5104 deselected in 93.85 seconds. Merge conflicts in shared docs were resolved by retaining both additions and regenerating the reference.

NOT RUN: gem5, RTL, native speed qualification, full Python suite, CI waits.

## Issues
Refs: #354, #355, #356


## PR 393

[#393](https://github.com/riscPrint/risc-v-workstation/pull/393). Merged: 2026-11-13T01:50:41Z.

Title: feat(regress): add cross-privilege control campaigns

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Add a project-configured RV64 privilege campaign under `rvw regress privilege`.
Generate 30 self-checking TVM, TW and TSR programs across M/S/U entry and both
control states. Check trap cause and PC, control retention, and an S-mode retry
after the M-mode handler clears the control. Reuse the existing C1 adapter and
strict Spike checker. Add MCP tools and functional groups with all-member pass.
Add four WFI wake programs with project-owned timer/software addresses. Cross
the two sources with global MIE clear/set. Allow legal early return. Check
interrupt entry state and retained register state. Emit C2 functional coverage
configuration separately from architectural outcome groups.
Keep this code separate from the MMU and multi-hart modules.

## Testing

- Targeted campaign tests: 20 passed, 0 skipped.
- Native Spike: 34 generated programs passed, 0 skipped. Each run uses `nice -n 10`
  and a two-second process-group timeout.
- Fast set before rebase: 759 passed, 4990 deselected, 0 skipped.
- Fast set after final rebase: 759 passed, 5099 deselected, 0 skipped.
- NOT RUN: RTL builds, DUT simulations, full Python suite, long formal jobs or CI.

Spike results are reference self-checks. They do not earn DUT coverage. Missing
or duplicate C1 evidence, incomplete strict matches and synchronization remain
inconclusive. The existing SUM/MXR/MPRV suites remain in the MMU module. Disabled
feature combinations and DUT campaign closure remain open. WFI physical clock
stop, external-event scheduling and broader privilege wake cases remain open.

## Issues

Refs: #139
Refs: #149

Roadmap notes: Add project-configured privilege campaign generation, short Spike
self-checks, and C1/strict-reference functional-group checks to regression
capabilities. Record the 30 reference-only control cases and four WFI cases. Retain disabled-feature
and DUT qualification as open work. No ROADMAP.md or TODO.md change is included.

The strict shim does not provide the native executable's complete CLINT device
behavior. No strict WFI match or DUT result is claimed from the native Spike
self-check runs. PLIC, reset, NMI and the remaining protection/extension issues
are not implemented by this PR.


## PR 394

[#394](https://github.com/riscPrint/risc-v-workstation/pull/394). Merged: 2026-11-13T03:03:29Z.

Title: feat(uvm): add project bench adapters and seeded regressions

Audit evidence label: unit tests only.

## Summary
Add project-owned UVM bench manifests and rvw uvm build, run, list, regress, coverage-merge and features commands with MCP tools. Add C1/C3 result conversion, positive completion evidence, UVM error/fatal handling, input hashes and a reusable base environment. Record CORE-V-VERIF practices and project ownership boundaries.

Recover this PR on current main. Keep both sides of the contracts, remove a duplicated UVM subsection and regenerate the command reference. Preserve main's live-session registration while adding regression-specific UVM registration. Include the profile diagnostics and workarounds added on main in the feature table.

Roadmap notes: reusable bench flow, base environment and feature evidence table. CPU/RAL additions are merged separately in #469, #536 and #559. Full protocol binding, architectural interrupt/debug comparison and C4 acceptance remain open.

## Testing
- Current flow unit tests: 26 passed, 0 skipped.
- Required fast set: 839 passed, 6823 deselected, 0 skipped.
- Project bench native build was not rerun during this final rebase. Native CPU, RAL and component checks are recorded in #469, #536 and #559.
- No BOOM build, full Python suite, hardware run or CI wait.

## Issues
Refs: #296. Source identity remains incomplete. Component C1/C3 results do not earn C4 core acceptance.

Recovery reached the brief's five merge-retry limit. This final cleanup is pushed without another merge attempt. The PR remains open for the parent worker to merge.


## PR 395

[#395](https://github.com/riscPrint/risc-v-workstation/pull/395). Merged: 2026-11-13T01:53:53Z.

Title: feat(formal): lower finite temporal sva and run parallel tasks

Audit evidence label: unit tests only.

## Summary
Add finite temporal SVA lowering through native open Yosys statements and a parallel SBY task runner. Support finite named sequences, delays/ranges, consecutive repetition, overlap/nonoverlap implication, disable iff, assume and cover. Keep named unsupported diagnostics. Add CLI and MCP commands, project manifest selection, C3, JUnit, requested bounded depth and trace paths.

## Testing
- New targeted native and unit tests: 43 passed, no skips. Later CLI frontend integration: 1 passed, no skips. Later unit/reference checks: 16 passed, 32 deselected. These sets overlap.
- Fast set after rebase: 759 passed, 5057 deselected, no skips.
- Later vector Boolean and sequence-alternative checks: 6 passed, 41 deselected, no skips.
- Five ABC legal fixtures reduce to combinational networks and produce expected native errors. They do not count as engine proofs.
- NOT RUN: full Python suite, BOOM builds/simulation, long formal jobs, full SystemVerilog scheduling qualification, GitHub CI wait.

## Issues
Refs: #61

Remaining: full temporal SVA and general liveness, sampled functions in the new frontend, all simulator scheduling regions, campaign transitive input closure, complete attribution and non-vacuity. Suite observations stay inconclusive. A bounded pass is never proven.

Roadmap notes: finite temporal SVA and parallel declared-task regression now exist. Keep FV9 partial. General SVA and campaign certification remain open. Related formal CLI/MCP and appended docs conflicts were resolved by retaining both workers' additions and regenerating the command reference.


## PR 396

[#396](https://github.com/riscPrint/risc-v-workstation/pull/396). Merged: 2026-11-13T01:36:30Z.

Title: feat(vip): add apb4 agents and fault-detection fixtures

Audit evidence label: ran on seeded RTL fixture.

## Summary

Add a declared APB4 profile with 32-bit addresses and data, one select, PPROT and byte strobes. Add UVM manager and reactive subordinate roles, a passive monitor, SVA protocol checks, directed and random sequences, address fault injection, functional coverage and a register scoreboard hook. Add matching Python cycle agents and an optional cocotb adapter. Add a seeded four-word RTL RAM with read corruption.

## Testing

- Targeted Python: `rvw/.venv/bin/python -m pytest rvw/tests/test_vip_apb.py -q`: 12 passed, no skips.
- Fast set before rebase: 759 passed, 4981 deselected, no skips. Repeated after rebase before push.
- Native cocotb 2.0.1 on Verilator 5.052: three seeds each completed 98 transfers on good RTL. Three corruption runs each failed with `APB_DATA` and no successful testcase. `nice -n 10 rvw/.venv/bin/python Uvm/vip/apb/cocotb_smoke.py --out /tmp/rvw-vip-apb-cocotb-1`.
- Final SV sources passed Verilator lint with the pinned Accellera UVM 2020.3.1 package and assertions/coverage enabled.
- Native UVM executable build exceeded the 120-second smoke limit during C++ compilation. UVM simulation NOT RUN. Reactive subordinate roles NOT RUN against native RTL. No BOOM build, full Python suite or CI wait.

## Issues

Refs: #190

Remaining: native UVM runtime qualification, reactive subordinate conformance and wider project integration. APB5 wakeup/user signals and four-state simulator qualification are outside this declared profile. No issue closure or SoC conformance claim.

Roadmap notes: APB4 simulation VIP now has UVM and Python/cocotb implementations. The cocotb manager/monitor has good-versus-buggy RTL evidence for three seeds. Python cases cover waits, byte strobes, access errors, reset interruption and phase/stability faults. UVM runtime and reactive subordinate qualification remain open. ROADMAP.md and TODO.md are unchanged as directed.


## PR 397

[#397](https://github.com/riscPrint/risc-v-workstation/pull/397). Merged: 2026-11-13T01:37:12Z.

Title: feat(regress): add project-selected virtual-memory matrices

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Add project-selected Sv39, Sv48, Sv57 and Sv32 requirement matrices to the existing MMU generator. Keep new page-table, PTE extension, two-stage and shootdown logic in separate modules. Add a C1 elf-dir suite example and functional groups. Preserve reference-only and DUT evidence boundaries.

The matrices contain 147 Sv39, 149 Sv48, 151 Sv57 and 142 Sv32 cases. Programs check data or exact trap cause, tval and PC. Add 28 Svnapot/Svpbmt cases, six nested HLV cases and three two-hart mailbox shootdowns. Extend the independent immutable-walk checker to each paging geometry.

The rebase preserves both workers' appended contract and README sections.

## Testing

- Targeted MMU and paging tests: 96 passed, zero skipped. This includes all 589 matrix programs and 28 PTE extension programs on Spike.
- Additional native Spike tests: six guest programs and three two-hart shootdown programs passed. Both targeted tests passed, zero skipped.
- Fast set before rebase: 759 passed, 4994 deselected. The post-rebase count is recorded below.
- RTL, BOOM builds, Sail and full Python suite: NOT RUN.

## Issues

Refs: #84, #147, #171, #154, #129, #99, #164, #148, #145, #140.

Keep each issue open. Remaining work includes complete DUT requirement closure, faulting and changing walk protocols, A/D atomicity and concurrent PTE updates, invalidation observations across an entire NAPOT range, independent PBMT transaction ordering, interrupt-based shootdowns and shared TLB completion, other guest x4 modes, VMID reuse and independent nested-walk checks.

Roadmap notes: the existing MMU regression tool now has project-selected RV32/RV64 paging matrices, geometry-aware immutable-walk checks, opt-in PTE extension cases, bounded nested HLV tests and two-hart mailbox shootdowns. Reference tests pass. DUT coverage and the limits above remain open. ROADMAP.md and TODO.md were not edited.

Post-rebase fast set: 759 passed, 5036 deselected, zero skipped.


## PR 398

[#398](https://github.com/riscPrint/risc-v-workstation/pull/398). Merged: 2026-11-13T01:37:24Z.

Title: feat(memory): add configured Zacas instruction campaigns

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add opt-in RV32/RV64 Zacas programs to the ordering runner. Cover all available widths, aq/rl flags, success/failure, double-XLEN register pairs, x0 pair rules, word sign extension and guard bytes. Add explicit locked-PMP fault and natural-alignment-only profiles. Keep default suites unchanged.

## Testing
46 targeted Python tests passed, no skips. Native Spike passed all three Zacas profiles on RV32 and RV64 at seed 7. Injected missing CAS, wrong return and failed-CAS write defects were rejected. The fast Python set ran before push.

NOT RUN: RTL, BOOM builds, concurrent multi-hart CAS, full Python suite. Instruction effects do not establish contention atomicity or external acquire/release ordering.

## Issues
Refs: #170. Contention observers and RTL campaigns remain open. Reserved odd register-pair encodings have no mandatory behavior assigned by these tests.

Roadmap notes: configured Zacas instruction, access-fault and alignment profiles now have native Spike smoke coverage. Concurrent atomicity and target-specific restrictions still need RTL evidence.


## PR 399

[#399](https://github.com/riscPrint/risc-v-workstation/pull/399). Merged: 2026-11-13T01:37:53Z.

Title: feat(formal): add counter and interface safety monitors

Audit evidence label: unit tests only.

## Summary

Add project-bound HPM, initialized-read and serial AXI-Lite safety monitors through `rvw formal template` and `formal_template` MCP. HPM models independent events, inhibit/filter, write priority, sticky overflow and interrupt enable. Initialized reads track written bits. AXI-Lite tracks independent AW/W acceptance and prior requests for responses.

## Testing

- Native Icarus references and injected faults: 7 passed, 0 skipped.
- Command reference: 3 passed, 0 skipped.
- Required fast set: 759 passed, 5017 deselected, 0 skipped.
- NOT RUN: SBY proofs, Scala tests, real-core campaigns, full Python suite.

## Issues

Refs: #98, #65, #66

Roadmap notes: Add optional generated safety monitors. Real-core event bindings, full microarchitectural rules, AXI payload stability/data and coherent TileLink gaps remain open. No issue is closed.


## PR 400

[#400](https://github.com/riscPrint/risc-v-workstation/pull/400). Merged: 2026-11-13T01:41:28Z.

Title: fix(cosim): retain fault and csr observation limits

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Reject Spike trap steps with logged memory effects. The shim can no longer discard those effects and infer zero completion. Report checked CSR snapshot and fault-access counts, including mismatching observations.

Add native tests for unread CSR snapshots, unsigned-load/store/LR/AMO fault attempts, misaligned/unmapped fault precedence, and locked TOR/NA4/NAPOT protection. Mutations check address mismatches and partial-effect refusals. Locked PMP configuration and address writes must remain ignored.

Roadmap notes: These are native reference and checker tests. DUT per-slot CSR and fault capture, Sail CSR/fault observations, independent partial-effect capture, PMP grain/priority and translation campaigns remain open. No core source was changed. No DUT match is claimed.

## Testing

- Combined policy/state/fault/PMP targeted tests: 103 passed, 0 skipped.
- Native Spike shim build passed against installed matching headers/libraries.
- Fast set: 759 passed, 5088 deselected, 0 skipped, 0 warnings on the final rebased tree.
- NOT RUN: BOOM or VexRiscv builds/simulations, full Python suite, Sail campaigns, CI.

## Issues

Refs: #8, #11, #87, #93. These broader issues remain open.


## PR 402

[#402](https://github.com/riscPrint/risc-v-workstation/pull/402). Merged: 2026-11-13T01:39:51Z.

Title: feat(formal): add automatic constant and fsm coverage checks

Audit evidence label: unit tests only.

## Summary
Add `rvw formal autocheck` with per-bit constant candidates, declared dead-code targets, FSM state targets and transition targets. Reuse the native formal app flow. Retain raw native results and distinguish reached targets, bounded observations, and conditional unbounded safety results. Add optional bounded output X propagation. Expose autocheck and the existing deadlock/livelock progress apps through MCP.

This is port-manifest based. It does not automatically extract all FSMs or dead branches, prove general liveness, or authorize coverage exclusions. Use `rvw cov prove` for guarded UNR exclusions. The existing X engine remains bounded and separate from four-state simulation.

Rebase resolution: preserve both the new safety-template MCP tool and the new app tools. Keep both documentation additions. Regenerate the command reference.

## Testing
- App/autocheck tests: 29 passed, 0 skipped, including native FSM state/transition and constant checks.
- Expanded autocheck tests: 6 passed, 0 skipped, including native output X propagation. Three overlap with the earlier run.
- Required fast set after rebase: 759 passed, 5079 deselected.
- No full suite, BOOM build or simulation, long formal job or CI wait.

## Issues
Refs: #62

Roadmap notes: Add port-manifest based FSM coverage, dead-code and constant checks, an optional output X-propagation app and MCP exposure for bounded progress contracts. General liveness, full source extraction and commercial parity remain unproven.


## PR 403

[#403](https://github.com/riscPrint/risc-v-workstation/pull/403). Merged: 2026-11-13T02:03:58Z.

Title: feat(uvm): generate versioned extension verification plans

Audit evidence label: unit tests only.

## Summary

Generate versioned custom-extension operand, exception and dependency cases. Generate menvcfg/senvcfg/henvcfg matrices from project legal writes, contexts, transitions and expected enabled/disabled behavior. Require separately attributed reference vectors and non-vacuous mutants. All generated cases remain not_run. Add CLI, MCP, example declaration and contract documentation.

The check command compares supplied observations against independent reference vectors as C3. Missing observations are inconclusive errors. This does not execute ISA programs or earn architectural acceptance.

Roadmap notes: plan generation and reference-vector data comparison implemented. Native custom-extension tests, actual envcfg control execution and mutation campaigns remain open. No roadmap/task files changed.

## Testing

- Targeted generator and command-reference tests: 16 passed, 0 skipped.
- Required fast set after rebase: 759 passed, 0 skipped, 5085 deselected.
- NOT RUN: native custom-extension or environment-control CPU tests, BOOM builds/simulation, full Python suite or C4 gates.

## Issues

Refs: #155, #177. Plan generation only. Both issues remain open for execution and qualification.


## PR 404

[#404](https://github.com/riscPrint/risc-v-workstation/pull/404). Merged: 2026-11-13T01:41:06Z.

Title: feat(memory): use pinned recorded litmus outcomes without herd

Audit evidence label: unit tests only.

## Summary
Use the external suite's recorded herd state sets when herd7 is absent. Pin the full result log and check the suite revision and all six test hashes. Keep native model execution and historical expectations distinct in reports. Reject malformed observations without treating them as a consistent sample.

## Testing
31 targeted Python tests passed, 1 skipped. The skip requires installed native herd7 and its pinned source. Fetched the open litmus suite outside the repository at 08728edcd99c7e1819d2d4c6789df6d5299ccb69. Read all six complete recorded sets and generated the existing RTL fixture plan. The fast Python set ran before push.

NOT RUN: native herd7, RTL, BOOM builds, full Python suite. No new DUT outcome is claimed. Existing native-herd behavior remains enabled when the tool is installed.

## Issues
Refs: #96. Broader litmus imports and production multi-hart DUT execution remain open. This fallback does not provide a Ztso model.

Roadmap notes: RVWMO reference generation now works from verified historical suite expectations when herd7 is unavailable. Reports identify the reference source. Sample consistency is not an exhaustive proof.


## PR 405

[#405](https://github.com/riscPrint/risc-v-workstation/pull/405). Merged: 2026-11-13T02:06:00Z.

Title: feat(formal): bit-blast C and RTL datapaths with cbmc

Audit evidence label: ran on seeded RTL fixture.

## Summary

Add `rvw formal datapath` and `formal_datapath`. Convert a closed mapped RTL netlist to Boolean C and bit-blast it with a C reference in CBMC. Support 8/16/32/64-bit operands, fixed transaction latency and completion checks. Keep C safety and unwinding failures inconclusive.

Add RISC-V M models and Berkeley SoftFloat F/D arithmetic and conversion wrappers. Add operand class splits and a pinned external-tree dependency helper. Keep source trees outside this repository.

## Testing

Targeted native datapath tests: 9 passed, 0 skipped. Covers wide proofs, arithmetic mutants, latency errors, undefined C division, and M division/product edge cases. Required fast set before rebase: 759 passed. Fast set after rebase: 759 passed, 5081 deselected.

Native smoke: CBMC 6.11.0 and Yosys 0.70. F32 square-root zero case proved against pinned SoftFloat. An incorrect F32 add DUT produced a counterexample. Attempting all SoftFloat sources at once produced an inconclusive compiler result. The dependency helper selects only the required sources and its two smoke checks completed.

NOT RUN: BOOM, full Python suite, long formal runs, production FPU proofs, all FP rounding/case combinations, iterative multiplier/divider DUT qualification, streaming or variable-latency proofs. C references remain trusted specifications. This is one transaction, not whole-core correctness.

## Issues

Refs: #19.

Roadmap notes: Add symbolic real-width C/RTL checking with CBMC, fixed-latency transaction checking, ready M and SoftFloat models and CLI/MCP. Keep FV 3 partial pending real iterative and FP unit bindings and native qualification across operations, rounding modes and exception cases.


## PR 406

[#406](https://github.com/riscPrint/risc-v-workstation/pull/406). Merged: 2026-11-13T01:48:19Z.

Title: feat(regress): verify smnpm tagged data pointers

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Add nine Smnpm tagged data-pointer cases across Sv39, Sv48 and Sv57. Check PMM readback, disabled-masking faults, and PMLEN 7/16 loads through MPRV with effective S privilege. Keep the pointer code in its own module. Reuse the MMU build, Spike, C1 and coverage commands.

## Testing

- Targeted pointer module: 3 passed, zero skipped. Nine generated programs passed Spike. A mutation that disables masking failed as required.
- Fast set after rebase: 759 passed, 5073 deselected, zero skipped.
- RTL, BOOM builds, Sail, debug interactions and full Python suite: NOT RUN.

## Issues

Refs: #179.

Keep the issue open. Ssnpm, Smmpm, U-mode, debug, instruction-fetch and guest masking interactions remain open. No DUT coverage is claimed.

Roadmap notes: opt-in Smnpm tagged-pointer scenarios now use the existing MMU regression framework. Native Spike data checks pass. Other pointer-masking extensions and DUT validation remain open. ROADMAP.md and TODO.md were not edited.


## PR 407

[#407](https://github.com/riscPrint/risc-v-workstation/pull/407). Merged: 2026-11-13T01:41:57Z.

Title: feat(lint): classify reset-domain crossings

Audit evidence label: unit tests only.

## Summary

- New `rvw/src/rvw/lint/rdc.py`: derives reset domains (reset source, kind, polarity, soft reset, clocks) from SpinalDB clock-domain data. A register without `init` is in the `none` reset domain.
- Each cross-reset register path gets one class: `async_assert_crossing` (error), `resetless_receiver`, `independent_reset`, `source_not_reset` (no hazard) or `missing_domain` (inconclusive).
- Recognizes async-assert/sync-deassert synchronizer chains (Spinal `ResetCtrl.asyncAssertSyncDeassert`/`BufferCC` shape). New rules: `rdc.async_release_unsynchronized` (replaces `rdc.async_release_unproved`), `rdc.comb_reset_logic`, `rdc.reset_as_data`, `rdc.missing_domain`, `rdc.isolation_unmatched`.
- Project constraints: `intent.isolation` (qualifier + reason) and existing `intent.reset_order` make a path `protected`, never proved. `rdc.status` is `findings`, `protected`, `inconclusive` or `no_crossings_found`; never clean.
- Stale waivers are errors: a waiver that matches nothing in a backend that ran adds `lint.stale_waiver` to `waiver_findings`.
- New shared `rvw/src/rvw/lint/graph.py` design view for the next lint/CDC/SDC modules.
- Shared format: `rvw.lint/1` gains `backends.structural.rdc`, `waiver_findings` and per-waiver `stale` (additive, documented in `docs/PLATFORM_CONTRACTS.md`). No SpinalDB schema change.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_lint*.py -q`: 112 passed, 17 skipped (extracted fixtures and Verible not set in that run).
- `RVW_LINT_FIXTURES=<fresh LintFixtures output> pytest rvw/tests/test_lint_extracted.py`: 15 passed (fixtures extracted with `Test/runMain spinaldb.LintFixtures` under the sbt lock).
- Fast set: 759 passed, 4979 deselected.
- Not run: full Python suite, BOOM or VexRiscv databases, any formal or recovery/removal check.

## Issues

Refs: #118. Remains: release timing, recovery/removal, functional reset reconvergence and reset behaviour between samples stay unproved; reset synchronizer recognition is structural.

Roadmap notes: LINT — RDC now classifies reset-domain crossings (async assertion, reset-less receiver, independent reset), recognizes reset synchronizers, and accepts declared isolation/order with reasons; stale waivers are errors.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 408

[#408](https://github.com/riscPrint/risc-v-workstation/pull/408). Merged: 2026-11-13T01:56:03Z.

Title: feat(cov): solve pinned integer stimulus candidates

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Add `rvw cov generate` and `cov_generate` for the pinned 170-bin integer operand/immediate profile per XLEN. Reuse the pinned ISA manifest and semantic observer bin definitions. Solve instruction encoding and operand constraints with `z3-solver==4.13.4.0`. Emit payload symbols, source, model, SMT constraints and hashes.

Keep unsupported goals, missing backend, bounded UNSAT and solver timeout separate. Preserve the full declared plan denominator. Candidates always have an empty measured-hit set. Each request has a separate Z3 context so repeated requests replay the same source. Project data supplies three writable registers. No core or cosim platform changes.

## Testing

- Post-rebase targeted stimulus, ISA, semantic observer and command reference tests: 22 passed, zero skips.
- Tests solve and independently decode/classify all 170 goals at RV32 and RV64. They check source replay, CLI/MCP parity, invalid resources, pinned source mutation, missing backend and UNSAT evidence.
- Fast set before rebase: 759 passed, 5018 deselected, zero skips. Final post-rebase fast set: 759 passed, 5129 deselected, zero skips. Installer checks: 64 passed.
- NOT RUN: C1/DUT simulations, native Spike candidate checks, paired random campaigns, full Python suite or CI.

## Issues

Refs: #349

Keep #349 open. This implements candidate generation only. The closed execution loop, ELF-bound payload qualification, controller/descendant CPU accounting, sealed campaign publication, safe resume, held-out arithmetic mutants and five paired native seeds on both cores remain. No measured closure rate or PSS conformance is claimed.

Roadmap notes: A pinned Z3 backend now emits source candidates for the 170-bin integer profile at each XLEN through CLI/MCP. Unit tests check all 340 candidates against decoder and semantic classifications. No candidate has earned a measured coverage hit. Sequence actions (#352) and RTL-goal feedback (#353) are not implemented by this change.


## PR 409

[#409](https://github.com/riscPrint/risc-v-workstation/pull/409). Merged: 2026-11-13T02:52:50Z.

Title: feat(formal): generate sampled power and test intent checks

Audit evidence label: unit tests only.

## Summary

Generate sampled clock-gating, isolation, retention, test-mode isolation and supply-transition monitors from explicit project-owned low-power intent. Add CLI/MCP access and an example. Optionally resolve declared DFT access paths from SpinalDB. Preserve unconstrained off-state storage and report the limits of sampled observations.

## Testing

- Power tests: 16 passed, 0 skipped. Native Icarus passes reference traces and detects seeded power/test and supply-sequence faults.
- Combined CSR, existing SoC bridge, safety, power and command-reference tests before the two extra supply tests: 56 passed, 0 skipped.
- Required fast set after rebase: 759 passed, 5142 deselected, 0 skipped.
- NOT RUN: SBY proofs, Spinal compile, real-core power campaigns, analog analysis, ATPG, full Python suite.

## Issues

Refs: #146, #157, #163, #198, #200, #162

Roadmap notes: Add project-owned sampled low-power intent and generated safety monitors. UPF import, outstanding-work pause/resume, physical power behavior, exhaustive DFT discovery and real-core bindings remain open. No issue is closed.


Rebase validation: power tests 16 passed. Fast set: 832 passed, 1 failed, 6667 deselected. The only failure is test_release_hygiene.py::test_tracked_text_has_no_personal_paths, which reports the untouched rvw/tests/cosim/test_adjudicate.py:51. Per the brief, this does not block merging.


## PR 410

[#410](https://github.com/riscPrint/risc-v-workstation/pull/410). Merged: 2026-11-13T01:55:59Z.

Title: feat(formal): generate common sva intents from typed channels

Audit evidence label: unit tests only.

## Summary
Add a common SVA intent library and generation from exported Spinal Stream/Flow channel types. Include handshake hold/stability, FIFO count rules, one-hot, finite arbiter response, request-response bounds and an explicit Flow payload range. Require reviewed clock and local port bindings. Add sampled multi-clock and between-edge asynchronous cancellation references. Preserve timeout/unknown regression outcomes when preparation leaves no model.

Depends on PR #395. This branch includes that PR's commits because it has not merged. Merge #395 first, then rebase this PR. The requested base remains main.

## Testing
- Library native and unit set: 20 passed, no skips.
- Native multi-clock/reset event references: 4 passed, no skips.
- Native vector Boolean/sequence-alternative references: 6 passed, no skips. These include expected ABC errors for optimized combinational legal fixtures.
- Final targeted non-native unit/reference set: 26 passed, 50 deselected, no skips.
- Final fast set: 759 passed, 5156 deselected, no skips.
- NOT RUN: full Python suite, BOOM builds/simulation, Scala builds, long formal runs, general async-event scheduling, GitHub CI wait.

## Issues
Refs: #294, #46, #61

#294: SVA-facing intent generation is implemented. It uses existing exported types. It does not change Spinal elaboration, infer missing domains/widths, support composite payloads, prove FIFO data order, match transaction IDs, or establish general fair liveness.

#46 remains partial. Independent clocked SVA statements and sampled reset cancellation have native references. Multi-clock from-sim/X flows, mixed-domain elaboration metadata, raw asynchronous property triggers and additional asynchronous state types remain open.

Roadmap notes: add common finite SVA intents and exported Stream/Flow generation to FV9. Record native dual-clock and between-edge reset cancellation references. Keep #46 partial and retain existing event-model limits. Do not claim commercial parity or whole-core proof.


## PR 411

[#411](https://github.com/riscPrint/risc-v-workstation/pull/411). Merged: 2026-11-13T01:44:55Z.

Title: feat(memory): add configured cache-block byte campaigns

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add an opt-in cache-block campaign with mandatory project block size. Check CBO.ZERO at three offsets, every zeroed byte, two complete adjacent blocks, and retained data across clean/flush/invalidate. Execute prefetch hints without requiring a cache effect. Record the ISA and block size in the reference report.

## Testing
Targeted ordering tests and native Spike smoke runs cover RV32/RV64 and 32/64-byte CMO sizes. Fault injections cover missing zeroing, partial zeroing and adjacent-byte corruption. The fast Python set ran before push.

NOT RUN: RTL, BOOM builds, bus/device clean/flush observers, privilege-control matrices, full Python suite. Spike byte checks do not prove cache writeback or coherence behavior.

## Issues
Refs: #137. Target cache/device effects, privilege controls and concurrent campaigns remain open.

Roadmap notes: cache-block extensions now have configured machine-mode byte and hint campaigns. Native results remain separate from bus-level cache maintenance evidence.


## PR 412

[#412](https://github.com/riscPrint/risc-v-workstation/pull/412). Merged: 2026-11-13T01:45:27Z.

Title: feat(wave): add indexed expression search, edges and native fst index

Audit evidence label: unit tests only.

## Summary

- `rvw wave find WAVE EXPR`: first time, last interval and all intervals where an expression over several signals holds (`&& || !`, comparisons, arithmetic, bit selects, `rose/fell/changed/stable/known`). x/z use three-valued logic; an unknown result never counts as true and is counted in `unknown_steps`.
- `rvw wave edges WAVE REGEX`: value changes, rising/falling edges (1-bit) and x/z transitions per signal in a window.
- Both read only the referenced signals' rows from a `.rvwi` index (merged per-signal `signal_time` cursors); on VCD/FST they stream one pass.
- `rvw wave index --reader wellen`: reads FST natively through pywellen (wellen, Surfer's reader), one signal at a time, with no `fst2vcd` conversion. `auto` (default) selects it for FST when the new `waves` extra is installed.
- `--indexed` on every wave query (MCP `indexed`): a cached index per absolute wave path under `RVW_WAVE_INDEX_DIR`, rebuilt when the wave's recorded size/mtime differs. `rvw wave verify INDEX` compares full SHA-256 (exit 1 when stale). The build fails if the source changes while it is indexed.
- MCP: `wave_find`, `wave_edges`, `wave_index`, `wave_index_verify`.
- Fix: MCP wave tools on `.rvwi` input failed (`module 'rvw.wave.ops' has no attribute '_sample'`). The new MCP test fails without the `capture.py` fix.
- PLATFORM_CONTRACTS: optional `source_stat`/`reader` metadata, wellen row order, cache layout.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_wave_search.py rvw/tests/test_wave.py rvw/tests/test_wave_index.py rvw/tests/test_mcp_tools.py rvw/tests/test_mcp_debug.py rvw/tests/test_command_reference.py -q`: all passed, 0 skipped (pywellen 0.25.7 and oss-cad-suite vcd2fst/fst2vcd installed). Without them the wellen/FST tests skip.
- Fast set: `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`: 759 passed.
- Native smoke (macOS arm64, `nice -n 10`): synthetic 500-signal wave, 2.4 M records, 65 MB VCD / 9 MB FST. Index build: wellen 51 s / 145 MB RSS; fst2vcd path 50 s / 145 MB. `find 'sig3 == sig4 || sig7[3:0] == 5'` on the index: 1.6 s, 48 MB RSS; streamed VCD: 13.8 s; same 175 intervals.
- Not run: multi-GB FST, full Python suite, Linux.

## Issues

Refs: #173. Direct native FST reading now works for index builds. Remaining: wellen still loads one signal fully into memory (a single huge signal is not bounded), and SQLite insertion dominates build time.

Roadmap notes: waves/debug area — `rvw wave find/edges` add expression search and edge counts on indexed waves; FST indexes read natively through wellen (pywellen, optional `waves` extra); cached `--indexed` mode rebuilds stale indexes.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 413

[#413](https://github.com/riscPrint/risc-v-workstation/pull/413). Merged: 2026-11-13T01:46:01Z.

Title: feat(vip): add pipelined ahb-lite protocol agents

Audit evidence label: unit tests only.

## Summary

Add AHB-Lite agents for one manager on a single-layer 32-bit bus. Support byte, halfword and word accesses and all eight burst encodings. Add UVM manager and reactive subordinate roles, a passive pipeline monitor, assertions, directed/random/fault sequences, functional coverage and an independent byte-memory scoreboard hook. Add matching Python cycle agents and cocotb pin adapters. Add a seeded pipelined RTL RAM with waits, two-cycle errors and good/corrupt variants.

## Testing

- Targeted Python: `rvw/.venv/bin/python -m pytest rvw/tests/test_vip_ahb.py -q`: 13 passed, no skips.
- Native cocotb 2.0.1 on Verilator 5.052: three good seeds and three `AHB_DATA` corruption failures. The campaign covers all burst encodings, all supported sizes, random bursts, wait states, access errors and reset interruption between address and data phases.
- Final UVM sources passed Verilator lint with the pinned Accellera UVM 2020.3.1 package, assertions and coverage.
- Required fast set run before push and repeated after rebase.
- UVM executable simulation NOT RUN. The prior APB build of the full pinned UVM library exceeded the brief's two-minute smoke limit. Reactive subordinate roles NOT RUN against native RTL. No BOOM build, full Python suite or CI wait.

## Issues

Refs: #199

Remaining: native UVM and reactive subordinate qualification, BUSY insertion campaigns, locked traffic and project integration. This is AHB-Lite. Arbitration, SPLIT, RETRY and AHB5 are outside its declared profile.

Roadmap notes: AHB-Lite now has UVM and Python/cocotb protocol agents with address/data pipeline tracking, all burst encodings, subword lanes, seeded waits and two-cycle errors. Good-versus-corrupt RTL evidence exists for the cocotb manager and monitor. Native UVM and reactive subordinate qualification remain open. ROADMAP.md and TODO.md are unchanged as directed.


## PR 414

[#414](https://github.com/riscPrint/risc-v-workstation/pull/414). Merged: 2026-11-13T02:07:03Z.

Title: feat(uvm): add python base environments and ral adapters

Audit evidence label: unit tests only.

## Summary

Add optional pyuvm 4/cocotb 2 base environments and a native four-word RTL memory fixture. Add an ordered scoreboard, byte-enabled CPU memory model, strict retirement callback wrapper, and rvw.soc RAL model with explicit asynchronous frontdoor/backdoor adapters. Record the qualification boundary and usage.

Roadmap notes: bounded Python base environment path implemented and exercised against RTL. The CPU environment still needs project instruction/memory agents, interrupt/debug agents and an independent retirement comparator. No automatic live Spike connection or full SV/pyuvm CPU parity is claimed. No roadmap/task files changed.

## Testing

- Native Verilator 5.052, pyuvm 4.0.1, cocotb 2.1.0 fixture: 1 passed, 0 skipped. It checks four writes, four reads and all eight declared bins. Its C3 is accepted by the shared reader.
- Model tests: 9 passed, 0 skipped. Includes mismatch, missing/unexpected data, zero checks, byte enables, bounds, retirement order, RAL checked mirror failure, RC, W1C and unknown reset.
- Required fast set after rebase: 759 passed, 0 skipped, 5135 deselected.
- NOT RUN: full Python suite, BOOM builds/simulation, full CPU ISA/interrupt/debug or live Spike parity, C4 gate.

## Issues

Refs: #296. Full CPU UVM and full semantic parity remain open. This PR is independent of the project SV flow PR #394 and the plan generator PR #403.


## PR 415

[#415](https://github.com/riscPrint/risc-v-workstation/pull/415). Merged: 2026-11-13T02:01:45Z.

Title: feat(arch): add bbv sampling and saved warmup analysis

Audit evidence label: unit tests only.

## Summary
Select actual representative C2 intervals with deterministic instruction-weighted BBV clustering. Retain all interval counts, cluster members, partial final intervals, weights and planned warmup bounds. Add a CPI aggregation helper that uses represented instruction fractions.

Compare saved warmup observations at one fixed ROI. Require conclusive C1, complete C2, matching captured ELF bytes, equal architectural suffixes, paired seeds and fixed memory settings. Report raw cycles, CPI/IPC, signed bias, absolute bias and observed error targets.

Both features have CLI and cancellable MCP tools. They do not launch simulations, restore checkpoints or qualify cache/predictor state. No issue is closed.

Roadmap notes: BBV phase selection and saved fixed-ROI warmup comparison are implemented. Full native sampling validation, RTL warmup measurements and checkpoint/cache/predictor qualification remain open.

## Testing
16 focused sampling, warmup and command-reference tests passed. Final rebased fast set: 759 passed, 5142 deselected in 156.91 seconds.

NOT RUN: gem5, RTL, checkpoint restore, cached-core warmup, learned-predictor warmup, full Python suite or CI waits. Warmup tests use synthetic saved observations.

## Issues
Refs: #183, #348


## PR 416

[#416](https://github.com/riscPrint/risc-v-workstation/pull/416). Merged: 2026-11-13T03:47:55Z.

Title: feat(formal): prove declared taint and access isolation policies

Audit evidence label: ran on seeded RTL fixture.

## Summary

Add `rvw formal security prove` and `formal_security_prove`. Map exported RTL, apply conservative Boolean IFT, bind source/sink/declassifier policies and prove the generated assertions with ABC PDR. Constant-time policies check declared timing outputs on every cycle. Reject control aliases that can disable checks.

Add static observed access isolation against an independent priority region policy. Check master, privilege, read/write/execute, full access containment and address wrap. Preserve project threat-model and unmodeled-channel declarations in the report.

## Testing

Native new policy tests: 10 passed, 0 skipped. Cover clean/leaking paths, registered release residue, permitted combinational release, timing-output leakage, static isolation and a grant mutant. Existing plus initial policy tests: 40 passed, 1 skipped. Required fast set before rebase: 759 passed, 5106 deselected. Post-rebase fast set: 759 passed, 5134 deselected.

NOT RUN: BOOM, full Python suite, long formal runs, production security campaigns. Static isolation consumes a resolved policy. It does not derive PMP/ePMP semantics from CSRs or prove policy updates with outstanding traffic. Full Zkt, dynamic PMP/ePMP, blackboxes, physical channels and whole-core isolation remain open.

## Issues

Refs: #20.

Roadmap notes: Add source/sink policy proofs over exported RTL, explicit declassification windows, declared timing-sink checks and independent static access isolation. Keep FV 4 partial for operation/core binding, dynamic PMP/ePMP policy semantics and broader observation channels.

Recovery validation: OSS CAD Suite first on PATH: test_secure_path.py 10 passed, no skips. Mixed Homebrew and OSS CAD Suite initially gave 4 solver errors and 6 passes. Fast set: 759 passed. No BOOM jobs or full suite ran.


## PR 417

[#417](https://github.com/riscPrint/risc-v-workstation/pull/417). Merged: 2026-11-13T03:03:01Z.

Title: feat(formal): recheck captured models with pinned signals

Audit evidence label: ran on seeded RTL fixture.

## Summary
Add `rvw formal recheck` and `formal_recheck` MCP for bounded solver what-if checks on captured BMC models. Pin exact top-module net names with additional all-sample equality assumptions. Keep the original drivers, assertions and assumptions. Require a separate full-depth feasibility cover before a bounded verdict. Retain the model, both SBY jobs, logs and input capture.

This does not establish an unbounded proof, a source repair, or a coverage exclusion. An inconsistent pin is inconclusive. Use the exact captured net name; this command does not infer source-level names.

## Testing
- Targeted tests: 4 passed, 0 skipped. Native Yosys/SBY/Z3 checks cover a removed failure, a retained failure and an assumption conflict.
- Required fast set after rebase: 759 passed, 5144 deselected.
- No full suite, BOOM build or simulation, long formal job, native GUI navigation or CI wait.

## Issues
Refs: #60

Roadmap notes: Captured-model bounded what-if solver rechecks now support input and internal net pins with a full-depth feasibility guard. Typed viewer validation, assumption reduction and general trace minimization remain open.


## PR 418

[#418](https://github.com/riscPrint/risc-v-workstation/pull/418). Merged: 2026-11-13T02:39:26Z.

Title: feat(formal): generate project RVFI wrappers and channel checks

Audit evidence label: ran on real core RTL.

## Summary

Generate an RVFI wrapper and project configuration from project-owned JSON port data. Add CLI and MCP generation and MCP access to the existing riscv-formal runner. Support NRET 1..16 with channel bounds and a retirement cover on every channel. Ship the upstream VexRiscv example binding. Update the original settings tables to the same NRET limit.

Generated auxiliary inputs are unconstrained. Review the bus environment before a real-core proof. The runner emits bounded C3 observations and an inconclusive C4 verdict unless a check fails. This does not establish real-core adapter conformance.

Roadmap notes: generic RVFI wrapper generation and multiple retirement channels are available. A two-channel native independent ADD fixture detects a channel-1 result mutation and refuses an inactive retirement channel. Real-core order/trap/killed-instruction/memory/multiple-effect conformance remains open.

## Testing

- Generator, runner and project tests with native Yosys/SBY/Yices: 90 passed, 12 deselected, 0 skipped. Includes correct/wrong two-channel and inactive-channel cases.
- Existing BTORMC native mutation cases under the documented oss-cad-suite environment: 3 passed, 62 deselected, 0 skipped. The Homebrew yosys-witness launcher lacked click; the matching suite launcher succeeds.
- Final post-rebase generator/runner/project/reference tests excluding native cases: 90 passed, 15 deselected, 0 skipped.
- Final post-rebase fast set: 805 passed, 5962 deselected, 0 skipped.
- Generated VexRiscv binding smoke on the existing upstream RTL, under the vex lock at nice 10: retirement cover passed; ADD and ADDI each timed out at the 10-second per-check limit. Overall inconclusive. No core build ran. Local C3 evidence: /tmp/conn-vex-portproof/results.json.
- NOT RUN: BOOM builds or formal campaigns, full real-core campaigns and adapter conformance, full Python suite, long formal campaigns, GCC/backend builds, GitHub CI waits.

## Issues

Refs: #63. Full real-core adapter conformance remains open.


## PR 419

[#419](https://github.com/riscPrint/risc-v-workstation/pull/419). Merged: 2026-11-13T01:49:29Z.

Title: test(sim): check native persistent state isolation

Audit evidence label: unit tests only.

## Summary

Check one compiled native model across three injected simulation failures and repeated passing runs. Verify fresh DUT, seeded PRNG, tohost device and progress-monitor state. Use a tiny accumulator. No BOOM run is required.

Roadmap notes: #14 gains bounded native reset coverage. Core-specific device inventories, coverage reset, native process cancellation and long-lived resource measurements remain open.

## Testing

- Native Scala: 10 passed, 0 skipped with `testOnly riscvsim.PersistentNativeSpec riscvsim.ServerSpec` under the sbt lock and nice. Native test execution took 14.277 seconds. sbt reported 30 seconds after lock acquisition.
- Fast Python: 759 passed, 0 skipped, 5174 deselected after rebase. Command: `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`.
- NOT RUN: BOOM, full Python suite, long resource measurements, GitHub CI.

## Issues

Refs: #14. This does not close the issue.


## PR 420

[#420](https://github.com/riscPrint/risc-v-workstation/pull/420). Merged: 2026-11-13T01:49:38Z.

Title: feat(memory): select a pinned Ztso litmus model

Audit evidence label: unit tests only.

## Summary
Add explicit RVWMO/Ztso model selection. Pin separate complete outcome hashes for `riscv-tso.cat` in the existing herdtools7 7.58 library. Require a project declaration before checking a Ztso DUT adapter. Keep unsupported DUTs unverified and refuse the RVWMO recorded fallback for Ztso.

## Testing
Native herd7 7.58 ran all six pinned tests with both models. Ztso retains all-zero SB, rejects the MP message-passing violation and rejects all-one LB. Targeted tests also check declaration requirements and missing-tool behavior. The fast Python set ran before push.

NOT RUN: Ztso RTL or production multi-hart adapter, BOOM builds, full Python suite. These are model results and checker tests, not DUT qualification.

## Issues
Refs: #184, #96. Native model support and recorded RVWMO expectations remain distinct. Ztso DUT execution and device-boundary campaigns remain open.

Roadmap notes: the pinned native memory-model runner and fixture planner support Ztso with separate outcome identities. No project implementation support is inferred.


## PR 421

[#421](https://github.com/riscPrint/risc-v-workstation/pull/421). Merged: 2026-11-13T01:52:48Z.

Title: feat(cosim): apply pmp grain and m-only vex settings

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Apply declared PMP grain in Spike and report it in comparison policy results. Add native grain readback and overlapping-entry priority tests. PMP priority remains the ISA rule: the lowest matching entry wins.

Make the VexRiscv example M-only in both the adapter and platform. Disable S/U generation, remove S/U misa bits, and read only machine trap CSRs. Keep explicit no-PMP, absent-PMP CSR and ECALL mtval choices.

Roadmap notes: PMP grain and priority reference checks are added. Split effects and cross-boundary translation campaigns remain open. The example configuration is changed; no native VexRiscv match is claimed.

## Testing

- Targeted native policy, PMP and build-capture tests: 75 passed, 0 skipped.
- Fast set after rebase: 759 passed, 5186 deselected, 0 skipped.
- Native Spike shim build passed.
- NOT RUN: VexRiscv/BOOM builds or simulations, full Python suite, Sail campaigns, CI.

## Issues

Refs: #8, #11. Split and partial effects remain open.


## PR 422

[#422](https://github.com/riscPrint/risc-v-workstation/pull/422). Merged: 2026-11-13T01:50:26Z.

Title: fix(formal): account for read-clear in CSR assembly

Audit evidence label: ran on seeded RTL fixture.

## Summary

Account for read-clear side effects from the initial CSR read and each readback in generated self-checking assembly. Otherwise preserved read-clear fields can give false failures in later accesses.

## Testing

- CSR tests: 15 passed, 0 skipped. Includes native Icarus monitor mutations and a RISC-V GCC assembly/link smoke test.
- Fast set: 759 passed, 5176 deselected, 0 skipped.
- NOT RUN: C1 execution, Spike comparison, SBY proof, Spinal compile, BOOM simulation, full Python suite.

## Issues

Refs: #85

Roadmap notes: Correct read-clear sequencing in generated assembly. The wider CSR compliance and binding gaps remain open.


## PR 423

[#423](https://github.com/riscPrint/risc-v-workstation/pull/423). Merged: 2026-11-13T01:52:13Z.

Title: feat(vip): add axi-stream packet agents and fifo checks

Audit evidence label: unit tests only.

## Summary

Add AXI4-Stream source and sink agents in UVM and Python/cocotb. Declare a 32-bit profile with TKEEP, TSTRB, TLAST, two-bit TID/TDEST and one TUSER bit per byte. Add stalled-signal and byte-qualifier assertions, directed/random/error sequences, functional coverage, packet monitors and an independent per-stream token scoreboard. Add a one-entry elastic RTL FIFO with a corrupt variant.

The scoreboard compares data bytes, position bytes, user bits and packet boundaries. It permits null-byte removal and cross-stream packet reordering. Missing TLAST, missing output and empty tests cannot pass.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_vip_axis.py -q`: 9 passed, no skips.
- Combined APB/AHB/AXI-Stream Python tests after rebase: 34 passed, no skips.
- Native Verilator 5.052 and cocotb 2.0.1: three good runs each completed 66 packets. Three corrupt runs each failed with `AXIS_PACKET_DATA_ORDER`. Directed and random traffic covers all keep masks, null and position bytes, byte user bits, stalls, packet termination and interleaved stream identities.
- Final UVM sources passed Verilator lint against the pinned Accellera UVM package with assertions and coverage.
- Required fast set after rebase: 759 passed, 5186 deselected, no skips, in 102.84 seconds.
- UVM executable simulation NOT RUN. The prior full pinned UVM build exceeded the two-minute smoke limit. Four-state qualification NOT RUN. No BOOM build, full Python suite or CI wait.

## Issues

Refs: #192

Remaining: native UVM runtime qualification and project integration. Other TUSER layouts need an adapter. AXI5-Stream is outside this profile.

Roadmap notes: AXI4-Stream simulation VIP now has UVM and Python/cocotb source/sink agents, byte and packet monitors, functional coverage and a stream-aware independent scoreboard. Three seeded good-versus-corrupt RTL campaigns qualify the cocotb source, sink and monitors on the declared profile. Native UVM runtime remains open. ROADMAP.md and TODO.md are unchanged as directed.


## PR 424

[#424](https://github.com/riscPrint/risc-v-workstation/pull/424). Merged: 2026-11-13T01:56:34Z.

Title: feat(regress): check ordered and faulting page walks

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Add 56 invalid-PTE and PMP-denied PTE-read programs across every Sv32/39/48/57 level. Reuse the generic MMU build, Spike reference and C1 suite path. Add optional ordered C2 walk records, format validation and an independent Python walker. Compare PTE levels, addresses, values and translation/fault results. Fenced leaf changes use separate reference snapshots. Bind report checks to C1 identity and require a passing C2 end. Missing records remain inconclusive. Keep walk results separate from architectural bins.

## Testing

- Targeted MMU Python checks: 152 passed, 9 deselected, zero skipped.
- New walker module with short Spike run: 62 passed, zero skipped. All 56 generated fault programs passed Spike.
- Fast set after rebase: see final count below.
- RTL, BOOM, Sail, full Python suite: NOT RUN.

## Issues

Refs: #84, #147, #171, #154.

DUT validation, hardware A/D walk writes, extension PTEs, root-switch walk records and translation-cache protocol closure remain open. Project adapters must implement the declared C2 capture contract. No DUT result is claimed.

Roadmap notes: per-level fault programs and ordered independent C2 walk checking now cover fixed mappings and fenced leaf changes. DUT capture and full protocol closure remain open. ROADMAP.md and TODO.md were not edited.
759 passed, 5242 deselected in 106.70s (0:01:46)


## PR 425

[#425](https://github.com/riscPrint/risc-v-workstation/pull/425). Merged: 2026-11-13T01:53:13Z.

Title: feat(sim): add identity-bound native snapshot envelopes

Audit evidence label: unit tests only.

## Summary

Add a native snapshot envelope and an adapter port API. Bind native bytes and eleven explicit harness state components to RTL, native build, harness and stimulus identities. Refuse corrupt or truncated files, stale identities, missing state, external effects and running instances before restore. Keep from-reset replay separate.

Add a bounded direct Verilator smoke test. It saves a tiny accumulator plus clock time, PRNG, memory and monitor counters at cycle 8. A fresh native process restores the file. Its remaining 12 samples equal the uninterrupted suffix. This is a native circuit result, not a RISC-V or C2 qualification result.

Roadmap notes: #132 and #346 gain a versioned envelope and bounded direct native evidence. No bundled Spinal adapter implements the port. The SpinalHDL 1.15.0 `IVerilatorNative` interface has no save/restore methods. Its scheduler uses live JVM continuation threads. Bridge and scheduler integration, VexRiscv restore, full device state, C2 qualification and save/restore cost measurements remain open. This PR does not close either issue.

## Testing

- Targeted: 13 passed, 0 skipped in 21.95 seconds. Command: `rvw/.venv/bin/python -m pytest rvw/tests/test_native_checkpoint.py rvw/tests/test_native_checkpoint_verilator.py -q`.
- Native build uses `nice -n 10` and a 120-second process-group budget. Native execution uses fresh processes.
- Fast Python: 759 passed, 0 skipped, 5194 deselected after rebase. Command: `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`.
- NOT RUN: Spinal live restore, VexRiscv live restore, BOOM, full Python suite, long performance runs or GitHub CI.

## Issues

Refs: #132, #346.


## PR 426

[#426](https://github.com/riscPrint/risc-v-workstation/pull/426). Merged: 2026-11-13T01:55:52Z.

Title: fix(memory): allow legal zero Zacas trap values

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Accept legal zero mtval observations in configured Zacas access-fault and alignment profiles. A nonzero value must still equal the fault address. Preserve all cause, PC, trap-count, register and memory checks.

## Testing
Native Spike tests inject permitted zero and incorrect nonzero values into the checker observation while still taking the real faults. Both profiles accept zero and reject incorrect nonzero addresses. The full targeted Zacas module and the fast Python set ran before push.

NOT RUN: RTL, BOOM builds, a target with naturally zero mtval, full Python suite. The injected observation is checker evidence, not a claim about Spike's native mtval value.

## Issues
Refs: #170. Concurrent CAS and target-specific exception campaigns remain open.

Roadmap notes: Zacas fault campaigns now permit legal platform trap-value behavior while preserving mandatory state checks.


## PR 427

[#427](https://github.com/riscPrint/risc-v-workstation/pull/427). Merged: 2026-11-13T01:56:31Z.

Title: feat(cosim): capture per-slot csr state in generic rvfi

Audit evidence label: unit tests only.

## Summary

Add per-slot CSR signal maps to the generic RVFI probe. Preserve each slot snapshot in its retirement record. The writer selects C2/2 and requires the exact declared CSR set. Add a CSR-only capability so CSR observations do not claim missing FP state. Correct the checker FP coverage report to use that capability.

Roadmap notes: Generic per-slot capture is available for adapters. Adapters must expose independent post-slot signals; BOOM capture is not enabled. Sail full-state CSR snapshots remain unavailable. Its current CSR write log does not establish full snapshots. This PR does not close #87.

## Testing

- Python CSR capability/state/unread CSR checks: 31 passed, 0 skipped.
- Locked Scala Test/compile passed.
- Locked focused Scala tests: 3 passed, 0 skipped.
- Fast set after rebase: 759 passed, 5303 deselected, 0 skipped.
- NOT RUN: BOOM/VexRiscv simulations, native multi-retire DUT capture, full Python suite, Sail CSR snapshots, CI.

## Issues

Refs: #87. Sail snapshots and core adapter wiring remain open.


## PR 428

[#428](https://github.com/riscPrint/risc-v-workstation/pull/428). Merged: 2026-11-13T01:56:29Z.

Title: feat(privilege): test disabled state across privilege controls

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Generate 36 FS-Off tests across SUM, MXR, MPRV, TVM, TW and TSR in M/S/U. Generate 72 absent-supervisor tests on M/U configurations. Check illegal-instruction cause and exact PC. Forward the project privilege configuration to Spike.

## Testing

- Targeted tests: 23 passed, 0 skipped.
- Short native Spike self-checks: 108 passed, 0 skipped, with nice and one-second per-program timeouts.
- Fast set after rebase: 759 passed, 5229 deselected, 0 skipped.
- NOT RUN: RTL builds or simulations, full Python suite, long formal or CI.

## Issues

Refs: #139

Other disabled-extension combinations and full DUT qualification remain open. No reference self-check earns DUT coverage.

Roadmap notes: Add FS-Off and absent-supervisor combinations to privilege campaign generation. Retain untested extensions and DUT qualification as open work.


## PR 429

[#429](https://github.com/riscPrint/risc-v-workstation/pull/429). Merged: 2026-11-13T01:57:55Z.

Title: feat(wave): add driver trace, sequences, transactions and wave diff

Audit evidence label: unit tests only.

## Summary

Verdi-style debug capability as CLI and MCP, all generic (no core names):

- `rvw wave why WAVE SIGNAL --at T --db DESIGN.db` (`wave_why`): active-driver tracing. Joins wave values with SpinalDB assignments and their `when`/`switch` chains. Decides the active assignment from condition-signal values (last full-width winner; undecided later candidates give `ambiguous`). Registers are explained at their last value change (`set_at`), with drivers evaluated just before that edge; asserted resets give `status: reset`. Walks back through `data` reads (`--depth`, `--max-nodes`). Output says `binding: unverified` (names joined by wave path).
- `rvw wave seq WAVE 'a ##1 b ##[1:3] c'` (`wave_seq`): clocked sequences with SVA-like delays (`##[n:$]` open), sampled pre-edge; matches, failures (failed step) and pending starts.
- `rvw wave txn` (`wave_txn`): Stream/Flow transfers with payload, wait cycles, stalls, throughput, `payload_changed` and `valid_dropped` issues. `--stream PATH --db DB` types valid/ready/payload from a database bundle.
- `rvw wave diff A B` (`wave_diff`): first divergence between two runs (name pairing, `--map` prefix rename, `--offset`, event or `--on-clock` sampling, `--all`). Status `match`/`diverged`/`no_points`; CLI exit 1 unless `match`.
- Close partly read index merges before the connection closes (removes unraisable sqlite warnings).

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_wave_why.py rvw/tests/test_wave_temporal.py rvw/tests/test_wave_search.py rvw/tests/test_wave.py rvw/tests/test_wave_index.py rvw/tests/test_mcp_tools.py -q`: 194 passed, 0 skipped. `why` uses the committed GCD database with a hand-written GCD wave; `txn --stream` uses the committed cluster database.
- Fast set: 759 passed.
- Not run: real BOOM/Vex waves with their databases, full Python suite.

## Issues

Refs: #297, #24. Adds active-driver tracing, temporal queries, transaction extraction and wave diff with first divergence. Remaining: what-if editing, alignment by retirement/transactions (diff aligns by time only), partial-range bit composition in `why`, real-core parity runs, GUI panels (next PR).

Roadmap notes: debug area — `rvw wave why/seq/txn/diff` (+ MCP) provide driver tracing joined with SpinalDB, SVA-like sequence search, Stream/Flow transaction extraction and first-divergence wave diff.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 430

[#430](https://github.com/riscPrint/risc-v-workstation/pull/430). Merged: 2026-11-13T02:42:23Z.

Title: feat(formal): generate Sail Zicond instruction checks

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Compile pinned Sail RV32 CZERO.EQZ and CZERO.NEZ result rules with Sail 0.20.1. Derive the condition, result selection and encoding from the pinned rule file. Record compiler/library/source/generated hashes and exact source lines. Generate a separate R-type RVFI shell. Add CLI and MCP generation.

Allow explicitly requested new instruction models in a private riscv-formal ISA list. The upstream checkout remains unchanged. These added checks do not redefine the base ISA.

Roadmap notes: the Sail result slice now covers enabled RV32 Zicond instructions that the current upstream checkout lacks. Disabled-extension traps, CSR MISA, RV64, full-machine state and the general full-Sail-model flow remain open. The RVFI shell is explicit and separate from Sail backend output. The issue remains open.

## Testing

- Native Sail 0.20.1 generation from sail-riscv commit 549e723031b34b5ffea5bbb56367be15c7a38a9e succeeded for both instructions.
- Independent native oracle/source checks: 11 passed, 0 skipped. Result, decode and PC mutants fail as required.
- New-model campaign checks: 3 passed, 10 deselected, 0 skipped. Correct and deliberately faulty RVFI fixtures ran through upstream riscv-formal and SBY.
- Existing runner/Sail/project regression checks: 83 passed, 4 skipped, 19 deselected. Skips need the separate existing arithmetic-slice artifacts/environment.
- Fast set before rebase: 759 passed, 5192 deselected. Post-rebase: 759 passed, 5269 deselected, 0 skipped.
- NOT RUN: BOOM builds, full Python suite, real-core campaigns, long formal runs, full Sail-machine compilation, GitHub CI waits.

## Issues

Refs: #64. Full-machine and additional extension coverage remain open.


## PR 431

[#431](https://github.com/riscPrint/risc-v-workstation/pull/431). Merged: 2026-11-13T02:09:10Z.

Title: feat(cov): execute bounded integer closure attempts

Audit evidence label: unit tests only.

## Summary

Add `rvw cov campaign` and `cov_campaign`. Select remaining integer goals, solve, compile, check ELF payload bytes, run C1, compare full C2 with strict Spike, and measure only payload coverage. Preserve failed attempts and incidental hits. Save immutable state generations and validate inputs and artifacts on resume. Record wall, controller CPU and reaped-child CPU for every attempt.

## Testing

Targeted campaign, payload, functional and command reference tests: 28 passed, zero skips. Fast set: 759 passed, 5461 deselected, zero skips.

NOT RUN: native compiler/DUT/Spike campaigns, BOOM builds, full Python suite, CI, paired random seeds or macOS descendant accounting qualification. No closure rate is claimed. Fixture tests reject matching prefixes, mismatches, synchronization, wrong ELF bytes and changed resume evidence.

## Issues

Refs: #349

Keep #349 open. Full transitive C8 dependency closure, sealed raw attempt publication, validated descendant CPU accounting, baseline comparison, cold-build allocation and paired native campaigns remain. Status stays inconclusive unless a checked defect fails the campaign.

Roadmap notes: The bounded integer closure loop now has CLI/MCP entry points, ELF-bound payload sampling, measured feedback and checked resume. Native closure and CPU-hour metrics remain unqualified.


## PR 432

[#432](https://github.com/riscPrint/risc-v-workstation/pull/432). Merged: 2026-11-13T02:01:08Z.

Title: feat(formal): extend finite sequence and sampled value lowering

Audit evidence label: unit tests only.

## Summary
Extend the finite temporal frontend with throughout, within, intersect and first_match. Lower single-argument sampled-value functions with full-vector history and bit-zero edge checks. Generate a support table from the semantic corpus. Keep explicit unsupported diagnostics for the remaining language.

## Testing
- OSS CAD Suite: temporal and composition tests, 65 passed. Final composition corpus, 22 passed. These sets overlap.
- Fast set: see the retained local test result before push.
- NOT RUN: full Python suite, BOOM builds or simulation, long formal jobs, full simulator scheduling qualification, GitHub CI wait.

## Issues
Refs: #61

Unbounded sequences and repetition, liveness, local variables, checkers, bind files and cross-clock sequences remain open. No full SVA conformance or design acceptance is claimed.

Roadmap notes: add finite sequence composition, finite first_match and sampled-value functions to the supported frontend subset. Keep #61 partial.


## PR 433

[#433](https://github.com/riscPrint/risc-v-workstation/pull/433). Merged: 2026-11-13T02:07:34Z.

Title: feat(privilege): add scheduled wfi and clock observation checks

Audit evidence label: unit tests only.

## Summary

Generate six WFI programs with C1 schedules for software, timer and external interrupts. Cross global MIE clear/set. Emit per-program regression suite options. Require matching C1 stimulus identity. Add an optional sampled clock-stop checker for stable state, pending input and resumed retirement.

## Testing

- Targeted tests: 30 passed, 0 skipped.
- RISC-V GCC: six generated programs compiled.
- Spike CLI: six inconclusive because it cannot drive these external input schedules. No false pass is reported.
- Fast set: 759 passed, 5422 deselected, 0 skipped.
- NOT RUN: RTL builds or simulations, physical clock-stop, full Python suite, formal or CI.

## Issues

Refs: #149

The project harness must drive the clock pause and record reference-clock samples. No hardware or DUT qualification is claimed. The API does not close the issue without those runs.

Roadmap notes: Add generated C1 input schedules and sampled clock-stop evidence checks to privilege campaigns. Retain project clock-driver integration and DUT qualification.


## PR 434

[#434](https://github.com/riscPrint/risc-v-workstation/pull/434). Merged: 2026-11-13T02:02:00Z.

Title: feat(lint): add cdc synchronizer library, assertions and rtl rules

Audit evidence label: ran on seeded RTL fixture.

## Summary

- `rvw/src/rvw/lint/cdc.py`: clock inference (`primary`, `divided` with `divide_by`, `gated` with enables, `generated` from blackboxes, `unknown`) with a `master` source and relationships (`same`, `related`, `asynchronous`, `declared_*`, `unknown`). Settings `intent.clocks` declare clock groups with reasons.
- Crossing classes: `sync_Nff` (2–6 stages through single-input wires), `gray_sync`, `qualified_data`, `glitch_before_sync` (`cdc.comb_before_sync`, error), `first_stage_fanout` (`cdc.sync_stage_fanout`, error), `multi_bit`, `unsynchronized`, `synchronous_related`; plus `cdc.fanout_before_sync`, `cdc.memory_crossing` / `cdc.async_fifo_candidate`. Spinal `BufferCC`, `StreamFifoCC`, `StreamCCByToggle`, `FlowCCByToggle`, `PulseCCByToggle`, `DataCC`, `ResetCtrl` are recognized from `components.class_name`. Gray recognition accepts both Spinal shift forms and a register that copies a Gray wire. `cdc.hierarchy` groups findings by component.
- Functional CDC step: `rvw lint --emit DIR` writes `rvw.cdc-obligations/1`, `cdc_checks.sv` (checker modules `rvw_cdc_gray`, `rvw_cdc_stable` and `bind` lines) and `checked/` RTL copies with the checkers inside the target modules (Yosys does not elaborate `bind`).
- `rvw/src/rvw/lint/rules.py`: new `rules` backend with 15 design-database rules (combinational loops, multiple drivers, driven inputs, latches, width truncation/extension, unused, unconnected outputs, undriven, constant registers, unreachable FSM states, no reset, clock as data, naming, max fan-out), configurable severities and parameters, exact-ID waivers.
- `rvw lint --sarif PATH`: SARIF 2.1.0 of all findings, with fingerprints and waiver suppressions.
- New extracted reference `SpinalDB/.../LintLibraryFixtures.scala` (BufferCC, StreamFifoCC, PulseCCByToggle, ResetCtrl reset synchronizer, divided clock).
- Shared format: additive `rvw.lint/1` fields and the new `rvw.cdc-obligations/1`, documented in `docs/PLATFORM_CONTRACTS.md`. No SpinalDB schema change.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_lint*.py rvw/tests/test_command_reference.py -q`: 131 passed, 18 skipped (extracted fixtures not set in that run; Verible).
- `RVW_LINT_FIXTURES=<fresh output of LintFixtures and LintLibraryFixtures> pytest rvw/tests/test_lint_extracted.py`: 16 passed. Fixtures extracted under the sbt lock.
- Native smoke (not in the test suite): `rvw lint --emit` on the extracted library RTL, then Yosys `sat -seq 16 -prove-asserts` on `checked/`: the two StreamFifoCC Gray obligations hold for 16 steps; a copy with the binary pointer instead of the Gray pointer fails.
- Fast set: 759 passed, 5456 deselected.
- Not run: BOOM or VexRiscv databases, `rvw formal bmc|prove` on emitted checks, simulation of `cdc_checks.sv`, full Python suite.

## Issues

Refs: #22. Remains: the checkers are single-clock immediate assertions with level semantics (toggle protocols need their own monitor); a structural match is still not a protocol proof; no frequency data; non-Spinal domain import; commercial comparison.

Roadmap notes: LINT — synchronizer recognition library (N-FF, Gray, qualified data, Spinal BufferCC/StreamFifoCC/toggle CCs), clock inference (divided/gated/generated), CDC assertion emission for formal/simulation, a 15-rule database lint backend and SARIF output.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 435

[#435](https://github.com/riscPrint/risc-v-workstation/pull/435). Merged: 2026-11-13T02:46:56Z.

Title: feat(formal): export custom instruction interfaces and tests

Audit evidence label: unit tests only.

## Summary

Add a versioned project-owned interface for pure R-type custom instructions. Validate explicit operands/state/effects, bitvector semantics and custom-space encoding conflicts. Export a stable JSON interface and Verilog result modules.

Generate GNU assembler macros, GNU C inline hooks, a standalone disassembler and a GCC machine-description fragment. Generate operand boundary vectors, alias/dependency assembly tests and x0-discard tests. Compare independently supplied reference vectors and track detected or surviving supplied mutants. Preserve missing evidence as gaps.

Roadmap notes: pure XLEN32/64 custom operations now have one versioned semantic interface, software hooks and generated verification plans. Extra state, memory effects, custom exceptions, full compiler plugin integration and DUT execution remain open. The GCC fragment is not a validated target-backend integration. These issues remain open.

## Testing

- 14 focused tests passed, 0 skipped, including command-reference checks.
- Native GNU GCC/binutils compilation passed for RV32I/ILP32 and RV64I/LP64. Object-byte decoding confirms a0/a1 input placement and a0 result placement in the generated inline function.
- Fast set after rebase: 759 passed, 5452 deselected, 0 skipped.
- NOT RUN: generated tests on a DUT, custom trap handling, complete GCC backend integration/build, objdump plugin integration, full Python suite, BOOM builds, real-core campaigns, GitHub CI waits.

## Issues

Refs: #122, #169, #155. Extra-state/effect semantics and native DUT/toolchain qualification remain open.


## PR 436

[#436](https://github.com/riscPrint/risc-v-workstation/pull/436). Merged: 2026-11-13T02:06:22Z.

Title: feat(regress): check translation protocols and ipi shootdowns

Audit evidence label: unit tests only.

## Summary

Add two-hart hardware A/D versus software RSW programs and project-addressed IPI shootdowns. Add project-declared protocol probes for atomic updates, TLB fill/hit/invalidation, stale entries, range invalidation and shootdown completion. Require explicit PBMT transaction-type policies. Keep protocol checks separate from architectural bins and retain inconclusive results for missing evidence.

## Testing

- Targeted walker/protocol checks: 69 passed, zero skipped. This includes 56 per-level fault programs and six new two-hart programs on Spike.
- Additional raw-walker integration test: six protocol tests passed, one native test deselected.
- Full Python suite, RTL, BOOM, Sail and hardware concurrency: NOT RUN.
- Final fast count below.

## Issues

Refs: #129, #99, #164, #148, #145.

DUT capture/validation, physical overlap, independent PBMT ordering and shared-TLB hardware completion remain open. This is a bounded protocol checker, not complete hardware qualification.

Roadmap notes: project-configured MMU suites now include IPI delivery and bounded concurrent A/D/RSW updates. Optional identity-bound translation probes check retained protocol events. DUT closure and ordering remain open. ROADMAP.md and TODO.md were not edited.
759 passed, 5418 deselected in 114.29s (0:01:54)


## PR 437

[#437](https://github.com/riscPrint/risc-v-workstation/pull/437). Merged: 2026-11-13T02:07:44Z.

Title: feat(cosim): compare sail fault completion observations

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Compare Sail scalar fault attempts and independently logged completion bytes. Preserve null data for uncompleted bytes. Reject overlapping fragments, wrong directions and split-page effects. Permit partial comparisons only when the reference adapter provides independent observations. Spike partial effects still refuse.

Add the C2/2 fault-only capability so fault observations do not require unavailable FP fields. Refresh one stale MCP inventory count from main, which caused two fast-test failures.

Roadmap notes: Sail zero-completion observations now have a native test. Same-page partial completion has synthetic memory-log and mutation checks only. Native partial faults, Spike partial effects, split-page effects and DUT fault capture remain open. No whole issue is closed.

## Testing

- Targeted Python tests with installed native Sail: 115 passed, 0 skipped.
- Final fast set: 759 passed, 5477 deselected, 0 skipped.
- NOT RUN: BOOM/VexRiscv builds or simulations, native partial-effect campaigns, full Python suite, CI.

## Issues

Refs: #8, #93. Split-page effects and Spike partial-effect capture remain open.


## PR 438

[#438](https://github.com/riscPrint/risc-v-workstation/pull/438). Merged: 2026-11-13T02:12:47Z.

Title: feat(sim): capture native harness and c2 writer checkpoints

Audit evidence label: ran on seeded RTL fixture.

## Summary

Add reusable direct Verilator model/context save and restore with adapter-owned harness serialization. Add C2 writer capture and fresh writer restore, including prefix bytes, position, digest, counters and pending late-tval traps. Add project snapshot-port control through `rvw sim checkpoint`, `resume`, `suffix-check` and MCP.

Roadmap notes: #132/#346 gain native harness helpers and executable checkpoint control. Spinal JNI and JVM continuation capture, bundled live ports, native VexRiscv qualification, full device state qualification and cost measurements remain open. These commands require project ports. They do not turn the existing Spinal adapter into a live-restorable adapter.

## Testing

- Targeted native envelope and reusable Verilator helper: 13 passed, 0 skipped, 27.17 seconds under vex lock and nice. Tiny accumulator only.
- Scala C2 writer: 1 passed, 0 skipped under sbt lock and nice. Checks byte equality, pending trap, IRQ, backwards cycles, ended writers, changed position and changed header.
- Snapshot port and suffix controls: 2 passed, 0 skipped. Fixture port, not native core qualification.
- Fast set after rebase: 759 passed, 0 skipped, 5494 deselected in 103.55 seconds. Command: `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`.
- Rebase kept main's new C2/2 CSR header and record checks. Command reference regenerated.
- NOT RUN: BOOM, VexRiscv live restore, full Python suite, long performance jobs, GitHub CI.

## Issues

Refs: #132, #346. Neither issue is closed.


## PR 439

[#439](https://github.com/riscPrint/risc-v-workstation/pull/439). Merged: 2026-11-13T02:08:06Z.

Title: feat(vip): add axi4 and axi4-lite protocol agents

Audit evidence label: unit tests only.

## Summary
Add bounded AXI4 and AXI4-Lite agents in Python/cocotb and SystemVerilog UVM. Support all five channels, aligned FIXED/INCR/WRAP bursts, per-ID response queues, independent AW/W acceptance, byte strobes, and exclusive reservations. Add monitor hooks, coverage, error injection, seeded RAM models and good/bad Python tests.

## Testing
- Targeted Python: 28 passed.
- Verilator lint of the interface, pinned Accellera UVM package, agent, fixture and test top: passed with warnings.
- Fast set: 759 passed, 5494 deselected. The rebase exposed a stale generated MCP tool count. Regenerated the reference and reran the set.
- NOT RUN: UVM runtime build, UVM simulation, cocotb RTL simulation, BOOM jobs and full Python suite.

## Issues
This is a bounded aligned 32-bit profile. Optional sidebands and unaligned traffic remain outside the profile. Reactive SV and cocotb runtime qualification remains open. The SV fixture scoreboard handles ordinary successful writes; exclusive-write policies use the project scoreboard hook.

Roadmap notes: Add AXI4/AXI4-Lite VIP cycle agents and SV components. Python tests and SV lint are evidence only for the declared profile. Keep runtime qualification open.


## PR 440

[#440](https://github.com/riscPrint/risc-v-workstation/pull/440). Merged: 2026-11-13T02:12:48Z.

Title: feat(formal): export captured cores and join testplan evidence

Audit evidence label: unit tests only.

## Summary
Export bounded SMT queries from captured SBY RTLIL, including jobs run with an AIGER engine. Support exact assertion selection and deletion-minimal sample constraint cores. Check bounded environment feasibility separately. Keep conflicting environments inconclusive. Group each captured assumption across samples and reduce conflicting environment cores.

Add `rvw formal testplan` and MCP. Join an explicit generated/hand-written property inventory with captured formal results, solver cores, activation cones and `rvw cov mutate` outcomes. Write JSON and escaped HTML. Group counts by module and declared Spinal source line. Keep missing evidence explicit and requirement obligations inconclusive.

## Testing
- Final solver/export and testplan group: 16 passed, 0 skipped, including native Yosys/Z3 valid and failing properties and conflicting assumptions.
- The final group includes testplan joins, missing evidence, ID errors, HTML escaping and output capture.
- Required fast set after report addition and rebase: 759 passed, 5682 deselected, 0 skipped. Repeated after later rebases before each push.
- Not run: full Python suite, BOOM build or simulation, long formal jobs, GUI navigation or GitHub CI wait.

## Issues
Refs: #62, #60

Roadmap notes: Automatic captured-model SMT export and formal testplan evidence joins are available. Core units are sample constraint groups, not minimal logic cells. The report has no automatic design-wide property discovery, full non-vacuity result or completed requirement obligations. Existing guarded `rvw cov prove` remains the UNR exclusion path. No new exclusion authority is added.


## PR 441

[#441](https://github.com/riscPrint/risc-v-workstation/pull/441). Merged: 2026-11-13T02:06:49Z.

Title: feat(vscode): add wave query panel for rvw wave results

Audit evidence label: unit tests only.

## Summary

- New VS Code feature `wave` (`vscode/features/wave/`): the **RVW Wave Query** view runs `rvw wave` queries (`find`, `edges`, `why`, `seq`, `txn`, `diff`, `changes`, `sample`) and shows the JSON result as a tree.
- Saved queries: `*.rvwq.json` (`rvw.wave-query/1`, paths relative to the file); New / Open / Run Again / Save commands. Queries run with `execFile` argument arrays only.
- Cross-navigation from result rows: driver assignment → database `file:line`; signal → `rvw query where` with the captured source-hash check (shared results model); any row with a time → `rvw wave cut` window opened in Surfer.
- No pass icons; ambiguous/unknown/diverged/issue rows get warnings; a diff with no points is `inconclusive`.
- Regenerate `docs/COMMAND_REFERENCE.md` (main had drifted; the fast reference test failed on main).

## Testing

- `cd vscode && npm ci && npm run typecheck && npm run build && npm test`: 22 passed, 0 failed, 0 skipped (3 new model tests on fixtures produced by the real `rvw wave why/txn/find`).
- Fast set: 757 passed and 2 failed before the reference regeneration (the failures were on main); `test_command_reference.py`: 3 passed after it.
- Not run: VS Code host or integration test for this feature, Surfer launch.

## Issues

Refs: #24, #297. Adds result panels for saved wave queries, driver traces and cross-navigation. Remaining: a live cursor link with Surfer, run/cancel controls beyond the progress indicator, host test.

Roadmap notes: IDE area — VS Code `wave` feature shows saved `rvw wave` queries (search, driver trace, sequences, transactions, diff) with source and wave-window jumps.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 442

[#442](https://github.com/riscPrint/risc-v-workstation/pull/442). Merged: 2026-11-13T02:08:38Z.

Title: feat(arch): model decoupled fetch and shared execution ports

Audit evidence label: unit tests only.

## Summary
Add decoupled fetch/decode buffers, an FTQ capacity limit, micro-op cache timing, shared execution port bindings, initiation intervals, distributed issue capacity, finite page walks, and a commit-slot stall partition to the own-core C2 timing model. Add a Python memory-service boundary for component models without changing ComponentSims.

## Testing
60 targeted OoO tests passed. The public fast set passed. No BOOM builds, RTL simulations, native gem5 runs, or full Python suite ran. These synthetic schedules do not establish RTL accuracy. Cache adapters, branch replay, fusion, elimination, and native pipeline acceleration remain open.

## Issues
Refs: #72, #357, #359, #362, #125. This is an own-model slice. It does not close the native gem5 acceptance tasks.

Roadmap notes: The own model now has configurable front-end and shared-port timing plus translation backpressure. Hardware accuracy, component cache integration, and wrong-path resource use remain open.


## PR 443

[#443](https://github.com/riscPrint/risc-v-workstation/pull/443). Merged: 2026-11-13T02:07:51Z.

Title: feat(sim): load captured per-hart images in generic harness

Audit evidence label: unit tests only.

## Summary
Add an opt-in generic multi-hart adapter path. Capture N pinned ELF inputs before compilation, load shared memory with overlap checks, retain per-hart entries and write per-hart RVFI through MultiHartSession. Existing adapters must declare their hart IDs to accept the new option.

## Testing
Eight targeted Scala tests passed, no skips. Twelve targeted Python tests passed, no skips. The fast Python set passed before push.

NOT RUN: production-core multi-hart RTL, BOOM builds, full Python suite. The driver test uses a software adapter and does not establish multi-hart ISA or ordering correctness.

## Issues
Refs: #90. Production core integration and an independent general execution checker remain open.

Roadmap notes: generic run/run-many now capture per-hart images and provide a shared-memory and per-hart RVFI service. Core-specific integration remains required.


## PR 444

[#444](https://github.com/riscPrint/risc-v-workstation/pull/444). Merged: 2026-11-13T02:10:21Z.

Title: feat(formal): lower named properties and checker bindings

Audit evidence label: unit tests only.

## Summary
Lower argument-free named properties and module-target checker bindings. Combine captured RTL and bind files into one sealed proof input. Retain original source records and refuse unsupported checker forms.

## Testing
- OSS CAD Suite: 54 temporal/binding tests passed. Final binding tests: 10 passed, including two separate-file CLI BMC cases. These sets overlap.
- Snapshot/frontend integration: 16 passed, 38 deselected.
- Fast set: retained local result before push.
- NOT RUN: full Python suite, BOOM, long formal jobs, simulator scheduling qualification, GitHub CI wait.

## Issues
Refs: #61

Instance-target binds, parameterized properties, checker output/event arguments, local variables and unbounded temporal constructs remain open.

Roadmap notes: support explicit ANSI-input checker declarations and named-port module-target binds, including separate input files. Keep full SVA partial.


## PR 445

[#445](https://github.com/riscPrint/risc-v-workstation/pull/445). Merged: 2026-11-13T02:48:47Z.

Title: feat(formal): track pinned profile obligations and changes

Audit evidence label: unit tests only.

## Summary

Import hash-pinned RVA23/RVB23 named-extension obligations for user and supervisor profiles. Expand supervisor inheritance without weakening mandatory requirements. Activate optional requirements from the ISA manifest. Report implemented, verified, missing, unsupported and unselected items separately. Include the existing compiler/DUT/reference/ACT/coverage configuration audit.

Require proof-result and obligation hashes, unbounded pass, nonzero assertions and reachable environment before a reviewed mapping can report verified. Add explicit-adoption baseline diffs, affected checker IDs, missing tests and present test hashes. Add CLI, MCP and a four-profile pinned example.

Roadmap notes: named profile-extension inventories and obligation diffs are implemented. Base/endian/ECALL paragraphs, notes, recommendations and implicit dependencies remain outside this parser. Normative conditions stay in the full captured obligation text for reviewed proof mapping. No full profile compliance or acceptance is claimed. Existing ISA/specification audit modules remain the configuration/catalog mechanisms.

## Testing

- 15 focused profile/ISA/reference tests passed, 0 skipped.
- Actual pinned source import succeeded for all four profile inventories at riscv-profiles commit e030b70992447784ad9081045d47ce6e278f381e. The result remains inconclusive. This is a source-import check, not a DUT check.
- Fast set after rebase: 759 passed, 5558 deselected, 0 skipped.
- NOT RUN: real-core profile compliance, native consumer probes for a real project, full Python suite, BOOM builds, real-core formal campaigns, GitHub CI waits.

## Issues

Refs: #104, #80, #141. Complete normative catalogs and real-project implementation/proof evidence remain open.


## PR 446

[#446](https://github.com/riscPrint/risc-v-workstation/pull/446). Merged: 2026-11-13T02:10:12Z.

Title: feat(sim): check independent atomic memory effects

Audit evidence label: unit tests only.

## Summary
Add an independent atomic memory observer at a declared serialized boundary. Check reservation-set invalidation, SC byte retention and success, bounded spurious failures under a certified constrained-loop service assumption, RV64 AMO effects and Zacas W/D/Q compare/swap effects.

## Testing
Four targeted Scala unit tests passed, no skips. The fast Python set passed: 759 passed, no skips.

NOT RUN: concurrent production RTL, Spike, BOOM builds, full Python suite. These are observer unit tests. aq/rl ordering and unbounded forward progress are not established. The spurious-failure bound is a project service condition, not a RISC-V architectural limit.

## Issues
Refs: #91, #97, #170. Project RTL bindings, contention campaigns and architectural ordering checks remain open.

Roadmap notes: independent byte checks now cover RV64 AMOs and W/D/Q CAS, with declared reservation-set and bounded SC service policy. RTL integration remains required.


## PR 447

[#447](https://github.com/riscPrint/risc-v-workstation/pull/447). Merged: 2026-11-13T02:13:11Z.

Title: feat(csim): add native component models and rvw csim command

Audit evidence label: unit tests only.

## Summary

Adds a native trace-driven component-model engine (`ComponentSims/csim.cc`, header-only models in `ComponentSims/include/csim/`) and the `rvw csim` command with MCP tools. All models are our own implementations from the published papers; no ChampSim, CBP or gem5 code is copied.

- Direction: bimodal, gshare, local, tournament, perceptron, hashed perceptron/GEHL, TAGE, L-TAGE, TAGE-SC-L (loop predictor + statistical corrector), BTFN, always-taken, perfect bound. Project-described stacks: TAGE `tables` (entries, history, tag bits), `loop.*`, `sc.*`; delayed update (`branch.update_delay`).
- Targets: multi-level BTB (partial tags, level latencies, refill), RAS with `none|pointer|pointer_top|full` repair exercised by a learned-CFG wrong-path walk, indirect targets from BTB or ITTAGE.
- Front end: decoupled BPU→FTQ→I-cache→decode delivery model (FDIP, BTB level bubbles, decode/execute redirects, wrong-path I-cache fetch).
- Memory: L1I/L1D/L2/LLC; LRU, random, PLRU, SRRIP, BRRIP, DRRIP, SHiP, Hawkeye, Belady OPT (L1D); prefetchers next-line, IP-stride, stream, BOP, SPP, SMS, Berti, EIP; late/useful/useless/pollution counts and a per-level prefetch queue; TLB + page walk caches with walks through the data cache.
- Memory dependence (store sets, wait table, always/never speculate, perfect) and value prediction (last value, stride, VTAGE), move and zero-idiom counts.
- Traces: C2 (converted, optional register values), CBP 2016 BT9, ChampSim binary (read natively, .xz/.gz), native `rvw.csim-trace/1`, legacy `rvw.branch-trace/1`.
- `rvw csim run|sweep|budget|convert|models|compare-rtl|build`; MCP `csim_run`, `csim_sweep`, `csim_budget`, `csim_models`, `csim_convert`, `csim_compare_rtl`. Sweeps give storage-budget marking (metadata or all bits) and a Pareto front.
- In-process library for timing models: C ABI (`capi.cc`) and `rvw.csim.lib.Components` (ticketed predict/update, BTB, RAS, ITTAGE, cache access with completion cycle) for the OoO model.
- RTL comparison (#358 first part): `rvw.bp-events/1` or Kanata `#rvw prediction` events against the model on the same C2 run; per-branch disagreement; inconclusive on missing identity, semantics, events or alignment; Kanata-inferred redirects reported apart.
- Project data: `examples/boom/csim/tage-l.json` (BOOM v4 withTAGELBPD sizes at spinal-boom 0cb0b69, `fidelity: approximate`, differences listed); `ComponentSims/examples/wide-core.json` (illustrative, not a product model).
- Contracts: new "Component study formats" section in `docs/PLATFORM_CONTRACTS.md`; command reference regenerated; AGENTS layout row updated.

## Testing

- `rvw/.venv/bin/python -m pytest ComponentSims/tests -q` — 83 passed (engine: hand-derived counter, BTB, RAS, PWC, MDP and VP cases; scalar perceptron reference; differential check against the legacy bimodal/gshare engine; OPT is the minimum over all policies; ChampSim reader; error cases).
- `rvw/.venv/bin/python -m pytest rvw/tests/test_csim_formats.py rvw/tests/test_csim.py -q` — 22 passed (C2/BT9 converters, study files, CLI, sweep/Pareto, library vs engine differential, RTL comparison with an injected mismatch and inconclusive cases).
- `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q` — 772 passed, 0 skipped (after rebase on origin/main). `test_csim_formats.py` is added to the fast set (no compiler needed).
- Not run: no BOOM build or simulation, no native RTL comparison (no adapter writes `rvw.bp-events/1` yet), no published CBP/ChampSim trace sets, no independent pinned TAGE-SC-L reference, full slow suite not run, CI not awaited.

## Issues

Refs: #351 — remaining: pin an independent TAGE-SC-L reference and compare per-branch predictions on reference traces.
Refs: #360 — remaining: validation against an independent reference on pinned traces.
Refs: #358 — remaining: a project adapter that emits `rvw.bp-events/1` and one native RTL comparison.
Refs: #365 — remaining: checks against pinned external references; no ChampSim code reused (nothing to inventory under #37).

Roadmap notes: Component simulators: native engine with TAGE-SC-L, perceptron, tournament, BTB/RAS/ITTAGE, FTQ front end, cache hierarchy with 9 replacement policies and 8 prefetchers, TLB/PWC, store sets and value prediction; `rvw csim` CLI/MCP with sweeps and storage budgets; C ABI for the OoO model; RTL event comparison format. Next: pinned reference qualification, project event adapter, sampled ROI weights.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 448

[#448](https://github.com/riscPrint/risc-v-workstation/pull/448). Merged: 2026-11-13T02:11:24Z.

Title: feat(lint): generate and check sdc timing intent

Audit evidence label: unit tests only.

## Summary

- New `sdc` backend (`rvw/src/rvw/lint/sdc.py`). Generation from clock-domain data: `create_clock` (periods from settings `sdc.clocks` or SpinalDB), `create_generated_clock` for divided and declared PLL clocks, `set_max_delay -datapath_only` from Spinal `crossClockMaxDelay`, `set_false_path` for recognized safe crossings and Spinal `crossClockFalsePath` reset synchronizers, `set_multicycle_path` from declared rows validated against elaborated register paths, and advisory clock groups when every crossing between two masters is recognized.
- Check of a project SDC file: `sdc.unmatched_clock`, `sdc.unconstrained_clock`, `sdc.unmatched_endpoint`, `sdc.unsafe_false_path` (an exception hides an unsafe crossing) and `sdc.unconstrained_crossing`. Generation also reports `sdc.unsafe_crossing`, `sdc.unmatched_multicycle`, `sdc.unresolved_max_delay` and `sdc.unknown_ratio`.
- `rvw lint --emit` also writes `constraints.sdc`.
- **Shared change (SpinalDB, additive):** new table `clock_frequencies(clock_domain_id, hz)` from Spinal `FixedFrequency`. No schema version bump: older databases lack the table and readers treat that as unknown. `rvw/src/rvw/query/schema.sql` gets the same table so `build-hdl` databases match. Documented in `SpinalDB/README.md` and `docs/PLATFORM_CONTRACTS.md`.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_lint*.py rvw/tests/test_query_hdl.py -q`: 140 passed, 21 skipped (extracted fixtures not set; Verible; native HDL tools).
- `RVW_LINT_FIXTURES=<fresh fixtures> pytest rvw/tests/test_lint_extracted.py`: 17 passed, including the SDC of the extracted library design (100 MHz `clkA` from the database, divided clock, 3 max-delay and 2 reset false paths). `LintLibraryFixtures` re-extracted under the sbt lock after the extractor change (compiles and writes the table).
- Fast set: 759 passed, 5645 deselected.
- Not run: the SpinalDB sbt test suite, any STA tool on the generated SDC, BOOM or VexRiscv databases.

## Issues

Refs: #185. Remains: object names follow a configurable `register_pattern`, not a specific synthesis tool's netlist; the SDC reader does not evaluate Tcl variables, loops or `-hierarchical` semantics; no STA run checks the constraints; this is logical intent, not routed timing signoff.

Roadmap notes: LINT — `rvw lint` sdc backend generates SDC from clock-domain data and Spinal timing tags and checks project SDC intent (unmatched/unconstrained clocks and paths, exceptions that hide unsafe crossings). SpinalDB records clock frequencies.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 449

[#449](https://github.com/riscPrint/risc-v-workstation/pull/449). Merged: 2026-11-13T02:12:05Z.

Title: feat(regress): expand two-stage hypervisor matrices

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Add a project-selected 102-program hypervisor matrix. Cross VS Sv39/48/57 with Sv39x4/48x4/57x4 G stages and HLV.D/HLVX.WU/HSV.D. Check VS/G permission faults, full VS A/D PTE contents, virtual-instruction controls, same-VMID G-root reuse with different payloads, and HS guest-fault CSRs. Check legal htinst/mtinst transformations. Add an independent Python nested walker that translates each VS PTE read through G stage and handles widened x4 root indices.

## Testing

- Hypervisor and walker checks including short Spike programs: 68 passed, zero skipped. All 102 hypervisor and 56 per-level fault programs passed Spike.
- Additional geometry, nested-walk and widened-root checks: seven passed, one native test deselected.
- RTL, BOOM, Sail, full Python suite and nested DUT capture: NOT RUN.
- Final fast count below.

## Issues

Refs: #140.

Keep the issue open. Independent nested DUT capture/comparison, all HFENCE scopes, guest fetch permission matrices and hardware nested A/D atomicity remain open. No DUT result is claimed.

Roadmap notes: reusable hypervisor suites now cover all selected x4 geometries, additional memory operations, VS A/D, HS fault CSRs and VMID/root reuse. The nested reference walker is independent of retirement effects. DUT closure remains open. ROADMAP.md and TODO.md were not edited.
759 passed, 5668 deselected in 79.59s (0:01:19)


## PR 450

[#450](https://github.com/riscPrint/risc-v-workstation/pull/450). Merged: 2026-11-13T02:12:29Z.

Title: perf(arch): add an optional native integer timing scheduler

Audit evidence label: unit tests only.

## Summary
Add an optional C timing scheduler for integer streams. The installer builds it with `--with-ooo`; unsupported configurations retain Python. Reports name the backend and include the selected native library in the engine identity. No third-party downloads are needed.

## Testing
113 targeted installer and OoO tests passed, including native builds and 100 seeded schedule comparisons. 759 fast tests passed. Bash syntax passed. A warmed alternating test of 200,000 synthetic integer instructions produced the same 50,004-cycle result in all three trials. Native throughput including validation and conversion was 0.47–0.53 million instructions per second. C2 parsing was excluded. The millions-per-second goal remains open.

No RTL simulations, BOOM builds, full suite, or native gem5 runs ran. Memory, branches, decoupled front-end timing and explicit port bindings use Python.

## Issues
Refs: #72. This accelerates the own model, not native gem5.

Roadmap notes: Optional integer native execution is available through the installer. Full-pipeline acceleration and RTL speed/accuracy qualification remain open.


## PR 451

[#451](https://github.com/riscPrint/risc-v-workstation/pull/451). Merged: 2026-11-13T02:12:22Z.

Title: feat(perf): split predictor accuracy by warmup, alias and context

Audit evidence label: unit tests only.

## Summary

- `rvw perf`: new `predictions.effects` (additive to `rvw.perf/1`). Per predictor and kind: `overall` accuracy, `steady_state` (only `warmup=false` and `alias=false`), and separate `by_warmup`, `by_alias`, `by_context` splits. Mispredict recovery and wrong-path costs give samples/unknown/sum/max plus mean and nearest-rank p50/p95. `?` states stay their own groups. The text report prints overall, steady-state, warmup and alias accuracy.
- SpinalKonata: generic hardware tags `PipelineTags.direction(...)` and `PipelineTags.target(..., "target"|"return", ...)` bind a project's observed predictor signals; absent optional signals are written `?`. The demo pipeline emits two direction outcomes; the real Verilator test checks the records and reads them back through the production Python effects report.
- Docs: PLATFORM_CONTRACTS (effects fields), perf README, SpinalKonata README.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_perf_events.py rvw/tests/test_perf.py -q`: 137 passed, 0 skipped.
- Scala, from `SpinalKonata/` under the sbt lock: `../scripts/with-lock.sh sbt nice -n 10 sbt -batch -Dsbt.offline=true 'set ThisBuild / dependencyOverrides += "org.scala-lang" % "scala-reflect" % "2.13.14"' test`: 6 passed, 0 failed (includes the real Verilator demo).
- Fast set: 759 passed.
- Not run: BOOM (no core change; the BOOM probe binding is core-owned).

## Issues

Refs: #49. Observed direction/target/return outcomes with recovery latency and wrong-path work now have hardware tags and reports; warmup, alias and context effects are reported separately. Remaining: wire the tags in the BOOM core probe (riscPrint/spinal-boom #12/#13) and validate on BOOM.

Roadmap notes: perf area — predictor effects report (warmup/alias/context marginals, steady-state accuracy, recovery p50/p95) and generic SpinalKonata direction/target tags.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 452

[#452](https://github.com/riscPrint/risc-v-workstation/pull/452). Merged: 2026-11-13T02:12:59Z.

Title: feat(cov): generate and execute bounded sequence actions

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Add bounded RAW/WAW/WAR, branch, jump and memory action recipes through `rvw cov actions` and `cov_actions`. Emit exact payload words, resource preconditions and an action graph. Extend the closure loop to generate these goals and measure them through the same strict C1/Spike verifier and existing sequence observer. Preserve unsupported memory goals in the denominator. Check that each payload PC retires once. Keep retirement pairs separate from pipeline hazards.

## Testing

Targeted actions, controller, payload sampling, sequence observer and command reference tests: 99 passed, zero skips. Fast set: 759 passed, 5784 deselected, zero skips.

Native GCC smoke under nice: 26 RV32/RV64 programs compiled and matched exact ELF payload bytes. This covers the two integer candidates and all 12 sequence kinds at distance four on both XLENs. Evidence: `/var/folders/s3/t4lhzzrj1qxfn3_y28334_340000gn/T/dv-native-0v9048k5`.

NOT RUN: DUT execution, native Spike sequence campaign, paired random comparison, full suite or CI. Native compile success earns no sequence coverage.

## Issues

Refs: #352

Keep #352 open. Native observed sequence closure, held-out campaign mutations and paired CPU-cost comparison remain. This is a bounded action subset and does not implement PSS.

Roadmap notes: Sequence candidates and closure-loop execution now share the existing retirement observer. Memory needs a declared writable program-data resource. Native assembler/ELF bytes were checked. DUT sequence closure remains unverified.


## PR 453

[#453](https://github.com/riscPrint/risc-v-workstation/pull/453). Merged: 2026-11-13T02:15:10Z.

Title: feat(formal): diagnose and install native proof engines

Audit evidence label: unit tests only.

## Summary

Add `rvw formal doctor` and MCP diagnostics with executable paths, enabled adapter features and explicit unmeasured qualification. Add Bitwuzla/cvc5 SMTBMC, BTORMC and suprove adapter entries. Map SBY UNKNOWN exit 4 to inconclusive. Record per-engine solved counts and total benchmark wall time. Add pinned external rIC3 and EBMC build flags and measured two-case HWMCC results.

This branch includes PR #401, which remained open after five conflict retries while main moved. Its implementation is required by the new adapters. No claim that #401 merged is made.

Roadmap notes: engine diagnostics and small pinned native measurements are available. Full-block capacity, general RTL abstraction and liveness, broad open-core property campaigns and native SSH campaigns remain open. Neither epic is complete.

## Testing

- Fast set: 759 passed, 5713 deselected, 0 skipped. Log `/tmp/deep-native-fast.log`.
- Targeted doctor/installer/portfolio tests: 13 passed, 0 skipped.
- Native two-case HWMCC run: ABC PDR solved 2/2. Yices, Z3, Bitwuzla and cvc5 solved 1/2 each. Induction on the second case remains inconclusive. Avy crashed on both. Raw results: `/tmp/rvw-deep-hwmcc-run2/result.json`; measured table in formal README.
- rIC3 and EBMC qualification NOT RUN: external native builds are in progress. rIC3 needs explicit nightly Rust and macOS library discovery. suprove is absent. Installer dry runs and bash syntax passed.
- Full Python suite, BOOM jobs, broad HWMCC, open-core property sets, licensed engines and CI waits NOT RUN.

## Issues

Refs: #21, #294. Keep both open.


## PR 454

[#454](https://github.com/riscPrint/risc-v-workstation/pull/454). Merged: 2026-11-13T02:13:06Z.

Title: feat(privilege): generate plic reset and smrnmi campaigns

Audit evidence label: unit tests only.

## Summary

Generate six PLIC arbitration/gateway programs, three reset restart programs and one Smrnmi entry/recovery program. PLIC expectations use the existing independent model, including claim despite threshold. Emit mailbox-driven C1 stimulus files and bind their hashes. Check sampled reset state and output validity for every requested pulse. Smrnmi checks entry, a nested ordinary trap and MNRET recovery.

## Testing

- Targeted Python tests: 27 passed, 0 skipped.
- RISC-V GCC: all ten generated programs compiled. Smrnmi uses numeric encodings with a base compiler ISA because this assembler does not accept the Smrnmi extension name.
- Fast set: 759 passed, 5680 deselected, 0 skipped.
- Spike CLI cannot inject these device/reset/NMI mailbox events. No reference or DUT pass is claimed.
- NOT RUN: RTL builds, DUT simulation, full suite, long formal or CI.

## Issues

Refs: #131
Refs: #111
Refs: #166

Remaining: project adapter drive/observation integrations, simultaneous context races, in-flight bus/debug reset, repeated RNMI and reset/error interactions. No issue is closed by generation or fixture tests.

Roadmap notes: Add project-owned PLIC, reset and Smrnmi program generation with replayable mailbox stimulus. Record native compilation separately from unrun event delivery and DUT qualification.


## PR 455

[#455](https://github.com/riscPrint/risc-v-workstation/pull/455). Merged: 2026-11-13T02:14:56Z.

Title: feat(debug): add debug module model, dmi drivers and compliance suite

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
- Reference Debug Module model (`dm.py`) for Debug 0.13.2 and 1.0 option sets: dmactive reset, hart selection, hart-array mask, halt groups, unavailable harts, ndmreset/hartreset, resethaltreq, abstract register/memory/quick-access commands, program buffer with autoexec, system-bus access with declared error codes. A small hart model (`hart.py`: RV I+M, Zicsr, traps, Debug Mode, step, stepie) and an Sdtrig trigger unit (`triggers.py`: mcontrol, mcontrol6, icount, itrigger, etrigger, chains, timing, WARL legalization, tcontrol).
- Reference JTAG DTM (`jtag.py`: IEEE 1149.1 TAP, IDCODE, DTMCS, DMI, BYPASS, request latency, sticky busy, dmireset, dmihardreset) and a remote_bitbang server: `rvw debug serve` exposes the model, or a core adapter's DMI bus, to OpenOCD.
- DMI drivers (`dmi.py`): `JtagDMI` over remote_bitbang (batched TCK) or in-process, `BusDMI`, and `ProcessBus`, a new C1 line protocol for a core adapter's simulated DMI bus.
- `rvw debug tap`: TAP/DTM conformance (reset from all 16 states, IR capture, IDCODE, BYPASS, DTMCS, DMI status, Pause-DR, sticky busy, dmireset, dmihardreset).
- `rvw debug suite`: 82 self-checking Debug Specification checks (groups dm, abs, pb, dbg, trig, sba). Each check asserts a spec rule and records observations. For non-model targets, each check runs again on the reference model and the observations are compared. The output is C3 (`debug-compliance`). Undeclared or skipped options are listed as unsupported, never passed.
- Project table `[debug_module] profile`; debug profile `rvw.debug-profile/1`; `examples/debug/spike.toml` records Spike's choices and two deviations as reasoned skips.
- MCP: `debug_suite`, `debug_tap`, `debug_checks`.

## Testing
- `rvw/.venv/bin/python -m pytest rvw/tests/test_debug_dm.py -q`: 33 passed. The tests cover all checks on the model, JTAG-level runs, reference-diff failures, eight seeded model bugs that each make the matching checks fail, the IEEE TAP table, busy/no-busy DTMs, the remote_bitbang server, the adapter line protocol, the CLI and C3 validation.
- `rvw/.venv/bin/python -m pytest rvw/tests/test_debug_spec.py -q`: 23 passed, 1 skipped (E-Trace reference not set).
- Native: `rvw/tests/test_debug_dm_native.py` (Spike 1.1.1-dev, 2 harts, SBA 64): 2 passed. The full suite gave no failures (no check failed), and the TAP campaign passed.
- Fast set: 792 passed.
- Not run: no core RTL target, because no adapter implements the hooks yet. No full slow suite.

## Issues
Closes: #133
Closes: #127
Closes: #153
Closes: #156
Refs: #144. Still open: virtualization with the H extension (only WARL vs/vu=0 is checked), textra/tdata3, size matching, NMI itrigger.

Roadmap notes: Debug area. The Debug Module reference model, JTAG/DMI drivers, remote_bitbang server, TAP/DTM campaign and Debug Specification compliance campaign (C3) are available, checked against native Spike. Spike findings: no haltsum0, data0 kept across dmactive=0, stepie not implemented (interrupts are taken while stepping), aarpostincrement ignored. Next step: a core adapter that exposes a DMI bus or a JTAG DTM.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

## PR 456

[#456](https://github.com/riscPrint/risc-v-workstation/pull/456). Merged: 2026-11-13T02:20:20Z.

Title: feat(cosim): add blocking online comparison transport

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add a blocking C2 handshake to the generic Scala trace writer and a DPI-C client. Step and compare before acknowledging each retirement. Stop on the first difference and retain the normal C5-ready report and captured input identity. Inject taken interrupts at the recorded boundary.

## Testing
- Transport tests: 2 passed, including a real socket adapter process.
- Existing live-launch tests without native tools: 10 passed, 1 deselected.
- Fast set after rebase: 759 passed, 5681 deselected.
- C++ DPI client syntax check passed.
- NOT RUN: Scala compile, RTL simulation, native Spike lockstep. Debug request synchronization is not implemented yet.

## Issues
Refs: #136

Roadmap notes: Cosim gains blocking online checking through the generic trace writer and a DPI hook. Debug event injection remains open. No DUT lockstep result is claimed.


## PR 457

[#457](https://github.com/riscPrint/risc-v-workstation/pull/457). Merged: 2026-11-13T02:14:45Z.

Title: feat(sim): map declared cache and pending fetch events

Audit evidence label: unit tests only.

## Summary
Map declared project cache events into independent cache and instruction-byte scoreboards. Track pending fetch requests through reply, consume and discard. Check cross-hart publication synchronization and physical alias observations. Require explicit campaign coverage.

## Testing
Three targeted Scala tests passed, no skips. The fast Python set passed before push.

NOT RUN: project RTL bindings, RTL cache error injection, BOOM builds, full Python suite. Tests use normalized observer events. Project adapters must establish synchronization and physical-address mappings.

## Issues
Refs: #103, #109. Production adapter mappings and RTL cache/pending-fetch campaigns remain open.

Roadmap notes: generic cache events now feed byte checks and consumed-fetch visibility checks. Model event tests remain separate from RTL evidence.


## PR 458

[#458](https://github.com/riscPrint/risc-v-workstation/pull/458). Merged: 2026-11-13T02:14:47Z.

Title: feat(checks): add pinned CSR field catalog and project overrides

Audit evidence label: ran on seeded RTL fixture.

## Summary

Add 416 pinned RISC-V Unified Database CSR definitions with 1,395 fields. Preserve aliases, extension conditions, reset expressions, legalization IDL, source hashes and notices as data. Add project overrides through the existing CSR generator and a VexRiscv M-only scratch selection. List the 26 privileged-table names missing field definitions in this source revision.

The generator does not evaluate IDL. Alias, hypervisor and debug execution bindings are refused. Full field coverage, privilege sequences, actual VexRiscv binding and compliance remain open.

## Testing

- CSR catalog and generator tests: 28 passed, 0 skipped. Existing native Icarus mutation and RISC-V assembly smoke cases passed.
- Required fast set: 759 passed, 0 skipped.
- NOT RUN: SBY proofs, Spinal compile, actual VexRiscv execution, BOOM simulation, full Python suite.

## Issues

Refs: #85

Roadmap notes: Add pinned standard CSR data and explicit project selections. Keep missing catalog fields, alias execution, privilege sequencing, real-core binding and compliance open.


## PR 459

[#459](https://github.com/riscPrint/risc-v-workstation/pull/459). Merged: 2026-11-13T02:14:53Z.

Title: feat(sim): inject project architectural state with readback

Audit evidence label: unit tests only.

## Summary

Add a project architectural state injection API. Validate exact CSR inventories, signal maps, widths, raw FPR values and RAM images before changing the DUT. Hold fetch, clear microarchitecture, inject, and read every mapped value back before release. Add an RV32IM bootstrap assembly path for cores without injection hooks.

Roadmap notes: #347 gains a generic injection port and bootstrap generator. #350 gains raw FPR transport, including f0 and NaN-boxed values. These are project API capabilities. Spike export/import, the qualified interchange format, VexRiscv simulation hooks, C1 sample completion and native continuation checks remain open. VM, devices, interrupts and multi-hart state are refused. The bootstrap does not restore cycle/instret counters or provide pre-fetch readback.

## Testing

- Targeted injection and bootstrap tests: 8 passed, 0 skipped. Includes native RISC-V GCC assembly/link at a saved non-reset PC, raw f0 bits, failed readback holding fetch, and unsupported state refusal.
- Fast set after rebase: 759 passed, 0 skipped, 5798 deselected in 71.70 seconds. `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`.
- NOT RUN: Spike transfer, native RTL injection, VexRiscv restore, BOOM, full Python suite, GitHub CI.

## Issues

Refs: #347, #350. No issue is closed.


## PR 460

[#460](https://github.com/riscPrint/risc-v-workstation/pull/460). Merged: 2026-11-13T02:15:33Z.

Title: feat(arch): search the own model with project cost estimates

Audit evidence label: unit tests only.

## Summary
Add `rvw arch ooo-search` and a cancellable MCP tool. Run grid sweeps or bounded Bayesian cycle search on complete C2 traces. Store completed points in SQLite and produce a Pareto report over speed and optional project analytic area/power estimates. Reuse the existing Bayesian proposal method.

## Testing
65 targeted OoO tests passed. The fast set passed. No RTL, BOOM builds, gem5 runs, or full Python suite ran. Costs are declared estimates. Uncertainty and hardware accuracy remain unmeasured. Bayesian search minimizes aggregate cycles; it is not multi-objective Bayesian optimization.

## Issues
Refs: #160. Physical PPA measurements, uncertainty intervals and independent RTL confirmation remain open.

Roadmap notes: Own-model grid/Bayesian exploration now has per-point storage and Pareto reports. Fixed committed traces and estimated costs limit these experiments.


## PR 461

[#461](https://github.com/riscPrint/risc-v-workstation/pull/461). Merged: 2026-11-13T02:17:42Z.

Title: feat(formal): lower eventual response to native liveness jobs

Audit evidence label: unit tests only.

## Summary
Lower single-clock Boolean eventual response properties to native Yosys live/fair cells. Generate an SBY live job using aiger suprove. Add CLI and MCP entry points. Keep missing tools and engine passes inconclusive. No finite response bound replaces eventuality.

## Testing
- Targeted frontend tests: 11 passed, including native Yosys live-cell creation and short periodic-trace semantics.
- Fast set: retained local result before push.
- NOT RUN: suprove proof (tool absent), full Python suite, BOOM builds/simulation, long formal jobs, GitHub CI wait.

## Issues
Refs: #61

Only simple eventual Boolean response is supported here. General unbounded sequence automata, reset cancellation, until operators, cross-clock liveness and mixed safety/liveness jobs remain open. Engine observation does not certify activation or non-vacuity.

Roadmap notes: add a native live/fair lowering path for eventual response. Keep general SVA and liveness qualification partial.


## PR 462

[#462](https://github.com/riscPrint/risc-v-workstation/pull/462). Merged: 2026-11-13T02:16:25Z.

Title: feat(vip): add tilelink-ul and tilelink-uh agents

Audit evidence label: unit tests only.

## Summary
Add bounded TileLink-UL and TileLink-UH A/D agents in Python/cocotb and SystemVerilog UVM. Support Get, PutFull, PutPartial, multi-beat UH messages, arithmetic and logical atomics, and hints. Add source tracking, same-edge responses, early acknowledgement handling, functional coverage, scoreboard hooks, seeded RAM fixtures and error injection.

## Testing
- Targeted Python: 31 passed.
- Pinned Accellera UVM plus interface, package, fixture and test top: Verilator lint passed with warnings.
- 772 passed, 5840 deselected in 82.77s (0:01:22)
- NOT RUN: UVM runtime build, UVM simulation, cocotb RTL simulation, BOOM jobs and full Python suite.

## Issues
The profile uses 32-bit data/address and 4-bit sources. UH messages are at most 64 bytes. Atomics are at most four bytes. Coherent B/C/E channels remain outside this profile. Native runtime qualification remains open. Supplied memory scoreboards use serial fixture traffic; concurrent overlapping memory operations need a project policy.

Roadmap notes: Add TileLink-UL/UH A/D cycle agents and SV components. Record Python tests and SV lint separately from runtime qualification.


## PR 463

[#463](https://github.com/riscPrint/risc-v-workstation/pull/463). Merged: 2026-11-13T02:16:22Z.

Title: feat(regress): verify pointer masking across privilege modes

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Add Ssnpm U-mode and Smmpm M-mode data tests with PMM readback. Support Sspm/Supm capability names only with explicit project controller declarations. Add tagged instruction-fetch checks: data masking must not mask fetch addresses. Keep the existing Smnpm cases and generic C1/Spike build path.

## Testing

- Pointer modules: six passed, zero skipped. All 54 new and nine existing programs passed Spike.
- Matrix/configuration checks after moving the generator: two passed, one native test deselected.
- RTL, BOOM, Sail, full Python suite, guest/debug masking interactions: NOT RUN.
- Final fast count below.

## Issues

Refs: #179.

Keep the issue open. Guest/debug interactions, M-mode tagged fetch and nonstandard environment controllers remain unsupported. No DUT result is claimed.

Roadmap notes: pointer suites now cover configured M/S/U controls, explicit Sspm/Supm controllers and tagged fetch faults. Guest/debug interactions and DUT validation remain open. ROADMAP.md and TODO.md were not edited.
772 passed, 5817 deselected in 81.13s (0:01:21)


## PR 464

[#464](https://github.com/riscPrint/risc-v-workstation/pull/464). Merged: 2026-11-13T03:05:44Z.

Title: feat(formal): search shortest counterexamples and export causes

Audit evidence label: unit tests only.

## Summary
Add `rvw formal shortest` and MCP for increasing-depth solver search on a captured BMC model with one assertion. Certify the first failing depth only when every smaller depth passed. Stop on unknown results. Preserve assumptions, captures, SBY jobs and traces.

Counterexample replay with successful SpinalTrace output now emits an agent-readable JSON dependency chain. Keep source locations, timestamps, observed values and accuracy limits. Missing graph data remains incomplete.

## Testing
- Replay, shortest search and explanation tests: 19 passed, 0 skipped, including native Yosys/SBY/Z3 shortest-depth search and replay tests. A later missing-graph test was added; the explanation file then passed 4 tests, overlapping the first run.
- Final required fast set: 808 passed, 6008 deselected, 0 skipped.
- Not run: full suite, BOOM build or simulation, long formal runs, native typed Spinal viewer navigation or CI wait.

## Issues
Refs: #60

Roadmap notes: Add shortest-depth solver search for single-assertion captures and JSON dynamic dependency chains. Multi-property shortest search, native typed/source viewer validation and general assumption adequacy remain open. The chain is trace evidence, not solver-proven counterfactual causality.


## PR 465

[#465](https://github.com/riscPrint/risc-v-workstation/pull/465). Merged: 2026-11-13T02:17:16Z.

Title: feat(sim): reverse step through validated checkpoint replay

Audit evidence label: unit tests only.

## Summary

Add `rvw sim reverse-step` and MCP `sim_reverse_step`. Validate native history identities, select the nearest checkpoint at or before an earlier instruction, restore into a fresh port, replay forward with a required time budget, check the reached count, then save stopped state. Report history limits. No waveform cursor is moved.

Roadmap notes: #191 gains CLI/MCP replay control. A project port must implement cancellation-aware replay. No bundled Spinal port implements it yet. Native reverse execution and C2 continuation qualification remain open. Execute the captured port source directly rather than using stale Python bytecode.

## Testing

- Targeted reverse and port tests: 3 passed, 0 skipped. Fixture port only.
- Fast set: 805 passed, 0 skipped, 5889 deselected in 85.08 seconds. `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`.
- NOT RUN: native reverse replay, VexRiscv restore, BOOM, full Python suite, GitHub CI.

## Issues

Refs: #191. This does not close the issue.


## PR 466

[#466](https://github.com/riscPrint/risc-v-workstation/pull/466). Merged: 2026-11-13T02:17:31Z.

Title: feat(privilege): add pmp epmp and physical boundary matrices

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Generate 394 base-PMP cases for TOR/NA4/NAPOT, permissions, lock, priority and MPRV. Add four separate Smepmp policy programs for MML, MMWP and RLB. Add physical first/last boundary probes with project-declared transfer counts and independent device state. Require independent PMA observations before the strict architectural check can earn a group.

## Testing

- Targeted tests: 27 passed, 0 skipped.
- Native Spike: 394 base-PMP and four Smepmp self-checks pass with nice and one-second per-program bounds.
- PMA: eight generated programs compile. Arbitrary project PMA needs a model/device adapter; no Spike or DUT PMA pass is claimed.
- Fast set after rebase: 805 passed, 5899 deselected, 0 skipped.
- NOT RUN: RTL builds/simulations, full Python suite, long formal or CI.

## Issues

Refs: #112
Refs: #138

Remaining: conflicting PMA regions, atomic/idempotency effects, the complete ePMP truth table, reset/lock observations and DUT qualification. Standard PMP coverage does not count as ePMP verification.

Roadmap notes: Add generic standard-PMP matrix generation, separate Smepmp policy programs and independent physical-boundary observations. Keep untested protection cases and DUT qualification open.


## PR 467

[#467](https://github.com/riscPrint/risc-v-workstation/pull/467). Merged: 2026-11-13T02:17:38Z.

Title: feat(wave): show spinal enum names from the design database

Audit evidence label: unit tests only.

## Summary

- `rvw wave changes|sample|find|seq --db DESIGN.db` (MCP `db`): signals with a Spinal enum database type (`State@seq[2]{idle=0,run=1}`) show element names. `changes` rows gain `enum`; `sample` adds `enums`; text output prints `0x1 (run)`.
- Expressions compare an enum signal with a string literal: `find WAVE "fsm_stateReg == 'run'" --db DESIGN.db`. An unknown element is an error listing the valid ones.
- `test_mcp_tools.py`: the tool count on main was stale (45 tools after other merges); update it.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_wave_typed.py rvw/tests/test_wave_search.py rvw/tests/test_wave_temporal.py rvw/tests/test_mcp_tools.py -q`: all passed, 0 skipped (enum fixture from the committed cluster database).
- Fast set: 772 passed.
- Not run: interactive Surfer/SpinalWaves checks (#83 stays open).

## Issues

Refs: #43, #83. Typed enum values are now available to agents in the CLI/MCP without the GUI. Remaining: Bundle/Vec grouping in CLI output, interactive viewer validation (#83), native package qualification on other hosts (#43).

Roadmap notes: waves area — `rvw wave --db` shows Spinal enum element names and accepts `'element'` literals in expressions.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 468

[#468](https://github.com/riscPrint/risc-v-workstation/pull/468). Merged: 2026-11-13T02:17:55Z.

Title: feat(cov): guide candidates with qualified rtl event feedback

Audit evidence label: unit tests only.

## Summary

Add project-owned RTL event recipes to `rvw cov campaign` and `cov_campaign`. Bind recipes to exact sampling-plan and generated-RTL hashes. Use a small UCB policy over newly observed events. Keep ISA hits separate. Continue bounded event search after ISA saturation. Vary seeded free integer operands while preserving the selected semantic predicate.

Require a complete strict C1/Spike pass before sampling RTL. Require a C1 receipt binding ELF, full RVFI trace, sample file, sampling plan and RTL. Missing hooks, stale receipts, incompatible/incomplete samples and repeated samples earn no reward. Preserve policy history and sample hashes on resume.

## Testing

Targeted guidance, campaign, pinned solver and RTL sampler tests: 51 passed, zero skips. Tests cover all 170 integer goals at each XLEN, seeded variation, saturation feedback, real sampler receipt integration and stale/missing evidence rejection. Fast set: 805 passed, 5932 deselected, zero skips.

NOT RUN: native DUT event campaign, independent native sampler mutation campaign, held-out event goals, paired random comparison, full suite or CI. The earlier native compiler smoke predates free-operand variation and is not claimed for this change.

## Issues

Refs: #353

Keep #353 open. Actual project sampling hooks, native held-out mutation evidence and measured CPU-hour comparison remain. This search uses the existing integer and sequence families. It cannot create arbitrary pipeline stress programs. No measured closure improvement or PSS conformance is claimed.

Roadmap notes: Coverage-guided candidate selection now consumes qualified exact-instance RTL event and sequence samples. Missing native hooks remain unsupported. Reports keep architectural and RTL evidence separate.


## PR 469

[#469](https://github.com/riscPrint/risc-v-workstation/pull/469). Merged: 2026-11-13T02:17:46Z.

Title: feat(uvm): add register predictor and standard ral sequences

Audit evidence label: unit tests only.

## Summary
Add normalized register transfers, a frontdoor adapter and an explicit predictor. Add standard UVM reset, bit-bash and access sequences. Refuse access checks with no backdoor. The generated RAL fixture uses a custom backdoor and completes 524 transfers.

Roadmap notes: RAL now has reusable adapters, predictor and standard sequences. Native evidence covers a four-word fixture. Physical peripheral qualification remains open.

## Testing
- Register generator unit tests: 9 passed, 0 skipped.
- Native Verilator 5.052 RAL test: 1 passed, 0 skipped. Uses pinned Accellera UVM with UVM_NO_DPI. Build and run stay below two minutes.
- Required fast set passed. No full Python suite, BOOM run or CI wait.

## Issues
Refs: #296. Live CPU integration and C4 acceptance remain open.


## PR 470

[#470](https://github.com/riscPrint/risc-v-workstation/pull/470). Merged: 2026-11-13T02:18:26Z.

Title: feat(formal): match registers across hierarchy changes

Audit evidence label: ran on seeded RTL fixture.

## Summary

Match relocated registers by a unique leaf name and equal width after manual and exact-name pairs. Keep ambiguous names unmatched. Keep every state bit inside the output proofs. The mapping adds no assumptions.

## Testing

- Native matching tests: 4 passed. Equal relocated RTL proves. An output mutant produces a counterexample.
- Existing equivalence tests with the first three matching unit tests: 21 passed.
- Required fast set after rebase: 805 passed, 5926 deselected.
- NOT RUN: BOOM builds, BOOM proofs, full Python suite, long formal jobs.

## Issues

Refs: #18.

Roadmap notes: Add unique leaf-name register matching across hierarchy changes. State encoding relations, blackbox contracts, generated clocks, mapped replay and BOOM proof reproduction remain open. This change does not complete the epic.


## PR 471

[#471](https://github.com/riscPrint/risc-v-workstation/pull/471). Merged: 2026-11-13T02:18:56Z.

Title: feat(lint): emit cdc checks from spinal clock-domain data

Audit evidence label: unit tests only.

## Summary

- New `SpinalChecks/src/main/scala/spinalchecks/CdcChecks.scala`: `CdcChecks.install(config)` adds an elaboration phase before `PhaseInsertChecks`. It finds every register with Spinal's `crossClockDomain` tag whose data comes, through plain copies, from a register in another clock, and declares:
  - `cdc.gray`: a multi-bit source changes at most one bit per source clock;
  - `cdc.pulse_width`: a one-bit source holds each value for `ceil(settle * f_src / f_dst)` source cycles, when both domains have a Spinal `FixedFrequency`.
  The checks are `DeclaredRule`s, so ids, waivers, Assert/Monitor modes and the report work as for other SpinalChecks rules.
- `rvw lint` reads Spinal `setSynchronousWith` (`ClockSyncTag` signal tags) as a `declared_synchronous` clock relationship.
- Docs: SpinalChecks README section and the lint README.

## Testing

- `scripts/with-lock.sh sbt nice -n 10 sbt -batch "testOnly spinalchecks.CdcChecksSpec"` (in `SpinalChecks/`): 1 test passed. It runs three Verilator simulations: legal Gray bus and slow level (no firing), binary bus through `BufferCC` (`cdc.gray` fires), fast toggling level (`cdc.pulse_width` fires).
- `rvw/.venv/bin/python -m pytest rvw/tests/test_lint_cdc.py -q`: 13 passed. Extracted fixture test: 17 passed.
- Fast set: 805 passed, 5923 deselected.
- Not run: full SpinalChecks sbt suite, formal runs of the new checks, BOOM.

## Issues

Refs: #22. Remains: sampled digital checks only (no metastability, setup/hold or phase model); handshake/toggle data-stability checks inside Spinal are not added yet.

Roadmap notes: LINT — "checks Spinal can emit from clock-domain info" started: SpinalChecks `CdcChecks` adds Gray and pulse-width checks from `crossClockDomain` tags and `FixedFrequency`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 472

[#472](https://github.com/riscPrint/risc-v-workstation/pull/472). Merged: 2026-11-13T02:20:01Z.

Title: feat(arch): model integer rename elimination and immediate fusion

Audit evidence label: unit tests only.

## Summary
Model move elimination, zero elimination and adjacent LUI/AUIPC+ADDI execution fusion in the C2 engine. Elimination bypasses issue and new physical-register allocation. Move dependencies remain intact. Both fused instructions retain ROB and commit entries. Project flags select each policy.

## Testing
69 targeted OoO tests and 805 fast tests passed. No RTL simulation, BOOM build, native gem5 run or full suite ran. Real free-list alias reclamation, macro-op decode fusion, memory renaming and fault recovery are not modeled.

## Issues
Refs: #362. This adds own-model policies; native gem5 acceptance remains open.

Roadmap notes: Configurable rename elimination and bounded immediate execution fusion are available. Native rename validation and complete alias handling remain open.


## PR 473

[#473](https://github.com/riscPrint/risc-v-workstation/pull/473). Merged: 2026-11-13T02:20:46Z.

Title: feat(debug): add openocd and gdb interoperability campaign

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
- `rvw debug interop`: GDB starts OpenOCD over a pipe (`gdb_port pipe`) against a remote_bitbang target. The target is a running simulation (`--port`), or the reference model that `rvw debug serve` serves for a profile (`--profile`).
- A GDB Python script checks each operation by its effect: `load` (the entry word equals the ELF bytes), register and memory writes (read back after the caches are flushed), software and hardware breakpoints (stop pc and loop counter), `stepi` and the jump step, a watchpoint (counter advanced, pc after the store), and `monitor reset halt` (pc equals the declared reset pc).
- C3 results (`debug-interop`) record the GDB and OpenOCD versions in `clients`. A connection without these effects is not a pass. A GDB error belongs to the first check it did not reach. Unreached checks are inconclusive.
- Fixture `rvw/tests/fixtures/debug/interop.S`. MCP tool `debug_interop`.

## Testing
- `rvw/.venv/bin/python -m pytest rvw/tests/test_debug_dm.py -q`: 36 passed (assessment, C3 attribution, OpenOCD config).
- Native (`rvw/tests/test_debug_dm_native.py -k interop`, OpenOCD 0.12.0+dev-00519, GDB 18.1 from the Homebrew `riscv64-elf-gdb` bottle, Spike 1.1.1-dev): 2 passed.
  - Reference model: every check passes.
  - Spike: 7 checks pass. Hardware breakpoint and watchpoint fail. Spike resets each trigger to `tdata1.type` 15, and this OpenOCD skips type-15 triggers ("Couldn't find an available hardware trigger"). The test pins this known outcome.
- Fast set: 808 passed.
- Not run: no core RTL target.

## Issues
Closes: #161

Roadmap notes: Debug area. OpenOCD/GDB interoperability is now checked by effect against the reference model and Spike. Finding: OpenOCD 0.12.0+dev cannot use Spike's type-15 reset triggers for hardware breakpoints or watchpoints.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 474

[#474](https://github.com/riscPrint/risc-v-workstation/pull/474). Merged: 2026-11-13T02:21:02Z.

Title: feat(sim): resolve captured historical adapter versions

Audit evidence label: unit tests only.

## Summary

Select captured project simulation adapters by exact revision or a version marker. Negotiate API 1 before launch. Pin script interpreters through C8. Record version, API, revision and manifest/executable hashes in supplied source identity. Unsupported revisions return no simulation result and remain bisect skips.

Roadmap notes: #335 gains captured historical adapter resolution in debug launches used by bisect. Projects must supply the manifest and adapters in each captured core revision. Gate integration, actual historical core adapters and core-side stability agreement remain open. #45 remains unqualified: no real core history was executed and no guilty commit is claimed.

## Testing

- Targeted resolver, debug adapter layout and shebang capture: 30 passed, 0 skipped.
- Fast set after rebase: 805 passed, 0 skipped, 5966 deselected in 99.82 seconds. `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`.
- Checks include exact-revision precedence, captured markers, unsupported API, escaped paths, legacy behavior, selection identity and refusing launch of an unsupported revision.
- NOT RUN: real historical core bisect, historical gates, BOOM, full Python suite, GitHub CI.

## Issues

Refs: #335, #45. Neither issue is closed.


## PR 475

[#475](https://github.com/riscPrint/risc-v-workstation/pull/475). Merged: 2026-11-13T02:21:19Z.

Title: feat(regress): model decoded iommu translation scenarios

Audit evidence label: unit tests only.

## Summary

Add a bounded decoded IOMMU model, seeded scenario generator, CLI, MCP tools and device-side exchange callback. Cover device/process contexts, first/second translation including G translation of first-stage PTE reads, isolation, translation caching, invalidation, fault/command queues and page MSI remapping. Bind independent observations to C1 and the scenario hash before consistency can be reported. Missing evidence remains inconclusive.

Record the pinned upstream C reference revision as metadata. This does not execute or qualify that model.

## Testing

- Targeted model, generated scenarios, C1 binding, CLI and MCP declarations: 11 passed, zero skipped.
- Fast set count below.
- Native IOMMU C reference, RTL, BOOM, Sail and full Python suite: NOT RUN. Native smoke testing remains Spike-only.

## Issues

Refs: #188.

Keep this issue open. Raw DDT/PDT/register conformance, ATS/PRI, architectural MSI encodings, atomic A/D and native C-reference/DUT transport integration remain unsupported. The model uses decoded project data and descriptive faults. It is not full IOMMU conformance.

Roadmap notes: reusable decoded IOMMU scenarios and a device-agent API now check translation/isolation/queues/MSI behavior. Full raw architectural integration remains open. ROADMAP.md and TODO.md were not edited.
805 passed, 5971 deselected in 99.00s (0:01:38)


## PR 476

[#476](https://github.com/riscPrint/risc-v-workstation/pull/476). Merged: 2026-11-13T02:21:22Z.

Title: feat(formal): select replay states and check finite fair progress

Audit evidence label: unit tests only.

## Summary

Select simulation replay states by declared coverage-hole targets bound to the captured waveform SHA-256. Rotate engines across selected states. Preserve bounded results, explicit restrictions and inconclusive campaign status. Add the `formal_swarm` MCP tool.

Add `formal model-live` and MCP for exact recurrent-progress checks on explicit finite graphs under generalized state-justice fairness. Report fair nonprogress components, infeasible fairness and deadlocks. This does not prove RTL liveness or certify RTL-to-model translation.

Record native rIC3 qualification and make external EBMC dependency fetches shallow.

Roadmap notes: coverage-directed state priorities and engine diversity are available. Explicit-model fairness checks are available. Native RTL liveness-to-safety, k-liveness, automatic coverage extraction, seed diversity, IC3 lemma reuse, finer RTL abstraction and broad capacity evidence remain open.

## Testing

- Targeted selection, fairness, swarm, installer and reference tests: 19 passed, 0 skipped. This includes short native replay.
- Fast set: 805 passed, 5973 deselected, 0 skipped. `/tmp/deep-state-fast.log`.
- Native rIC3 1.5.2: safe counter proved, seeded fault found, both pinned HWMCC cases proved. Two-case total wall time 2.194 s. `/tmp/rvw-deep-ric3-{counters,hwmcc}/result.json`.
- A further native rIC3 BMC check found a version mismatch with SBY's old bounded flags. It reports error; no bounded qualification is claimed. A follow-up will fix this.
- EBMC build in progress. Full Python suite, BOOM jobs, broad HWMCC, open-core property campaigns and CI waits NOT RUN.

## Issues

Refs: #21, #294. Both epics remain open.


## PR 477

[#477](https://github.com/riscPrint/risc-v-workstation/pull/477). Merged: 2026-11-13T02:23:41Z.

Title: feat(memory): search scalar axiomatic execution graphs

Audit evidence label: unit tests only.

## Summary
Add independent scalar RVWMO/Ztso candidate execution search for annotated C2/2 runs. Build co/rf/fr/po-loc/ppo relations, check both acyclicity axioms and RMW atomicity, and return a witness or a bounded inconclusive result. Require complete project dependency observations and cross-check annotations against RVFI instruction identity, masks and bytes. Add CLI/MCP interfaces and seeded RV64 concurrent assembly fragments with races, locks, AMOs and fences.

## Testing
22 targeted Python tests passed, no skips. Nine targeted Scala tests passed, no skips or cancellations. Native GCC assembled three seed-7 RV64 hart fragments. The fast Python set passed: 805 passed, no skips.

NOT RUN: native herd differential validation, Spike or RTL execution of generated programs, production multi-hart integration, BOOM builds, full Python suite. The scalar profile excludes mixed-size overlaps, device memory, faulting executions and external writers. Dependency completeness must be supplied by the project. No full-core memory-model qualification is claimed.

## Issues
Refs: #90, #91, #97. Production adapters still need complete dependency capture. Generated fragments need project linking, completion detection, execution and trace capture.

Roadmap notes: arbitrary supported scalar executions can now be checked without a litmus-specific expected-outcome list. The seeded generator supplies project-ready assembly fragments. Native model differential validation and RTL campaigns remain open.


## PR 478

[#478](https://github.com/riscPrint/risc-v-workstation/pull/478). Merged: 2026-11-13T02:22:13Z.

Title: feat(vip): add uart serial agents and fifo reference

Audit evidence label: unit tests only.

## Summary
Add UART agents in Python/cocotb and SystemVerilog UVM. Support 5 to 9 data bits, parity, one or two stop bits, integer baud timing, error observations and error injection. Add both endpoint drivers, passive monitors, coverage, scoreboard hooks and seeded good/bad serial echo fixtures. Add a Python receive FIFO reference with software-read and observed-status checks for level, overrun, errors and IRQ threshold.

## Testing
- Targeted Python: 26 passed.
- Pinned Accellera UVM, agent, interface, fixture and test top: Verilator lint passed with warnings.
- 805 passed, 5993 deselected in 84.62s (0:01:24)
- NOT RUN: UVM runtime build, UVM simulation, cocotb RTL simulation, hardware FIFO/IRQ tests, BOOM jobs and full Python suite.

## Issues
Refs: #202

Keep #202 open. Native serial, FIFO and IRQ qualification needs a project UART and register map. The provided FIFO policy is explicit: drop newest on overflow, sticky errors, configured level threshold. Analog timing, baud drift and flow-control pins are outside this profile.

Roadmap notes: Add UART cycle agents, SV components, serial echo fixtures and reference FIFO/IRQ hooks. Keep native UART and hardware FIFO/IRQ qualification open.


## PR 479

[#479](https://github.com/riscPrint/risc-v-workstation/pull/479). Merged: 2026-11-13T02:22:35Z.

Title: feat(cov): extend pinned encoded and integer operand domains

Audit evidence label: unit tests only.

## Summary

Extend pinned opcode coverage to vector register fields, compressed aliases, scalar rounding fields, atomic ordering and bounded vector control fields. Use the exact captured argument widths. Keep reserved raw rounding encodings in the expected denominator. Extend integer operand-value classes to A, Zba, Zbb, Zbc, Zbs and Zicond source families. Never use integer RVFI values for FP/vector data.

## Testing

Targeted domain, pinned-plan, semantic and semantic-form tests: 67 passed, zero skips. Includes an end-to-end pinned vector encoding fixture and retained unobserved domains. Fast set: 805 passed, 6013 deselected, zero skips.

NOT RUN: native DUT or reference campaigns, exhaustive version-bound spec catalog review, full suite or CI.

## Issues

Refs: #82

Keep #82 open. Complete version-bound semantic catalogs for all configured extensions, FP/vector operand data hooks, privileged-event obligations and exhaustive legal/illegal/unavailable crosses remain. Encoded-field coverage is not ISA compliance.

Roadmap notes: More pinned scalar, compressed and vector encoded fields now have fixed expected bins. Scalar integer operand families include A and ratified Zb/Zicond families. Unseen and reserved encoding bins remain in the denominator.


## PR 480

[#480](https://github.com/riscPrint/risc-v-workstation/pull/480). Merged: 2026-11-13T02:22:38Z.

Title: feat(cosim): exchange rvvi and spike observation streams

Audit evidence label: unit tests only.

## Summary
Add C2 exchange with RVVI-TEXT 0.5 and Spike commit logs through CLI and MCP. Preserve full C2 in vendor state or comments. Check mapped retirement fields against preserved state on import. Sparse logs produce explicit partial observations and cannot earn an architectural match. Refuse unsupported Spike effects.

## Testing
- Targeted exchange tests: 4 passed.
- Fast set: see local run log; no native simulator is needed for conversion.
- NOT RUN: full RVVI latching/conformance suite, external simulator round trip, RTL simulation.

## Issues
Refs: #189
Remaining: full RVVI element and latching support, richer raw Spike effects.

Roadmap notes: Co-simulation has a bounded RVVI-TEXT 0.5 and Spike log exchange path. Conversion is not independent checking. Complete round trips require the vendor C2 state extension.


## PR 481

[#481](https://github.com/riscPrint/risc-v-workstation/pull/481). Merged: 2026-11-13T02:22:51Z.

Title: feat(formal): check bounded iterative datapath transactions

Audit evidence label: ran on seeded RTL fixture.

## Summary

Check one variable-latency datapath transaction with `--max-latency`. Compare result bits and optional flags at the first done event. Require completion within the bound. Keep operands stable after a one-clock reset and start pulse.

Add `--binding` and a small Python binding library for project module and port names. Bindings retain all width, direction, driver and unsupported-cell checks. Expose both options through `formal_datapath`.

## Testing

Native targeted tests: 14 passed. Include iterative shift/add multiplication, repeated-subtraction division, renamed project ports, a wrong-result mutant and an insufficient completion bound. Existing fixed-latency, C safety and RISC-V M model tests also pass.

Required fast set after rebase: 808 passed, 5977 deselected.

NOT RUN: BOOM builds, full Python suite, long formal jobs, native FPU or SoftFloat DUT qualification.

## Issues

Refs: #19.

Roadmap notes: Add handshake-bounded iterative datapath checking and project port bindings. Streaming transactions, backpressure, FPU qualification, bit-manipulation and scalar crypto model coverage remain open. Keep the epic open.


## PR 482

[#482](https://github.com/riscPrint/risc-v-workstation/pull/482). Merged: 2026-11-13T02:54:29Z.

Title: feat(checks): generate typed simple-bus assertion bindings

Audit evidence label: ran on seeded RTL fixture.

## Summary

Add generated AXI4-Stream stability, APB setup/wait and bounded AHB-Lite address/error monitors. Add `formal buses` and `formal_buses` MCP to derive top-component ports and instance binds from recorded SpinalDB bundle types. Missing clock associations and unsupported cases remain explicit. No bindings returns no_checks and exit 3.

Full protocol compliance, AHB burst/data rules, deeper hierarchy and automatic AXI4/Lite/TileLink database binding remain open. Existing AXI4 and TileLink monitors remain separate.

## Testing

- Combined native bus/resource monitor, recorded-format synthetic database and command-reference tests: 36 passed, 0 skipped. SpinalDB discovery uses simple class names and the AXI4-Stream payload parent.
- Verilator 5.052 accepted generated APB instance binds against a tiny synthetic Top. Elaboration took 0.008 seconds. This is fixture integration only.
- Last pushed revision fast set: 821 passed, 0 skipped.
- A later local rebase is blocked: 820 passed, 1 failed. The inherited release-hygiene finding is rvw/tests/cosim/test_adjudicate.py:51:personal_path. That file is outside this PR and was not edited. The failing rebase was not pushed.
- NOT RUN: SBY proofs, Spinal compile, extracted real-core binding, BOOM simulation, full Python suite.

## Issues

Refs: #66

Roadmap notes: Add simple-bus generated safety templates and bounded typed database binding. Retain full protocol, deeper hierarchy, real-design and coherent-channel gaps.


## PR 483

[#483](https://github.com/riscPrint/risc-v-workstation/pull/483). Merged: 2026-11-13T02:23:33Z.

Title: feat(csim): qualify tage-sc-l against pinned cbp 2016 reference

Audit evidence label: unit tests only.

## Summary

- `rvw csim qualify` and MCP `csim_qualify`: compare a csim direction study with a pinned external reference predictor on the same traces. References: CBP-5 (2016) TAGE-SC-L 64 KB and 8 KB by A. Seznec (`AndreSeznecLimited.tar.gz`, sha256 `5ed93324…ace181`). The archive is fetched into the csim cache, checked against the pin, never enters the repository, and is built with an owner-written harness (`ComponentSims/qualify/ref_harness.cc`) and type shim.
- One recorded guard on the cached copy (`if (NOSKIP[i])` → `if (i <= NHIST && NOSKIP[i])`): the upstream allocation loop reads past its arrays (found with AddressSanitizer; it crashed the 8 KB predictor on real traces). In-range accesses do not change. The report carries the patch.
- Matched studies `ComponentSims/examples/tage-sc-l-64kb.json` (63.8 KiB) and `tage-sc-l-8kb.json` (8.5 KiB) with their structural differences listed.
- `rvw csim convert spike` / `--format spike`: Spike `-l --log-commits` logs to `rvw.csim-trace/1` (branch kinds, loads/stores with decoded sizes, optional values).
- Contracts and README updated (qualification table, `rvw.csim-qualify/1`, Spike input).

Measured (Spike traces of qsort, dhrystone, median, rsort, towers, spmv; whole program): all 12 rows are within 10% relative MPKI of the reference; per-branch prediction agreement 0.89–1.00. Example: qsort 64 KB reference 40.86 MPKI, csim 42.08.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_csim_formats.py rvw/tests/test_csim.py -q` — 24 passed (Spike converter; qualification against a stand-in reference archive with exact agreement; pin mismatch refused).
- `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q` — 806 passed after rebase.
- Native run of `rvw csim qualify` against both real references on six Spike benchmark traces (table in `ComponentSims/README.md`).
- Not run: CBP 2016 trace sets (their server did not answer), long traces, full slow suite, CI not awaited.

## Issues

Refs: #351 — done here: pinned independent reference, source revision (sha256) and storage configurations, MPKI and per-branch comparison. Remaining: published long reference traces; internal state transition comparison is not possible with different hashing.

Roadmap notes: Component simulators: TAGE-SC-L qualified against the pinned CBP-5 64 KB/8 KB references within 10% MPKI on six benchmark traces; Spike commit logs accepted as input.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 484

[#484](https://github.com/riscPrint/risc-v-workstation/pull/484). Merged: 2026-11-13T02:24:04Z.

Title: feat(bugmem): add bug-pattern memory for failure reports

Audit evidence label: unit tests only.

## Summary

- New tool `rvw bugmem` (`rvw/src/rvw/bugmem/`): `add`, `match`, `list`, `evaluate`, with MCP `bugmem_add`, `bugmem_match`, `bugmem_list`, `bugmem_evaluate`.
- Signatures are weighted features from an `rvw bundle` summary (or a C1 result): C3 signature, assertion file, suspected unit, oldest unretired instruction class, traps, stalled channels, last function, spin loop, old open requests, message words without numbers.
- `match` ranks stored failures by weighted Jaccard similarity and prints shared features plus the stored cause, fix and verified scope. It says "similarity, not diagnosis"; status `candidates` or `no_match`.
- Store: JSON lines (`rvw.bugmem/1`) outside the repository (`--store`, `RVW_BUGMEM`, `~/.local/share/rvw/bugmem.jsonl`), with the report SHA-256 and recorded source/core/config/ELF identity. Duplicate report bytes are refused; a cause is required.
- `evaluate`: leave-one-out top-1/top-k accuracy over labelled records; single-occurrence labels count as `unmatchable`, not misses.
- README, AGENTS.md Layout row, command reference.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_bugmem.py -q`: 4 passed, 0 skipped.
- `test_command_reference.py`, `test_release_hygiene.py`, `test_mcp.py`: 49 passed.
- Fast set: 808 passed.
- Not run: matching accuracy on real held-out defects (no labelled defect set exists yet).

## Issues

Refs: #32. Stores failure signatures with causes, fixes and scope with source identities, and measures leave-one-out accuracy. Remaining: build a held-out set of real defects and tune the weights on it.

Roadmap notes: debug area — new `rvw bugmem` tool (bug-pattern memory, generic). Components table needs a row: `rvw/src/rvw/bugmem/`, generic, status: first increment.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 485

[#485](https://github.com/riscPrint/risc-v-workstation/pull/485). Merged: 2026-11-13T02:24:13Z.

Title: feat(sim): load project device models through native dpi

Audit evidence label: unit tests only.

## Summary

Load project-owned native device libraries through a versioned ABI. Supply independent handles, JSON configuration, seeded initialization, MMIO, cycle updates, interrupts and versioned snapshot/restore callbacks. Add DPI-C bindings with explicit failure status and no C++ exceptions crossing into RTL.

Roadmap notes: #295 gains a native device plugin/DPI interface. #187 gains a library boundary usable by project SystemC models. No native SystemC/TLM adapter, VPI callback binding, standard UART/CLINT/PLIC/block models or Linux-boot device set is delivered. Projects must bind library/configuration identity and device state into the native envelope. Those integrations remain open.

## Testing

- Native plugin and real Verilator DPI testbench: 2 passed, 0 skipped, 10.15 seconds under the vex lock and nice. Independent handles, seeded MMIO, ticks, interrupt delivery, fresh-device snapshot/restore, malformed state and DPI errors are checked.
- Fast set: 808 passed, 6028 deselected in 73.36s (0:01:13). Command: `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`. Zero skips.
- NOT RUN: SystemC/TLM, VPI, Linux boot, VexRiscv device integration, BOOM, full Python suite, GitHub CI.

## Issues

Refs: #295, #187. Neither issue is closed.


## PR 486

[#486](https://github.com/riscPrint/risc-v-workstation/pull/486). Merged: 2026-11-13T02:25:32Z.

Title: feat(lint): import clock domains from verilog for cdc and rdc

Audit evidence label: unit tests only.

## Summary

- `rvw query build-hdl` (`rvw/src/rvw/query/hdl.py`) now writes `clock_domains` from Yosys flip-flop cells: clock and reset nets followed through ports to toplevel inputs, `clock_edge` from `CLK_POLARITY`, `ASYNC` for `$adff`/`$adffe`/`$adlatch`, `SYNC` for `$sdff*`, polarity and `reset_value`. Registers get `clock_domain_id`; roots get `clock_role`.
- Clock and reset pins are no longer data edges (the same as Spinal databases). Hidden Yosys temporaries become aliases of the one visible name of a bit; only visible names become registers.
- `rvw lint`: the shared graph view drops hidden alias pairs for `yosys-verilog` databases, and `structural.py` uses that view (one edge map for CDC, RDC and depth checks). CDC/RDC classes now work on non-Spinal Verilog.
- Shared format: no new tables or columns. `build-hdl` databases fill existing columns (`clock_domains`, `signals.clock_domain_id`, `reset_value`, `clock_role`) and drop clock/reset `sel` edges. Documented in `SpinalDB/README.md`.

## Testing

- With native Yosys: `rvw/.venv/bin/python -m pytest rvw/tests/test_query_hdl.py -q`: 8 passed, 2 skipped. The new test builds a two-clock Verilog design and checks the domains, an async reset, a `sync_2ff` class and no `rdc.reset_as_data`.
- `rvw/.venv/bin/python -m pytest rvw/tests/test_lint*.py -q`: all passed (extracted fixtures: 17 passed with `RVW_LINT_FIXTURES`).
- Fast set: 809 passed, 6101 deselected.
- Not run: large Verilog designs, the full Python suite.

## Issues

Refs: #22 (non-Spinal domain import). Remains: synchronous resets in plain mux logic stay data; no memories or blackboxes in the HDL importer.

Roadmap notes: LINT — CDC/RDC now runs on non-Spinal Verilog through `rvw query build-hdl` clock-domain import.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 487

[#487](https://github.com/riscPrint/risc-v-workstation/pull/487). Merged: 2026-11-13T02:25:43Z.

Title: feat(cosim): load declared spike extension libraries

Audit evidence label: unit tests only.

## Summary
Load project-declared Spike extension libraries from captured copies. Register each named factory before ELF execution. Use existing C2 CSR snapshots for custom CSR comparison. Reject these libraries for Sail.

## Testing
- Declaration/capture and native custom instruction tests: 7 passed. Native test checks literal result 7 and detects altered DUT value 8.
- Targeted platform and declaration tests: 54 passed.
- Fast set after rebase: 809 passed, 6121 deselected.
- Native shim rebuilt with the installed Spike headers and library.
- NOT RUN: RTL simulation, custom CSR native fixture, third-party extension campaigns.

## Issues
Refs: #143
Remaining: custom operand layouts for reference trace generation, native custom CSR fixture, broader independent custom ISA cases.

Roadmap notes: Cosim can load project reference extensions with captured library identity. Custom state can use C2 CSR snapshots. This is a first integration, not custom ISA qualification.


## PR 488

[#488](https://github.com/riscPrint/risc-v-workstation/pull/488). Merged: 2026-11-13T02:25:52Z.

Title: feat(formal): replay timed events with simulation assertion counts

Audit evidence label: ran on seeded RTL fixture.

## Summary
Replay explicit timestamped input events through Icarus or Verilator. Run the finite SVA set with per-property assertion/assumption/cover counts. Retain unrelated clocks, async reset and asynchronous property-input events. Write C1 results and monitor point records consumable by rvw cov. Preserve four-state X observations with Icarus; refuse X checks on two-state Verilator.

## Testing
- Native replay tests: 7 passed across Icarus and Verilator, including legal/faulted SVA, async events/reset, four-state X and C1 coverage import.
- Finite frontend regression checks: 8 passed, 38 deselected, including native BMC integration.
- Fast set: retained local result before push.
- NOT RUN: full Python suite, BOOM builds/simulation, long formal jobs, full simulator-region qualification, arbitrary solver-state replay, GitHub CI wait.

## Issues
Refs: #46, #61

Events are explicit input sequences, not arbitrary from-sim state loading. Data/reset changes must be at a distinct timestamp from property clock changes. Finite simulation does not discharge future obligations. General asynchronous property expressions and additional async state types remain open.

Roadmap notes: add timestamped multi-clock native simulation and finite-SVA counts in C1 plus rvw cov monitor-point import. Keep formal replay/state loading and full SVA partial.


## PR 489

[#489](https://github.com/riscPrint/risc-v-workstation/pull/489). Merged: 2026-11-13T02:26:04Z.

Title: feat(privilege): add versioned interrupt controller models

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Add versioned IMSIC/APLIC reference devices and generated register programs. Add ACLINT pending-state programs and current fast-interrupt Smnip threshold save/restore programs. Pin AIA 1.0, fast-interrupts v0.20 at b623d1262ed40a255fd290333d8e0c6d0c44b2e8, and ACLINT v1.0-rc4 at 4e570bfd3201f2c09e5afd290b5091526b0f099a in project examples. The v0.20 source says Stable and uses ACLIC/Smnip names. No frozen-status claim is made.

Select an explicit Python reference backend where the native Spike platform lacks these devices. Reports say model-based, bind model-source hashes and cannot earn DUT groups. Keep older incompatible CLIC drafts separate.

## Testing

- Targeted Python tests: 32 passed, 0 skipped.
- All 14 generated controller programs compile with RISC-V GCC.
- Python reference: 14 model-based self-checks pass. These are not Spike or DUT results.
- Fast set: 808 passed, 6041 deselected, 0 skipped.
- NOT RUN: RTL builds/simulations, full suite, long formal or CI.

## Issues

Refs: #158
Refs: #165
Refs: #186

Remaining: guest-file and full virtualization campaigns, APLIC level-to-MSI conversion, vector entry, asynchronous preemption and DUT qualification. The small model rejects unsupported level-to-MSI calls. No issue is closed.

Roadmap notes: Add pinned controller reference models and register campaigns, with explicit model-based evidence. Retain unsupported controller features and project/DUT integration.


## PR 490

[#490](https://github.com/riscPrint/risc-v-workstation/pull/490). Merged: 2026-11-13T02:27:01Z.

Title: feat(formal): check named weak fairness in coherence graphs

Audit evidence label: unit tests only.

## Summary
Add named weak-fairness SCC checks for each finite coherence request target. Include environment stutter. Separate scheduler starvation excluded by fairness from fair retry/noncompletion cycles. Expose the checker through the existing model script's --fair option.

## Testing
Five targeted Python tests passed. Five existing coherence model unittest tests passed. Native Python explored the baseline and seeded retry/lost-ack/stale-data cases. The fast Python set passed: 809 passed, no skips.

NOT RUN: TLC/Murphi cross-checks, RTL liveness, BOOM builds, full Python suite. The model remains a finite whole-message two-agent/one-home abstraction. Channel queues, MESI/MOESI profiles and real TileLink-C refinement remain open.

## Issues
Refs: #128, #361. Queue/resource/directory extensions and independent model cross-checks remain open.

Roadmap notes: coherence progress now has named weak-fairness SCC checks with explicit finite scope and budget outcomes. No general fair RTL liveness claim is made.


## PR 491

[#491](https://github.com/riscPrint/risc-v-workstation/pull/491). Merged: 2026-11-13T02:26:41Z.

Title: feat(sim): report recorded native build and run costs

Audit evidence label: unit tests only.

## Summary

Add `rvw sim profile` and `sim_profile` MCP. Report recorded C1 phase costs, cached state, counters, derived throughput, native/result identity and missing measurements. List PATH discovery with clean `not_installed` for missing Arcilator/CIRCT/ccache tools. Print explicit two/four-thread and split flag profiles without applying them or assigning them to recorded results.

Roadmap notes: #74/#344 gain a cost report. Captured PGO, hierarchy bridge integration, ccache trials, separate Scala/RSS instrumentation and native performance campaigns remain open. #345 remains open: the report is not an Arcilator engine, lowering integration or installer. No speed improvement is claimed.

## Testing

- Targeted report tests: 2 passed, 0 skipped. Missing and invalid measurements stay absent; error status stays visible; profile_applied remains false.
- Fast set after rebase: 809 passed, 0 skipped, 6117 deselected in 50.51 seconds. `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`.
- PATH inspection found Verilator/Icarus and no arcilator, circt-verilog or ccache.
- NOT RUN: Arcilator native lowering, PGO, hierarchy, ccache, performance trials, BOOM, full Python suite, GitHub CI.

## Issues

Refs: #74, #344, #345, #295. No issue is closed.


## PR 492

[#492](https://github.com/riscPrint/risc-v-workstation/pull/492). Merged: 2026-11-13T02:28:43Z.

Title: feat(formal): hunt bounded bugs with engine and seed diversity

Audit evidence label: unit tests only.

## Summary

Add `formal bug-hunt` and MCP with increasing BMC bounds, engine diversity and rIC3 seed diversity. Freeze pinned RTL once. Retain attempts and unstarted tasks. Stop on a concrete failure. A complete safe schedule remains inconclusive.

Adapt older SBY bounded flags to the qualified rIC3 1.5 CLI. Preserve native exit status and output. Clear inherited OSS CAD Suite Python launcher settings in the wrapper. Record its hash.

Add EBMC build prerequisites and macOS deployment-target compatibility to the external installer.

Roadmap notes: bounded engine/seed search is available. General RTL liveness, IC3 lemma reuse, finer counter/RAM/UF abstractions and broad full-block capacity remain open. No epic closure or parity claim.

## Testing

- Targeted hunt, compatibility, installer, portfolio and reference tests: 18 passed, 0 skipped.
- Fast set passed; exact counts are in `/tmp/deep-hunt-fast.log`.
- Native rIC3 BMC, depth 20 and seed 7: bounded success on safe counter; concrete failure on seeded fault. `/tmp/rvw-deep-ric3-bmc-after3-{counter,fault}/result.json`.
- Native bug-hunt: six bounded safe tasks completed with inconclusive campaign status. Fault campaign stopped at the first deeper rIC3 counterexample and retained unstarted work. `/tmp/deep-hunt-native2-{counter,fault}/result.json`.
- EBMC native build is in progress; qualification is NOT RUN in this PR.
- Full Python suite, BOOM builds, broad HWMCC/open-core campaigns and CI waits NOT RUN.

## Issues

Refs: #21, #294. Keep both open.


## PR 493

[#493](https://github.com/riscPrint/risc-v-workstation/pull/493). Merged: 2026-11-13T02:27:28Z.

Title: feat(vip): add spi controller and peripheral agents

Audit evidence label: unit tests only.

## Summary
Add four-wire SPI controller and peripheral agents in Python/cocotb and SystemVerilog UVM. Support all four clock modes, 1 to 32 bits per word and both bit orders. Add monitor checks at chip-select boundaries, sequences, error injection, coverage, scoreboard hooks, seeded stimulus and good/bad digital loopback fixtures. Peripheral response queues consume a word only after its final sample edge.

## Testing
- Targeted Python: 35 passed across all four modes, both bit orders and 1/8/16/32-bit widths.
- Pinned Accellera UVM plus agent, interface, fixture and test top: Verilator lint passed with warnings.
- 809 passed, 6157 deselected in 77.18s (0:01:17)
- NOT RUN: UVM runtime build, UVM simulation, cocotb RTL simulation, DUT FIFO tests, BOOM jobs and full Python suite.

## Issues
Refs: #204

Keep #204 open for native mode qualification and project FIFO checks. SPI has no generic in-band backpressure. Projects must bind register/FIFO status to a project scoreboard. Multi-select, analog/shared-line behavior, dual/quad lanes and DDR modes remain outside the profile.

Roadmap notes: Add bounded SPI cycle and SV agents, including controller/peripheral roles and digital fixtures. Keep native runtime and FIFO qualification open.


## PR 494

[#494](https://github.com/riscPrint/risc-v-workstation/pull/494). Merged: 2026-11-13T02:27:34Z.

Title: feat(checks): check resource allocation conservation and CAM matches

Audit evidence label: unit tests only.

## Summary

Add generated independent allocation ownership, CAM single-match and unsigned counter-bound templates. Allocation checks compare DUT live state with independent accepted allocation/release events, reject duplicate lanes and invalid tags, and detect reuse of live entries or release of free entries. Declared reset ownership is a parameter. Same-edge release then allocation permits reuse.

Projects instantiate these templates with their own structures. Full ROB recovery, database inference, rename/LSQ semantics and real-core bindings remain open.

## Testing

- Targeted Icarus legal/fault and command-reference tests: 16 passed, 0 skipped.
- Required fast set: 809 passed, 0 skipped.
- NOT RUN: SBY proofs, Spinal compile, real-core binding, BOOM simulation, full Python suite.

## Issues

Refs: #65

Roadmap notes: Add independent resource ownership, CAM and bounded-counter safety templates. Retain broader microarchitecture and real-core integration gaps.


## PR 495

[#495](https://github.com/riscPrint/risc-v-workstation/pull/495). Merged: 2026-11-13T02:27:40Z.

Title: feat(formal): add bit and scalar hash reference models

Audit evidence label: ran on seeded RTL fixture.

## Summary

Add 32/64-bit models for 20 bit-manipulation operations. Add SHA-256 and SM3 models for RV32/RV64 and SHA-512 models for RV64. Preserve RV64 sign extension for word hash results. Use unsigned C arithmetic with defined shift ranges.

Add six SoftFloat EQ/LT/LE wrappers with exception flags. Model files use the existing datapath CLI and project binding API.

## Testing

- Bit and hash models: 8 passed. Include polynomial carryless multiplication checks, signed ordering, rotation boundaries, hash transforms and sign extension. Symbolic ANDN and SHA256SIG0 fixtures prove. Independent output mutants produce counterexamples.
- Pinned external SoftFloat: 8 passed. Native F32/F64 EQ/LT/LE edge cases and flags. Symbolic F32 EQ result/flag fixture proves over all operand bits. A missing invalid flag produces a counterexample.
- Required fast set after rebase: 809 passed, 6146 deselected.
- NOT RUN: BOOM builds, full Python suite, long formal jobs, project FPU arithmetic proofs, full Zb/Zk qualification.

## Issues

Refs: #19.

Roadmap notes: Add 20 bit operation models, scalar hash models and SoftFloat comparisons. AES, SM4, RV32 split SHA-512, remaining Zb instructions and project FPU arithmetic qualification remain open. Keep the epic open. Functional hash models do not prove constant execution time.


## PR 496

[#496](https://github.com/riscPrint/risc-v-workstation/pull/496). Merged: 2026-11-13T02:28:03Z.

Title: feat(regress): generate random vm programs and coverage crosses

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Generate seeded multi-page VM programs with mixed loads/stores, invalid PTEs and permission faults. Check every access result and final physical data. Bound programs to 64 pages and 128 accesses. Restore MPP before each MPRV access after traps. Keep the existing C1 ELF-dir/Spike framework.

Emit declarative functional groups from every MMU build. Cover walks/PTEs, translation protocols, pointer controls, two-stage observations and IOMMU captures. Support C2/2 functional coverage with per-hart/per-epoch histories. Keep observation coverage separate from correctness.

## Testing

- Random, coverage, ISA and payload tests: 11 passed, zero skipped. Nine random programs passed Spike, including maximum bounds. A missing-MPP-reset mutation failed as required.
- Walker/random/coverage Python checks: 65 passed, two native tests deselected.
- Wider integration run: 40 passed, one unrelated existing error-message assertion failed in cosim/test_formats.py::test_csr_masks_ranges_and_access_decoding. It expects csr_masks; unchanged code reports unknown csr_sync. The other targeted checks pass. That assertion was not weakened or changed.
- RTL, BOOM, Sail and full Python suite: NOT RUN.
- Final fast count below.

## Issues

Refs: #84, #147, #171, #154, #129, #99, #164, #148, #145, #140, #179, #188.

The random programs are bounded data-access campaigns with preset A/D. Missing DUT capture remains coverage holes. No native DUT qualification is claimed.

Roadmap notes: VM suites now include constrained random mappings/accesses and reusable functional cross groups across the MMU areas. C2/2 multi-hart coverage histories are isolated. Full DUT closure remains open. ROADMAP.md and TODO.md were not edited.
809 passed, 6127 deselected in 76.55s (0:01:16)


## PR 497

[#497](https://github.com/riscPrint/risc-v-workstation/pull/497). Merged: 2026-11-13T02:28:50Z.

Title: feat(csim): add context rows and scalar reference checks

Audit evidence label: unit tests only.

## Summary

- `rvw.csim-trace/1` gets `X ORD CONTEXT` rows (privilege mode or address space from that ordinal on). The C2 converter writes them from `mode`, the Spike converter from the commit-line privilege digit (initial row plus each change).
- Context policies: `btb.context` = `shared|flush|tagged`, `ras.context` = `shared|flush`, `memory.tlb.context` = `shared|flush|tagged` (TLBs and page walk caches). Reports count context changes and flushes.
- New `ComponentSims/tests/test_csim_reference.py`: separate scalar Python references for a set-associative LRU BTB, a circular RAS (with 2-byte and 4-byte calls), and LRU and SRRIP caches; the engine matches them exactly on random traces.
- Contract, README and model catalog updated.

## Testing

- `rvw/.venv/bin/python -m pytest ComponentSims/tests -q` — 92 passed (8 new reference checks, new context-policy test).
- `rvw/.venv/bin/python -m pytest rvw/tests/test_csim_formats.py -q` — 15 passed (mode changes become context rows).
- `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q` — 810 passed after rebase.
- Not run: full slow suite, CI not awaited, no RTL traces.

## Issues

Refs: #360 — done: context transitions; BTB and RAS checked against independent scalar references. Remaining: pinned external trace sets.
Refs: #365 — done: LRU and SRRIP checked against independent scalar references. Remaining: a pinned external cache/prefetch reference.

Roadmap notes: Component simulators: context-aware BTB/RAS/TLB policies; BTB, RAS, LRU and SRRIP match scalar references exactly.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 498

[#498](https://github.com/riscPrint/risc-v-workstation/pull/498). Merged: 2026-11-13T02:29:46Z.

Title: feat(sim): define external netlist and sdf replay handoffs

Audit evidence label: unit tests only.

## Summary

Define optional external gate-netlist/SDF replay requests, native adapter ports and capability reports. Capture netlist, SDF and cell-library bytes before native replay. Check declared cells, delays, timing checks, corner and unknown behavior. Add `rvw sim timing-handoff` and MCP `sim_timing_handoff`.

Roadmap notes: #214 gains an executable interface-readiness contract. Declared compatibility is not annotation evidence or physical signoff. External adapters must qualify their cell models and refuse ignored annotation. No native gate-level backend or standard-cell library is bundled. A native replay port must return a C1 outcome; compilation alone is refused.

## Testing

- Targeted handoff tests: 2 passed, 0 skipped. Check input byte capture, unsupported cells/delays/checks/unknown behavior, and compile-only refusal.
- Fast set after rebase: 809 passed, 0 skipped, 6153 deselected in 68.44 seconds. `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`.
- NOT RUN: native SDF annotation, gate-level replay, physical validation, BOOM, full Python suite, GitHub CI.

## Issues

Refs: #214. This supplies the handoff contract. Native adapter qualification remains open.


## PR 499

[#499](https://github.com/riscPrint/risc-v-workstation/pull/499). Merged: 2026-11-13T02:29:01Z.

Title: feat(lint): add lint_emit mcp tool and protected reset merges

Audit evidence label: unit tests only.

## Summary

- New MCP tool `lint_emit` (`settings`, `out`, optional `sarif`): runs the lint report and writes the CDC checker modules, bind lines, checked RTL copies, obligation list and generated SDC. `lint_report` gains an optional `sarif` path. Both call the new `rvw.lint.cli.report_outputs`, which the CLI also uses.
- `rdc.reconvergence` no longer reports a merge whose every cross-reset path is declared protected (isolation qualifier or reset order); such endpoints are listed in `rdc.protected_merges`.
- `docs/COMMAND_REFERENCE.md` regenerated; lint README updated.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_lint_rules.py rvw/tests/test_lint.py rvw/tests/test_lint_rdc.py rvw/tests/test_lint_depth.py rvw/tests/test_command_reference.py -q`: all passed (2 skipped: Verible).
- Fast set: 809 passed, 6148 deselected.
- Not run: an MCP server session end to end, the full Python suite.

## Issues

Closes: #118. With #407 and this PR, the remaining acceptance item is met at the structural and declared-intent level: asynchronous assertion crossings, synchronous release recognition, reconvergence under declared isolation/order, and unknown controls are all reported, and missing domain data is inconclusive. Sampled reset protocol checks stay in SpinalChecks `ResetChecks`. Recovery/removal, metastability and analog timing stay outside the digital model and are not claimed.

Roadmap notes: LINT — RDC (#118) done at structural + declared-intent level; `lint_emit` MCP tool.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 500

[#500](https://github.com/riscPrint/risc-v-workstation/pull/500). Merged: 2026-11-13T02:29:03Z.

Title: feat(query): explain design diffs with locations and covering tests

Audit evidence label: unit tests only.

## Summary

- `rvw query explain OLD.db NEW.db [--coverage COV.json] [--effect CMP.json]` and MCP `query_explain` (`rvw.diff-explain/1`).
- Each `rvw query diff` entry (component, port, register, memory, signal, logic, connection) gets its Scala locations (declaration and assignment lines; old DB for changed/removed, new DB for added).
- With an `rvw.coverage/1` database of the OLD revision: the tests that hit points mapped to those lines. Status `covered`, `unhit`, `unmapped`, `uncovered` (added hardware) or `unknown`.
- Conservative selection: `covering` only when every item is covered; otherwise `all` tests, with the uncertain items listed.
- With `--effect` (perf/arch compare JSON): a measured effect of the whole change, never attributed per difference. No performance model runs.
- PLATFORM_CONTRACTS section for `rvw.diff-explain/1`; query README.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_query_explain.py rvw/tests/test_query.py rvw/tests/test_mcp.py rvw/tests/test_command_reference.py -q`: 243 passed, 0 skipped (GCD / buggy GCD committed databases, synthetic coverage points).
- Fast set: 809 passed.
- Not run: a real core diff with real coverage; gem5 effect prediction.

## Issues

Refs: #28. Joins typed hardware differences with the tests that cover them, with conservative fallbacks. Remaining: requirement/proof-dependency joins, a per-difference effect prediction (gem5), and validation against changed designs with known outcomes.

Roadmap notes: debug/IDE area — `rvw query explain` gives a self-explaining diff (locations, covering tests, whole-change measured effect).

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 501

[#501](https://github.com/riscPrint/risc-v-workstation/pull/501). Merged: 2026-11-13T02:29:42Z.

Title: feat(workloads): add pinned coremark riscv-tests and zstd recipes

Audit evidence label: unit tests only.

## Summary
Add pinned riscv-tests, CoreMark-derived smoke, and zstd recipes to `rvw workloads`. Keep Embench as the default. Capture pinned source dependencies and copied runtime files. Reuse the architecture benchmark Makefile. Add cancellable workload MCP tools.

## Testing
39 targeted workload tests and 809 fast tests passed. Native RISC-V GCC 15.1.0 built median, Dhrystone, the CoreMark-derived kernel and zstd v1.5.7. Spike verified all four with exit 0 and the expected empty stdout. CoreMark checks all three upstream CRCs. zstd compresses a fixed 256 KiB input and checks every decompressed byte with heap allocation refused.

No RTL simulation, BOOM build, gem5 run or full suite ran. The CoreMark-derived short kernel produces no CoreMark score. zstd uses a round-trip self-check, not an independent decompressor. The other riscv-tests recipe entries were not run.

## Issues
Refs: #282. Broader workload coverage, Linux programs, and RTL sampling qualification remain open.

Roadmap notes: Open recipes now cover Embench, CoreMark algorithm kernels, Dhrystone/riscv-tests and a larger compression library. The four new native smoke checks passed on Spike; no RTL performance qualification is implied.


## PR 502

[#502](https://github.com/riscPrint/risc-v-workstation/pull/502). Merged: 2026-11-13T02:30:22Z.

Title: feat(cosim): compare debug entry snapshots

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add separate C2/2 debug events and full debug snapshots. Inject halt requests at the observed boundary without executing a debug ROM instruction. Compare debug mode, dpc, dcsr and the step bit. Keep ordinary trap events separate.

## Testing
- Debug/state/blocking transport tests: 32 passed. This includes native Spike halt entry, instruction-boundary preservation and mutation detection.
- Fast set passed after rebase.
- Native shim rebuilt.
- NOT RUN: RTL, WFI/interrupt/exception debug campaign, debug ROM, resume or automatic stepping.

## Issues
Refs: #136
Remaining: resume and automatic step transitions, triggers and full debug campaign. The step bit is compared as state only.

Roadmap notes: Cosim compares explicit debug halt entry and state, including through blocking online transport. No full debug qualification is claimed.


## PR 503

[#503](https://github.com/riscPrint/risc-v-workstation/pull/503). Merged: 2026-11-13T02:31:00Z.

Title: feat(cov): exchange ucis counters and export native coverage

Audit evidence label: unit tests only.

## Summary

Add `rvw cov exchange` and `cov_exchange`. Export and import the declared UCIS 1.0 counter profile. Preserve source identity, bin tuples, native metric kinds, Scala links and exclusions as metadata. Keep functional holes as zero-count bins. Reject incompatible source/plan/semantic/exclusion merges and unsupported XML structures. Imported exclusions remain unverified.

Export exact Verilator DAT keys or native LCOV through `verilator_coverage --write-info`. Write a metadata sidecar for every output. The counter profile uses coverpoint bins for code, functional and assertion counters. Native UCIS metric tags and arbitrary vendor profiles remain unsupported.

## Testing

Targeted interchange and command reference tests: 11 passed, zero skips. Fast set: 809 passed, 6230 deselected, zero skips.

Native checks under nice: exported XML validated with xmllint against the external Accellera FC4SC schema at 31b9339a34a40975fea0bb92a0ef876a6624b857. The upstream schema's misplaced XML declaration was removed before parsing; no schema declarations changed. Native Verilator DAT/LCOV smoke retained `DA:12,3`. Evidence: `/var/folders/s3/t4lhzzrj1qxfn3_y28334_340000gn/T/dv-exchange-native-_417zlkd`.

NOT RUN: commercial vendor round trips, UCIS C API, native DUT coverage collection, full suite or CI.

## Issues

Refs: #180

Keep #180 open for native UCIS code/assertion metric mappings and external vendor profile interoperability. This is an explicit counter transport subset. It grants no proof exclusion or C4 acceptance.

Roadmap notes: Code, functional and assertion counters can now cross the declared UCIS XML profile with preserved native semantics metadata. Native DAT and LCOV exports retain metadata sidecars. Vendor-native UCIS coverage mapping remains unqualified.


## PR 504

[#504](https://github.com/riscPrint/risc-v-workstation/pull/504). Merged: 2026-11-13T02:31:38Z.

Title: feat(formal): bind composite channel intents from spinaldb

Audit evidence label: ran on seeded RTL fixture.

## Summary
Generate per-field Stream stability and Flow range contracts for composite payloads. Resolve local channel ports, widths, clocks and reset polarity from SpinalDB. Refuse ambiguous or mixed domains and derived clock/reset wiring. Retain the single-payload API and publish a binding provenance sidecar.

## Testing
- Targeted database and intent tests: 26 passed, including native positive and per-field negative payload cases.
- Fast set: retained local result before push.
- NOT RUN: full Python suite, new native SpinalDB extraction, BOOM builds/simulation, long formal jobs, GitHub CI wait.

## Issues
Refs: #61, #294

Channels without domain metadata need an explicit register domain anchor. Clock-enable/soft-reset domains, falling-edge domains and nonlocal channel ports remain unsupported. Database staleness warnings do not establish current RTL parity.

Roadmap notes: support composite payload fields and database-derived bindings. Keep broader channel-domain inference and full SVA partial.


## PR 505

[#505](https://github.com/riscPrint/risc-v-workstation/pull/505). Merged: 2026-11-13T02:31:49Z.

Title: feat(wave): align wave diffs on events such as commits

Audit evidence label: unit tests only.

## Summary

- `rvw wave diff A B --align EXPR [--align-b EXPR]` (MCP `wave_diff` `align`, `align_b`): compare two runs event by event. At each rising clock edge where the event expression holds (pre-edge values), the selected signals are sampled; the k-th event of A is compared with the k-th event of B.
- First divergence reports the event index and both A/B times; a run with fewer events is `diverged` with that cause. Text output shows the event and times.
- Use case: two configurations or a fix with different timing, aligned on commit valid or Stream fire instead of raw time.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_wave_temporal.py -q`: 10 passed, 0 skipped (a delayed run matches by events but diverges by time; a payload change; a run with fewer events).
- Fast set: 810 passed.
- Not run: real core waves.

## Issues

Refs: #24, #297. Adds alignment by retirement/transaction events for wave diffs. Remaining: alignment by C2 RVFI order across trace files and explicit alignment uncertainty for out-of-order events.

Roadmap notes: debug area — `rvw wave diff --align` compares runs by event order (commits, transfers).

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 506

[#506](https://github.com/riscPrint/risc-v-workstation/pull/506). Merged: 2026-11-13T02:32:46Z.

Title: feat(checks): check concurrent device requests and hardware events

Audit evidence label: unit tests only.

## Summary

Add an independent reset-based register oracle for concurrent accepted device requests, per-master transaction IDs, reordered responses, register snapshots and independent hardware increment/clear/set events. Reuse project-owned SoC register maps. Add CLI/MCP access. Matching samples remain inconclusive; missing responses remain listed.

The event array explicitly linearizes software effects at accepted requests. This is not a real-device capture binding. HPM event provenance, interrupts, variable device timing and full real-device campaigns remain open.

## Testing

- Device-event and command-reference tests: 11 passed, 0 skipped.
- Required fast set: 810 passed, 0 skipped.
- NOT RUN: native device execution, SBY, Spinal compile, real-core event capture, BOOM simulation, full Python suite.

## Issues

Refs: #142, #98

Roadmap notes: Add concurrent register-event checking from independent reset state. Retain real-device/HPM event binding and campaign gaps.


## PR 507

[#507](https://github.com/riscPrint/risc-v-workstation/pull/507). Merged: 2026-11-13T02:32:50Z.

Title: feat(cosim): add vu and vs delegation cases

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add reusable RV64H programs and literal expected privilege and virtualization transitions. Cover VS ECALL to HS, VU ECALL to HS, and delegated VU ECALL to VS followed by VS ECALL to HS. These use the existing hypervisor state comparator.

## Testing
- Native Spike delegation cases: 3 passed.
- Fast set passed after rebase.
- NOT RUN: H-capable RTL, full hypervisor interrupts, translation fault/store campaigns.

## Issues
Refs: #114
Remaining: full H-capable DUT campaigns, two-stage stores and fault precedence.

Roadmap notes: Existing C2/2 hypervisor comparison now has portable VU/VS delegation programs and native reference readiness checks. No DUT result is claimed.


## PR 508

[#508](https://github.com/riscPrint/risc-v-workstation/pull/508). Merged: 2026-11-13T02:33:27Z.

Title: feat(regress): compare complete nested c2 walks

Audit evidence label: unit tests only.

## Summary

Compare complete nested C2 walks against an independent two-stage Python walker. Include G translation of every VS PTE read and the final payload. Bind C2 identity to C1 and use hash-checked generated table source. Support preset-A/D fixed mappings and fenced G-root reuse. Partial/cached captures remain inconclusive. Keep unsupported references inconclusive rather than reporting false extra-walk mismatches. Observe captured VS/G reads in functional groups without granting correctness.

## Testing

- Nested captures, scalar walks and coverage: 154 passed, one native test deselected, zero skipped.
- Generated nested model/mutation matrix: 87 passed. Includes VS/G faults, HLVX permission semantics, root reuse and corrupted returned PTEs.
- RTL, BOOM, Sail, full Python suite and fresh native runs: NOT RUN. No DUT capture result is claimed.
- Final fast count below.

## Issues

Refs: #140, #84.

Hardware A/D nested walks, complete HFENCE scopes, guest fetch campaigns and project DUT probe integration remain open. Missing capture is not a pass.

Roadmap notes: optional C2 nested walk captures now have an independent complete-record checker and separate VS/G observation coverage. Cached/partial/unsupported cases remain inconclusive. ROADMAP.md and TODO.md were not edited.
810 passed, 6354 deselected in 56.42s


## PR 509

[#509](https://github.com/riscPrint/risc-v-workstation/pull/509). Merged: 2026-11-13T02:34:18Z.

Title: feat(arch): predict memory dependencies and replay alias violations

Audit evidence label: unit tests only.

## Summary
Add finite load-PC/store-PC dependence prediction and alias replay to the C2 timing model. Unpredicted loads can pass unresolved stores. A violation trains the predictor and reexecutes younger instructions, including consumers. Keep replay distinct from memory renaming. Submit component memory service only after translation completes so callback times stay ordered.

## Testing
73 targeted OoO tests and 810 fast tests passed. Tests cover alias recovery, consumer reexecution, learned waits, non-alias speculation, bounded predictor capacity and component callback ordering.

No RTL simulation, BOOM build, gem5 run or full suite ran. This model retains committed-path entries during replay. It does not model speculative store data, cache cancellation, store-set unions or hardware memory renaming.

## Issues
Refs: #362.

Roadmap notes: Own-model memory dependence prediction and replay are available. RTL correlation, native acceleration of memory timing and component cache adapters remain open.


## PR 510

[#510](https://github.com/riscPrint/risc-v-workstation/pull/510). Merged: 2026-11-13T02:34:05Z.

Title: feat(csim): add mockingjay, ipcp, bingo and load address prediction

Audit evidence label: unit tests only.

## Summary

- Mockingjay replacement (`replacement: mockingjay`, after Shah, Jain & Lin, HPCA 2022): sampled sets learn a reuse distance per PC signature; lines carry an estimated time remaining that ages with set accesses; scans are trained to the far value and evicted first.
- IPCP data prefetcher (`kind: ipcp`, after Pakalapati & Panda, ISCA 2020): per-IP classes global stream, constant stride, complex stride (signature table) and next line, with per-class counts in the report.
- Bingo data prefetcher (`kind: bingo`, after Bakhshalipour et al., HPCA 2019): SMS-style footprints kept under the long event (PC + address) and the short event (PC + offset); long-event hits are counted.
- Load address prediction section `lap` (last address, stride, context with delta history): coverage, accuracy and misprediction PKI.
- Model catalog, README, contract section list and sweep metrics (`lap_coverage`, `lap_accuracy`) updated. All owner-written from the papers.

## Testing

- `rvw/.venv/bin/python -m pytest ComponentSims/tests -q` — 98 passed (Mockingjay beats LRU on a scan mix and stays above OPT; IPCP shows all three classes and halves misses; Bingo learns repeated region footprints; context address prediction beats stride on a periodic pattern).
- `rvw/.venv/bin/python -m pytest rvw/tests/test_csim.py rvw/tests/test_csim_formats.py -q` — 25 passed.
- `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q` — 810 passed after rebase.
- Not run: external pinned references for these models, long traces, full slow suite, CI not awaited.

## Issues

Refs: #365 — adds Mockingjay, IPCP, Bingo and load address prediction. Remaining: a pinned external cache/prefetch reference.

Roadmap notes: Component simulators: model zoo adds Mockingjay replacement, IPCP and Bingo prefetchers and load address prediction.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 511

[#511](https://github.com/riscPrint/risc-v-workstation/pull/511). Merged: 2026-11-13T02:34:13Z.

Title: feat(cov): report native metrics per linked scala line

Audit evidence label: unit tests only.

## Summary

Add `scala_line_metrics` to the existing coverage report and MCP result. Separate native toggle, expression/condition, FSM and other metric summaries at each linked Scala line. Deduplicate repeated links at the same line. Retain holes, exclusions and native metric names. Keep statement-hit status undetermined.

## Testing

Targeted source-line and existing code coverage tests: 20 passed, zero skips. Fast set: 810 passed, 6267 deselected, zero skips.

NOT RUN: new native collection, whole-core Scala attribution measurement, sbt, DUT simulation, full suite or CI. Fixture results do not establish Scala statement hits.

## Issues

Refs: #42

Keep #42 open. This adds report detail over existing links. It does not recover unavailable statement attribution or missing native source links.

Roadmap notes: Native metrics now have separate per-Scala-line summaries through existing coverage CLI/MCP reports. Whole-core source attribution and actual Scala statement hits remain unresolved.


## PR 512

[#512](https://github.com/riscPrint/risc-v-workstation/pull/512). Merged: 2026-11-13T02:34:33Z.

Title: feat(debug): check e-trace streams with traps, loss and filters

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
- E-Trace ingress (`etrace_flow.py`) now covers exceptions, interrupts, trap returns and privilege changes. Trap causes come from C2 trap events. An exception is an exception-only entry at the trapping pc. xRET is reported as itype 6, which is what the pinned baseline encoder and decoder need (see the README).
- `rvw debug etrace-check`: builds the expected stream from C2 with the pinned reference encoder and compares a capture (`.te_inst` or `.te_inst_raw`) field by field. It decodes the capture in segments split at known gaps (`--loss-at`) and trace-lost support packets, resyncs only at sync-start packets, aligns each segment with C2 in order, and reports lost spans as `unknown` windows. It never shows guessed execution. `--filter` (privilege, address ranges, exclusions, start/stop) gives one reference encode per qualified window, and a `leak` verdict for decoded PCs or sync addresses from unqualified execution.
- `rvw debug etrace-loss`: drop, overflow, wrap and truncate faults at sampled positions, with C3 results (`etrace-loss`).
- Test helper `rvw/tests/spike_c2.py` (Spike commit log to C2). Fixture `traps.S` (branches, M-mode and U-mode ecalls, mret).

## Testing
- `rvw/.venv/bin/python -m pytest rvw/tests/test_debug_trace.py -q`: 11 passed. The tests cover ingress kinds, trap causes, segmentation, injection, windows and verdicts, filters, leaks and packet comparison.
- Native, `RVW_ETRACE_REFERENCE` (pin ffb6bb72) with Spike 1.1.1-dev: `rvw/tests/test_debug_trace_native.py` 4 passed.
  - flow_match and packet_match with exceptions and U-mode.
  - A corrupted branch map gives `mismatch`. A bit for an unobserved branch changes only `packets`.
  - Every loss-campaign fault passes, with unknown windows.
  - An M-only filter gives flow_match for a filtered capture and `leak` for an unfiltered one.
- Fast set: 819 passed.
- Not run: no core RTL encoder capture exists; context changes are not tested.

## Issues
Refs: #168. Open: context changes; options beyond the baseline encoder.
Refs: #172. Open: resync at trap syncs; vendor overflow markers.
Refs: #195. Open: authentication controls; encoder trigger inputs.

Roadmap notes: Trace area. E-Trace checks now cover traps, privilege, loss windows with resynchronization, and qualification filters with leak detection, against the pinned reference flow. Next step: an RTL encoder capture from a core adapter.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

## PR 513

[#513](https://github.com/riscPrint/risc-v-workstation/pull/513). Merged: 2026-11-13T02:34:31Z.

Title: feat(formal): prove paired security and reset contracts

Audit evidence label: ran on seeded RTL fixture.

## Summary

Add `rvw formal security pair` and `formal_security_pair`. Prove a declared two-copy digital contract: equal architectural observation prefixes require equal current microarchitectural observations. Public inputs and reset are shared. Secret inputs are independent. The contract does not infer instruction retirement alignment.

Add declared constant-time unit checks with no architectural guard. Add initial-state independence and declared output reset-value checks. Report reset coverage as declared, total output and proved bits. Refuse embedded DUT formal properties and nondeterministic cells.

## Testing

Native targeted tests: 12 passed. Include leak/control pairs, explicit architectural disclosure, uninitialized state reaching outputs, reset-value mutants, declared Zkt timing outputs and an embedded assumption rejection. Tests use OSS CAD Suite first on PATH.

Required fast set after rebase: 810 passed, 6278 deselected in 62.81s (0:01:02).

NOT RUN: BOOM builds, whole-core security, full Python suite, long formal jobs, physical leakage or entropy-quality checks.

## Issues

Refs: #20.

Roadmap notes: Add two-copy causal observation contracts, declared unit timing proofs, initial-state dependence and output reset coverage. Dynamic PMP/ePMP, full instruction qualification and entropy interfaces remain open. Existing Spike campaigns retain their separate sampled evidence contract.


## PR 514

[#514](https://github.com/riscPrint/risc-v-workstation/pull/514). Merged: 2026-11-13T02:45:42Z.

Title: feat(privilege): add timer state control and cfi matrices

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Generate RV64 Sstc, state-enable, environment-control, landing-pad and shadow-stack suites. Include VS timer-control combinations and HENVCFG access when H is selected. Check actual lower-mode entry, denied-access cause/PC, landing-pad labels and fault codes. Shadow-stack cases cover normal push/pop, mismatch, ordinary/Bare rejection, normal stores to SS pages and read-only-page recovery. Keep the small CFI fixture in its own module.

Sstc reference profiles require Zicntr. The installed Spike crashes on several Sstc accesses without time support. Those earlier results were inconclusive. The corrected profiles below pass.

## Testing

- Targeted Python tests: 28 passed, 0 skipped.
- Native Spike: 90 bounded program/profile self-checks pass: Sstc 13, H Sstc 29, stateen 6, environment 6, H environment 12, landing 12 and shadow 12. Shared cases are repeated across H/non-H profiles; this is not 90 distinct scenario names.
- All native runs use nice and one-second per-program bounds.
- Fast set after rebase: 810 passed, 6279 deselected, 0 skipped.
- NOT RUN: RTL builds or simulations, full suite, long formal or CI.

## Issues

Refs: #159
Refs: #176
Refs: #177
Refs: #174
Refs: #175

Remaining: RV32 split timer access, all extension-state gates, full virtualization transitions, interrupted landing-pad sequences, guest shadow stacks and DUT qualification. No issue is closed from reference-only evidence.

Roadmap notes: Add pinned RV64 privilege-extension and CFI program generation. Record the bounded native reference outcomes. Keep unsupported combinations and DUT qualification open.

Final rebase validation: privilege tests 72 passed, 0 skipped. Fast set: 820 passed, 1 failed, 6643 deselected. The failure is release hygiene in unchanged upstream rvw/tests/cosim/test_adjudicate.py:51 (personal path). It is outside this worker area and remains unwaived.


## PR 515

[#515](https://github.com/riscPrint/risc-v-workstation/pull/515). Merged: 2026-11-13T02:43:19Z.

Title: feat(memory): generate bounded tilelink channel monitors and binds

Audit evidence label: unit tests only.

## Summary
Generate a bounded single-beat TileLink-C channel monitor and SystemVerilog bind from two project-selected Spinal TileLink Bus types and signal IDs in SpinalDB. Check accepted request/probe/grant/ack sequences, permissions, independent expected data and bounded outstanding ages. Add CLI/MCP entry points and explicit profile limits.

## Testing
Five targeted Python tests passed, no skips. Native Verilator elaborated the generated bind and ran the baseline plus five seeded defects: early grant, stale grant data, lost GrantAck, missing grant and stale intervention data. The fast Python set passed: 810 passed, no skips.

NOT RUN: production design-database integration, real coherent home/cache refinement, multi-beat traffic, BOOM builds, full Python suite. The native runtime uses scripted RTL channel signals and a typed SQL fixture. Project oracle independence and bounded service assumptions remain explicit obligations. Error responses and other-line traffic are outside this success-only profile.

## Issues
Refs: #128, #363. Real coherent-fabric campaigns, multi-beat/refinement checks and independent protocol model cross-checks remain open.

Roadmap notes: memory tools now generate runnable two-client single-line TL-C channel monitors and binds with native seeded-defect smoke evidence. This does not close protocol refinement or production integration.


## PR 516

[#516](https://github.com/riscPrint/risc-v-workstation/pull/516). Merged: 2026-11-13T02:35:06Z.

Title: feat(vip): add resolved open-drain i2c agents

Audit evidence label: unit tests only.

## Summary

Add I2C cycle models, a cocotb write adapter and a SystemVerilog UVM agent. Use explicit open-drain low enables and resolved inputs. Check ACK/NACK, repeated START, bounded clock stretching, arbitration loss and partial transfers. Add an ACK/NACK fixture and scoreboard.

Roadmap notes: I2C has digital manager and monitor support. Reactive UVM subordinate, SV reads and runtime qualification remain open.

## Testing

- Python I2C tests: 9 passed.
- Verilator 5.052 lint with pinned Accellera UVM: passed.
- Required fast Python set: 810 passed, 6376 deselected after rebase.
- Not run: UVM runtime builds, cocotb RTL simulation, BOOM builds or the full Python suite.

## Issues

Refs: #205. Keep open for reactive roles and runtime qualification.


## PR 517

[#517](https://github.com/riscPrint/risc-v-workstation/pull/517). Merged: 2026-11-13T02:35:18Z.

Title: feat(wave): save and open portable debug sessions

Audit evidence label: unit tests only.

## Summary

- `rvw wave session save S.json --wave W [--db DB] [--signal RX ...] [--cursor T ...] [--query Q ...] [--artifact F ...] [--note]` (MCP `wave_session_save`): one `rvw.debug-session/1` file with resolved signal names, cursor times, embedded saved queries, and path/size/SHA-256 of the wave, database, adjacent C1 `result.json` and other bound files.
- `rvw wave session open S.json [--root DIR]` (MCP `wave_session_open`): finds each artifact at its recorded path or by its last path parts under `--root` / the session directory, verifies SHA-256, and reports `ok` / `changed` / `missing` artifacts and missing signals. `complete` only when all match; exit 1 otherwise. No central service.
- PLATFORM_CONTRACTS section for `rvw.debug-session/1`; wave README.
- `test_mcp_tools.py` tool count updated (main was already two tools behind).

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_wave_session.py rvw/tests/test_mcp_tools.py -q`: 23 passed, 0 skipped (moved directory, changed wave, missing result, CLI exits).
- Fast set: 810 passed.
- Not run: a cross-machine open (simulated by moving the directory).

## Issues

Refs: #24. Covers "export selected signals, cursors, source views and exact run identities as an external session description; open the same session elsewhere and report missing artifacts". Remaining: the VS Code wave view does not yet load sessions; source views are carried only through embedded queries.

Roadmap notes: IDE/debug area — portable debug sessions (`rvw wave session save/open`) bound to artifact SHA-256.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 518

[#518](https://github.com/riscPrint/risc-v-workstation/pull/518). Merged: 2026-11-13T02:35:37Z.

Title: feat(formal): qualify ebmc with native aiger input

Audit evidence label: ran on seeded RTL fixture.

## Summary

Pass original pinned AIGER bytes to EBMC's native reader. Keep the Yosys safety inventory separate. Record the native input format. Add positive/fault qualification and final per-engine bounded/unbounded HWMCC tables to the formal README.

Roadmap notes: native rIC3 and EBMC qualification is available on small cases. Full out-of-order blocks, small-open-core property campaigns, broader HWMCC capacity and licensed comparisons remain open.

## Testing

- Targeted portfolio/importer/installer tests: 18 passed, 0 skipped.
- Fast set: 810 passed, 6278 deselected, 0 skipped. `/tmp/deep-ebmc-fast.log`.
- EBMC 6.2: safe counter proved, seeded fault found. Native AIGER proved a19-p15; itc99-b13-p10 remains inconclusive under 20-induction. `/tmp/rvw-deep-ebmc-{counters,hwmcc}/result.json`.
- Final 12 s/job pinned HWMCC runs: ABC PDR and rIC3 solved 2/2; EBMC and each SMT backend solved 1/2. Bounded runs are separate in the README table. Avy crashes, missing suprove and ABC BMC3 errors remain explicit. `/tmp/rvw-deep-final-{prove,bmc}/result.json`.
- External EBMC build used the documented macOS deployment-target patch. No verification algorithm changed.
- Full Python suite, BOOM jobs, broad HWMCC, open-core property campaigns and CI waits NOT RUN.

## Issues

Refs: #21, #294. Neither epic is complete.


## PR 519

[#519](https://github.com/riscPrint/risc-v-workstation/pull/519). Merged: 2026-11-13T02:51:02Z.

Title: feat(formal): derive autocheck candidates from design databases

Audit evidence label: unit tests only.

## Summary
Derive formal autocheck candidates from a captured SpinalDB database. Read module ports and complete output enum encodings. Generate enum state/transition targets, constants, toggles, one-hot/mutex candidates, simple whole-width arithmetic candidates and exposed memory address bounds. List unsupported extraction explicitly.

Add one-hot/mutex, array-bound, signed/unsigned add/sub overflow, toggle and FIFO overflow/underflow/ordering monitors. Support explicit semantic endpoint contracts and bounded arbiter/handshake response kinds. Reject a fairness field in bounded progress checks. Add kind selection and waivers. Waived checks run no solver and cannot earn a pass.

Carry module and Spinal source locations into generated properties. Let formal testplan read generated app inventories and saved per-property results directly.

## Testing
- Final targeted database/app/autocheck/testplan group: 32 passed, 0 skipped, including native Yosys/SBY/Z3 tests.
- Native seeded FIFO overflow, underflow and ordering faults were detected; the correct FIFO passed its bounded check.
- Later boolean-option guard and database/report tests: 15 passed, 12 deselected, 0 skipped. These overlap the preceding group.
- Existing app regression group: 29 passed; one new database fixture failed because its destination was Boolean. The fixture now uses a matching-width destination, and its targeted database group passed.
- Required fast set before the first push: 833 passed, 6689 deselected, 0 skipped. Repeated after each rebase.
- Not run: full Python suite, BOOM build or simulation, long formal jobs, general liveness, native typed viewer navigation or CI wait.

## Issues
Refs: #62, #60

Roadmap notes: Add database-driven port/enum/simple-operation candidates, generic safety monitors, waivers and generated source-line testplan inventories. General liveness under fairness, automatic FIFO/arbiter role discovery, internal enum exposure, arbitrary expression lowering and complete solver cell-core coverage remain open. The local SBY live backend requires suprove, which is not installed. Bounded response checks do not establish general liveness. No new UNR exclusion authority is granted.


## PR 520

[#520](https://github.com/riscPrint/risc-v-workstation/pull/520). Merged: 2026-11-13T02:35:49Z.

Title: feat(cosim): fetch pinned external vector suite sources

Audit evidence label: unit tests only.

## Summary
Add CLI and MCP setup for pinned external CHIPS Alliance riscv-vector-tests sources and its pinned test environment. Retain the existing strict vector-state suite comparison as the verdict path. No workstation submodule is added.

## Testing
- Setup unit tests: 2 passed.
- Actual external fetch succeeded at `[local path omitted]`. Both commit ids verified.
- Fast set passed after rebase.
- NOT RUN: vector test generation/build, full upstream suite, V-capable RTL.

## Issues
Refs: #75
Remaining: full vector suite execution, vector partial memory effects, agnostic values, upstream coverage gaps.

Roadmap notes: Vector suite setup now pins both source repositories outside the workstation. Existing C2/2 full-vector-state checking remains required. Prepared source is not a suite pass.


## PR 521

[#521](https://github.com/riscPrint/risc-v-workstation/pull/521). Merged: 2026-11-13T02:36:32Z.

Title: feat(checks): import literal UPF isolation intent and generate checks

Audit evidence label: unit tests only.

## Summary

Import an explicit literal UPF 2.1 domain/isolation subset. Generate independent sampled isolation assertions and instance binds from project observations. Preserve normalized intent, input hashes and unmonitored domains. Reject unsupported Tcl, commands, options and strategies. Add CLI/MCP access and a fixture example.

This increment does not import retention, supply networks/state tables or clock-gating intent. Those constructs are refused. Physical power, binding completeness and real-core behavior remain unverified. PR #409 remains separate and open.

## Testing

- UPF subset/native Icarus seeded monitors and command reference: 36 passed, 0 skipped.
- Verilator 5.052 accepted the generated monitor and instance bind against a tiny synthetic Top. Elaboration took 0.009 seconds.
- Required fast set: 821 passed, 0 skipped.
- NOT RUN: SBY, Spinal compile, real-device power execution, physical power analysis, BOOM simulation, full Python suite.

## Issues

Refs: #162, #157, #163, #146

Roadmap notes: Add literal domain/isolation UPF import and sampled check generation. Keep retention, supply-state tables, clock-gating import and real-core/physical evidence open.


## PR 522

[#522](https://github.com/riscPrint/risc-v-workstation/pull/522). Merged: 2026-11-13T02:37:09Z.

Title: feat(arch): model soc traffic queues and abstract power states

Audit evidence label: unit tests only.

## Summary
Add `rvw arch traffic` and a cancellable MCP job. Model declared multi-agent post-cache traffic through finite pipelined resources. Report transaction latency, bandwidth, transfer utilization, queue waits and occupancy. Optional project parameters add abstract sleep/wake timing and energy.

## Testing
Three targeted traffic tests and 821 fast tests passed. Cases check serialized bandwidth, finite capacity, two-agent interference, multi-hop routes and sleep/wake costs. No RTL, BOOM build, gem5 run, full suite or physical power measurements ran.

## Issues
Refs: #124, #125, #201. This slice consumes declared post-cache traffic. Cache replacement, coherence, RTL observation matching and calibrated physical power remain open.

Roadmap notes: An independent SoC traffic and abstract energy model is available. It uses store-and-forward routes with resource-local queues. It is not a credit-accurate interconnect or a physical power flow.


## PR 523

[#523](https://github.com/riscPrint/risc-v-workstation/pull/523). Merged: 2026-11-13T06:14:46Z.

Title: feat(formal): translate finite psl properties to shared sva

Audit evidence label: unit tests only.

## Summary
Translate a finite Verilog-flavor PSL subset to the existing SVA frontend. Add CLI and MCP generation commands. Support clock declarations, Boolean/next implications, flat finite SEREs and suffix implication. Reject unsupported language before publication.

## Testing
- Targeted tests: 18 passed, including native legal/faulted next-cycle and suffix implications on SMTBMC/Yices.
- Final fast set after retry 5 rebase: 833 passed, 6682 deselected. The earlier main-branch cosim personal-path failure is fixed in the new base. No cosim file was changed in this PR.
- Post-rebase PSL checks: 14 passed, 4 native cases deselected; the four native cases passed in the earlier 18-test run.
- NOT RUN: full Python suite, full PSL conformance, BOOM builds/simulation, long formal jobs, GitHub CI wait.

## Issues
Refs: #61

PSL verification units, nested SEREs, multiple clocks, abort and unbounded/liveness operators remain unsupported. Generation is not a verification result.

Roadmap notes: add a finite PSL adapter sharing the SVA backend. Keep full PSL/SVA language qualification partial.


## PR 524

[#524](https://github.com/riscPrint/risc-v-workstation/pull/524). Merged: 2026-11-13T02:37:27Z.

Title: feat(regress): cover fetch walk faults and napot range remaps

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Add fetches to every Sv32/39/48/57 per-level invalid-PTE/PMP-denied-read fault case. The matrix now has 84 programs. Add six NAPOT range remap programs that prime all 16 pages, rewrite all 16 PTEs and check new values after a global fence or 16 per-page fences. Do not assume one address-specific fence removes every subrange entry.

## Testing

- Walk/fetch/range checks: 94 passed, zero skipped. All 84 fault and six range programs passed short Spike runs.
- RTL, BOOM, Sail and full Python suite: NOT RUN.
- Final fast count below.

## Issues

Refs: #84, #147, #171, #154, #164.

DUT capture and internal refill/invalidation validation remain open. No internal cache-granularity claim is made.

Roadmap notes: fault generators now include instruction-fetch PTE-read faults at every level. Full-range NAPOT remapping checks every affected page after required fences. DUT closure remains open. ROADMAP.md and TODO.md were not edited.
821 passed, 6436 deselected in 72.80s (0:01:12)


## PR 525

[#525](https://github.com/riscPrint/risc-v-workstation/pull/525). Merged: 2026-11-13T02:37:38Z.

Title: feat(formal): check digital entropy interface protocols

Audit evidence label: unit tests only.

## Summary

Add an `entropy` property to `rvw formal apps` and the existing `formal_apps` MCP tool. Bind a project seed word, access policy, refill and fatal-health events. Check access errors, non-ES16 data masking, RV64 extension, wipe-on-read, BIST retention and DEAD persistence.

Use the scalar crypto 1.0.1 digital seed contract. Do not test numerical uniqueness or claim physical entropy quality. Declare the continuous-word and sampled-event binding in the README and shared contract.

## Testing

Native targeted tests: 6 passed. The control proves. Missing wipe, DEAD escape, missing access errors and stale data masking each produce a counterexample. Invalid seed width is refused.

Required fast set after rebase: 821 passed, 6411 deselected.

NOT RUN: BOOM builds, full Python suite, long formal jobs, physical entropy, certification, project privilege decoding or full seed-CSR qualification.

## Issues

Refs: #203, #20.

Roadmap notes: Add digital entropy interface protocol and failure monitors. Physical health tests, refill independence, entropy certification, address decoding and privilege-policy generation remain open. Keep #203 open.


## PR 526

[#526](https://github.com/riscPrint/risc-v-workstation/pull/526). Merged: 2026-11-13T02:38:19Z.

Title: feat(regress): generate directed tests for pinned sail rules

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Add `rvw regress sail-tests` and `regress_sail_tests`. Generate bounded RV32 add/sub/addi fragments linked to exact existing pinned Sail rule and result obligations. Query expected values through the public DII API. Require complete, nontrapping retirement streams. Preserve reference packets, token/source hashes, boundary/seeded inputs and instruction/register mutation observations. Reject changed rule bytes before connecting.

The project supplies four registers, an RV32 Sail endpoint and the failure/termination runtime. Endpoint binary identity is not attested. Reference-generated data is not a DUT pass. Some mutants can survive individual cases; the report preserves survivors.

## Testing

Final focused directed-generator, source-pin guard and command reference tests: 14 passed, zero skips. Fast set: 821 passed, 6417 deselected, zero skips.

An earlier broad targeted source-slice check: 13 passed, 11 optional native/source cases skipped. No skipped case is claimed as a pass.

NOT RUN: native Sail oracle generation, generated DUT programs, broad Sail/CSR generation, held-out mutant campaign, full suite or CI. Fixture oracle tests do not establish native reference behavior.

## Issues

Refs: #29

Keep #29 open. Full Sail instruction/CSR generation, attested oracle identity, independent native execution and held-out quality measurements remain.

Roadmap notes: Three existing pinned RV32 arithmetic obligations now have a CLI/MCP directed-test generator with reference expectations and mutation observations. General Sail compilation and DUT validation remain unverified.


## PR 527

[#527](https://github.com/riscPrint/risc-v-workstation/pull/527). Merged: 2026-11-13T02:40:20Z.

Title: feat(vip): add gpio state and interrupt agents

Audit evidence label: unit tests only.

## Summary

Add GPIO cycle reference, stimulus and cocotb adapter. Add the matching SV UVM driver, monitor, coverage and scoreboard. Check direction changes, declared synchronizer latency, edge and level interrupts and reset. Include good/bad GPIO RTL and runtime entry points for GPIO and I2C.

Roadmap notes: GPIO digital pin and interrupt references are implemented. Native UVM and cocotb qualification remain open. Analog contention and metastability are outside the declared profile.

## Testing

- GPIO Python tests: 6 passed.
- Verilator lint with pinned Accellera UVM: passed.
- Required fast tests: 821 passed, 6450 deselected.
- Not run: UVM runtime builds, cocotb RTL simulation, BOOM builds or full Python suite.

## Issues

Refs: #209. Runtime qualification remains open.


## PR 528

[#528](https://github.com/riscPrint/risc-v-workstation/pull/528). Merged: 2026-11-13T02:38:44Z.

Title: fix(lint): remove alias false findings on verilog imports

Audit evidence label: unit tests only.

## Summary

Running `rvw query build-hdl` + `rvw lint` (rules, structural, sdc) on the SERV core (`ref/serv`, `serv_top`, 219 registers) showed false findings from Verilog imports. This fixes them:

- `rvw/src/rvw/lint/graph.py`: reads the importer's `Yosys net alias` rows. Hidden names are dropped, register vector bits merge into their one visible name (wire vectors do not merge, so bit slices do not form false loops), and other name-to-bit links stay as connectivity in `alias_edges`. New `loads()`/`drivers()` look through alias bits.
- `rvw/src/rvw/lint/rules.py`: alias rows are not drivers; constant ties are. Comb-loop search ignores alias links; loop members list visible owner names. Unused/undriven/unconnected checks look through alias bits, toplevel ports that share a bit, and ties.
- `rvw/src/rvw/query/hdl.py`: records a constant on a child input, or a child output tied to a constant, as a `Yosys constant` assignment; keeps a cell's self-edge (a real loop), as SpinalDB does.
- No schema change.

## Testing

- With native Yosys: `rvw/.venv/bin/python -m pytest rvw/tests/test_lint*.py rvw/tests/test_query_hdl.py -q`: 145 passed, 21 skipped. New `test_lint_hdl.py` covers a shared alias, constant ties through ports, slice-only vector logic (no false loop), a register vector and one real loop.
- Extracted Spinal fixtures: 17 passed.
- SERV manual run: before, 1 false loop and up to 160 false unused/undriven findings (depending on the alias handling); after, no rule findings. `yosys check` on `serv_rf_if` confirms no loop. Structural: one clock, `no_crossings_found`.
- Fast set: 821 passed, 6445 deselected.
- Not run: other cores, the full Python suite.

## Issues

Refs: #22. Remains: synchronous resets in plain mux logic are data in the HDL import; a loop across bits of one merged register vector cannot occur, but cross-bit wire loops through shared names are found only at bit level.

Roadmap notes: LINT — lint rules validated on a real Verilog core (SERV) through the HDL import with no false findings.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 529

[#529](https://github.com/riscPrint/risc-v-workstation/pull/529). Merged: 2026-11-13T02:39:17Z.

Title: feat(wave): read fst directly through wellen for searches

Audit evidence label: unit tests only.

## Summary

- `rvw wave find|edges|seq|txn|diff` on `.fst` read the wave directly through wellen (pywellen, `waves` extra): only the referenced signals are decoded, with a bisect to the window start; no `fst2vcd` conversion and no index needed. `RVW_WAVE_FST_READER=vcd` keeps the converter path; without pywellen nothing changes.
- Shared `wellen_header` helper for the index builder and the direct reader.
- Limit (documented): pywellen does not expose the FST end time, so an interval still open at the end uses the last change of the signals read for `true_time`.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_wave_search.py rvw/tests/test_wave_temporal.py rvw/tests/test_wave_index.py rvw/tests/test_wave.py -q`: 170 passed, 0 skipped. The new test checks find/edges/seq parity with the VCD and that the FST is never opened as text.
- Fast set: 821 passed.
- Native smoke (macOS arm64, `nice -n 10`): 9 MB / 500-signal FST, `find 'sig3 == sig4 || sig7[3:0] == 5'`: 0.85 s and 68 MB RSS direct; 9.8 s through fst2vcd; same 175 intervals.
- Not run: multi-GB FST.

## Issues

Refs: #173. Direct native FST seeking now covers the search commands. Remaining: `changes`/`sample`/`cut` on FST still use the converter (or an index), and a single huge signal is decoded whole by wellen.

Roadmap notes: waves area — searches read FST natively through wellen (about 10x faster than fst2vcd on the fixture).

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 530

[#530](https://github.com/riscPrint/risc-v-workstation/pull/530). Merged: 2026-11-13T02:39:41Z.

Title: feat(csim): add simpoint sampling and weighted point runs

Audit evidence label: unit tests only.

## Summary

- `rvw csim simpoint TRACE --interval N` (MCP `csim_simpoint`): SimPoint-style phase sampling. Basic-block vectors per interval, 15-dimension random projection, k-means++ for k = 1..max-k, smallest k reaching 90% of the BIC range; one representative interval and an instruction-share weight per cluster (`rvw.csim-simpoints/1`).
- `rvw csim run-points STUDY TRACE --points FILE [--warmup N]` (MCP `csim_run_points`): fast forward (`skip_instructions`, no state change), warm up, measure each point, and report weighted metrics (`rvw.csim-simpoint-report/1`). Sampling error is not estimated and the report says so.
- Engine: `skip_instructions` study key (must not exceed `warmup_instructions`); the front-end model skips the fast-forwarded instructions.
- Contracts, README, catalog and command reference updated.

Measured: qsort Spike trace (230k instructions), 10 points at a 10 000-instruction interval, TAGE-SC-L 64 KB: weighted 43.6 MPKI against 42.1 MPKI for the full run.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_csim.py rvw/tests/test_csim_formats.py -q` — 26 passed (two-phase trace: k=2 with 1/3 and 2/3 weights; weighted metric equals the weighted mean; skip/warmup/measure counts).
- `rvw/.venv/bin/python -m pytest ComponentSims/tests -q` — 98 passed.
- `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q` — 821 passed after rebase.
- Not run: long workloads, sampling-error study, full slow suite, CI not awaited.

## Issues

Refs: #351, #365 — sampled ROI support for per-workload studies. No issue is closed by this PR.

Roadmap notes: Component simulators: SimPoint-style weighted simulation points and point runs.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 531

[#531](https://github.com/riscPrint/risc-v-workstation/pull/531). Merged: 2026-11-13T02:39:47Z.

Title: feat(cosim): compare serialized harts with shared spike ram

Audit evidence label: unit tests only.

## Summary
Compare multi-hart C2 in one Spike machine with shared RAM, per-hart processor state, and per-hart checker history. Require an explicit serialized-retirement memory profile. Execute each reference retirement in capture order. Retain per-hart reports and the first mismatching hart.

## Testing
- Native shared store/load, mismatch detection and blocking transport: 3 passed.
- Hart 0 stores literal 7; hart 1 reads 7. A changed observation of 8 fails.
- Fast set passed after rebase. Native shim rebuilt.
- NOT RUN: RTL multi-hart, RVWMO, external agents, reset epochs beyond zero, independent memory-model validation.

## Issues
Refs: #189
Remaining: weak-memory profiles, per-hart images/reset state, external-agent writes and custom extension setup.

Roadmap notes: Cosim now has a restricted multi-hart shared-memory baseline. The declared profile requires serialized retirement visibility. It does not establish coherent-bus or weak-memory correctness.


## PR 532

[#532](https://github.com/riscPrint/risc-v-workstation/pull/532). Merged: 2026-11-13T02:40:43Z.

Title: feat(vscode): open debug sessions in the wave query view

Audit evidence label: unit tests only.

## Summary

- VS Code `wave` feature: **Wave: Open Debug Session** runs `rvw wave session open --json` and shows artifact status (ok / changed / missing), signals, cursors and embedded queries. An incomplete session gets a warning headline that names what is missing.
- **Wave: Run Saved Query** runs an embedded query row; cursor rows open a wave window in Surfer around the cursor (session wave path).

## Testing

- `cd vscode && npm run typecheck && npm run build && npm test`: 23 passed, 0 failed, 0 skipped (new model test for session headlines, embedded queries and cursor times).
- Not run: VS Code host test, Surfer launch.

## Issues

Refs: #24. The IDE now opens portable sessions from `rvw wave session save`. Remaining: a live cursor link with Surfer.

Roadmap notes: IDE area — the wave view opens debug sessions and runs their saved queries.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 533

[#533](https://github.com/riscPrint/risc-v-workstation/pull/533). Merged: 2026-11-13T02:40:52Z.

Title: feat(regress): check independent memory-type effects

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Add independent device-visible transaction checks for memory-type campaigns. Projects declare expected IDs, physical addresses, directions, widths, types, optional data and ordering edges. Captures supply strictly ordered visible effects. Detect wrong effects, replay, extra effects and violated declared order. Keep missing effects/plans inconclusive and keep memory results separate from TLB/atomicity evidence. Add functional observation groups.

## Testing

- Memory/protocol/coverage tests: ten passed, one native test deselected, zero skipped.
- Existing Svnapot/Svpbmt extension smoke: 28 generated programs passed Spike.
- RTL, device observers, BOOM, Sail, full Python suite: NOT RUN.
- Final fast count below.

## Issues

Refs: #148.

Actual DUT device-visible capture and project memory-type/ordering policy integration remain open. Request issue order is not accepted as a substitute. No global IO ordering rule is inferred.

Roadmap notes: independent memory-type effect checks now validate declared physical effects and ordering constraints. Project DUT observers and qualification remain open. ROADMAP.md and TODO.md were not edited.
821 passed, 6527 deselected in 77.73s (0:01:17)


## PR 534

[#534](https://github.com/riscPrint/risc-v-workstation/pull/534). Merged: 2026-11-13T02:42:18Z.

Title: feat(arch): repeat three-size scheduling measurements

Audit evidence label: unit tests only.

## Summary
Add `rvw arch sched-study` and a cancellable MCP job. Reuse the C1 scheduling runner for three stream sizes and at least three seeds with fixed memory timing. Report fitted slopes, adjacent slopes, residuals, nonlinear scaling and repeated-seed intervals. Refuse independent streams when eight register chains cannot hide declared latency.

## Testing
41 targeted scheduling tests passed and two skipped because native LLVM TableGen was absent. 821 fast tests passed. Synthetic runner tests check seed propagation and report math. No RTL scheduling study, BOOM build, full suite, native gem5 run or compiler target rebuild ran.

## Issues
Refs: #369. Mixed held-out, branch, dependent-load, bypass and variable-latency kernels remain open. Native generated LLVM/GCC integration remains open under #367.

Roadmap notes: Repeated three-size scheduling studies now detect nonlinear scaling and expose seed variation. These retirement slopes still include front-end and commit limits and do not establish isolated execution latency.


## PR 536

[#536](https://github.com/riscPrint/risc-v-workstation/pull/536). Merged: 2026-11-13T02:42:08Z.

Title: feat(uvm): add live scalar cpu environments and spike checks

Audit evidence label: unit tests only.

## Summary
Add a live scalar RVFI monitor and independent Spike DPI scoreboard. Add shared instruction/data memory services with seeded response delays, byte masks and fetch errors. Add reset, interrupt and debug pin sequences. Add Python CPU memory, retirement and coverage services, a cocotb monitor and an optional pyuvm environment.

Update captured replay to Spike ABI 6 and pass PMP granularity. Check optional post-retirement GPR and CSR snapshots. Add explicit unsupported feature requirements and workarounds. Verilator 5.052 rejected dynamic arrays at the DPI boundary; fixed arrays plus a count work in the native fixture.

The bounded fixture executes five ADDI instructions and one MISA read from an ELF. It is not VexRiscv. Normal runs export C1/C2/C3. The standard coverage command consumes the C2 traces. Source identity remains incomplete. No C4 acceptance is claimed.

Roadmap notes: live scalar CPU infrastructure and SV/Python fixture paths now work. Full protocol-agent wiring, live VexRiscv binding, interrupt/debug architectural comparison, general CSR qualification and C4 integration remain open.

## Testing
- Targeted CPU, UVM parser, ABI and feature tests: 73 passed, 0 skipped.
- Required fast set: 821 passed, 6559 deselected, 0 skipped.
- Native Verilator 5.052 with pinned Accellera UVM: two seeds and three deliberate corruptions passed all five C3 checks. Corruptions cover destination data, GPR state and MISA state.
- Icarus/cocotb: one native test passed, including GPR and MISA snapshots.
- Captured UVM/Spike replay: normal comparison and deliberate corruption both passed their C3 checks.
- rvw cov functional consumed 12 retirements across both seeds with no unknown encodings.
- All native builds used nice and bounded timeouts. No BOOM build, VexRiscv build, full Python suite, hardware run or CI wait. No generated VexRiscv RTL or cached build was present in this worktree; the short native tests used the seeded fixture.

## Issues
Refs: #296. This does not close the full CPU UVM or C4 scope. PR #394 remains open after the recovery retry limit.


## PR 537

[#537](https://github.com/riscPrint/risc-v-workstation/pull/537). Merged: 2026-11-13T02:42:10Z.

Title: feat(cosim): adjudicate spike and sail in one flow

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Run Spike and Sail in one CLI/MCP flow. Preserve both original reports, verify common captured input identities, and name which reference the DUT matches at the first differing boundary. Never convert disagreement into a pass.

## Testing
- Adjudication tests: 5 passed, including an actual native Spike/Sail run with a bounded ELF and strict comparison.
- Fast set: 821 passed, 6555 deselected.
- NOT RUN: RTL, automatic disagreement reduction, full capability-intersection campaigns.

## Issues
Refs: #100
Remaining: automatic reduction and specification-rule links. Unsupported reference capabilities remain inconclusive.

Roadmap notes: A single command now reports two-reference agreement or disagreement and retains all evidence. Native reference readiness is tested. No DUT result is claimed.


## PR 538

[#538](https://github.com/riscPrint/risc-v-workstation/pull/538). Merged: 2026-11-13T02:42:48Z.

Title: feat(privilege): add reri and digital dvfs campaigns

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Pin ratified RERI v1.0 at 12eef3f549fe54f817185b1e084b85537f442999 in project data. Add a small record model for severity/priority overwrite, sticky history, RDIP/SINV races, write protection and corrected-error counting. Generate logging/recovery programs with optional project RAS interrupt routes.

Add project-defined DVFS state sequences, retained-state programs and independent digital handshake observations. Require voltage readiness before increasing frequency and lower frequency before voltage reduction. Do not infer analog voltage or PLL qualification.

Preserve known C1 self-check failures when optional observations are missing. Add the privilege package Layout row.

## Testing

- Targeted tests: 28 passed, 0 skipped.
- RISC-V GCC: seven RERI and one DVFS program compile, including configured IRQ handlers.
- Python references: eight model-based outcomes pass. These are not Spike or DUT results.
- Fast set after rebase: 821 passed, 6557 deselected, 0 skipped.
- NOT RUN: RTL builds/simulations, physical error/poison injection, analog validation, full suite, long formal or CI.

## Issues

Refs: #181
Refs: #197

Remaining: project device drivers and observations, full record-bank options, physical poison propagation, error/reset interaction and DUT qualification. No issue is closed by model-based results.

Roadmap notes: Add pinned RERI logging/recovery and project digital DVFS campaigns. Record Python model-based results separately from native, DUT and physical qualification.


## PR 539

[#539](https://github.com/riscPrint/risc-v-workstation/pull/539). Merged: 2026-11-13T02:42:58Z.

Title: feat(cov): check reusable block evidence assumptions

Audit evidence label: unit tests only.

## Summary

Add `rvw cov block-check` and `cov_block_check`. Define a reusable block evidence interface for declared source hashes, exact tested parameters, environment assumptions and hash-bound C1 records. Require matching C1 block receipts and conclusive passing records. Reject changed sources, untested parameters, missing assumptions and stale evidence. New integration wiring is always uncovered.

## Testing

Targeted block-evidence and command-reference tests: 10 passed, zero skips. Fast set: 821 passed, 6558 deselected, zero skips.

NOT RUN: native block simulation, SoC integration, runtime assumption monitoring, physical qualification, full suite or CI. Tests use recorded C1 fixtures. Static assumption matching does not establish runtime enforcement.

## Issues

Refs: #167

Keep #167 open for native reusable-block evidence, complete transitive input capture, formal evidence transfer and integration wiring qualification.

Roadmap notes: The project-owned block evidence interface now checks exact tested configurations and declared integration assumptions through CLI/MCP. It cannot transfer evidence to new wiring or changed parameters automatically.


## PR 540

[#540](https://github.com/riscPrint/risc-v-workstation/pull/540). Merged: 2026-11-13T02:43:01Z.

Title: feat(lint): show rvw lint findings as vs code diagnostics

Audit evidence label: unit tests only.

## Summary

- New VS Code feature `vscode/features/lint/`: **Lint: Run rvw lint** (settings from `lint.settings` or a file picker), **Run Again**, **Open Saved Report or SARIF**, **Clear Diagnostics**.
- Findings from every backend (native lint, `rules`, `structural` CDC/RDC, `sdc`) become diagnostics in the Problems panel at their file and line; RTL `file:line:col` endpoints are parsed; unlocated findings go to line 1 of the settings file. Rule ID as code, `rvw lint <backend>` as source. Waived findings are hints with their reason; stale waivers are errors.
- Status bar: report status, active/waived counts and backends not run. It shows the report status as written; it never says clean unless `rvw lint` did.
- Parsing is in `src/model.ts` (no VS Code API) with unit tests for rvw.lint/1, SARIF 2.1.0, errors and inconclusive reports.

## Testing

- `cd vscode && npm ci && npm run typecheck && npm run build && npm test`: typecheck clean, build done, 26 tests passed (3 new).
- Python fast set: 821 passed, 6557 deselected.
- Not run: the extension in a real VS Code window (no integration test for this feature), `npm run package`.

## Issues

Refs: #22 (editor output). Remains: no quick fixes or waiver editing in the editor.

Roadmap notes: LINT/IDE — lint findings show as VS Code diagnostics from a run or saved SARIF.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 541

[#541](https://github.com/riscPrint/risc-v-workstation/pull/541). Merged: 2026-11-13T02:43:31Z.

Title: feat(debug): add n-trace codec, checks and vendor trace adapters

Audit evidence label: unit tests only.

## Summary
- `ntrace.py`: a separate, versioned N-Trace codec `rvw-ntrace/1`. It has a reference encoder from C2 (BTM and HTM modes, periodic sync, history and ICNT overflow through ResourceFull, Ownership on privilege change, traps as BTYPE 1), MDO/MSEO byte packing and unpacking, and a decoder that follows the ELF program image. E-Trace support never counts as N-Trace support.
- `rvw debug ntrace-check`: builds the expected stream from C2 (one encode per qualified window when `--filter` is set) and compares captured messages. It decodes in windows split at Error messages, known gaps and decode failures, and resyncs only at ProgTraceSync. Verdicts: `flow_match`, `partial_match`, `mismatch`, `leak`. A capture without its stop message is not a full match.
- `rvw debug ntrace-loss`: drop, overflow (Error), wrap and truncate faults with C3 results (`ntrace-loss`).
- Vendor adapters (`rvw.trace-adapter/1`) and `rvw debug trace-adapter`: an adapter must cite a specification and a license and give known packet vectors that unpack and repack exactly. An adapter without vectors is refused, because a vendor name is not evidence. `examples/trace/nexus-htm-template.toml` is a template whose vectors come from the rvw codec. No SiFive or Andes adapter is bundled, because there are no license-cleared vendor vectors.
- `Asm.auipc` for the model hart.

## Testing
- `rvw/.venv/bin/python -m pytest rvw/tests/test_debug_ntrace.py -q`: 12 passed. C2 comes from the model hart (branches, M-mode ecall, mret to U-mode, U-mode ecall). The tests cover the round trip, both modes with and without periodic sync, corruption, truncation, filters and leaks, the loss campaign, unmarked loss (mismatch) against marked loss (partial_match), and adapter vectors (pass, missing, wrong).
- Manual: the same flow on the Spike `traps.S` C2 decodes exactly in both modes.
- Fast set: 833 passed.
- Not run: no RTL N-Trace encoder capture; no vendor vectors.

## Issues
Refs: #194. Open: timestamps, multiple SRC, data trace, repeat-branch messages, an RTL encoder capture, and checking the SYNC/EVCODE/ETYPE/RCODE/BTYPE defaults against the ratified N-Trace tables.
Refs: #207. Open: SiFive and Andes adapters need vendor vectors with a usable license.

Roadmap notes: Trace area. N-Trace has its own reference encoder, decoder and loss/filter checks, separate from E-Trace. The vendor adapter mechanism requires packet vectors. Next step: an RTL encoder capture, and vendor vectors.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

## PR 542

[#542](https://github.com/riscPrint/risc-v-workstation/pull/542). Merged: 2026-11-13T06:15:26Z.

Title: feat(vip): discover typed buses and generate bench skeletons

Audit evidence label: unit tests only.

## Summary

Add `rvw vip list`, `buses` and `bench` with matching MCP tools. Inventory all 20 current protocol/model modules. Select buses by exact Spinal bundle class from C6. Generate explicit captured pin bindings. Check required pins, including UART serial handles. Refuse ambiguous selections and existing output files. Generated benches stop until project reset, stimulus and expected results are added.

Preserve the new split contract documentation layout. Put the bench contract in `docs/contracts/vip.md` and regenerate the command reference.

Roadmap notes: typed bus discovery and cocotb skeleton generation are implemented. Stream/TileLink mapping and project-specific optional-pin/width adaptation remain open. This PR remains open after the brief's five merge retries. Its current head includes the final inventory/binding update.

## Testing

- Catalog/CLI/MCP and skeleton tests: 4 passed.
- All targeted VIP tests: 204 passed.
- Required fast tests on current head: 878 passed, 1 skipped, 7326 deselected.
- Earlier unrelated release-hygiene failure on main was fixed upstream. The final run passed.
- Not run: generated benches on project RTL, UVM runtime builds, BOOM jobs or full Python suite.

## Issues

Refs: #205, #209. This adds shared discovery and scaffolding. It does not close full protocol qualification.


## PR 543

[#543](https://github.com/riscPrint/risc-v-workstation/pull/543). Merged: 2026-11-13T02:58:24Z.

Title: feat(formal): replay failed equivalence partitions in simulation

Audit evidence label: ran on seeded RTL fixture.

## Summary

Extend the existing `rvw formal cex` CLI and MCP path to failed closed eqy output partitions. Capture the failed partition model and both source snapshots. Use the existing waveform edits, Yosys simulation, reduction and simulation testbench export.

Require an actual failed native partition. Report `source_flow: equiv`. Reproduction needs the same assertion in baseline and edited simulation with no assumption failure. Preserve replay exit 1 and inconclusive proof status. This is partition simulation, not project simulator or whole-core reproduction.

## Testing

Native targeted replay and existing BMC replay tests: 15 passed. Include an end-to-end failed equivalence proof, simulation reproduction, generated artifacts and refusal of missing/nonfailed/foreign partition models.

Additional native export validation: test_equiv_export.py, 3 passed. It checks committed source revisions, module selection and small one-command export/proof cases.

Required fast set after rebase: 821 passed, 6559 deselected in 80.73s (0:01:20).

NOT RUN: BOOM builds, full Python suite, long formal jobs, project simulator replay or whole-core reproduction.

## Issues

Refs: #18.

Roadmap notes: Add failed equivalence partition simulation replay through the existing counterexample command. Project source mapping, blackbox contracts, generated clocks and BOOM proof reproduction remain open.


## PR 544

[#544](https://github.com/riscPrint/risc-v-workstation/pull/544). Merged: 2026-11-13T02:44:15Z.

Title: feat(sim): restore live vexriscv state through the spinal bridge

Audit evidence label: ran on real core RTL.

## Summary

Add live synchronous register and memory capture through the Spinal bridge. Add a project-owned VexRiscv cycle loop that captures pending bus responses, RAM, counters, trap state and C2 writer state. Restore this state in a new JVM without executing the instruction prefix.

Bind the snapshot to the ELF, emitted RTL and compiled harness classes. Check its digest before restore. The fixed-latency RAM-only probe is separate from the general Python snapshot port and from native `--savable` serialization.

## Testing

- Native VexRiscv `test_checkpoint_probe.py`: 1 passed. Checkpoint after retirement 8; complete resumed C2 bytes equal the uninterrupted trace, including cycles and terminal event. Core a62c145aa042a5de874344e0a7683bd7c8c8c870, SpinalHDL 1.15.0.
- Native `testOnly riscvsim.BridgeStateSpec`: 1 passed. Restore registers and memory into a fresh model; reject malformed state before writes.
- Targeted Python checkpoint tests: 14 passed.
- Fast Python set: 810 passed, 6258 deselected before rebase. Post-rebase fast result recorded below.
- NOT RUN: BOOM, full Python suite, random-latency/SoC/ROI continuation, throughput measurements, GitHub CI.

## Issues

Refs: #132, #346. General snapshot-port integration, native implementation-state serialization, BOOM qualification and save/restore cost measurements remain open.

Roadmap notes: VexRiscv now has a native fresh-process live continuation probe through the Spinal register/memory bridge. The bounded smoke suffix matches exactly. This does not qualify all adapter modes or close the complete checkpoint work.

Post-rebase fast set: 820 passed, 6618 deselected, 1 failed. The failure is an unrelated incoming-main release-hygiene finding in `rvw/tests/cosim/test_adjudicate.py:51` (`personal_path`). This PR does not change that file.


## PR 545

[#545](https://github.com/riscPrint/risc-v-workstation/pull/545). Merged: 2026-11-13T02:44:19Z.

Title: feat(wave): add typed bundle and stream values from the database

Audit evidence label: unit tests only.

## Summary

- `rvw wave value WAVE NAME --at T --db DESIGN.db` (MCP `wave_value`): typed value of a signal, Bundle, Stream/Flow, Vec or Area. Leaves are nested by Spinal path below NAME (`payload.0`) with value, database type, wave name and enum element. A Stream gets `fire` (valid && ready; null when unknown). Leaves absent from the wave are listed.
- `test_mcp_tools.py` tool count updated (main had moved again).

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_wave_typed.py rvw/tests/test_mcp_tools.py -q`: all passed, 0 skipped (cluster database Stream `io.cmd` with a Vec payload and an enum register).
- Fast set: 821 passed.
- Not run: interactive Surfer/SpinalWaves rendering (#83).

## Issues

Refs: #83, #43. Agents get typed hierarchy, Vec and enum values without the GUI. #83's interactive viewer checks stay open.

Roadmap notes: waves area — `rvw wave value` returns typed Bundle/Stream/Vec values with enum names.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 546

[#546](https://github.com/riscPrint/risc-v-workstation/pull/546). Merged: 2026-11-13T02:46:38Z.

Title: feat(csim): add multiperspective perceptron qualification references

Audit evidence label: unit tests only.

## Summary

- `rvw csim qualify --reference` gains pinned CBP-5 (2016) references: `cbp2016-mpp-64kb`, `cbp2016-mpp-8kb`, `cbp2016-mpp-unlimited` (D. A. Jiménez, multiperspective perceptron), `cbp2016-mpp-tage-64kb` (MPP with TAGE) and `cbp2016-pruett-64kb`. Archives are fetched into the csim cache and checked by sha256; nothing enters the repository.
- The harness compiles a reference's own translation units when needed (`sources`), allocates the predictor on the heap (the unlimited predictors overflow the stack) and the shim adds `<cassert>`.
- References without a matched csim study need `--study`; the report says whether the NOSKIP guard applied.
- New budget-matched study `ComponentSims/examples/hashed-perceptron-64kb.json` (64.05 KiB, 16 tables).
- Seznec's unlimited predictor stops on its own assertion with this harness and is not listed.

Measured on the six Spike benchmark traces: csim hashed perceptron 64 KB vs MPP 64 KB is within about 10% MPKI on all six (qsort 41.75 vs 40.90); csim TAGE-SC-L 64 KB vs MPP unlimited ranges from 0.27 vs 0.36 (dhrystone) to 16.09 vs 12.57 (spmv). Table in `ComponentSims/README.md`.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_csim.py -q` — 12 passed (reference table sanity, no-study error).
- Native qualification runs against all five new references on six traces.
- `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q` — 820 passed, 1 failed: `test_release_hygiene.py::test_tracked_text_has_no_personal_paths` reports `rvw/tests/cosim/test_adjudicate.py:51`, a file already on `origin/main` from the cosim area; this PR does not touch it.
- Not run: full slow suite, CI not awaited.

## Issues

Refs: #351 — more pinned independent references.

Roadmap notes: Component simulators: qualification references now include the CBP-5 multiperspective perceptron (8 KB, 64 KB, unlimited), MPP+TAGE and Pruett predictors.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 547

[#547](https://github.com/riscPrint/risc-v-workstation/pull/547). Merged: 2026-11-13T02:52:12Z.

Title: feat(cosim): assess optional cheri reference configuration

Audit evidence label: unit tests only.

## Summary
Add a short pinned CHERI Sail assessment and optional platform configuration hooks. Require a full reference commit and capability width. Refuse stock scalar comparison when CHERI is selected. Also remove a local path from the new two-reference test so it uses RVW_SAIL or PATH.

## Testing
- CHERI hook and fail-closed tests: 2 passed.
- Release-hygiene checks passed after the local-path fix.
- Fast set: 833 passed, 6640 deselected.
- NOT RUN: CHERI reference build, CHERI prototype or capability-state comparison. This PR is the requested assessment and config scope only.

## Issues
Refs: #210
Remaining: capability trace schema, pinned dependency assessment, native reference bridge and independent checking prototype.

Roadmap notes: CHERI is recorded as an optional architecture assessment. No standard-profile or capability comparison result is claimed.


## PR 548

[#548](https://github.com/riscPrint/risc-v-workstation/pull/548). Merged: 2026-11-13T02:47:55Z.

Title: feat(lint): check toggle handshakes and copy waivers in vs code

Audit evidence label: unit tests only.

## Summary

- CDC: qualified data whose qualifier source register toggles itself is a toggle handshake (`StreamCCByToggle` shape). It gets a `toggle_stable` obligation, and `rvw lint --emit` writes checker `rvw_cdc_toggle`: data changes only in the cycle the request toggles. `rvw.cdc-obligations/1` gains the kind (documented).
- VS Code lint feature: quick fix **Copy rvw lint waiver for <rule>** copies an exact waiver row (config, rule, endpoint, `finding_id`) with a `TODO` reason; stale-waiver and id-less findings are refused. Diagnostics now keep the finding id (from rvw.lint/1 or the SARIF fingerprint).

## Testing

- With native Yosys: `rvw/.venv/bin/python -m pytest rvw/tests/test_lint_hdl.py rvw/tests/test_lint_cdc.py -q`: all passed. New native test: a Verilog toggle handshake through `build-hdl`, `--emit` and a Yosys `sat -seq 12` BMC on the checked RTL; the correct design holds and a design that changes data between toggles fails with "proof did fail".
- `cd vscode && npm run typecheck && npm run build && npm test`: 27 passed.
- Fast set: 832 passed, 1 failed, 6652 deselected. The failure is `test_release_hygiene.py::test_tracked_text_has_no_personal_paths` on `rvw/tests/cosim/test_adjudicate.py:51`, a file this PR does not touch (already on `main`).
- Not run: the extension in a real VS Code window.

## Issues

Refs: #22.

Roadmap notes: LINT — toggle-handshake data-stability checker in the CDC emit step; VS Code quick fix for exact waivers.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 549

[#549](https://github.com/riscPrint/risc-v-workstation/pull/549). Merged: 2026-11-13T02:48:41Z.

Title: feat(sim): check hart lifecycle and shared interrupt ownership

Audit evidence label: unit tests only.

## Summary
Add a project-normalized HSM-style hart lifecycle observer. Check start entries and opaque arguments, stop/start transitions, bounded transition age, independent reset epochs, coalesced IPI inputs and shared interrupt-claim ownership. Keep reset/IPI and claim-drain policy explicit.

## Testing
Three targeted Scala tests passed, no skips or cancellations.

The required fast set ran after rebase: 832 passed, 1 failed, 0 skipped. The failure is inherited from origin/main: test_tracked_text_has_no_personal_paths reports rvw/tests/cosim/test_adjudicate.py:51. This PR does not edit that other worker's file or waive its check.

NOT RUN: SBI firmware flows, CLINT timer/PLIC RTL, real hotplug, BOOM builds, full Python suite. Tests drive normalized lifecycle events. No architectural platform qualification is claimed.

## Issues
Refs: #151. Actual firmware/RTL lifecycle and shared-resource campaigns remain open.

Roadmap notes: generic lifecycle checks now separate project stop/reset policy from shared IPI and interrupt ownership checks. Production SBI HSM and CLINT/PLIC integration remain open.


## PR 550

[#550](https://github.com/riscPrint/risc-v-workstation/pull/550). Merged: 2026-11-13T02:48:37Z.

Title: feat(arch): time project-declared custom register operations

Audit evidence label: unit tests only.

## Summary
Time project-declared custom register operations from C2. Rules select reserved custom opcodes, declare sources/destination and use explicit latency classes and port bindings. Reject overlapping rules, mismatched C2 registers and hidden control/memory effects. Search can sweep custom latency on the same committed path.

## Testing
76 targeted OoO tests passed. Fast set: 832 passed, one failed. The inherited release-hygiene failure is rvw/tests/cosim/test_adjudicate.py:51:personal_path. It remains on current main and is outside this worker's ownership. The test and file are unchanged. A targeted hygiene recheck also failed: 39 passed, one failed.

No RTL simulation, BOOM build, gem5 run, full suite or physical PPA measurements ran. Custom instruction semantics, software costs and physical implementation remain unverified.

## Issues
Refs: #196.

Roadmap notes: The own model can time declared register-only custom operations. Independent correctness checks, software trade-offs and RTL PPA remain separate requirements. Current main has an unrelated release-hygiene failure in the cosim area.


## PR 551

[#551](https://github.com/riscPrint/risc-v-workstation/pull/551). Merged: 2026-11-13T02:50:32Z.

Title: feat(wave): add a head-to-head debug task protocol and runner

Audit evidence label: unit tests only.

## Summary

- `rvw wave bench TASKS.json [--var NAME=VALUE]` (MCP `wave_bench`, a job): runs `rvw.debug-tasks/1` files. Each task: a question, one rvw command (`argv` with `{NAME}` / `{dir}` variables), `expect` checks on the JSON output (`equals`, `contains`, `any`), and a hand-recorded `reference` from another tool (`tool`, `seconds`, `steps`, `solved`, `notes`).
- Status per task: `solved`, `unsolved`, `no_checks` or `error`, with rvw wall seconds. A speedup is reported only for solved tasks with a recorded reference time; without references the result says nothing is compared.
- `examples/wave-tasks/`: protocol README and four fixture tasks (driver trace, Stream protocol issue, first stall, handshake latency). No reference results are recorded.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_wave_tasks.py rvw/tests/test_mcp_tools.py -q`: all passed (example pack: 4/4 solved; missing variable, unsolved and reference speedup cases).
- Fast set: 832 passed, 1 failed: `test_release_hygiene.py::test_tracked_text_has_no_personal_paths` on `rvw/tests/cosim/test_adjudicate.py:51`, a file from another area already on main; not touched here.
- Not run: any Verdi session (no reference times recorded).

## Issues

Refs: #297. Adds the head-to-head task comparison protocol and the rvw side of its measurement. Remaining: record reference results with Verdi on the same tasks, and add tasks on real core waves.

Roadmap notes: debug area — head-to-head debug task protocol (`rvw wave bench`, `examples/wave-tasks/`).

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 552

[#552](https://github.com/riscPrint/risc-v-workstation/pull/552). Merged: 2026-11-13T02:50:36Z.

Title: feat(regress): verify guest pointer controls and hlvx exemption

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Add 81 Ssnpm guest pointer programs. Check VS/VU HLV/HSV masking through henvcfg.PMM and senvcfg.PMM. Check U-mode HUPMM controls with HU enabled and explicit host Bare initialization. Confirm HLVX remains exempt from masking. Read PMM back and check exact fault cause/tval/PC or recovered data. Keep pointer transforms outside the unsupported nested reference path, which remains inconclusive.

## Testing

- Final guest-pointer module: two passed, zero skipped. All 81 generated programs passed short Spike runs.
- Earlier fast run: 832 passed and one unrelated baseline release-hygiene failure at rvw/tests/cosim/test_adjudicate.py:51. That file was unchanged by this work. No check was waived.
- Final post-rebase fast count below.
- RTL, BOOM, Sail, debug mode and full Python suite: NOT RUN.

## Issues

Refs: #179, #140.

Debug-state masking and an independent nested pointer-transform model remain open. No DUT result is claimed.

Roadmap notes: guest pointer suites now cover VS/VU and U-mode HUPMM controls plus the HLVX exemption. Debug state and independent pointer-transform capture modeling remain open. ROADMAP.md and TODO.md were not edited.
833 passed, 6668 deselected in 98.37s (0:01:38)


## PR 553

[#553](https://github.com/riscPrint/risc-v-workstation/pull/553). Merged: 2026-11-13T02:51:47Z.

Title: feat(lint): check sdc generated clocks and multicycle paths

Audit evidence label: unit tests only.

## Summary

- SDC check (`rvw/src/rvw/lint/sdc.py`): `create_generated_clock` targets must be design register outputs (`sdc.unmatched_endpoint`), and `-divide_by` must match the inferred divider (`sdc.generated_mismatch`). `set_multicycle_path` must name registers with an elaborated register path between them (`sdc.unmatched_multicycle`).
- Object patterns match in both directions (SDC globs against concrete names, `register_pattern` against concrete SDC names), so concrete names such as `div_reg/Q` also match.
- Round-trip test: the generated SDC checked against the same design gives no findings.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_lint_sdc.py -q`: 7 passed. Extracted fixtures (`RVW_LINT_FIXTURES`): 17 passed.
- Fast set: 833 passed, 6680 deselected.
- Not run: any STA tool; the full Python suite.

## Issues

Closes: #185. With #448 this meets the acceptance items: declared clocks, generated clocks, false paths and multicycle intent are checked against elaborated endpoints; unmatched and unconstrained clocks, endpoints and crossings are reported; the backend states that it checks logical intent, not routed timing signoff.

Roadmap notes: LINT — SDC intent (#185) done: generation from clock-domain data plus checks of clocks, generated clocks, exceptions and multicycle paths against the design.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 554

[#554](https://github.com/riscPrint/risc-v-workstation/pull/554). Merged: 2026-11-13T02:53:23Z.

Title: feat(memory): model queued mesi and moesi directories

Audit evidence label: unit tests only.

## Summary
Add finite queued MESI/MOESI directory profiles. Model separate capacity-one A/B/C/D/E message queues, per-line active transactions, abstract upgrades and repeated requests. Check exclusive/dirty ownership and independent data invariants with named weak-fairness SCC progress. Add CLI/MCP entry points and preserve explicit state-budget outcomes.

## Testing
17 targeted Python tests passed, no skips. MOESI exhausted the two-request/one-line graph at 627 states and the one-request/two-line graph at 391 states. Five seeded defects failed: lost ack, stale data, early grant, starvation and cyclic wait. The fast Python set passed: 833 passed, no skips. The inherited cosim path hygiene failure is fixed on the rebased main.

NOT RUN: TLC/Murphi independent model checks, real coherent-fabric RTL, BOOM builds, full Python suite. Messages remain whole and single beat. Source/sink allocation, voluntary eviction and transaction reset are not modeled. No RTL refinement claim is made.

## Issues
Refs: #128, #361. Independent model cross-checks and RTL refinement remain open.

Roadmap notes: finite coherence experiments now include queued MESI/MOESI profiles, multiple line transactions and repeated requests with named fairness. Broader directory and real-fabric claims remain open.


## PR 555

[#555](https://github.com/riscPrint/risc-v-workstation/pull/555). Merged: 2026-11-13T02:52:23Z.

Title: feat(privilege): cross all disabled-feature control combinations

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Cross all 64 requested combinations of SUM, MXR, MPRV, TVM, TW and TSR with actual privilege entry. Add five disabled-feature profiles: FS Off, VS Off, absent F, absent V and absent S. Generate 1152 programs in total. Check cause, exact PC and control retention using captured WARL readback. Account for MRET clearing MPRV on lower-mode entry.

## Testing

- Targeted tests: 28 passed, 0 skipped.
- Short Spike smoke: 72 generated programs compiled and passed across all profiles, modes and operations at masks 00, 15, 2a and 3f. This is a sample, not a pass for all 1152 programs.
- Fast set after rebase: 833 passed, 6673 deselected, 0 skipped.
- NOT RUN: other generated programs, RTL builds or simulations, full suite, long formal or CI.

## Issues

Refs: #139

SUM/MXR data-permission cases remain in the MMU framework. These disabled-operation checks do not replace them. Full campaign DUT qualification remains open.

Roadmap notes: Add complete requested control-mask generation for disabled FS/VS and absent F/V/S profiles. Record 72 bounded native reference smoke results separately from the full generated matrix and unrun DUT work.


## PR 556

[#556](https://github.com/riscPrint/risc-v-workstation/pull/556). Merged: 2026-11-13T02:52:47Z.

Title: feat(fault): add fault injection campaigns against c2

Audit evidence label: unit tests only.

## Summary
- New tool `rvw fault` (`rvw/src/rvw/fault/`, README, Layout row) with these subcommands:
  - `sites`: register sites from the design database (`signals`, kind `reg`, not pruned; generated registers only on request; include/exclude globs).
  - `plan`: a seeded sample of `stuck0`, `stuck1` and `flip` faults over a cycle window. It records the population (site bits × cycles × kinds) and uses exhaustive mode when the population is small.
  - `run`: a golden run plus one run per fault through the core adapter (`run --fault FILE`, new optional C1 extension). The adapter must confirm the injection in `details.fault`, so injection success is measured separately from detection. Each fault is classified against the golden C2 architectural records: `detected` (failure status, a declared mechanism in `details.detections`, or a timeout with `--watchdog`), `silent_corruption`, `safe`, `timeout`, `not_injected` or `inconclusive`.
  - `report`: counts, denominators, sampled fraction, diagnostic coverage with a 95 % Wilson interval, safe fraction, unresolved faults. Outputs also include C3 (`fault-campaign`: detected or safe = pass, SDC = fail) and `outcomes.json` with the evidence for each fault. There is no ISO 26262 or reliability claim.
- MCP: `fault_sites`, `fault_run`, `fault_report`. Contract: "C1 fault injection".

## Testing
- `rvw/.venv/bin/python -m pytest rvw/tests/test_fault.py -q`: 6 passed. The tests use a fake C1 adapter that runs the debug model hart with a parity checker on one register. Each of detected-by-self-test, detected-by-parity, silent corruption, safe and not-injected (unreached cycle, unknown site) is exercised, together with a refused failing golden run, adapter-confirmation rules, seeded plans and the CLI.
- Fast set: 838 passed, 1 failed. The failure is `test_release_hygiene.py::test_tracked_text_has_no_personal_paths` on `rvw/tests/cosim/test_adjudicate.py:51`, a file already on main from another area. This change does not touch it.
- Not run: no real core adapter implements `--fault` yet. The RiscvSim BOOM adapter does not.

## Issues
Refs: #52. Done: the stuck-at and transient campaign, injection success measured apart from detection, classification, denominators and coverage. Open: protected-memory codewords, FMEDA records and equivalence groups, lockstep/redundancy campaigns, security fault campaigns, memories as sites, a RiscvSim `--fault` implementation, and tool-qualification documents.

Roadmap notes: Safety area. `rvw fault` gives seeded stuck-at/flip campaigns classified against golden C2, with diagnostic coverage and confidence intervals. Next step: `--fault` in the RiscvSim adapter (Verilator force on database register paths).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

## PR 557

[#557](https://github.com/riscPrint/risc-v-workstation/pull/557). Merged: 2026-11-13T02:53:52Z.

Title: feat(arch): share project descriptions across timing engines

Audit evidence label: unit tests only.

## Summary
Allow the own timing engine to read the same O3 project description as native gem5. An explicit ooo table supplies own-model execution timing and policies. Shared CPU widths, capacities, decode width and FTQ size are projected from common fields. Reject conflicting duplicate dimensions and mismatched C2 presets. Keep separate own-model files supported.

## Testing
80 targeted OoO tests passed. The standalone model/front-end/projection group passed 61 tests and skipped one native test. 833 fast tests passed. The previously observed upstream release-hygiene failure is fixed on this base.

No RTL simulation, BOOM build, gem5 run, full suite or native timing qualification ran. Shared dimensions do not establish matching queue partitioning, predictor state, caches or pipeline timing. Execution latencies remain explicit project data.

## Issues
Refs: #72.

Roadmap notes: Both architecture engines can consume one O3 project file. Width/capacity drift is rejected. Dynamic timing agreement remains unmeasured.


## PR 558

[#558](https://github.com/riscPrint/risc-v-workstation/pull/558). Merged: 2026-11-13T02:53:09Z.

Title: feat(csim): add micro-op cache to the front-end model

Audit evidence label: unit tests only.

## Summary

- `frontend.op_cache`: a trace-driven micro-op cache in the csim front-end model. Lines are keyed by aligned fetch window (`window_bytes`); a window takes `ceil(ops / ops_per_line)` lines of one set (LRU), more than `max_lines_per_window` is uncacheable. A group hits when all its lines are present: it skips the I-cache and legacy decode and delivers `op_width` ops per cycle after `latency`; each change between op-cache and legacy delivery costs `switch_penalty`. Context rows flush it (default).
- Report: lookups, hit rate, op coverage, fills, uncacheable windows, mode switches, context flushes, storage (`op_bits` per op). Sweep metric `op_cache_coverage`.
- This is the csim component model; the gem5 micro-op cache in #359 stays with the arch area.

## Testing

- `rvw/.venv/bin/python -m pytest ComponentSims/tests -q` — 99 passed (hit rate and coverage above 95% on a warm loop, higher delivered IPC than legacy decode, tiny cache misses, uncacheable windows, context flush, storage formula).
- `rvw/.venv/bin/python -m pytest rvw/tests/test_csim.py rvw/tests/test_csim_formats.py -q` — 27 passed.
- `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q` — 833 passed after rebase.
- Not run: op cracking or fusion (one instruction = one op), full slow suite, CI not awaited.

## Issues

Refs: #360 — front-end component coverage. Refs: #359 (gem5 side, not changed).

Roadmap notes: Component simulators: micro-op cache in the front-end delivery model.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 559

[#559](https://github.com/riscPrint/risc-v-workstation/pull/559). Merged: 2026-11-13T02:54:57Z.

Title: feat(uvm): add cpu program and seeded control sequences

Audit evidence label: unit tests only.

## Summary
Add a CPU virtual sequencer. Connect shared memory, control requests and the retirement scoreboard. Add a program sequence that loads the ELF-derived image, resets the DUT and waits for a bounded retirement count. The native CPU example now uses it.

Add seeded interrupt/debug request sequences in SV and Python. Project data supplies the allowed IRQ mask. Expose the Python callbacks through a pyuvm sequence. Extend the pin fixture with 16 random transfers and a final resume after its six directed transfers.

Roadmap notes: reusable CPU program and random pin sequencing now exists in SV and Python. These pin checks do not establish CPU interrupt/debug architectural behavior. Live protocol binding and C4 source identity remain open.

## Testing
- Targeted UVM/CPU/control/feature tests: 81 passed, 0 skipped. Includes the pyuvm control sequence.
- Required fast set: 833 passed, 6686 deselected, 0 skipped.
- Native CPU virtual-sequence path: 5/5 C3 checks passed across two seeds and three deliberate corruptions.
- Native component/pin suite: initial compile reached its 120-second limit and reported build error. A separate bounded make resumed that build. Its subsequent normal and three corruption runs passed all 10 C3 checks. The original timeout result remains separate from the passing resumed results.
- All native commands used nice and bounded timeouts. No BOOM build, full Python suite, hardware run or CI wait.

## Issues
Refs: #296. Architectural IRQ/debug comparison and C4 acceptance remain open.


## PR 560

[#560](https://github.com/riscPrint/risc-v-workstation/pull/560). Merged: 2026-11-13T02:54:40Z.

Title: feat(sim): run a spike bootstrap continuation on vexriscv

Audit evidence label: ran on real core RTL.

## Summary

Capture a bounded RV32IM M-mode Spike state after K retirements. Read all GPRs, project profile CSRs and the complete declared physical RAM. Add a VexRiscv bootstrap image path and a native test that resumes at a saved non-reset PC.

The test changes mscratch before capture. It compares the post-transfer C2 instruction, PC, writeback and active memory fields against the original Spike continuation through tohost. It does not resynchronize Spike. The bootstrap reserves code RAM and changes counters.

## Testing

Ten targeted capture/injection tests passed. The native bootstrap continuation passed, including the post-transfer mscratch read. Post-rebase fast set: 833 passed, 6713 deselected.
NOT RUN: full Python suite, fresh-Spike import, C1 restore-port integration, pre-fetch readback, FP/system RTL, BOOM, GitHub CI.

## Issues

Refs: #347, #350. This is a real RV32IM bootstrap sample. Full interchange, fresh-Spike import, C1 replay identities and pre-fetch readback remain open. FP/system injection remains fixture-only.

Roadmap notes: Add native Spike-to-VexRiscv RAM-only bootstrap continuation evidence. Keep the qualified architectural-checkpoint contract, unsupported profile work and Linux boot separate.

Validation results: 10 targeted capture/injection tests passed. Native Spike-to-VexRiscv continuation passed; the final version also passed with an mscratch read and branch in the suffix. Post-rebase fast set: 833 passed, 6713 deselected. The extra fresh-process checkpoint regression timed out after 600 seconds waiting for the shared vex lock behind another worker's formal campaign. It did not start RTL execution. The original checkpoint native test passed in #544.


## PR 561

[#561](https://github.com/riscPrint/risc-v-workstation/pull/561). Merged: 2026-11-13T02:55:09Z.

Title: feat(formal): emit shared sva from a spinal property builder

Audit evidence label: unit tests only.

## Summary
Add spinalchecks.Sva, a small Scala property builder beside Spinal RTL. Resolve final local signal names after generation and emit the same SVA used by the existing frontend. Support finite sequences, sampled values, implication, assert/assume/cover and explicit reset. Keep emission separate from RTL insertion and verification.

## Testing
- Locked SpinalChecks Test/compile passed. Initial compile took 36 seconds; the final targeted test compile took 5 seconds.
- Targeted JVM Scala tests: 3 passed, including final names from a tiny elaborated Spinal design. No simulation was run for that naming check.
- Python/JVM/native emission tests: 3 passed, including positive and seeded-fault SVA on SMTBMC/Yices.
- Fast set: 839 passed, 6741 deselected, no skips.
- NOT RUN: full Python suite, BOOM, long sbt test suites, long formal jobs, automatic RTL assertion injection, GitHub CI wait.

## Issues
Refs: #61

The builder emits module-local snippets. Projects must include or bind them before verification. Full SVA and automatic property insertion remain outside this API.

Roadmap notes: add a small Spinal Scala property API that emits shared SVA. Keep full language qualification and automatic insertion partial.


## PR 562

[#562](https://github.com/riscPrint/risc-v-workstation/pull/562). Merged: 2026-11-13T02:55:22Z.

Title: feat(cosim): compare optional qemu boot observations

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add bounded single-hart QEMU CPU-log comparison through CLI and MCP. Compare PC, next PC, integer source values and integer destinations. Retain input hashes and unchecked state. Add an optional partial third reference to Spike/Sail adjudication. QEMU cannot outvote an architectural mismatch.

## Testing
- QEMU/adjudication tests: 9 passed, including native QEMU and native Spike/Sail.
- All ten additions together: 35 passed, 0 skipped in 5.11 seconds. Native extension, debug halt, H delegation and multi-hart shared RAM tests included.
- Fast set passed after rebase.
- NOT RUN: full Linux boot, RTL, asynchronous event injection, non-integer QEMU state comparison.

## Issues
Refs: #100
Remaining: full Linux boot and interrupt synchronization, QEMU memory/CSR/FP/vector/H state. The current adapter checks bounded boot segments before unsupported events and sets architectural_match=false.

Roadmap notes: QEMU is an optional partial third reference for bounded boot observations. Reports state the compared fields. Unsupported events are inconclusive. No complete Linux or architectural match is claimed.


## PR 563

[#563](https://github.com/riscPrint/risc-v-workstation/pull/563). Merged: 2026-11-13T02:56:49Z.

Title: feat(memory): run seeded concurrent programs on spike

Audit evidence label: unit tests only.

## Summary
Run the seeded concurrent RV64 fragments on native Spike. Add a bare-metal hart dispatch, independent completion flags, a bounded HTIF completion wrapper and an explicit shared-memory linker layout. Add CLI/MCP entry points and retain source/ELF hashes and native command details.

## Testing
Six targeted Python tests passed, no skips. The native seed-7 smoke completed on three Spike harts with 20 generated operations per hart. Timeout handling remains inconclusive. The fast Python set ran before push.

NOT RUN: generated-program RTL execution, C2 capture from Spike, axiomatic ordering for this native smoke, BOOM builds, full Python suite. A completion pass does not establish memory-model conformance. The report retains ordering:not_checked and rtl:not_run.

## Issues
Refs: #90, #91, #97. Project C2 dependency capture and RTL generator campaigns remain open.

Roadmap notes: seeded races, locks and atomics now have a bounded native multi-hart completion runner. Ordering and RTL evidence remain separate.


## PR 564

[#564](https://github.com/riscPrint/risc-v-workstation/pull/564). Merged: 2026-11-13T02:56:38Z.

Title: feat(formal): check dynamic pmp and epmp access safety

Audit evidence label: ran on seeded RTL fixture.

## Summary

Add a `pmp` formal app property over a project CSR-bank port binding. Check OFF, TOR, NA4 and NAPOT with four-byte granularity, full access containment, first-touch priority, effective privilege, locked PMP permissions, MMWP and MML shared-region permissions.

Support dynamic policy inputs. For fixed response latency, retain each request's permission across later CSR changes. Check grant safety only. Keep CSR writes, WARL, sticky/lock transitions, RLB, variable response ordering and other initiators outside the claim.

## Testing

Native targeted tests: 7 passed. Controls cover all address modes and MML table entries at zero/one response latency. Mutants grant illegal accesses, use current policy for old requests, and ignore first-touch overlap. Invalid address width is refused. Early runs exposed a loop-variable latch and an X index in generated code; both are fixed. Independent fixture table and region errors were also corrected.

Required fast set after rebase: 839 passed, 6782 deselected in 84.18s (0:01:24).

NOT RUN: BOOM builds, full Python suite, long formal jobs, whole-core isolation or CSR update/lock qualification.

## Issues

Refs: #20.

Roadmap notes: Add request-time dynamic PMP/ePMP grant-safety proofs with MML/MMWP and fixed-latency responses. CSR update rules, RLB, lock enforcement, variable response IDs and complete SoC initiator coverage remain open.


## PR 565

[#565](https://github.com/riscPrint/risc-v-workstation/pull/565). Merged: 2026-11-13T02:56:56Z.

Title: feat(formal): measure captured assertion enable activation

Audit evidence label: unit tests only.

## Summary
Measure recognized Yosys assertion-enable guards automatically in captured-model core extraction. Retain bounded activation outcomes, reduced blocking cores and blocking assumption cells. Scope assertion and assumption metadata to the correct module so repeated module-local indices cannot select a child property by mistake.

Show module summaries, core status and labels, cell-coverage availability, activation and source locations in the HTML testplan. Support explicit core-to-inventory aliases while retaining the native property ID.

## Testing
- Activation, core export, solver and testplan tests: 23 passed, 0 skipped.
- Native Yosys/Z3 tests exercise reachable and assumption-blocked enables.
- An actual ABC/AIGER BMC job was exported to SMT automatically and rechecked with Z3. No hand-written SMT was supplied.
- Required fast set: 839 passed, 6744 deselected, 0 skipped.
- Not run: full suite, BOOM build or simulation, long formal jobs, general liveness, native typed viewer navigation or CI wait.

## Issues
Refs: #62, #60

Roadmap notes: Automatic procedural assertion-enable measurement and blocking assumption cores are available. These guards are not every logical antecedent in a property. Full non-vacuity, assumption adequacy, complete functional requirement obligations and minimal logic-cell cores remain open. Bounded unreachability does not authorize UNR coverage exclusions. An inventory alias is a declared association, not a semantic-equivalence certificate.


## PR 566

[#566](https://github.com/riscPrint/risc-v-workstation/pull/566). Merged: 2026-11-13T02:57:36Z.

Title: fix(wave): keep fst array names when reading through wellen

Audit evidence label: unit tests only.

## Summary

Fix for the direct FST reader from #529 and the wellen index reader from #412:

- wellen splits Verilator unpacked-array elements into a scope plus an `[i]` variable (`arrays.a.[0]`). Rejoin them as the VCD reader names them (`arrays.a.a[0]`), so searches and indexes use the same names as `fst2vcd`.
- wellen drops the index of escaped Icarus names (`\a[0]` and `\a[1]` become one `\a` variable). Such FSTs now fall back to `fst2vcd` for searches, and an `auto` index build uses the VCD reader. An explicit `--reader wellen` build refuses them (`WellenNames`).
- FSTs that pywellen cannot read also fall back to the converter path, which reports the real error.

## Testing

- `rvw/tests/test_wave_array_names.py` now also runs `search.edges` and `search.find` on real Icarus and Verilator FST/VCD waves. Before the fix, the Verilator FST case returned no matching names and the Icarus FST case merged two elements.
- `rvw/.venv/bin/python -m pytest rvw/tests/test_wave.py rvw/tests/test_wave_capture.py rvw/tests/test_wave_index.py rvw/tests/test_wave_search.py rvw/tests/test_debug_wave_values.py rvw/tests/test_wave_array_names.py rvw/tests/test_wave_temporal.py -q`: 240 passed, 0 skipped (native Icarus and Verilator from oss-cad-suite).
- Fast set: 839 passed.

## Issues

Refs: #173.

Roadmap notes: none.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 567

[#567](https://github.com/riscPrint/risc-v-workstation/pull/567). Merged: 2026-11-13T02:57:59Z.

Title: feat(plan): roll up project verification evidence and trends

Audit evidence label: unit tests only.

## Summary

Add the project-owned `VPlan` class, `rvw plan status` and `plan_status` MCP tool. Map requirements and features to explicit coverage groups, C1/C3 tests, named formal app properties and C4/block checks. Report holes, evidence hashes, unassigned requirements and compatible coverage/closure trends. Optional hashes pin evidence bytes.

Missing/inconclusive evidence and empty checks remain open. Bounded formal passes cannot meet unbounded obligations. Block-only evidence cannot close integration scope. Changed plans refuse trend comparison; changed coverage contexts report incompatible trends. Recorded closure is not C4 acceptance or a completeness proof. Add tool README, Layout row and shared contracts.

## Testing

Focused VPlan and command reference tests after rebase: 12 passed, zero skips. Fast set: 839 passed, 6794 deselected, zero skips.

Tests cover fixed denominators, unassigned requirements, stale pins, missing groups, no checks, C1/C3 inconclusive results, named formal properties and bounded/unbounded separation, RTL sequences, gate rejection, block/integration scope, trend context changes and CLI/MCP parity.

NOT RUN: real project closure campaigns, new native formal/test execution, full Python suite or CI. Fixture rollups do not establish actual feature closure.

## Issues

Refs: #30, #167

This is a verification-plan status tool over recorded evidence. Requirement completeness and correct evidence mappings remain project review duties. Proof exclusion rollups, live execution and unconditional proof claims remain outside the first version.

Roadmap notes: Add `rvw plan` to Components and verification planning. It provides project-owned requirement/feature mappings, per-feature evidence holes and trend through JSON/MCP. No native whole-core closure or gate acceptance follows.


## PR 568

[#568](https://github.com/riscPrint/risc-v-workstation/pull/568). Merged: 2026-11-13T02:58:16Z.

Title: feat(debug): check abstract fpr access and trigger size matching

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
- Debug Module model: abstract Access Register for FPRs (`0x1020`–`0x103f`, raw 64-bit bits) when the profile declares `fpr`.
- Trigger unit: declared access-size matching (`triggers.sizes`; mcontrol sizelo, mcontrol6 size). Undeclared sizes legalize to 0 (any size).
- New checks: `abs.fpr_roundtrip` (all 32 FPRs; sets mstatus.FS first when CSR access exists) and `trig.size_match` (a 16-bit store trigger ignores a 32-bit store to the same address and fires before the 16-bit store).
- Spike: FPR access passes. Spike does not keep size 2 in tdata1, so `examples/debug/spike.toml` keeps the default (size 0 only), and the check reports unsupported.

## Testing
- `rvw/.venv/bin/python -m pytest rvw/tests/test_debug_dm.py -q`: 36 passed. The full model profile now declares FPR and sizes.
- Native Spike suite (`rvw/tests/test_debug_dm_native.py -k profile`): 1 passed, with no check failing. A manual run with sizes declared for Spike failed `trig.size_match` on the readback, which is correct for a wrong declaration.
- Fast set: 839 passed.

## Issues
Refs: #153. Open: relaxedpriv.
Refs: #144. Open: H-extension virtualization, textra/tdata3, execute size matching, NMI itrigger.

Roadmap notes: Debug area. The compliance campaign now covers abstract FPR access and trigger access-size matching.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

## PR 569

[#569](https://github.com/riscPrint/risc-v-workstation/pull/569). Merged: 2026-11-13T03:00:19Z.

Title: test(checks): prove generated monitor fixtures with sby

Audit evidence label: ran on seeded RTL fixture.

## Summary
Add slow native SBY proofs for generated CSR, HPM, initialized-read, AXI-Lite, allocation-pool, CAM, counter, ROB, credit, free-list, rename, issue, forwarding, AXI-Stream, APB and AHB monitors. Each good fixture must prove; each seeded fault must produce FAIL. Add native Spike execution of the two generated VexRiscv project CSR programs.

## Testing
- SBY and native bus/binding tests: 52 passed, no skips. Includes 16 unbounded good-fixture proofs and 16 seeded failures.
- Native Spike programs: 2 passed, no skips.
- SpinalChecks Test/compile: passed under the sbt lock, 37 seconds.
- NOT RUN: real-core CSR binding, full protocol compliance, full Python suite, BOOM builds.

## Issues
Refs: #85, #66, #65

Roadmap notes: Generated monitor fixture proofs and CSR reference execution now have native evidence. Real VexRiscv CSR bindings, catalog gaps, aliases and privilege sequences remain open. Fixture proofs do not establish a design proof.

Additional native validation: `testOnly spinalchecks.CsrChecksSpec` passed 2 tests under the sbt lock in 14 seconds. The post-rebase fast set result is recorded below.

Post-rebase fast set: 839 passed, 6826 deselected, no skips.


## PR 570

[#570](https://github.com/riscPrint/risc-v-workstation/pull/570). Merged: 2026-11-13T02:58:30Z.

Title: feat(farm): add persistent service queue and owner API

Audit evidence label: unit tests only.

## Summary
Add a persistent local queue with priorities, attempt-based owner fairness, bounded retries and retained outcomes. Add dead-worker process identity checks and checked cancellation. Add a token-authenticated multi-user HTTP queue and live run view. Preserve the existing SSH farm and C3 dashboard.

## Testing
- Local service tests: 6 passed, 0 skipped.
- Fast set before rebase: 833 passed, 6725 deselected.
- Final fast set: 839 passed, 0 skipped, 6799 deselected.
- NOT RUN: real SSH hosts, RTL, cluster jobs, full Python suite, CI.

## Issues
Refs: #25

Remains: SSH worker crash reattachment, integrated C3 trend/cluster/bundle HTTP views, streaming artifacts and the wider verification management acceptance list. Local command completion is not a DUT pass. Queue fairness counts attempts rather than CPU time.

Roadmap notes: native farm now has an optional persistent local service queue and an owner-isolated HTTP API. Worker recovery retains infrastructure faults and retries only under policy.


## PR 571

[#571](https://github.com/riscPrint/risc-v-workstation/pull/571). Merged: 2026-11-13T02:58:32Z.

Title: test(vip): qualify python adapters against good and bad rtl

Audit evidence label: ran on seeded RTL fixture.

## Summary

Qualify all nine current Python agent modules against real good/bad RTL. Add bounded standalone Icarus fixtures for SPI, UART, I2C, GPIO, AXI and TileLink. Keep these builds independent of UVM. Include a separate AXI4-Lite adapter campaign. Record each fixture's scope in the README.

Roadmap notes: all current Python modules now have real RTL adapter evidence. AXI/TileLink scope is single-beat reads. Full protocol conformance, UVM runtime and reactive APB/AHB roles remain separate.

## Testing

- Targeted Python VIP tests: 169 passed.
- Icarus: SPI, UART, I2C, GPIO, AXI4, AXI4-Lite and TileLink each passed seed 17 on good RTL and detected the exact expected bad-DUT diagnostic. Each campaign took 0.9 to 1.4 seconds.
- Verilator: APB, AHB and AXI-Stream existing cocotb campaigns each passed 3 good seeds and detected 3 expected bad-DUT diagnostics.
- Required fast tests: 839 passed, 6799 deselected in 84.00s (0:01:23)
- Not run: UVM runtime builds, BOOM jobs, full Python suite or full protocol conformance campaigns.

## Issues

Refs: #205, #209. This adds bounded RTL evidence. It does not close full protocol qualification.


## PR 572

[#572](https://github.com/riscPrint/risc-v-workstation/pull/572). Merged: 2026-11-13T02:58:57Z.

Title: feat(csim): compare two study reports per trace

Audit evidence label: unit tests only.

## Summary

- `rvw csim compare BASE CANDIDATE [--tolerance R]` and MCP `csim_compare`: per-trace metric deltas between two `rvw.csim-study-report/1` documents, paired by trace sha256 (else path). Each shared metric gets base, candidate, change, relative change and `better|worse|same`. MPKI, PKI, storage and false dependences are lower-is-better; the others higher-is-better. Unpaired traces are counted.
- Contract (`rvw.csim-compare/1`), README and command reference updated.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_csim.py rvw/tests/test_mcp_tools.py -q` — 34 passed (TAGE vs bimodal: direction MPKI better, storage worse; schema check).
- `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q` — 839 passed after rebase.
- Not run: full slow suite, CI not awaited.

## Issues

Refs: #351 — agent-facing comparison of studies. No issue is closed.

Roadmap notes: Component simulators: `rvw csim compare` for per-trace study deltas.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 573

[#573](https://github.com/riscPrint/risc-v-workstation/pull/573). Merged: 2026-11-13T03:00:33Z.

Title: test(cosim): make adjudication unit checks hermetic

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Update the legacy `csr_sync` rejection test to match the current unknown-key error. Separate the optional native Spike/Sail test from unit adjudication tests. Require `RVW_TEST_NATIVE_ADJUDICATE=1` to run that integration. Add a stubbed call-path test that needs no Sail executable.

## Testing

- Targeted formats/adjudication: 27 passed, 1 skipped (native integration opt-in).
- Fast set after rebase: 839 passed, 6833 deselected.
- Native Sail integration NOT RUN.

## Issues

Refs: #11.

Roadmap notes: adjudication unit checks are independent of installed references. Native adjudication remains a separate opt-in check.


## PR 574

[#574](https://github.com/riscPrint/risc-v-workstation/pull/574). Merged: 2026-11-13T03:01:08Z.

Title: feat(farm): execute explicit shards locally or on kubernetes

Audit evidence label: unit tests only.

## Summary
Add a shared explicit shard plan for local queue and Kubernetes Job execution. Render image, CPU/memory resources and cache/result PVC mounts. Submit, inspect and cancel with kubectl. Validate C1/C3 files from a shared results mount and retain missing cells.

## Testing
- Targeted tests: 3 passed, 0 skipped, using local commands and fake kubectl.
- Final fast set: 839 passed, 0 skipped, 6836 deselected.
- NOT RUN: real cluster, kind, tool image builds, RTL, full Python suite, CI.

## Issues
Refs: #59

Owner instruction authorizes the cluster backend. Remaining: built tool images, automatic cache build/publication, regress gate executor integration, object storage and live cluster scale/parity checks. Existing SSH plans are unchanged. The rendered plain manifest is the deployment artifact.

Roadmap notes: explicit local/Kubernetes batch executor available through CLI/MCP. Cluster results remain unqualified until a real cluster run.


## PR 576

[#576](https://github.com/riscPrint/risc-v-workstation/pull/576). Merged: 2026-11-13T03:02:32Z.

Title: feat(arch): connect shared native cache and predictor models

Audit evidence label: unit tests only.

## Summary
Connect the own timing model to the component worker's in-process native library. Reuse shared direction prediction, multi-level BTB, RAS/indirect interfaces, cache hierarchy, prefetch and TLB services. Add instruction fetch service and cross-line/page data segmentation. Preserve native component statistics and source identity. No ComponentSims files change.

## Testing
84 targeted OoO tests and 839 fast tests passed. Four native adapter tests check warm cache reuse, hierarchy service, instruction fetch, cross-line accesses, BTB target training and direction prediction. The native component library built and ran in the targeted tests.

No RTL simulation, BOOM build, native gem5 run, full suite or RTL fidelity qualification ran. Prediction/history remains actual-path prediction at issue. BTB delay adds to branch resolution timing. FTQ-directed prefetch, instruction TLB service, speculative predictor repair and full demand-MSHR/bandwidth timing remain open.

## Issues
Refs: #72, #124, #357. This adds own-model integration and does not close native gem5 feature acceptance.

Roadmap notes: The own model now uses shared native cache/prefetch/TLB and predictor implementations. It no longer needs duplicate cache or branch algorithms. Hardware correlation and native whole-pipeline acceleration remain open.


## PR 577

[#577](https://github.com/riscPrint/risc-v-workstation/pull/577). Merged: 2026-11-13T03:02:01Z.

Title: feat(wave): name pc values by elf symbol and profile functions

Audit evidence label: unit tests only.

## Summary

- `rvw wave changes --elf PROG.elf [--pc RX]` (MCP `wave_changes` `elf`, `pc`): rows of PC-like signals get `symbol: name+0xoff` from the ELF symbol table (standard-library reader, no toolchain).
- `rvw wave profile WAVE PC --elf PROG.elf [--valid EXPR]` (MCP `wave_profile`): rising clock edges per function where `valid` holds (e.g. commit valid), with fractions and time-aligned `phases` (runs of one function). A PC maps only to a sized symbol that contains it, else `(no symbol)`; x/z PCs count as `unknown`.
- Test fixture `rvw/tests/data/wave_profile.elf` (5 KB, two sized functions) with its assembly source and build command.
- `test_mcp_tools.py` tool count updated (main had moved again).

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_wave_symbols.py rvw/tests/test_mcp_tools.py -q`: 23 passed, 0 skipped.
- Fast set: 839 passed.
- Not run: real core waves with a workload ELF.

## Issues

Refs: #24. Starts "join symbols, workload phases and hardware events in one time-aligned report". Remaining: DWARF line/stack views, multi-hart joins, flame views.

Roadmap notes: debug area — `rvw wave profile` and `changes --elf` join ELF symbols with wave PC values.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 578

[#578](https://github.com/riscPrint/risc-v-workstation/pull/578). Merged: 2026-11-13T03:02:38Z.

Title: feat(privilege): cover the full smepmp mml permission table

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Generate all 16 L/R/W/X entries of the Smepmp 1.0 MML permission table. Cross M/S/U read/write/fetch and MPRV effective S/U data access for 208 programs. Use separate shared bootstrap code/data rules. Require an explicit project RLB capability because RLB is optional. Check MML set and RLB clear before each probe. Keep these results separate from base PMP.

## Testing

- Targeted Python tests: 26 passed, 0 skipped.
- Native Spike: all 208 generated programs compiled and passed with nice and one-second per-program bounds.
- Fast set: 839 passed, 6789 deselected, 0 skipped.
- NOT RUN: RTL builds/simulations, actual PMP reset, full suite, long formal or CI.

## Issues

Refs: #138

Remaining: additional security-policy transition cases, independent reset/lock observations and DUT qualification. No base-PMP or reference-only result closes this issue.

Roadmap notes: Add complete MML permission-table generation and bounded native reference results. Retain reset, transition and DUT qualification limits.


## PR 579

[#579](https://github.com/riscPrint/risc-v-workstation/pull/579). Merged: 2026-11-13T03:03:02Z.

Title: feat(vip): add wishbone classic agents and memory checks

Audit evidence label: unit tests only.

## Summary

Add Wishbone Classic SV UVM and Python agents. Support 32-bit byte-addressed words, byte selects, ACK/ERR termination, seeded waits and a 16-word reference memory. Check stable pending requests and bad read data. Include a cocotb adapter, good/bad SV fixture and native smoke entry point.

Roadmap notes: Wishbone Classic cycle verification is available. RTY, pipelined/block cycles and native runtime qualification remain outside this profile.

## Testing

- Wishbone Python tests: 4 passed.
- Verilator lint with pinned Accellera UVM: passed.
- Required fast tests: 839 passed, 6875 deselected in 81.73s (0:01:21)
- Not run: UVM runtime builds, Wishbone cocotb RTL runs, BOOM jobs or full Python suite.

## Issues

Refs: #56.


## PR 580

[#580](https://github.com/riscPrint/risc-v-workstation/pull/580). Merged: 2026-11-13T03:30:38Z.

Title: feat(sim): connect vexriscv live state to reverse replay

Audit evidence label: ran on real core RTL.

## Summary

Connect the VexRiscv live process port to checkpoint and reverse-step. Native validation found and fixed two defects: a fresh process port must report a stopped boundary before restore, and the live state inventory must include synchronous memory-read buffers. Lower supported read-first memory ports to explicit registers. Refuse unsupported combined and mixed-width ports. Check restored state before execution. Add a private lock override and bound native make jobs.

The real reverse test captures retirement 8, reverses from instruction 15 to 10, and compares the complete state with an independent from-reset checkpoint at instruction 10. The comparison includes RTL registers, register-file memory, RAM, pending bus responses, cycle counters and C2 writer prefix. It passes with private core a62c145aa042a5de874344e0a7683bd7c8c8c870.

## Testing

- Native public reverse-step test: 1 passed in 164.24 seconds, using a private VexRiscv copy and vex-simsrv lock.
- Direct native replay versus independent reset state: exact full-state match at retirement 10.
- Targeted process-port and reverse tests: 4 passed.
- Fast set before final fetch/rebase: 839 passed, 6874 deselected.
- Focused native BridgeStateSpec with a synchronous memory read: 1 passed.
- NOT RUN: full Python suite, BOOM, C1 resume publication, interactive debugging and GitHub CI.

## Issues

Refs: #191. C1 resume publication and an interactive debugger remain outside this port. Do not close the full issue.

Roadmap notes: Live VexRiscv reverse replay now has native full-state equality evidence. Synchronous memory-read state is included. The process-port restore boundary check is fixed. Combined and mixed-width synchronous memory ports remain unsupported.


## PR 581

[#581](https://github.com/riscPrint/risc-v-workstation/pull/581). Merged: 2026-11-13T03:08:47Z.

Title: feat(farm): enforce cumulative queue budgets and report costs

Audit evidence label: unit tests only.

## Summary
Enforce cumulative run, agent and project budgets in the persistent local queue. Bound launches by remaining core-hours, wall time and job count. Reserve active attempts under the admission transaction. Report attempts, execution-state totals and optional explicit monetary rates.

## Testing
- Targeted service and cost tests: 9 passed, 0 skipped.
- Final fast set: 838 passed, 1 skipped, 6939 deselected. Main temporarily skips test_command_reference during the parallel push.
- NOT RUN: RTL, cluster, full Python suite, CI.

## Issues
Refs: #57

Remains: Kubernetes budget admission, measured aggregate CPU/RSS/disk caps, external plugin accounting and joining charges to C4 verdicts. CPU charge uses declared cores times elapsed time and includes cleanup overruns. Monetary cost is null without an explicit rate.

Roadmap notes: local service has cumulative shared budgets and persistent attempt costs. Existing SSH reservations remain separate.


## PR 582

[#582](https://github.com/riscPrint/risc-v-workstation/pull/582). Merged: 2026-11-13T03:18:56Z.

Title: feat(formal): plan portable resource-aware scenarios

Audit evidence label: unit tests only.

## Summary
Add a deterministic finite action/resource IR and backend-specific timing plans. Check supplied observations for outcomes, data transfers, ordering and capacity. Keep missing observations and zero expected comparisons inconclusive. Add CLI/MCP commands, an example and a pinned-source native PSS reuse assessment.

## Testing
- Targeted tests: 16 passed, including deterministic ordering, three backend plans, resource segments, data/outcome faults, invalid plans, stale results and CLI round trips.
- Latest fast set: 838 passed, 1 skipped, 7035 deselected. The inventory test is marked skipped on main for the parallel push. The explicit command-reference generator check passed. The initial fast run passed 839 with no skips.
- NOT RUN: native pssc compilation (not installed), actual model/RTL/FPGA operations, full Python suite, BOOM, long formal jobs, GitHub CI wait.

## Issues
Refs: #150

The planner does not execute operation bindings. The checker covers supplied observation records only. Native PSS integration, symbolic/randomized solving and real backend execution remain open. No design acceptance or hardware evidence is inferred.

Roadmap notes: add portable finite resource-aware plans and a supplied-record outcome checker. Keep native PSS and physical/backend qualification partial.


## PR 583

[#583](https://github.com/riscPrint/risc-v-workstation/pull/583). Merged: 2026-11-13T03:05:18Z.

Title: feat(csr): bind vexriscv scratch storage without a reset claim

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Bind the VexRiscv CSR plugin's actual scratch storage and accepted access callbacks to the generated catalog model. Keep the plugin optional. The binding reads the materialized project model and supports the declared full-width M-mode scratch register.

Fix a real model mismatch: VexRiscv does not initialize mscratch on reset. Add reset_known=false to CSR project rows and resetKnown=false to Scala CsrModel. For this restricted full-write mode, state/read checking starts after the first accepted write. Generated safe assembly establishes a value before comparison. No DUT reset value is claimed.

## Testing
- CSR Python, SBY and Spike tests: 65 passed, no skips. Good resetless fixture proves; its seeded fault fails.
- Spinal CsrChecksSpec: 4 passed, no skips, 13 seconds under the sbt lock.
- VexRiscv compile and elaboration passed under both vex and sbt locks. Compile: 52 seconds. Elaboration: 5 seconds. The emitted checks.json records csr.read:mscratch, csr.state:mscratch and csr.access:mscratch as inserted. No RTL CSR execution campaign was run. Core source revision a62c145aa042a5de874344e0a7683bd7c8c8c870.
- NOT RUN: RTL CSR campaign, catalog-wide bindings, aliases, privilege sequences, BOOM builds, full Python suite.

## Issues
Refs: #85

Roadmap notes: Add explicit unknown-reset semantics and a project-owned mscratch binding. The remaining catalog gaps, alias execution, privilege sequences and real RTL campaign remain open. This PR does not close #85.

Fast set after rebase: 839 passed, 6882 deselected, no skips.



## PR 584

[#584](https://github.com/riscPrint/risc-v-workstation/pull/584). Merged: 2026-11-13T03:13:58Z.

Title: feat(formal): add explicit conditional blackbox model contracts

Audit evidence label: unit tests only.

## Summary

Add explicit trusted blackbox behavioral models to sequential equivalence. Capture model and manifest hashes and retain unproved implementation obligations. Unresolved blackboxes, design assumptions and nondeterministic models remain refused.

Completed modeled proofs report `conditional` with a separate `contract_verdict`. They always exit 1. They cannot earn unconditional equivalence. Add a working `formal_equiv` MCP binding with matching result-status checks, correct multiple-source argument handling and the Boolean dsec flag.

## Testing

Native and MCP targeted tests: 5 passed. Equal/unequal model-based cases remain conditional. A model assumption cannot earn proof evidence. MCP tests preserve source arrays and reject exit-zero conditional results.

Required fast set after rebase: 838 passed, 1 skipped, 6929 deselected in 73.36s (0:01:13).

NOT RUN: BOOM builds, full Python suite, long formal jobs, physical blackbox correspondence or generated-clock equivalence.

## Issues

Refs: #18.

Roadmap notes: Add conditional blackbox behavioral contracts and working baseline equivalence MCP delivery. Physical/model correspondence remains unproved. Generated/gated clocks and BOOM reproduction remain open. PR #387 still holds the separate per-output latency/rename increment after its merge retry limit.


## PR 585

[#585](https://github.com/riscPrint/risc-v-workstation/pull/585). Merged: 2026-11-13T03:07:19Z.

Title: fix(cosim): disable supervisor csrs in m-only vex example

Audit evidence label: unit tests only.

## Summary

Disable the supervisor CSR access inherited from `CsrPluginConfig.all2` in the M-only VexRiscv example. `supervisorGen=false` alone leaves SATP and other supervisor CSR mappings enabled. Do not hide the resulting illegal-instruction mismatch with reference masks. Add a native regression for an illegal SATP access.

## Testing

- JDK 21 / SpinalHDL 1.15.0 `root/compile`: passed (36 s).
- Current checker against 41 saved RV32UI RTL traces: 0 matches, 41 mismatches at `csrwi satp, 0`, before this adapter fix. Historical traces do not validate the changed RTL.
- Fresh RTL ISA runs and native regression NOT RUN yet: shared vex lock occupied by another worker's formal campaign. No new match count claimed.
- Fast set: see final recorded result below.

## Issues

Refs: #11, #70.

Roadmap notes: fix the example's declared M-only configuration. Native ISA comparison remains open until the changed RTL runs.

Fast set: 837 passed, 1 skipped, 1 failed, 6923 deselected. The failure was generated command-reference drift already on the rebased main. Regenerated it; targeted command-reference tests: 2 passed, 1 skipped.


## PR 586

[#586](https://github.com/riscPrint/risc-v-workstation/pull/586). Merged: 2026-11-13T03:08:40Z.

Title: feat(vip): add single-port sram and rom agents

Audit evidence label: unit tests only.

## Summary

Add single-port SRAM/ROM Python agents with fixed read latency, byte write masks, initial contents and explicit reset policy. Add matching bounded SV UVM stimulus, monitor, coverage, scoreboard and good/bad RAM fixture. Include a cocotb pin adapter.

Roadmap notes: generic digital memory agents are available. Python supports ROM initial words and configurable latency. SV uses 16 words and one-cycle reads. Multiport collisions and ECC remain outside this profile.

## Testing

- SRAM/ROM Python tests: 5 passed.
- Verilator lint with pinned Accellera UVM: passed.
- Required fast tests: 838 passed, 1 skipped, 6928 deselected. A stale generated command reference on main was regenerated before this pass.
- Not run: UVM runtime builds, SRAM cocotb RTL runs, BOOM jobs or full Python suite.

## Issues

Refs: #56.


## PR 587

[#587](https://github.com/riscPrint/risc-v-workstation/pull/587). Merged: 2026-11-13T03:08:36Z.

Title: fix(cov): preserve assertion snapshot merge semantics

Audit evidence label: unit tests only.

## Summary

Preserve assertion counter merge semantics. Add compatible event counts. Take the maximum of peak-active counts. Require active snapshots to agree and keep their value. This prevents repeated report merges from inflating snapshot or peak counters.

## Testing

Focused interchange tests: 9 passed, zero skips. Combined targeted checks for this area's new modules: 193 passed, 1 skipped. Fast set: 838 passed, 1 skipped, 6893 deselected.

The skip is the upstream command-reference check disabled for the parallel push. This PR does not add or change that skip. The two remaining command-reference checks ran in the combined targeted set.

NOT RUN: new native DUT collection, vendor UCIS round trips, full Python suite or CI. XML structure does not change.

## Issues

Refs: #180

Roadmap notes: Counter merges now keep snapshot and peak semantics. UCIS native metric mappings and vendor profile interoperability remain open.


## PR 588

[#588](https://github.com/riscPrint/risc-v-workstation/pull/588). Merged: 2026-11-13T03:08:43Z.

Title: refactor(formal): isolate app and counterexample entry points

Audit evidence label: unit tests only.

## Summary
Move formal app, proof-core and counterexample command and MCP registrations to owned modules. Move their user guide to README-apps.md and link it from the main guide. Keep every registered tool and command.

## Testing
12 targeted tests passed. Fast set: 838 passed, 1 skipped, 6936 deselected. Native proof campaigns and heavy jobs NOT RUN. Command reference regenerated.

## Issues
Refs: #60, #62.

Roadmap notes: App entry points now have separate files to reduce conflicts between formal workers.


## PR 589

[#589](https://github.com/riscPrint/risc-v-workstation/pull/589). Merged: 2026-11-13T03:09:22Z.

Title: fix(formal): run generated vex checks with explicit fast engines

Audit evidence label: ran on real core RTL.

## Summary

Expand the generated VexRiscv RVFI binding to all 37 RV32I instruction checks, reg, forward/backward PC, causal, liveness, unique and retirement cover. Select ABC for instruction checks and retain explicit consistency cycles and engines. The generated wrapper has unconstrained bus inputs. It does not contain the hand-written wrapper's fairness assumptions. Liveness can fail in this environment. Keep those failures visible.

## Testing

- Plan regression: 1 passed.
- Fast set: 838 passed, 1 skipped, 6936 deselected. The skip is the existing batched command-reference check.
- Native generated VexRiscv campaign completed with 110 seconds per check: 42 bounded PASS, one liveness assertion FAIL, one forward-PC timeout. All 37 instruction checks passed. PR #611 records the full per-check table. An ABC forward-PC retry at cycles [10,20] also timed out; its retirement cover passed. The BTORMC retry at cycles [5,15] passed in 15.8 seconds; its retirement cover also passed. PR #677 records the retry table and selects that explicit bound. Selected outcomes across attempts are 43 bounded PASS and one liveness assertion FAIL. This combines different bounds; it is not a fresh uniform-depth campaign. The original C4 reject remains visible. No unbounded proof or adapter conformance is claimed.
- NOT RUN: BOOM, full Python suite, full-machine ISA proof.

## Issues

Refs: #63

Roadmap notes: Generated VexRiscv bindings now select the full existing instruction and consistency campaign. Native outcomes remain bounded observations. Fair environment integration and independent adapter conformance remain open.



## PR 590

[#590](https://github.com/riscPrint/risc-v-workstation/pull/590). Merged: 2026-11-13T03:09:41Z.

Title: feat(arch): time non-trapping csr fence and return operations

Audit evidence label: unit tests only.

## Summary
Time non-trapping CSR and fence instructions used by whole-program startup. Serialize older and younger execution. Model MRET/SRET through the existing committed-path return/recovery path. Refuse blocking/trapping system operations and unavailable cache/translation invalidation transitions. Regenerate the shared command reference after upstream CLI changes.

## Testing
28 targeted control/base/component tests passed. The fast set passed after command-reference regeneration. No RTL simulation, BOOM build, gem5 run or full suite ran. These tests do not verify CSR semantics or privilege behavior. FENCE.I with instruction caches, possible SATP writes with component translation, SFENCE.VMA and traps remain explicit errors.

## Issues
Refs: #72.

Roadmap notes: Whole-program timing can include declared non-trapping startup control operations. Invalidation/context transitions still require component API support and are refused instead of silently ignored.


## PR 591

[#591](https://github.com/riscPrint/risc-v-workstation/pull/591). Merged: 2026-11-13T03:09:25Z.

Title: fix(rvw): decouple width test from reference and drop duplicates

Audit evidence label: unit tests only.

## Summary
- `test_command_reference_does_not_depend_on_terminal_width` compared the checked-in `docs/COMMAND_REFERENCE.md`, so it failed after every merge while the main check is skipped. It now compares two renders (COLUMNS=40 and 200). The width-independence check stays real.
- Remove the duplicated `## UVM bench manifests and results` section at the end of `docs/PLATFORM_CONTRACTS.md` (identical copy from a keep-both resolution).
- Merge the two `rvw/src/rvw/privilege/` rows in the AGENTS.md Layout table.
- Regenerate `docs/COMMAND_REFERENCE.md` (sheriff batch).

## Testing
- `pytest rvw/tests/test_command_reference.py`: 2 passed, 1 skipped (the deferred check).
- Fast set before the change: 1 failed (this test), 837 passed, 1 skipped.

## Issues
None. Sheriff maintenance of `main`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 592

[#592](https://github.com/riscPrint/risc-v-workstation/pull/592). Merged: 2026-11-13T03:10:39Z.

Title: feat(uvm): bind the live cpu environment to vexriscv

Audit evidence label: ran on real core RTL.

## Summary

Add a project-owned live VexRiscv pyuvm environment using the shared CPU memory and Spike scoreboard. Bind both simple buses and scalar RVFI from project data. Require a checked full-word tohost pass store. Add a next-PC corruption mode and an opt-in native regression.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_uvm_vex_live.py -q`: 1 passed, 1 native test skipped without opt-in.
- Fast set: 837 passed, 1 skipped, 1 failed, 6925 deselected. The unrelated failure is `test_command_reference_does_not_depend_on_terminal_width`. The brief defers this file. No command-reference changes are committed.
- Live add ISA run is queued under the shared vex lock. Another worker holds that lock for a formal campaign. No native VexRiscv result is claimed yet.
- NOT RUN: full suite, BOOM, CI, complete ISA campaign, IRQ/debug architecture, C4 acceptance.

## Issues

Refs: #296

The first item remains incomplete until the native ISA runs finish. This commit supplies the missing live project binding. It does not close #296.

Roadmap notes: add live VexRiscv pyuvm bus/RVFI binding and a corruption probe. Native qualification is pending the shared vex lock. SoC, architectural controls, C4 and scaffold work remain open.


## PR 593

[#593](https://github.com/riscPrint/risc-v-workstation/pull/593). Merged: 2026-11-13T03:11:27Z.

Title: feat(checks): bind multichannel bus safety by recorded type

Audit evidence label: ran on seeded RTL fixture.

## Summary
Generate five-channel AXI4/AXI-Lite and qualified TileLink channel monitors from recorded Spinal bus types. Preserve every recorded payload sideband. Add valid/payload stall safety, AXI burst field rules, AXI-Lite response encoding and TileLink opcode checks. Resolve local controls for hierarchical instances and retain per-instance coverage and limitations.

These checks do not establish complete protocol compliance. Beat counts, outstanding transaction/ID order, exclusives and coherence state still need scoreboards. Ambiguous or unsupported bus classes stay reported with reasons.

## Testing
- Native SBY: 6 passed, no skips. Three good fixtures prove and three seeded faults fail.
- Typed database binding tests: 8 passed, no skips, including nested instance controls and all five AXI channels.
- NOT RUN: real SpinalDB bus capture campaign, complete AXI/TileLink transaction proofs, BOOM builds, full Python suite.

## Issues
Refs: #66

Roadmap notes: Add recorded-type multichannel safety and nested instance control resolution. Keep full protocol compliance, beat/ID/exclusive tracking and coherent transaction scoreboards open.

Fast set after command reference regeneration: 838 passed, 1 skipped, 6955 deselected. An earlier run found a stale inherited command reference; it was regenerated in this PR.


Additional native qualification: under the sbt lock, testOnly spinalchecks.AxiWriteSpec spinalchecks.AxiReadSpec passed all 7 tests in 55 seconds. This tests the existing Scala monitors, including W-before-AW, ID reordering, burst lengths and exclusive-response faults. It does not upgrade Python channel-only bindings to transaction scoreboards.


## PR 594

[#594](https://github.com/riscPrint/risc-v-workstation/pull/594). Merged: 2026-11-13T03:11:42Z.

Title: feat(farm): cluster failures and bundle representatives

Audit evidence label: unit tests only.

## Summary
Cluster C3 failures by assertion, recorded mismatch PC/instruction or trap cause. Preserve members and source revisions. Link known failures without waiving them. Build one C5 bundle per cluster through the existing builder with reruns disabled. Reuse the identity-aware regression comparison for baseline diffs.

## Testing
- Targeted tests: 3 passed, 0 skipped.
- Final fast set: 838 passed, 1 skipped, 6951 deselected. Main temporarily skips test_command_reference during the parallel push.
- NOT RUN: RTL, full Python suite, native C5 reruns, CI.

## Issues
Refs: #25

Remains: root-cause review and integration into the live HTTP dashboard. C5 calls require an existing C1 run path. Missing paths and errors stay explicit. Clusters are review aids, not waivers or proofs of shared root cause.

Roadmap notes: farm triage supports recorded failure clusters, representative bundles and C3/C4 baseline comparisons.


## PR 595

[#595](https://github.com/riscPrint/risc-v-workstation/pull/595). Merged: 2026-11-13T03:11:59Z.

Title: feat(vip): add interrupt line stimulus and timing checks

Audit evidence label: unit tests only.

## Summary

Add sampled interrupt-line Python and SV UVM agents. Drive level vectors with declared durations. Check minimum pulse width, unknown values and scheduled level/timing expectations. Include coverage, a cocotb adapter and good/bad line-loopback fixture.

Roadmap notes: line-level stimulus and observation are available. Controller pending bits, priority and CPU trap delivery remain project-owned. SV expectations cover scheduled windows only.

## Testing

- Interrupt Python tests: 3 passed.
- Verilator lint with pinned UVM: passed.
- Required fast tests: 838 passed, 1 skipped, 6954 deselected.
- Not run: UVM runtime builds, interrupt cocotb RTL runs, BOOM jobs or full Python suite.

## Issues

Refs: #56.


## PR 596

[#596](https://github.com/riscPrint/risc-v-workstation/pull/596). Merged: 2026-11-13T03:12:20Z.

Title: feat(cosim): wire vex mscratch into retirement snapshots

Audit evidence label: ran on real core RTL.

## Summary

Wire actual VexRiscv `mscratch` storage into the single RVFI retirement slot. Declare the exact snapshot address in a CSR-only C2/2 header. Do not declare FP state or snapshots for other CSRs. Add a native regression that checks two distinct post-write values. The example has no debug module.

## Testing

- VexRiscv `root/compile`: passed, 18 seconds.
- CSR capability and unspecified-reset comparator tests: 30 passed.
- Native snapshot timing test NOT RUN: the shared vex lock remains held by another worker's formal campaign.
- Fresh native ISA comparison and debug entry NOT RUN. No RTL CSR match is claimed.

## Issues

Refs: #11, #70.

Roadmap notes: the single VexRiscv retirement slot now carries `mscratch`. Native timing validation remains required; other CSR addresses and a debug-capable example remain open.

Fast set after rebase: 838 passed, 1 skipped, 6947 deselected.


## PR 597

[#597](https://github.com/riscPrint/risc-v-workstation/pull/597). Merged: 2026-11-13T03:13:21Z.

Title: feat(formal): reduce fair response liveness to safety

Audit evidence label: ran on seeded RTL fixture.

## Summary
Reduce single-clock response liveness with state justice to a full-state lasso safety assertion. Keep outstanding requests until a response. Map memory before collecting every state bit. Reject unsupported state and clocks. Add app-live CLI, MCP and guide.

## Testing
Native Yosys/SBY/ABC PDR: 3 tests passed, including fair response proof and a never-acknowledge mutant failure. Entry-point test passed. Fast set: 838 passed, 1 skipped, 6951 deselected. Heavy core jobs NOT RUN. K-induction returned unknown for the valid example; PDR is the default.

## Issues
Refs: #62. Fairness feasibility and existential CTL deadlock checks remain open.

Roadmap notes: Native fair response liveness-to-safety is available for finite synchronous RTL. Bounded runs remain bounded lasso searches.


## PR 598

[#598](https://github.com/riscPrint/risc-v-workstation/pull/598). Merged: 2026-11-13T03:14:10Z.

Title: feat(farm): select source-impact suites within a time budget

Audit evidence label: unit tests only.

## Summary
Propose time-budgeted suites from changed source files, transitive design-database signal impact and observed per-test coverage/cost. Retain mandatory and unknown tests. Preserve fallback_all from the existing coverage selector. Report uncovered impact and deadline overruns.

## Testing
- Targeted tests: 3 passed, 0 skipped.
- Fast set: 838 passed, 1 skipped. The command-reference check is temporarily skipped by main during the parallel push.
- NOT RUN: held-out regressions, RTL, full Python suite, CI.

## Issues
Refs: #25

Selection is advisory. It requires a project-supplied test observation catalogue bound to the database hash. It does not earn a gate acceptance or validate selection quality without held-out runs.

Roadmap notes: farm select supplies a 600-second default impact/cost scheduling plan. Unknown effects retain tests rather than silently dropping them.


## PR 599

[#599](https://github.com/riscPrint/risc-v-workstation/pull/599). Merged: 2026-11-13T03:14:47Z.

Title: feat(arch): model floating-point dependencies and register pressure

Audit evidence label: unit tests only.

## Summary
Track integer and FP register dependencies separately. Model mutable f0, FP loads/stores, operation-family timing, three-source FMA and separate FP register pressure. Read encoded FP destinations instead of treating C2 integer rd data as FP writeback. Shared project descriptions project numPhysFloatRegs.

## Testing
92 targeted OoO tests passed. Fast set: 838 passed, one skipped. Tests cover FP bank mapping, loads, FMA dependencies, mutable f0, pressure stalls and C2 timing. No RTL simulation, BOOM build, gem5 run or full suite ran.

This is timing only. The engine does not execute or verify FP arithmetic, rounding, flags or operand-dependent latency. Vector and trapping execution remain unsupported. FP streams use Python.

## Issues
Refs: #72.

Roadmap notes: FP dependency/resource timing now permits explicit FP workload classes. Native FP acceleration, full register reclamation and RTL accuracy remain open.


## PR 600

[#600](https://github.com/riscPrint/risc-v-workstation/pull/600). Merged: 2026-11-13T03:14:30Z.

Title: feat(uvm): compose map-driven soc verification services

Audit evidence label: unit tests only.

## Summary

Compose the merged APB4, AXI4-Lite and UART monitors with the CPU Spike scoreboard and map-derived Python RAL. Route frontdoors by SoC region. Check bus reads against an independent reset-based register model. Add a pyuvm component and a two-peripheral map example. Require CPU comparisons, traffic on each bus and the expected UART stream at completion.

## Testing

- Targeted composition, live-binding and CPU-model tests: 12 passed, 1 optional native test skipped.
- Fast set: 838 passed, 1 skipped, 6955 deselected in 92.85s (0:01:32).
- NOT RUN: connected RTL SoC, full suite, BOOM, CI, C4 gate.
- The current profile supports plain known-reset 32-bit RW registers. It refuses bus errors and bursts. Project callbacks still supply active drivers and wire sampling. Unit tests are not evidence of SoC execution.

## Issues

Refs: #296

The SoC item is partial. Active connected RTL qualification remains open. The VexRiscv native ISA run is still queued behind the shared vex lock.

Roadmap notes: reusable Python CPU/APB/AXI-Lite/UART composition and SoC-map RAL now exist. A project must connect actual wires before it can claim SoC execution. No C4 acceptance is claimed.


## PR 601

[#601](https://github.com/riscPrint/risc-v-workstation/pull/601). Merged: 2026-11-13T03:15:33Z.

Title: feat(query): elaborate full SystemVerilog with slang in build-hdl

Audit evidence label: unit tests only.

## Summary

- `rvw query build-hdl --frontend slang` elaborates full SystemVerilog through the yosys-slang plugin (`read_slang --keep-hierarchy`). Options: `-I DIR`, `-D NAME[=VALUE]`, `-G NAME=VALUE` (top parameters), `--std`, `--slang PATH`. Plugin order: `--slang`, `$RVW_SLANG` (`scripts/install.sh --with-formal` builds a pinned one), then the plugin that OSS CAD Suite ships beside Yosys.
- C8 capture: the whole directory of each source and each include directory is captured before elaboration. slang reads only the copies, so local and `-I` includes resolve inside the capture. `input_files` lists the captured files. `meta.hdl_options` and `meta.slang_plugin_sha256` record the configuration and plugin.
- A second slang pass reads the JSON AST (`--dump-ast`): per-instance parameter values (artifact `hdl/parameters.json`, shown by `rvw query component`) and declared SV types (`signals.type`, for example `p::state_e`, `logic[31:0]`).
- Writer changes for all HDL frontends: memories (`mem` signals, `memories`/`mem_ports` rows, `mem_write` assignments), `$buf` bit-to-bit, `$aldff` async resets, one hidden hub per multi-bit cell (Ibex edges 1.9M -> 179k, build 26 s -> 7 s), bit nodes named after a net (`q_o[3]`), generate paths `g[1].u` that also resolve as `g.1.u`, component names from the instance cell.
- New MCP tool `query_build_hdl`. Lint now treats every `yosys-*` frontend as an HDL import.
- Docs: `SpinalDB/README.md` (slang section and memory semantics), C6 contract subsection, query README, design note.

## Testing

- `RVW_HDL_REF=[local path omitted] rvw/.venv/bin/python -m pytest rvw/tests/test_query_slang.py rvw/tests/test_query_hdl.py rvw/tests/test_hdl_semantics.py rvw/tests/test_lint_hdl.py rvw/tests/test_mcp.py -q`: 63 passed, 0 skipped. Includes Ibex `ibex_core` (all core files, lowRISC Ibex fork at 2c72091) and an independent reachability oracle over the slang netlist.
- Fast set: 837 passed, 2 failed: `test_command_reference.py::test_command_reference_matches_declarations` and `::test_command_reference_does_not_depend_on_terminal_width` (deferred; `docs/COMMAND_REFERENCE.md` is not committed per the brief).
- Not run: full Python suite, CI, a second full SV core (only Ibex plus the synthetic design).

## Issues

Refs: #370. Remaining: a second full SV core, statement-level source precision, exact vs conservative edge marking, IP model contracts and unresolved-model refusal for blackboxes, project (`rvw.toml`) build integration (planned with #55/#26 `rvw init --hdl`).

Roadmap notes: Design database front ends: full SystemVerilog now elaborates through yosys-slang (`build-hdl --frontend slang`) with captured includes, per-instance parameters and SV types; Ibex `ibex_core` builds in about 7 s and every `rvw query` command works on it. Memories are imported for all HDL frontends.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 602

[#602](https://github.com/riscPrint/risc-v-workstation/pull/602). Merged: 2026-11-13T03:15:55Z.

Title: feat(checks): generate project rules and missing-binding summaries

Audit evidence label: unit tests only.

## Summary
Add project-instantiated FIFO ordering, valid/ready stability, one-hot/mutex, grant/fairness, age-matrix consistency and selected-store forwarding templates. Keep signal names in project data. Retain existing ROB, credit and allocation-pool conservation templates.

Add `rvw checks generate --all` and `checks_generate` MCP. The project manifest selects stream, bus, CSR, queue and power inputs. Emit available sources/bindings and a per-kind/per-instance summary. Missing bindings remain unbound; source emission alone does not count as a bound check. Existing output directories are refused.

## Testing
- Microarchitecture SBY cases: 12 passed, no skips. Six good fixtures prove and six seeded faults fail.
- Project generation, missing/invalid project data, binding summaries and command-reference tests: 6 passed, 1 skipped.
- NOT RUN: design-level proofs, automatic stream/power binding, real device/HPM campaign, full Python suite, BOOM builds.

## Issues
Refs: #65, #66, #85

Roadmap notes: Add project microarchitecture rule bindings and one-command generation with explicit missing-binding reports. Age checks establish consistency, not allocation-time order. Forwarding uses explicit oldest-to-youngest slot order and full data units; byte merging requires per-byte instances. Stream/power automatic binding and full protocol transaction scoreboards remain open.

Combined native and project checks: 78 passed, no skips, in 103.34 seconds. This includes SBY generated-monitor proofs/mutants, bounded property intents, typed buses, microarchitecture rules, project summaries and Spike.

Post-rebase fast set: 838 passed, 1 skipped, 6985 deselected.


## PR 603

[#603](https://github.com/riscPrint/risc-v-workstation/pull/603). Merged: 2026-11-13T03:16:04Z.

Title: feat(vip): add digital clock and reset timing agents

Audit evidence label: unit tests only.

## Summary

Add digital clock/reset Python and SV UVM agents. Generate fixed half-period clocks. Check edge spacing, reset hold cycles and falling-edge release. Include a cocotb source, coverage, scoreboard and bad reset-release fixture.

Roadmap notes: clock/reset digital waveform checks are available. Analog jitter, PLL lock, clock gating and clock/reset crossing qualification remain outside the profile.

## Testing

- Clock/reset Python tests: 4 passed.
- Verilator lint with pinned Accellera UVM: passed.
- Required fast tests: 838 passed, 1 skipped, 6977 deselected in 109.00s (0:01:49)
- Not run: UVM runtime builds, clock/reset cocotb RTL runs, BOOM jobs or full Python suite.

## Issues

Refs: #56.


## PR 604

[#604](https://github.com/riscPrint/risc-v-workstation/pull/604). Merged: 2026-11-13T03:19:14Z.

Title: feat(evidence): index and query original cross-tool reports

Audit evidence label: unit tests only.

## Summary
Add rvw evidence index/query and MCP tools over C1/C3/C4/C5, formal, coverage and lint reports. Return exact captured observations, configuration and assumptions. Recheck original files and explicit dependency hashes. Missing or changed inputs weaken integrity without changing source verdicts.

## Testing
- Targeted tests: 3 passed, 0 skipped.
- Fast set: 838 passed, 1 skipped. Main temporarily skips the generated command-reference check during the parallel push.
- NOT RUN: native tools, large-campaign performance, full Python suite, CI.

## Issues
Refs: #95

Remains: automatic tool-specific dependency extraction and formal/cov/lint semantic validation. These records are explicitly JSON-only validated. The index does not replace generation admission, infer acceptance or manufacture assumptions.

Roadmap notes: a shared evidence index now supports original-report queries and explicit dependency joins across tools.


## PR 605

[#605](https://github.com/riscPrint/risc-v-workstation/pull/605). Merged: 2026-11-13T03:18:11Z.

Title: feat(uvm): generate csr qualification from the catalog

Audit evidence label: unit tests only.

## Summary

Add a catalog-derived CPU CSR qualification service and a pyuvm sequence wrapper. Reuse `rvw.formal.csr` loading and its independent state oracle. Generate read checks, safe zero/all-ones/walking-one/random writes and restore writes. Initialize project-safe unknown-reset registers before reads. Require absent registers to trap. Never infer reset values or destructive-write safety from a CSR address.

## Testing

- Targeted tests: 6 passed, 0 skipped. Cover data/trap corruption, catalog materialization, reset restoration, unknown-reset initialization, absent CSR traps and safe-write opt-in.
- Fast set: 838 passed, 1 skipped, 6995 deselected in 104.86s (0:01:44).
- NOT RUN: native CPU CSR callback, architectural interrupt/debug qualification, full suite, BOOM, CI or C4 gate. The native VexRiscv run remains queued behind another worker's vex lock.

## Issues

Refs: #296

CSR sequence infrastructure is implemented. Project instruction-execution callbacks and native CPU qualification remain open. This does not establish interrupt or debug architecture. The example VexTop has no debug port.

Roadmap notes: catalog-derived CSR qualification now reuses the checks worker's oracle through a CPU execution callback and pyuvm sequence. Architectural interrupt/debug and live CSR qualification remain open.


## PR 606

[#606](https://github.com/riscPrint/risc-v-workstation/pull/606). Merged: 2026-11-13T03:19:48Z.

Title: test(memory): exercise concurrent rv64 atomics and cas on rtl

Audit evidence label: ran on seeded RTL fixture.

## Summary
Extend the existing subset RTL fixture to RV64 doubleword atomics and contended doubleword CAS. Connect independent byte/reservation checks, retain native adjacent-word guards, and capture branch-free AMO/LRSC C2/2 traces for the axiomatic checker. Preserve the RV32 default. Require explicit physical locations and retain full-width annotation values as canonical decimal strings.

## Testing
Nine targeted Scala tests passed, including five RV64 tests with 52 native fixture runs. Eleven selected existing RV32 tests passed. A broader 17-test regression had 16 passes and one missing-input failure: the pinned official litmus test needs RVW_FIXTURE_PLAN. That test was not changed or disabled. Nineteen targeted Python tests passed.

Forty native C2/2 traces were allowed under RVWMO and Ztso: 80 finite execution checks. Native seeded defects reject torn AMOs/CAS, wrong returns, lost reservation invalidation, adjacent corruption, missing CAS writes and writes from failed CAS.

The final fast set ran after rebase: 838 passed, 1 skipped. Main temporarily skips command-reference consistency for the parallel documentation batch. A direct generated-reference comparison passed.

NOT RUN: the pinned litmus campaign without its plan, production-core multi-hart RTL, external weak aq/rl ordering, word/quadword CAS contention, native herd differential validation, BOOM builds, full Python suite. The fixture is a serialized instruction subset. CAS is outside the scalar axiomatic capture profile. No production-core qualification is claimed.

## Issues
Refs: #90, #91, #97, #170. Production adapters, weak-memory RTL and broader CAS width campaigns remain open.

Roadmap notes: RV64 concurrent AMO/LRSC and doubleword CAS now have tiny native fixture evidence and fault rejection. Captured physical AMO/LRSC executions feed the independent graph checker. Production and weak-memory evidence remain separate.


## PR 607

[#607](https://github.com/riscPrint/risc-v-workstation/pull/607). Merged: 2026-11-13T03:18:44Z.

Title: feat(formal): discover typed streams and expose internal fsms

Audit evidence label: unit tests only.

## Summary
Discover Stream and Flow roles by Spinal type and generate output Stream backpressure checks. Expose retained internal enum signals by exact RTL name and verify widths before FSM checks. Report counter and FIFO/arbiter/CAM candidates with concrete database evidence and unsupported semantic bindings. Add generated/proven/bounded/failed/unsupported counts.

## Testing
Targeted apps/autocheck/database set: 37 passed. Updated database tests: 7 passed. Native internal exposure test: 1 passed. Fast set: 838 passed, 1 skipped, 6975 deselected. Real library database built: 2 components, 54 signals, 1 memory. Initial asynchronous-reset run was refused. Synchronous library rerun is pending the sbt lock. Heavy core builds and simulations NOT RUN.

## Issues
Refs: #62. Full automatic FIFO, arbiter and CAM semantic endpoint contracts remain unsupported. Counter wrap requirements are not inferred.

Roadmap notes: Typed Stream checks and internal FSM exposure work. Role reports preserve unsupported cases. Native end-to-end counts will follow the synchronous library run.


## PR 608

[#608](https://github.com/riscPrint/risc-v-workstation/pull/608). Merged: 2026-11-13T03:26:17Z.

Title: feat(cosim): compare ordered vector memory and run upstream slice

Audit evidence label: unit tests only.

## Summary

Capture ordered successful vector loads and stores from Spike in bare RAM. Extend C2/2 with declared `vector_memory` and exact per-retirement `vector_accesses`. Compare the whole access list and full vector state. Refuse missing capture, translated/device access and partial fault effects. Preserve scalar checks.

Add a reproducible pinned upstream `vadd.vv` slice build and strict fresh-Spike replay script. No vector DUT is available. This is a reference transport/state check, not independent vector arithmetic validation or a DUT suite pass.

## Testing

- Native upstream generator, RV64GCV GCC build, Spike execution and fresh-Spike strict C2 replay: complete match, 1,333 instructions, 2,536 vector accesses, VLEN 128 / ELEN 64, zero synchronizations.
- Vector memory and V/H state tests: 38 passed.
- Vector memory, scalar fault and FP rounding checks after final shim build: 25 passed.
- Fast set before rebase: 838 passed, 1 skipped, 6975 deselected.
- No vector RTL or vector DUT run. No full riscv-vector-tests campaign. No translated/device/partial-fault vector comparison.

## Issues

Refs: #75.

Roadmap notes: a pinned generated upstream arithmetic slice now runs natively through C2, including vector memory. Full suite coverage and vector DUT validation remain open.

Fast set after rebase: 838 passed, 1 skipped, 7024 deselected. The platform contract rebase conflict retained both workers' separate subsections.


## PR 609

[#609](https://github.com/riscPrint/risc-v-workstation/pull/609). Merged: 2026-11-13T03:19:55Z.

Title: feat(vip): add generic jtag scans and test access topology

Audit evidence label: unit tests only.

## Summary

Add generic JTAG IR/DR scan agents, reuse the TAP transition table and export declared test-access topology. Check adjacent TAP connections and mode reachability against supplied independent graphs. Missing graph evidence remains inconclusive. Keep RISC-V debug conformance separate.

Roadmap notes: generic TAP scanning and topology declarations are available. Design-database topology extraction, boundary-cell qualification and native runtime remain open.

## Testing

- JTAG Python tests: 2 passed.
- Verilator lint with pinned Accellera UVM: passed.
- Required fast tests: 838 passed, 1 skipped, 7025 deselected in 77.75s (0:01:17)
- Not run: UVM runtime builds, JTAG cocotb RTL runs, BOOM jobs or full Python suite.

## Issues

Refs: #211. Extraction and native qualification remain open.


## PR 610

[#610](https://github.com/riscPrint/risc-v-workstation/pull/610). Merged: 2026-11-13T03:20:11Z.

Title: docs(contracts): split platform contracts into per-topic files

Audit evidence label: unit tests only.

## Summary
`docs/PLATFORM_CONTRACTS.md` was the top conflict source (140 of 193 commits today touched it). Keep-both rebase resolutions had also scrambled it: about 80 `###` subsections from many areas were appended under `## C9 compiler scheduling extension`, nine more sat in the file preamble, and one `##` section was duplicated.

- Each topic now has its own file under `docs/contracts/`: `project.md`, `c1-run.md` … `c9-arch-models.md`, `resources.md`, and one file per area (`mmu.md`, `formal.md`, `formal-cex.md`, `formal-deep.md`, `arch.md`, `uvm.md`, `csr.md`, …).
- Stray subsections go to their area file as `##` sections. The text is unchanged; a line-multiset check confirms that only the duplicated UVM section and the old title/intro sentence were removed.
- `docs/PLATFORM_CONTRACTS.md` is now the index: intro, principles, links, layout. It says where new contract text goes.
- Rewrite the 13 `PLATFORM_CONTRACTS.md#anchor` links to the new files. Update `AGENTS.md`, `CONTRIBUTING.md` and `test_query_round19.py` (reads `docs/contracts/c6-design-database.md`).
- Regenerate `docs/COMMAND_REFERENCE.md`.

Workers: put new contract text in your area's `docs/contracts/<area>.md`. If an old branch rebases onto this, its contract text can land in the index. The sheriff moves it each round.

## Testing
- Fast set: 838 passed, 1 skipped (deferred command reference check).
- No other test reads the contracts file (`git grep PLATFORM_CONTRACTS rvw/tests scripts`).

## Issues
None. Sheriff maintenance of `main`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 611

[#611](https://github.com/riscPrint/risc-v-workstation/pull/611). Merged: 2026-11-13T03:28:15Z.

Title: feat(formal): generate sail bitmanip and architectural monitors

Audit evidence label: ran on seeded RTL fixture.

## Summary

Generate 19 RV32 binary Zba/Zbb/Zbs/Zbc instruction result models from pinned Sail rules. Reuse the native Sail compiler and RVFI shell. Record source, helper, compiler, library and output hashes. Keep only reachable generated modules and lower fixed-width expressions for Yosys. No hand-written instruction model files are checked in.

Add an architectural-state proof kit for cores without RVFI. A project maps retirement-aligned PC, complete register pre/post snapshots, read/write indices, memory effects, trap/mode and optional CSR snapshots. Yosys exposes those observations without cuts. Generate a monitor, frame assertions, wrapper and runnable riscv-formal project. Both generators have CLI, MCP and contract documentation.

Record all 44 native generated VexRiscv check outcomes: 42 bounded PASS, one liveness assertion FAIL, one forward-PC timeout. All 37 instruction checks passed. The forward-PC retry is queued. Preserve C4 reject and the generated wrapper's unconstrained-environment limit.

## Testing

- Fast set: 848 passed, 1 existing skip, 7137 deselected.
- Native architectural-state tests: 6 passed, no skips. Correct ADD is bounded PASS, a wrong result is rejected, and an extra register write triggers a frame assertion. These are fixtures, not core conformance.
- Native Sail generation completed for all 19 models. Independent result/decode/PC/empty-memory and wrong-result tests: 39 passed, no skips. Each proof had a 60-second limit. Zbc basis checks also passed a separate 6-test run. Their multiplier is zero or one-hot; the other operand is arbitrary.
- Regenerated Zicond models are byte-identical to the models that passed the earlier 13 native tests.
- Earlier arbitrary-both-operand Zbc comparisons timed out with Yices and ABC. Those attempts remain inconclusive. Generated models contain no basis restriction.
- NOT RUN: BOOM, full Python suite, complete ISA/profile proof, full-machine Sail generation. Floating-point, CSR and privileged transitions remain open.

## Issues

Refs: #63, #64

Roadmap notes: Add generated binary bit-manipulation slices and a no-RVFI architectural-state monitor kit. Keep full-machine effects, actual-core map conformance, CSR semantics and unrestricted Zbc oracle proof as explicit gaps.


## PR 612

[#612](https://github.com/riscPrint/risc-v-workstation/pull/612). Merged: 2026-11-13T03:21:09Z.

Title: feat(probes): add simulation probe api and riscvsim event collector

Audit evidence label: unit tests only.

## Summary

- New top-level `SpinalProbes/` library: a typed, simulation-only probe API a core designer calls at elaboration: `Probe.branch`, `cacheAccess`, `tlb`, `pageWalk`, `stage`, `retire`, `flush`, `stall`, `csrWrite`, `interruptTaken`, `traceIngress`, `counter` (optional `hpm` selector), `faultSite`, `custom`. Off by default: each call returns at once and adds no hardware unless the elaboration runs under `Probe.enabled(true)`. Enabled calls copy their signals into named public wires `rvwprobe__KIND__NAME__FIELD` in the caller's top scope (also from inside a `when`).
- Why a new library and not inside SpinalKonata: SpinalKonata writes Kanata only and carries a BOOM subproject; probes feed about a dozen consumers and Kanata is one converter among them. The library depends on spinalhdl-core/-sim only.
- RiscvSim: `ProbeCollector` samples enabled probes each cycle into one compact `rvw.probe-events/1` stream (`[cycle, id, values...]`, counters summed into the end record). C1 gets `--probes` (own `ModelKey.probes`, `_probes` model name, replay/identity/build/run-many forwarding, artifact `probe_events`). Adapters opt in with `supportsProbes`; the command line refuses `--probes` otherwise.
- `SpinalProbes/README.md` holds the inventory of every event format the consumer tools expect and which probe feeds each. Contract: new subsection "Probe event stream" in `docs/PLATFORM_CONTRACTS.md`.

## Testing

- `SpinalProbes`: `sbt test` (under the sbt lock): 3 passed (probes off: no `rvwprobe` text in Verilog; on: named wires and sites; name checks).
- `RiscvSim`: `sbt 'testOnly riscvsim.ProbeCollectorSpec'` with Verilator: 2 passed (event rows, counter totals, end record; disabled elaboration has no probes).
- Fast Python set: 847 passed, 2 failed (`test_command_reference.py`, deferred per the brief; this PR adds no CLI command).
- Not run: the full RiscvSim suite, BOOM, any VexRiscv run (next PRs).

## Issues

Refs: #49 (stall-cause and pipeline events now have a producer API; core wiring follows).

Roadmap notes: new component `SpinalProbes/` (generic, simulation-only probe API) with RiscvSim `ProbeCollector` and C1 `--probes`. Status: library and collector done; converters (`rvw probes`), VexRiscv wiring and the bring-your-own-core section follow.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 613

[#613](https://github.com/riscPrint/risc-v-workstation/pull/613). Merged: 2026-11-13T03:24:22Z.

Title: feat(arch): expose native component counts for rtl comparison

Audit evidence label: unit tests only.

## Summary
Expose native cache demand/writeback/prefetch counts and TLB/page-walk counts in the own model's flat event map. Preserve the nested component report. This lets the existing saved RTL event mapper select native component counts without another file format or ledger.

## Testing
93 targeted OoO tests passed. Fast set: 838 passed, one skipped. The skipped command-reference declaration test was disabled upstream for the parallel push; this PR does not alter or waive it. Native cache tests check the flat demand counts against the component report. No RTL simulation, BOOM build, gem5 run or full suite ran.

## Issues
Refs: #31, #125. This supplies event plumbing for calibration. It does not add per-commit RTL execution, prove event predicate equivalence or qualify continuous calibration.

Roadmap notes: Native cache/TLB/prefetch counts are available to existing calibration maps. Probe predicates, ROI agreement and RTL drift execution remain project obligations.


## PR 614

[#614](https://github.com/riscPrint/risc-v-workstation/pull/614). Merged: 2026-11-13T03:21:54Z.

Title: feat(probes): add rvw probes list, summary and consumer converters

Audit evidence label: unit tests only.

## Summary

- New `rvw probes` (package `rvw/src/rvw/probes/`, auto-registered CLI and MCP):
  - `list --db DB | --events FILE`: the probes of a design (from the `rvwprobe__KIND__NAME__FIELD` wires in a SpinalDB database, or from a `rvw.probe-events/1` header) and one row per consumer tool: `enabled`, `missing` (names the probe kind and fields to add), `unknown` (meta not in the database) or `no_converter`.
  - `summary EVENTS`: event counts and counter totals.
  - `convert EVENTS --to bp-events|kanata|cache|mmu|counts|hpm|etrace-ingress|interrupts`: writes each consumer's existing format. `bp-events` aligns events 1:1 with C2 branch retirements and refuses count, PC or taken differences (speculative or missed events). `counts` needs a complete stream and binds the C1/C2 hashes for `rvw arch ooo-calibrate`. `interrupts` checks interrupt-taken probes against C2 interrupt traps (`consistent`/`mismatch`/`inconclusive`).
- MCP: `probes_list`, `probes_summary`, `probes_convert`.
- Formats are in the "Probe event stream" contract subsection merged in #612.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_probes.py -q`: 10 passed (bp-events read back by `rvw.csim.rtl.read_bp_events`; Kanata read back by `rvw.perf.kanata`; MMU rows accepted by `rvw.regress.mmu_protocol.check`; refusals for speculative, misaligned and other-ELF events; DB listing; CLI; MCP registration). Added to the fast set.
- Fast set: 847 passed before this PR's module was added; only `test_command_reference.py` fails (deferred per the brief; `docs/COMMAND_REFERENCE.md` not committed).
- Not run: any converter on real RTL events (next PR, VexRiscv).

## Issues

Refs: #49

Roadmap notes: `rvw probes` added (generic). Converters exist for csim compare-rtl, perf (Kanata stages and stalls), cache observer, MMU observations, ooo-calibrate counts, HPM bindings, E-Trace ingress and an interrupt check. No converter yet for C2/2 per-slot CSR snapshots, C2 `mmu_walks` grouping, Kanata prediction records and fault sites.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 615

[#615](https://github.com/riscPrint/risc-v-workstation/pull/615). Merged: 2026-11-13T03:24:58Z.

Title: feat(farm): expose resumable workflow plans and event replay

Audit evidence label: unit tests only.

## Summary
Expose persistent command dependency plans, capability discovery, resume and completion events. Queue only nodes whose dependencies completed. Replay owner-filtered SSE events from a persistent sequence cursor through the authenticated service. Keep execution state separate from verification results.

## Testing
- Targeted workflow and service tests: 9 passed, 0 skipped.
- Fast set: 838 passed, 1 skipped. Main temporarily skips the generated command-reference check during the parallel push.
- NOT RUN: RTL, full Python suite, CI, external webhook delivery.

## Issues
Refs: #123

Limits: advance is explicit; completion events appear on the next advance/status call. SSE supplies finite replay batches and clients reconnect with Last-Event-ID. No webhook is sent. Concurrent workflow advances are not coordinated.

Roadmap notes: farm workflow and authenticated SSE replay support resumable agent command DAGs without whole-result polling.


## PR 616

[#616](https://github.com/riscPrint/risc-v-workstation/pull/616). Merged: 2026-11-13T03:26:22Z.

Title: feat(checks): import sampled upf retention and supply tables

Audit evidence label: unit tests only.

## Summary
Import literal UPF retention strategies with sampled high/low controls and power-state tables with explicit project supply-state codes. Generate monitors and instance bindings. Retention supplies stay recorded as names; analog availability and physical power behavior are not inferred.

Also fix two generated-check defects found during qualification: unknown-reset Python CSR models now require M-mode full writes, and typed TileLink monitors allow unaccepted offers to change. TileLink rows explicitly report opcode_safety instead of generic Stream stall safety.

## Testing
- UPF/CSR targeted suite: 58 passed, no skips, 17.17 seconds. Includes retention and supply-table SBY good/mutant cases.
- Typed bus and UPF retention suite after the TileLink correction: 14 passed, no skips. The TileLink good fixture changes payload while stalled.
- Fast set after rebase: 838 passed, 1 skipped, 7060 deselected.
- NOT RUN: physical power behavior, full UPF/Tcl semantics, clock/power gating import, real device/HPM campaign, full Python suite, BOOM builds.

## Issues
Refs: #146, #85, #66

Roadmap notes: Add sampled retention save/restore checks and supply-state tuple checking with explicit bindings. Keep physical power behavior, gating import, full UPF semantics and real-device/HPM binding open. Correct TileLink pre-acceptance offer semantics without claiming transaction compliance.


Post-rebase validation: fast set 848 passed, 1 skipped, 7065 deselected. The command-reference skip is explicitly recorded by the parallel-push coordinator in test_command_reference.py.


## PR 617

[#617](https://github.com/riscPrint/risc-v-workstation/pull/617). Merged: 2026-11-13T03:24:25Z.

Title: test(memory): compare axiomatic outcomes with pinned herd sets

Audit evidence label: unit tests only.

## Summary
Cross-check the independent graph checker against every complete outcome set pinned for SB, MP and LB, fenced and unfenced, under RVWMO and Ztso. Add a data-dependency thin-air cycle check. Keep third-party sources outside the repository.

## Testing
13 targeted Python tests passed, no skips. All 12 outcome-set hashes match the committed reference pins. The six external litmus source files were fetched at the pinned revision outside the repository and matched their source hashes.

Fast set: 838 passed, 1 skipped. Main temporarily skips command-reference consistency during the parallel documentation batch.

NOT RUN: native herd7, new RTL, BOOM builds, full Python suite. This is pinned-reference validation for six patterns. It is not a complete independent validation of all RVWMO relations.

## Issues
Refs: #90, #96, #97.

Roadmap notes: the graph checker now has complete-outcome regression checks against the existing RVWMO/Ztso reference pins. Broader native differential validation remains open.


## PR 618

[#618](https://github.com/riscPrint/risc-v-workstation/pull/618). Merged: 2026-11-13T03:24:45Z.

Title: feat(uvm): add solver stimulus and observed coverage export

Audit evidence label: ran on seeded RTL fixture.

## Summary

Add optional Z3 bounded-integer constrained stimulus for pyuvm and explicit observed functional bins. Export existing coverage-exchange counters into `rvw cov exchange` and UCIS. Preserve zero-count bins. Unsatisfiable or unknown solves cannot return a transaction. Add a real RTL memory fixture and small SV randc/transition-bin probes.

## Testing

- Targeted solver and coverage tests: 3 passed, 0 skipped with z3-solver 4.15.4.0.
- Native pyuvm/cocotb memory test on Verilator 5.049 devel: 1 passed, 0 skipped, 72 RTL checks, 36 transactions, 108 simulated ns, all 8 declared bins hit.
- CLI UCIS export/import retained all 8 bins and 72 counts after fixing bin ordering. A reversed-domain unit test covers the ordering regression.
- Native probes on `5.049 devel v5.048-26-g25d4827bd (mod)`: 4-bit randc checked a full cycle. Transition-bin probe emitted COVERIGN and failed its coverage assertion. This is a measured engine-specific gap.
- Fast set: 838 passed, 1 skipped, 7026 deselected in 119.28s (0:01:59).
- NOT RUN: complete SV constraint/coverage conformance, full suite, BOOM, CPU qualification, CI or C4.

## Issues

Refs: #296

This supplies a solver-backed Python path and observed functional coverage transport. It does not establish every language construct or coverage closure. CPU/SoC acceptance and advanced SV features remain open.

Roadmap notes: Python constrained stimulus and observed functional coverage are available. Native memory checks and UCIS transport passed. The installed Verilator ignores the tested SV transition bin; the tested randc cycle passed. Keep those version-specific results distinct.


## PR 619

[#619](https://github.com/riscPrint/risc-v-workstation/pull/619). Merged: 2026-11-13T03:25:18Z.

Title: feat(formal): extract bounded cell cores and vacuity probes

Audit evidence label: ran on seeded RTL fixture.

## Summary
Export every supported mapped Boolean cell equation as a named bounded solver constraint. Report the full cell inventory and core membership. Test combinational assertion-leaf replacement vacuity with unchanged design equations. Evaluate explicit requirement obligations through stable property IDs. Preserve inconclusive outcomes for missing evidence.

## Testing
19 targeted tests passed, including native valid, failing and contradictory-environment cell queries. Native retained model: 234 mapped cells, 60 core cells, deletion-minimal, 92 solver calls. Fast set: 838 passed, 1 skipped, 7033 deselected. Heavy core jobs NOT RUN.

## Issues
Refs: #62. The new analysis is bounded. Full temporal non-vacuity and unbounded functional cell coverage remain open. Requirement discharge is conditional on declared obligations and captured assumptions.

Roadmap notes: Bounded mapped cell cores, combinational leaf vacuity probes and explicit requirement obligations now work without promoting structural cones to full functional coverage.


## PR 620

[#620](https://github.com/riscPrint/risc-v-workstation/pull/620). Merged: 2026-11-13T03:25:41Z.

Title: test(vip): qualify reactive apb and ahb roles against rtl

Audit evidence label: ran on seeded RTL fixture.

## Summary

Qualify the APB and AHB Python reactive subordinates against independent small RTL managers. Run seed 17 with good and bad subordinates. Require exact data diagnostics for the negative runs. Build no UVM runtime.

Roadmap notes: bounded reactive read/wait evidence is available for APB/AHB. Writes, byte lanes, errors, reset interruption and sustained pipelining remain outside this campaign.

## Testing

- APB/AHB targeted Python tests: 25 passed.
- APB Icarus campaign: good passed, bad subordinate detected, 2.0 seconds.
- AHB Icarus campaign: good passed, bad subordinate detected, 1.4 seconds.
- Required fast tests: 848 passed, 1 skipped, 7056 deselected in 119.58s (0:01:59)
- Not run: UVM runtime builds, full protocol campaigns, BOOM jobs or full Python suite.

## Issues

Refs: #48, #56.


## PR 621

[#621](https://github.com/riscPrint/risc-v-workstation/pull/621). Merged: 2026-11-13T03:25:52Z.

Title: refactor(rvw): discover per-command modules and fast-test opt-ins

Audit evidence label: unit tests only.

## Summary
Remove three shared-file hot spots.

- New `rvw.common.subcommands`: a tool can put each command group in `rvw/src/rvw/<tool>/commands/<name>.py` with `register(subparsers)` and `mcp_tools()`. `rvw formal` now calls `register_commands("rvw.formal", s)`. The MCP registry collects `mcp_tools()` from every `rvw.<tool>.commands` package. New formal commands need no edit to `formal/cli.py` or `formal/mcp_tools.py` (27 and 24 edits today).
- `rvw/tests/conftest.py`: a module with `pytestmark = pytest.mark.fast` joins the fast set without an edit to `FAST_MODULES`, and does not also get `slow`. `test_workloads.py` already used this.
- `test_mcp_tools.py::test_tool_declarations_do_not_import_sdk`: replace the fixed count `59` (stale after each merge) with a structural check: every tool has a matching name, a description, an object schema and a callable handler; the job tools exist; each selected package has tools.
- AGENTS.md documents both mechanisms.

Existing registrations are unchanged; the tool set (209 tools) and the parser are the same.

## Testing
- `pytest rvw/tests/test_subcommands.py` (new, fast): 4 passed.
- `pytest rvw/tests/test_mcp_tools.py -k declarations`: 1 passed.
- Fast set: 842 passed, 1 skipped.

## Issues
None. Sheriff maintenance of `main`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 622

[#622](https://github.com/riscPrint/risc-v-workstation/pull/622). Merged: 2026-11-13T03:31:51Z.

Title: feat(privilege): verify imsic files and aplic msi gateways

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Generate IMSIC supervisor and selected VS guest-file cases, including an uninjected peer-file check. Add APLIC edge/level-to-MSI programs for both polarities and rearming. Follow the pinned AIA 1.0 pending-bit rules rather than impose PLIC gateway semantics. Inactive and delegated sources cannot deliver through the parent model.

Correct the Smnip reference model to keep one previous-threshold field. Nested handlers must explicitly save and restore that field in software. The model no longer creates an implicit hardware stack.

## Testing

- Targeted tests: 39 passed, 0 skipped.
- RISC-V GCC: 16 programs compile across machine, supervisor, VS guest and APLIC MSI profiles.
- Python references: 16 model-based outcomes pass. These are not native Spike or DUT results.
- Fast set: 838 passed, 1 skipped, 6960 deselected. Upstream temporarily skips the command-reference declaration check during this parallel push. This PR does not change that test.
- NOT RUN: RTL builds/simulations, full suite, long formal or CI.

## Issues

Refs: #158
Refs: #165
Refs: #186

Remaining: multiple-hart campaigns, full guest context switches, controller backpressure campaigns, asynchronous preemption and DUT qualification. Generated mailbox events still need a project driver.

Roadmap notes: Add IMSIC file isolation and APLIC MSI gateway program generation. Record model-based outcomes separately from native and DUT evidence. Correct the nested-priority model's software save/restore boundary.

Final rebase fast set: 852 passed, 1 skipped, 7096 deselected. The upstream command-reference declaration skip remains. All 16 model-based reference outcomes pass again with the corrected model-source hashes.


## PR 623

[#623](https://github.com/riscPrint/risc-v-workstation/pull/623). Merged: 2026-11-13T03:28:46Z.

Title: feat(mcp): serve authenticated client-isolated sse sessions

Audit evidence label: unit tests only.

## Summary
Serve authenticated MCP over HTTP/SSE with explicit tool allowlists, a fixed project and separate client job stores. Add a narrow read-only role. Run remote tools in owned workers with per-client per-run supervisor budgets. Retain cancellation, locks and cost reports without changing other clients' environment.

## Testing
- Targeted remote MCP and budget tests: 18 passed, 0 skipped.
- Includes an actual local HTTP/SSE initialize/list/call roundtrip, auth rejection, cross-client visibility and budgeted worker errors.
- Final fast set: 852 passed, 1 skipped, 7089 deselected. Main temporarily skips test_command_reference during the parallel push.
- NOT RUN: external/cloud clients, TLS proxy, RTL, full Python suite, CI.

## Issues
Refs: #54

Limits: trusted-project service, no filesystem sandbox; use an existing TLS proxy for remote access. Remote MCP job stores are in-memory. Budgets apply per run, not cumulative client totals. Read-only roles are an explicit narrow query list. All remote calls return job IDs.

Roadmap notes: authenticated remote MCP now supports isolated client sessions, project binding, owned worker execution and per-run budgets.


## PR 624

[#624](https://github.com/riscPrint/risc-v-workstation/pull/624). Merged: 2026-11-13T03:30:10Z.

Title: feat(uvm): scaffold apb register benches from design data

Audit evidence label: unit tests only.

## Summary

Add `rvw uvm new` and `uvm_new` MCP to generate a runnable pyuvm APB register-reset bench from SpinalDB and an rvw SoC map. Select APB from the Spinal bundle class. Map unique pins, clock/reset and RTL files. Connect the merged APB agent and Python RAL. Check actual bus read responses against declared register reset values.

The first runnable profile supports one APB3/4 bus, one clock/reset and one MMIO region. Other recognized bus classes return explicit profile diagnostics. It does not produce a passing empty scaffold.

## Testing

- Targeted tests: 3 passed, 0 skipped, including one native generated-bench run on Verilator.
- Fast set: 848 passed, 1 skipped, 7081 deselected in 125.97s (0:02:05).
- NOT RUN: CPU scaffold, multi-bus SoC scaffold, SV output, full suite, BOOM, CI or C4.
- No command-reference changes are committed, as required by the worker brief.

## Issues

Refs: #296

The APB register profile is runnable. Generic new-core CPU wiring and other active protocol profiles remain open.

Roadmap notes: `rvw uvm new` now generates a native-tested APB pyuvm reset-read bench from design and map data. Other bus types and automatic CPU environments remain open.


## PR 625

[#625](https://github.com/riscPrint/risc-v-workstation/pull/625). Merged: 2026-11-13T03:31:46Z.

Title: feat(arch): overlap correctly predicted branches with younger work

Audit evidence label: unit tests only.

## Summary
Add an optional correct-path branch overlap policy. Correctly predicted branches can remain unresolved while younger work issues, renames and fetches. Preserve misprediction recovery and serial CSR/fence rules. Clear younger prediction decisions on memory replay. Add front-end phase-pressure counters and name the optional decode phase in reports.

## Testing
96 targeted OoO tests passed. Fast set: 852 passed, one skipped. Main disables the command-reference declaration check for this parallel push; this PR does not alter it. A separate native component TLB smoke passed: two accesses, one TLB miss and one page walk. Tests show correct predictions overlap work while misses keep the original recovery cost.

No RTL simulation, BOOM build, gem5 run or full suite ran. Prediction remains at issue on a fixed committed trace. Wrong-path instructions and predictor history checkpoint/restore remain unmodeled. This is timing exploration, not recovery qualification.

## Issues
Refs: #72.

Roadmap notes: Configurable correct-path overlap removes mandatory serialization of all correct branches. Native gem5 features, speculative history repair and RTL fidelity remain open.


## PR 626

[#626](https://github.com/riscPrint/risc-v-workstation/pull/626). Merged: 2026-11-13T03:32:45Z.

Title: feat(formal): compare sampled generated clock events

Audit evidence label: ran on seeded RTL fixture.

## Summary

Add opt-in sampled-event equivalence for generated clocks and simple clock-gating latches. Normalize both complete wrappers with Yosys clk2fflogic before closed eqy output proofs. Require unmatched-state prove. Capture optional input stability assumptions at root rising-edge samples.

Completed queries remain conditional and exit 1. Do not claim analog, between-sample, clock-tree or unconditional hardware equivalence. Keep default frontend latch/clock rejection. Extend counterexample simulation to conditional negative verdicts. Expose the controls through formal_equiv MCP.

## Testing

- New sampled-event/MCP tests: 5 passed. Prove the modeled clock-gating insertion fixture, detect a wrong-enable mutant, replay its counterexample in Yosys simulation, and retain default latch rejection.
- Combined sampled-event and existing equivalence tests: 22 passed.
- Required fast set after rebase: 848 passed, 1 skipped, 7061 deselected. The skip is the upstream temporary command-reference batch rule.
- NOT RUN: BOOM builds, full Python suite, long formal jobs, physical clock qualification or asynchronous reset-cell support in this mode.

## Issues

Refs: #18.

Roadmap notes: Add conditional sampled-event generated/gated-clock comparison and input setup contracts. Physical clock behavior and project clock-model qualification remain open. No new unconditional gate acceptance is granted.


## PR 627

[#627](https://github.com/riscPrint/risc-v-workstation/pull/627). Merged: 2026-11-13T03:30:37Z.

Title: feat(vip): add reduced coherent event and ownership checks

Audit evidence label: unit tests only.

## Summary

Add `rvw.chi-like/1`, a reduced coherent event stream with Python and SV UVM agents. Check request credits, transaction IDs, per-line exclusion, snoop acknowledgements, reference data and ownership. Keep the project bridge and licensed CHI protocol separate.

Roadmap notes: reduced coherent trace checking is available. This is not Arm CHI wire support. Licensed backend translation, dirty forwarding, ordering channels, retries and native qualification remain open.

## Testing

- Reduced coherent Python tests: 2 passed.
- Verilator lint with pinned Accellera UVM: passed.
- Required fast tests: 852 passed, 1 skipped, 7102 deselected in 134.07s (0:02:14)
- Not run: UVM runtime builds, coherent RTL bridges, licensed CHI campaigns, BOOM jobs or full Python suite.

## Issues

Refs: #212. Native licensed CHI integration remains open.


## PR 628

[#628](https://github.com/riscPrint/risc-v-workstation/pull/628). Merged: 2026-11-13T03:31:18Z.

Title: test(regress): record generic identity removal prerequisites

Audit evidence label: unit tests only.

## Summary
Inventory the three shipped C1 regression configurations and record the prerequisites for removing generic command/toolchain capture. Add a negative completeness test: changing a declared command leaves the fake adapter's identity unchanged, but generic capture correctly forces re-execution. Retain the fields to avoid losing this protection.

## Testing
- New fake-adapter migration test: 1 passed, 0 skipped.
- Final fast set: 852 passed, 1 skipped, 7155 deselected. Main temporarily skips test_command_reference during the parallel push.
- NOT RUN: native BOOM/VexRiscv completeness, RTL, full Python suite, CI.

## Issues
Refs: #76

Removal remains blocked. Complete replacement dependency identities and negative tests are not established. The simulation collector captures fewer launcher commands than the generic declarations. Simulation-engine files belong to another worker and were not changed. Deleting declarations now would weaken input capture.

Roadmap notes: #76 remains open with an adapter inventory and a regression test for the identity gap. No generic input field was removed.


## PR 629

[#629](https://github.com/riscPrint/risc-v-workstation/pull/629). Merged: 2026-11-13T03:31:40Z.

Title: fix(cosim): guard absent vex supervisor interrupt input

Audit evidence label: unit tests only.

## Summary

Guard the absent supervisor external-interrupt port when the VexRiscv example initializes and drives its M-only CSR plugin. The first fresh native run previously stopped at cycle zero with a null-port assignment. Declare only the live MSIP, MTIP and MEIP inputs in the adapter and Spike platform. SEIP schedules must be refused.

## Testing

- Fresh native run before this fix: C1 `assert`, zero retired instructions, null-port assignment in `spinal.core.sim.setLong`. This is failure evidence, not an ISA match.
- Native SATP/CSR tests, 49 ISA tests and live lockstep reruns queued on the shared vex lock. No result claimed yet.
- Fast set before rebase: 852 passed, 1 skipped, 7100 deselected.

## Issues

Refs: #11, #70.

Roadmap notes: fix a real M-only adapter startup failure and make the interrupt capability declaration exact. Native qualification remains pending until the queued runs finish.

Fast set after rebase: 852 passed, 1 skipped, 7154 deselected.


## PR 630

[#630](https://github.com/riscPrint/risc-v-workstation/pull/630). Merged: 2026-11-13T03:32:05Z.

Title: feat(checks): import literal upf power-switch gating

Audit evidence label: unit tests only.

## Summary
Import literal single-control UPF power switches and their input/output supply names. Bind independent input/output availability and a project-selected settling bound. Generate a sampled gating monitor and instance binding. General Boolean expressions, analog power ramps and clock-gating import remain unsupported.

## Testing
- UPF switch, retention and isolation suite: 45 passed, no skips, 21.78 seconds.
- Native switch proof/mutant, parser and main importer tests passed.
- Fast set after rebase: 852 passed, 1 skipped, 7158 deselected. The skip is the coordinator's command-reference batch-generation check.
- NOT RUN: physical power behavior, real power-switch cell binding, full UPF/Tcl semantics, full Python suite, BOOM builds.

## Issues
Refs: #146

Roadmap notes: Add literal power-switch gating import with sampled project settling bounds. Do not claim analog ramp, cell connectivity or clock-gating verification.


## PR 631

[#631](https://github.com/riscPrint/risc-v-workstation/pull/631). Merged: 2026-11-13T03:32:36Z.

Title: feat(uvm): reject unqualified project bench requirements

Audit evidence label: unit tests only.

## Summary

Add explicit required-feature filtering to project UVM builds. CLI `--require-feature` and MCP `required_features` reject unqualified HDL backdoor, VPI polling, advanced constraints/coverage, four-state and commercial VIP requirements before output creation or native tools. Reuse the existing profile diagnostics and workarounds. Passing the filter does not qualify a language feature.

## Testing

- Targeted tests: 8 passed, 0 skipped. Include CLI diagnostics and refusal before output creation or even manifest access.
- Fast set: 852 passed, 1 skipped, 7166 deselected in 74.48s (0:01:14).
- NOT RUN: full suite, commercial VIP, Accellera HDL DPI/VPI qualification, BOOM or CI.

## Issues

Refs: #178, #296

The existing adapter can run the bounded native UVM profile. This change makes its remaining feature limits explicit at build time. Full imported VIP and HDL backdoor support remain unqualified.

Roadmap notes: project UVM builds now refuse explicitly required features outside the qualified runner profile. Existing feature evidence remains separate from this filter. No C4 acceptance is added.


## PR 632

[#632](https://github.com/riscPrint/risc-v-workstation/pull/632). Merged: 2026-11-13T03:32:56Z.

Title: feat(formal): search each assertion and export typed witnesses

Audit evidence label: ran on seeded RTL fixture.

## Summary
Search each captured assertion independently while retaining assumptions. Share a time budget and keep separate shortest certificates. Add exact property selection and SpinalWaves witness conversion with VCD scope discovery. Record the real StreamFifo database autocheck counts in README-apps.md.

## Testing
6 targeted tests passed. Native two-property shortest depths: 3 and 5 samples. Native typed VCD export passed with explicit UInt test metadata. Offline checker build took 24 seconds. Fast set: 848 passed, 1 skipped, 7087 deselected. Real synchronous StreamFifo database run: 13 generated, 1 proven, 0 bounded passes, 12 observation failures, 1 unsupported input-producer record. Heavy core jobs and interactive viewer navigation NOT RUN.

## Issues
Refs: #60, #62. Full temporal vacuity and arbitrary source-type navigation remain open. The library run does not establish complete FIFO ordering or whole-core coverage.

Roadmap notes: Independent multi-property shortest search and typed witness export work. Real library autocheck evidence is recorded with observation semantics and limits.


## PR 633

[#633](https://github.com/riscPrint/risc-v-workstation/pull/633). Merged: 2026-11-13T03:33:30Z.

Title: feat(query): add a GHDL front end for VHDL designs

Audit evidence label: unit tests only.

## Summary

- `rvw query build-hdl --frontend ghdl` elaborates VHDL through the GHDL Yosys plugin (`ghdl --std=08 --work=LIB files -e TOP`). Options: `--library`, `-G NAME=VALUE` (top generics), `--std 93|08` (default 08), `--ghdl-plugin PATH` (else `$RVW_GHDL_PLUGIN`, else the plugin bundled with Yosys). MCP `query_build_hdl` takes `frontend: ghdl` and `library`.
- The plugin writes no source attributes. A second pass, `ghdl --file-to-xml` over the same captured files, gives entity lines (component location), port/signal declaration lines and the first assignment statement line per signal. Component `module` is the entity name (GHDL's `<entity>_B<arch>...` module names are mapped back).
- Clock/reset roots (all `yosys-*` frontends) now follow only ports, aliases, buffers and inverters, and flip edge/polarity per inverter. Before, NEORV32's `rstn_i` was reported active high, because GHDL inverts it for `$adff`. A net derived by other logic is now its own root instead of an arbitrary input found through the logic.
- A register net's `reset_value` is now the concatenation of its own bits' reset values (before, every net got the whole cell's value).
- `scripts/build-ghdl-plugin.py` builds a pinned ghdl-yosys-plugin revision with the GHDL headers of the exact libghdl commit, outside the checkout. The OSS CAD Suite 2026-05-01 plugin emits `$memwr_v2` cells that fail the Yosys cell check, so VHDL memories need the rebuilt plugin.
- Docs: `SpinalDB/README.md` (VHDL section), `docs/contracts/query.md` (GHDL contract section), query README, design note.

## Testing

- `RVW_GHDL_PLUGIN=~/.cache/rvw/lib/ghdl.so RVW_HDL_REF=[local path omitted] rvw/.venv/bin/python -m pytest rvw/tests/test_query_ghdl.py -q`: 5 passed (synthetic VHDL design with a package record, generics, generate and async reset; independent netlist oracle; refusals; NEORV32 `neorv32_cpu` at 7bd0858). With the bundled plugin: 4 passed, 1 skipped (NEORV32 needs the rebuilt plugin).
- `rvw/tests/test_query_slang.py test_query_hdl.py test_hdl_semantics.py test_lint_hdl.py`: 57 passed.
- `scripts/build-ghdl-plugin.py --cxx clang++` built and loaded the plugin (macOS arm64, about 12 s).
- Fast set (command-reference tests deselected per the brief): 838 passed, 1 skipped.
- Not run: full Python suite, CI, the build script on Linux or with the installer's pinned OSS CAD Suite 2026-10-22 (its plugin revision may need `--plugin-rev`).

## Issues

Refs: #371. Remaining: a second real VHDL design beyond NEORV32 plus the synthetic one, generic values per instance, mixed-language designs, an installer flag for the plugin build, foreign model declarations.

Roadmap notes: Design database front ends: VHDL designs now build through GHDL (`build-hdl --frontend ghdl`) with VHDL declaration and assignment lines; NEORV32 `neorv32_cpu` builds and every `rvw query` command works on it. Clock and reset roots now follow inverters, so reset polarity is that of the input.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 634

[#634](https://github.com/riscPrint/risc-v-workstation/pull/634). Merged: 2026-11-13T03:38:26Z.

Title: feat(formal): check internal rtl dependency paths without cuts

Audit evidence label: ran on seeded RTL fixture.

## Summary

Add `rvw formal internal-path` and `formal_internal_path` for conservative internal RTL dependency checks. Capture self-contained source bytes, flatten the design, map memories and walk bit dependencies without cutting drivers. Report no_path, path_found or incomplete with source/netlist hashes and a witness. Black boxes, unknown directions and node limits prevent an absence result. A path does not prove Boolean influence.

Refuse uncaptured Verilog includes in this checker and in the architectural-state generator.

## Testing

- Targeted internal path tests with native Yosys: 5 passed, no skips.
- Architectural-state uncaptured-include regression: 1 passed, 6 deselected.
- Fast set: 852 passed, 1 existing skip, 7184 deselected.
- NOT RUN: full Python suite, BOOM, full-core influence proofs or two-copy noninterference.

## Issues

Refs: #107

Roadmap notes: Internal forbidden paths can now be checked against captured flattened RTL. The graph conservatively includes data, clock, reset and control dependencies. Boolean sensitization, conditional noninterference and design acceptance remain outside this result.


## PR 635

[#635](https://github.com/riscPrint/risc-v-workstation/pull/635). Merged: 2026-11-13T03:34:09Z.

Title: feat(sim): add standard device plugin models and linux recipe

Audit evidence label: unit tests only.

## Summary

Add standard device models through the existing DeviceApiV1 ABI. The optional CPython bridge reuses the UART 16550 TX, CLINT/ACLINT MTIMER/MSWI and PLIC models. Add buffered HTIF console output and a simple mapped RAM disk. Project JSON selects the model, layout, clock ratio and scheduled PLIC input levels. Add a shared-library build helper and project configuration examples.

Add a Linux/OpenSBI recipe using the rvw soc RAM map and explicit project CPU/device bindings. Boot the pinned Debian kernel and selected BusyBox initramfs in native QEMU with the generated DTB. The recipe checks input hashes and requires the userspace marker, no timeout and exit code zero.

Limits: UART RX/FIFO/modem timing, ACLINT supervisor software interrupts, live PLIC gateway callback wiring, virtio/DMA, host disk persistence and RTL/plugin-backed Linux boot remain unsupported. The current RV32IM M-only VexRiscv example cannot boot this RV64/Sv39 image. The recipe documents the required core and platform functions.

## Testing

- Six targeted tests passed, including actual shared-library compilation and fresh-handle UART snapshot restore through DevicePlugin. Repeated after rebase: 6 passed.
- Native QEMU 11.1.3 with its OpenSBI firmware: reached RVW_LINUX_USERSPACE_OK and powered off with exit 0. Kernel SHA-256 08f6dbe2dd3b1b411e26b65c27b89f780e8af5d3d0ef4cde84a9f3291e2440f2; generated DTB 86fd47229d3f929140ab1251c58997483e38efc77d0b7d144c99301acc34dbe0.
- Native library build helper ran successfully with CPython 3.13 on macOS ARM64.
- Fast set before final fetch/rebase: 852 passed, 1 skipped, 7168 deselected. The command-reference check is deferred by the work brief. One warning came from concurrent pytest temporary-directory cleanup.
- NOT RUN: full Python suite, BOOM, Linux on RTL, live device-to-core bus wiring, Spike Linux boot and GitHub CI.

## Issues

Refs: #295. This is device and reference-boot infrastructure. It does not qualify a whole-core Linux simulation engine.

Roadmap notes: Standard device models can be selected from project data through the plugin ABI. A map-derived reference DTB boots the pinned Linux image to userspace in QEMU. Device routing into a real RTL adapter remains open.


## PR 636

[#636](https://github.com/riscPrint/risc-v-workstation/pull/636). Merged: 2026-11-13T03:34:21Z.

Title: feat(vip): add abstract memory and noc stress agents

Audit evidence label: unit tests only.

## Summary

Add abstract memory-controller/NoC traffic agents. Model seeded latency/jitter, bounded bandwidth, refresh-like pauses and QoS priority. Independently check source credits, response data/errors and starvation limits. Include a cocotb event sender and matching SV UVM event bridge, coverage and scoreboard.

Roadmap notes: abstract memory/NoC stress is available. A project bridge is required for real interfaces. DDR timing, electrical validation and native controller qualification remain separate.

## Testing

- Stress Python tests: 3 passed.
- Verilator lint with pinned Accellera UVM: passed.
- Required fast tests: 852 passed, 1 skipped, 7180 deselected in 76.89s (0:01:16)
- Not run: UVM runtime builds, native controller/NoC campaigns, BOOM jobs or full Python suite.

## Issues

Refs: #182. Native project-interface campaigns remain open.


## PR 637

[#637](https://github.com/riscPrint/risc-v-workstation/pull/637). Merged: 2026-11-13T03:35:41Z.

Title: feat(formal): check finite graph progress possibility

Audit evidence label: unit tests only.

## Summary
Check progress possibility from every reachable state of an explicit finite graph. Include fair cyclic components and fair suffix feasibility. Keep existential progress separate from universal response liveness and from RTL translation claims.

## Testing
7 targeted tests passed. Fast set: 852 passed, 1 skipped, 7201 deselected. Tests cover unreachable dead regions, reachable traps, optional infinite waits, infeasible fairness and fair nonprogress traps. Heavy native core jobs NOT RUN.

## Issues
Refs: #62. RTL graph extraction is not supplied by this app.

Roadmap notes: Exact finite-graph progress possibility now complements the native liveness-to-safety response app.


## PR 638

[#638](https://github.com/riscPrint/risc-v-workstation/pull/638). Merged: 2026-11-13T03:36:31Z.

Title: fix(uvm): synchronize separate cpu trap observations

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Handle project trap pulses separately from live CPU retirements. Check each cause and tval through an independent Spike step. Add reusable requested-IRQ and debug halt-state comparison services. Reject unrequested IRQ causes and unsupported debug resume. Add expected/actual diagnostics for retirement failures and run add/beq/lw as independent reset/reference tests in one native build. Retain per-program comparison counts.

Document selection of current C1-generated RTL. The first attempted ISA run used stale MSU RTL with an M-only platform and lacked trap synchronization. It failed on `SPIKE_MISMATCH:pc`. That run is not a CPU match or a core bug finding.

## Testing

- Targeted services and adjacent UVM tests: 23 passed, 1 optional native test skipped.
- Fast set: 852 passed, 1 skipped, 7196 deselected in 89.65s (0:01:29).
- Native first attempt: 1 failed, 0 skipped (`SPIKE_MISMATCH:pc`). Corrected three-program run is queued under the shared vex lock. Another worker has held it since 03:26 UTC. No corrected native pass is claimed.
- NOT RUN: native architectural interrupt/debug qualification, complete ISA, full suite, BOOM, CI or C4.

## Issues

Refs: #296

Native CPU qualification remains open pending the corrected run. VexTop has no debug port. The generic debug service is tested with an independent stub, not native debug hardware. Random IRQ/debug execution and SoC/C4 acceptance remain open.

Roadmap notes: live CPU trap synchronization and reusable reference control checks now exist. Native ISA qualification remains pending; an initial configuration-mismatched run failed. Do not count it as an ISA pass or attribute it to the core.


## PR 639

[#639](https://github.com/riscPrint/risc-v-workstation/pull/639). Merged: 2026-11-13T03:36:37Z.

Title: feat(checks): bind native gpio and vexriscv counter events

Audit evidence label: ran on real core RTL.

## Summary
Bind the independent device checker to the actual SpinalHDL 1.15.0 Apb3Gpio direction word. Observe accepted APB accesses and real IP responses. Check reset reads, masked writes and readback; a seeded observation fault must fire register.bus_data. Other GPIO words remain outside this model.

Add optional VexRiscv mcycle/minstret bindings to actual CSR storage and independent clock/last-stage firing events. Add masked software writes to HpmChecks so RV32 half writes preserve unselected increment/carry bits. Existing callers keep full-width write semantics. Require the existing writable machine counter interfaces before adding callbacks.

## Testing
- HpmChecksSpec plus GpioDeviceSpec: 4 passed, no skips, 15 seconds under the sbt lock. Includes good/fault GPIO runs and masked counter-write tests.
- Fast set after rebase: 852 passed, 1 skipped, 7198 deselected. The skip is the coordinator's command-reference batch check.
- VexRiscv HPM compilation passed in 38 seconds. Elaboration passed in 8 seconds. Both vex and sbt locks were held. The emitted report records hpm.count:mcycle and hpm.count:minstret as inserted. This is elaboration evidence, not an RTL execution campaign.
- NOT RUN: HPM RTL execution campaign, programmable HPM/interrupt/filter qualification, complete GPIO/SoC coverage, physical devices, full Python suite, BOOM builds.

## Issues
Refs: #142, #98

Roadmap notes: Add a concrete native GPIO direction binding and optional real VexRiscv counter event bindings. Keep programmable events, architectural retirement conformance, real-core execution campaigns and complete device coverage open. No issue is closed.



## PR 640

[#640](https://github.com/riscPrint/risc-v-workstation/pull/640). Merged: 2026-11-13T03:36:30Z.

Title: feat(formal): preserve typed sampled history and explicit depth

Audit evidence label: unit tests only.

## Summary
Add positive decimal history depths and nested sampled calls to the finite SVA frontend. Preserve historic expression width and signedness. Use four-state comparisons for edge and stability functions in simulation. Add Scala .past(N) and update the generated support table.

## Testing
- Native composition/history cases: 30 passed.
- Sampled-value and Icarus/Verilator replay cases: 16 passed, including seven independent four-state vector transitions.
- Older non-native temporal cases: 9 passed, 37 deselected.
- Locked Scala Test/compile passed in 21 seconds after an earlier lock-wait timeout. Targeted Scala tests: 3 passed.
- Fast set: 852 passed, 1 main-branch inventory skip, 7171 deselected. Explicit command-reference check passed.
- NOT RUN: full Python suite, BOOM, long formal jobs, full simulator-region qualification, gated or alternate-clock history, GitHub CI wait.

## Issues
Refs: #61

Depths are decimal 1..64. Nesting is limited to eight calls. Initial formal history remains unconstrained. Gated history, alternate clock arguments and sampled reset conditions remain refused. Full SVA remains open.

Roadmap notes: extend finite SVA sampled-value support and correct signed/four-state observations. Keep full language and scheduling qualification partial.


## PR 641

[#641](https://github.com/riscPrint/risc-v-workstation/pull/641). Merged: 2026-11-13T03:37:33Z.

Title: feat(farm): connect live evidence views and checked crash recovery

Audit evidence label: unit tests only.

## Summary
Connect the authenticated live dashboard to owner-scoped C3 runs, pass-rate trends, test history, failure clusters and C5 bundle drill-down. Add checked SSH worker-crash process cleanup and release only that dead worker's reservations after cleanup. Add explicit bounded C1 DUT retries with isolated attempt evidence. A later pass retains the observed DUT failure; mixed outcomes require matching ELF/RTL/native-tool/options identity to mark instability.

## Testing
- Combined tests for all new farm/platform increments: 35 passed, 0 skipped.
- Fast set: 852 passed, 1 skipped, 7213 deselected. Main temporarily skips the generated command-reference check during the parallel push.
- Crash fixtures use real local process groups and fake dead-worker records. No remote cluster or RTL evidence is claimed.
- NOT RUN: native SSH hosts, browser visual checks, RTL, full Python suite, CI.

## Issues
Refs: #25

Limits: live C3 evidence must be inside an owned job directory. External history uses the static dashboard. Unknown old process identities require operator cleanup. Remote temporary artifact cleanup/reattachment and streaming remain open. Broader requirements closure, licensed-tool scheduling and campaign-scale benchmarks remain separate.

Roadmap notes: live regression management now includes authenticated evidence views, isolated retry attempts and checked SSH crash cleanup. Collection/execution state remains separate from DUT and C4 verdicts.


## PR 642

[#642](https://github.com/riscPrint/risc-v-workstation/pull/642). Merged: 2026-11-13T03:37:46Z.

Title: feat(vip): define optional dram model integration contracts

Audit evidence label: unit tests only.

## Summary

Define optional DRAM model integration contracts with explicit model/version, mode and clock requirements. Add a reduced independent ACT/PRE/RD/WR/REF bank, timing and data checker. Reject absent backend bridges and missing read evidence. Add SV UVM native-model extension points with an inert fixture.

Roadmap notes: DRAM integration contracts and reduced checker are available. A project must supply the native model and response scheduler. Full JEDEC/controller qualification and board signoff remain open.

## Testing

- DRAM Python tests: 2 passed using mock callbacks.
- Verilator lint with pinned Accellera UVM: passed.
- Required fast tests: 852 passed, 1 skipped, 7217 deselected.
- Not run: native DRAM model integration, controller campaigns, UVM runtime builds, BOOM jobs or full Python suite.

## Issues

Refs: #213. Native supported-model qualification remains open.


## PR 643

[#643](https://github.com/riscPrint/risc-v-workstation/pull/643). Merged: 2026-11-13T03:38:21Z.

Title: feat(cov): seal raw attempts and bind native closure identity

Audit evidence label: unit tests only.

## Summary

Archive declared initial inputs and the coverage implementation in an immutable C8 generation. Seal each raw attempt once. Pin generation IDs and manifest hashes in campaign state. Verify archives, working artifacts and current inputs on resume. Older unsealed state cannot resume under the changed implementation identity.

Gate coverage credit on C1 source/input completeness, generated RTL hash and captured reference dependencies. Keep program-specific ELF/C2/C1 data and Python caches out of reference backend identity. Stop on a changed native identity without new credit. Preserve reference reports when identity checks refuse credit.

Pass the recorded C1 core name to public cosim calls in both the closure and riscv-dv paths. This fixes checks launched outside the selected core's project directory. No cosim source changes.

## Testing

Focused closure archive/identity and random campaign tests: 44 passed, zero skips. Fast set: 852 passed, 1 skipped, 7200 deselected. The skip is the upstream command-reference check disabled during the parallel push; this PR does not change it.

Tests cover sealed raw bytes, archive corruption, input archive identity, stale resume, native model changes, reference binary changes, payload/cache identity separation, incomplete C1/reference metadata and public API core forwarding.

NOT RUN: native DUT/Spike closure campaigns, cross-host replay, descendant CPU qualification, paired baseline, full suite or CI. Per-attempt cost samples exclude sealing/publication overhead. Rates remain null.

## Issues

Refs: #349, #48

Keep both issues open. Native execution validation, complete project dependency qualification, total cost accounting and paired random comparison remain. Explicit campaign replay is the next increment. Core TestRIG hooks remain outside this worktree's scope.

Roadmap notes: Campaign state now binds immutable input/raw-attempt evidence and exact C1/reference execution identities. Random checks select the C1 core explicitly. Native qualification and complete cost metrics remain unverified.


## PR 644

[#644](https://github.com/riscPrint/risc-v-workstation/pull/644). Merged: 2026-11-13T03:38:44Z.

Title: feat(cosim): inspect capture and comparison scope with doctor

Audit evidence label: unit tests only.

## Summary

Add `rvw cosim doctor` and MCP `cosim_doctor` for a new core's first C2 trace. Validate every record and report declared capture, record counts, completion, configured comparisons, exact conditional CSR/counter/interrupt masks and platform choices. Distinguish CSR-only capture from FP, vector memory, debug and hypervisor capture. No reference is run and no match is claimed.

Document the workflow in BRING_YOUR_OWN_CORE and the cosim README. Add the inspection contract under the split cosim contract and regenerate the CLI/MCP reference.

## Testing

- Targeted capture-doctor and command-reference tests: 6 passed, 1 skipped.
- Native upstream vector C2 inspection: 1,333 instructions, complete trace, vector memory configured, compared=false.
- Native DUT comparison, hardware validation and model capability certification are outside this inspection command.

## Issues

Refs: #11, #70.

Roadmap notes: new core agents can inspect capture and configured comparison scope before running a model. Actual comparisons and applied masks remain in `cosim check`.

Fast set after rebase: 856 passed, 1 skipped, 7217 deselected. Refreshed generated upstream query command changes too.


## PR 645

[#645](https://github.com/riscPrint/risc-v-workstation/pull/645). Merged: 2026-11-13T03:38:41Z.

Title: docs(contracts): move contract text back out of the index

Audit evidence label: no code.

## Summary
After #610 split the contracts, #612 and later merges rebased old branches with keep-both and put the whole old single file (about 4,800 lines) back into `docs/PLATFORM_CONTRACTS.md`.

- Move each section that those branches added or changed into its `docs/contracts/<topic>.md` file (22 sections: MCP transport, workflow plans, ISA/state monitors, VIP bridge, equivalence events, own-core branch overlap, UPF retention/supply/power switch, probe events, cell cores, shortest counterexamples, VexRiscv ports, device checkpoints, IMSIC, and others).
- Drop copies that equal an earlier version of the single file (stale context from the old branches).
- Rebuild the index from the files in `docs/contracts/`.
- A line check finds no non-historical line from the old file that is missing in the new files.

To prevent a repeat, the shared rebase helper (`wt/union-rebase.sh`, outside the repo) now runs `wt/rehome-contracts.py --rebase` on a conflict in this file. It moves that commit's contract changes into the topic files instead of keeping both sides.

## Testing
- Fast set: 852 passed, 1 skipped.
- Simulated an old-branch rebase (new section and one edit made on the pre-split file) with the new helper: the edit went to `docs/contracts/sim.md`, the new section went to `docs/contracts/debug.md`, and the index stayed clean.

## Issues
None. Sheriff maintenance of `main`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 647

[#647](https://github.com/riscPrint/risc-v-workstation/pull/647). Merged: 2026-11-13T03:41:35Z.

Title: feat(vip): add optional pcie transaction model adapters

Audit evidence label: unit tests only.

## Summary

Add optional PCIe transaction-model adapters with explicit backend name/version and bridge. Check enumeration identity, command enables, address windows, read completions and host-memory DMA effects. Add a SV UVM native-model extension point and completion/data reference.

Roadmap notes: semantic PCIe model adaptation is available. Native models, endpoint bridges and specification-dependent qualification remain project-owned. No TLP codec or PHY support is claimed.

## Testing

- PCIe Python tests: 2 passed with mock callbacks.
- Verilator lint with pinned Accellera UVM: passed.
- Required fast tests: 856 passed, 1 skipped, 7265 deselected in 90.64s (0:01:30)
- Not run: native PCIe model integration, endpoint RTL, UVM runtime builds, BOOM jobs or full Python suite.

## Issues

Refs: #215. Native model and endpoint qualification remain open.


## PR 648

[#648](https://github.com/riscPrint/risc-v-workstation/pull/648). Merged: 2026-11-13T03:42:15Z.

Title: fix(uvm): reject incomplete serial observations at completion

Audit evidence label: unit tests only.

## Summary

Refuse SoC completion when a trailing UART frame is still in progress, even if the earlier expected stream matched. Add a failing-prefix regression. Correct the VexRiscv generated-RTL documentation to use C1 `details.rtl_dir`.

## Testing

- Targeted SoC tests: 3 passed, 0 skipped.
- Fast set: 852 passed, 1 skipped, 7236 deselected in 89.22s (0:01:29).
- NOT RUN: connected RTL SoC, full suite, BOOM, CI or C4.
- The corrected VexRiscv ISA matrix remains queued behind another worker's vex lock. The first attempted run failed; no corrected CPU pass is claimed.

## Issues

Refs: #296

Roadmap notes: SoC completion now rejects a trailing partial UART frame. Native connected SoC qualification remains open.


## PR 649

[#649](https://github.com/riscPrint/risc-v-workstation/pull/649). Merged: 2026-11-13T03:42:42Z.

Title: feat(agent): add machine-readable agent guide with mcp resource

Audit evidence label: unit tests only.

## Summary
- `rvw agent guide [--workflow ID] [--json|--markdown [--write FILE]]`: five workflows (`bring-up`, `test-fails`, `add-coverage`, `prove-property`, `performance-question`), each an ordered list of `rvw` commands and MCP tools with decision points (next step, other workflow, `done` or `stop`).
- One data file (`rvw/src/rvw/agent/playbook.json`, `rvw.agent-guide/1`) feeds the CLI, the MCP tool `agent_guide`, the MCP resources `rvw://agent/guide` and `rvw://agent/guide/<id>`, and the generated block in `docs/AGENT_SETUP.md`.
- MCP server: packages can declare `mcp_resources()`; the server lists and reads them (SDK 2.x handlers and 1.x decorators). Server instructions point agents at `agent_guide`.
- Contract text in `docs/contracts/agent-bench.md` ("Agent guide"). Layout row and README added.

## Testing
- `rvw/.venv/bin/python -m pytest rvw/tests/test_agent_guide.py -q`: 5 passed. It parses every step's `cli` with the real rvw parser, checks every MCP tool name against the discovered registry, checks decision targets, checks that `docs/AGENT_SETUP.md` holds the generated block, and runs a real MCP stdio session (list and read resources, call `agent_guide`).
- Fast set: `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`: 861 passed, 1 skipped (command-reference check is skipped on main during the batch regeneration).
- Not run: `docs/COMMAND_REFERENCE.md` regeneration (main regenerates it in one batch); no native tools needed.

## Issues
Refs: #27 (agent loop entry point). The bring-up end-to-end check that walks this guide on a scratch core follows in a separate PR.

Roadmap notes: agent experience: `rvw agent guide` and MCP resource `rvw://agent/guide` give agents a machine-readable playbook generated from the same data as AGENT_SETUP.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

## PR 650

[#650](https://github.com/riscPrint/risc-v-workstation/pull/650). Merged: 2026-11-13T03:43:08Z.

Title: feat(soc): pair observed request tags with memory retirements

Audit evidence label: unit tests only.

## Summary

Add `rvw soc pair` and `soc_pair` to pair independently observed bus request tags with C2 memory retirements. Bind capture bytes to the C2 hash and C1 source/RTL/ELF/seed/session identity. Refuse address-only pairing, duplicate request tags and stale identities.

Compare split-beat byte addresses, direction, data, response timing and memory errors. Keep missing links/responses, posted-store error reporting and unretired/speculative requests as explicit gaps. Matching samples remain inconclusive.

## Testing

- Targeted pairing tests: 10 passed, no skips. Cases include independent C2 data, split beats, wrong data/errors, late load response, reused tags, stale trace/session identity, missing responses and posted stores.
- Command reference and direct pairing tests: 11 passed, 1 existing skip before the final registration test was added.
- Fast set: 856 passed, 1 existing skip, 7277 deselected.
- NOT RUN: fresh DUT capture, BOOM/VexRiscv builds or simulation, full Python suite. Existing capture version 1 does not emit retirement request tags. This increment does not invent those observations.

## Issues

Refs: #134

Roadmap notes: Add provenance-bound request-tag pairing with independent architectural memory effects. Actual project probe integration, decoder selection, translated/big-endian buses, atomic/multi-hart pairing, register effects and full bridge qualification remain open.


## PR 651

[#651](https://github.com/riscPrint/risc-v-workstation/pull/651). Merged: 2026-11-13T03:43:25Z.

Title: feat(formal): bind fifo and arbiter apps from typed structure

Audit evidence label: ran on seeded RTL fixture.

## Summary
Bind FIFO ordering/capacity and arbiter accepted-transfer checks from typed channels and memory structure. Expose internal counters and memory addresses by exact RTL name. Generate counter-wrap observations and connect CAM candidates to memory bounds. Retain pruned public ports in subcomponent interfaces so native interface checks match emitted RTL.

## Testing
45 targeted tests passed. Native arbiter proof and double-accept mutant checks passed. Real StreamFifo database ordering run: 1 generated, 1 proven, 0 bounded passes, 0 failed, 7 unsupported discovery records. Fast set: 852 passed, 1 skipped, 7221 deselected. Heavy core jobs NOT RUN.

## Issues
Refs: #62. Composite payloads, multi-memory FIFOs, CAM key matching and duplicate-entry policy remain unsupported. Counter-wrap rows are observations, not overflow requirements.

Roadmap notes: Standard typed FIFO and arbiter interfaces now bind automatically. Real library FIFO ordering evidence is recorded. CAM memory bounds and internal counter observations remain distinct from semantic policy proofs.


## PR 652

[#652](https://github.com/riscPrint/risc-v-workstation/pull/652). Merged: 2026-11-13T03:43:40Z.

Title: feat(farm): build shared shard plans from c1 manifests

Audit evidence label: unit tests only.

## Summary
Build a shared local/Kubernetes shard plan from a C1 run-many manifest. Copy ELF inputs by hash, retain every expected cell and bind config/seed/options identities. Write per-shard manifests and render the same commands as cluster Jobs. Use main's split farm contract file.

## Testing
- End-to-end local fake-adapter shard test: 1 passed, 0 skipped.
- Shard test plus release hygiene: 41 passed, 0 skipped.
- Final fast set: 856 passed, 1 skipped, 7266 deselected. Main temporarily skips test_command_reference during the parallel push.
- NOT RUN: real cluster/kind, native RTL, full Python suite, CI.

## Issues
Refs: #59

Remaining: tool-image builds, automatic model-cache publication, object storage and gate-generation import. Other adapter stimulus dependencies must be mounted and captured by the project. The PVC must expose the same absolute shared root. No cluster/native parity is claimed.

Roadmap notes: farm plan now generates a C1 identity-bound shard plan consumed by both local and Kubernetes executors.


## PR 653

[#653](https://github.com/riscPrint/risc-v-workstation/pull/653). Merged: 2026-11-13T03:45:08Z.

Title: feat(memory): check complete multibeat tilelink messages

Audit evidence label: unit tests only.

## Summary
Extend the generated TileLink-C monitor to complete multi-beat C/D messages. Assemble line data before permission/data checks, retain fixed headers and bounded partial-message age, and preserve the existing single-beat profile. Validate full-line oracle width and report beats per line.

## Testing
Three targeted Python tests passed. Native Verilator ran single-beat regression cases and a 64-byte-line/64-bit-beat baseline with six seeded defects: early grant, corrupt middle D beat, truncated ProbeAckData, changed D header, corrupt middle C beat and truncated ReleaseData.

The existing real CacheFiber baseline and corrupt-backing-byte negative test also passed in separate bounded native runs. Those tests validate the existing complete-message oracle, not this generated monitor's refinement of CacheFiber.

Fast set: 852 passed, 1 skipped. Main temporarily skips command-reference consistency during the parallel documentation batch.

NOT RUN: generated monitor bound to the real cache/home, production database integration, stalled-payload stability, independent client reset, BOOM builds, full Python suite. Expected data must be correct for the complete message epoch. Other-line and error traffic remain outside the success profile.

## Issues
Refs: #128, #363. Real cache/home binding and model refinement remain open.

Roadmap notes: generated TL-C monitors now cover complete multi-beat data and partial-message progress with seeded native rejection. Scripted monitor evidence and existing real-cache evidence remain separate.


## PR 654

[#654](https://github.com/riscPrint/risc-v-workstation/pull/654). Merged: 2026-11-13T03:44:08Z.

Title: feat(sim): add pinned arcilator c1 and c2 engine probe

Audit evidence label: unit tests only.

## Summary

Add --with-arcilator to the installer. Fetch pinned CIRCT firtool-1.163.0 binaries outside the repository with pinned archive hashes. Support macOS ARM64/x64 and Linux x64. Check the release version. Missing or unsupported native tools fail explicitly.

Add a generic native scalar-port model API for Arcilator and Verilator. Project adapters own signal maps, clocks, memory and completion. Add a bounded real VexRiscv probe that writes existing C1/C2 files. Seeded ready stalls and one-cycle memory responses drive the same captured RTL and ELF on both engines. Require actual retired tohost completion. Keep the build identity separate from complete C4 identity.

## Testing

- Native seeded scalar regression: 2 tests passed. Check reset and 40 seeded register updates against independent arithmetic on both engines.
- Native real-core regression: 1 passed in 18.70 seconds. Both engines passed 17 retired instructions in 81 cycles with seed 7. Complete C2 files were byte-identical, including all fields, cycle numbers and end event.
- RTL SHA-256: 85901d3da9d45c0860bfa29a902d51fede05d2f7a53e85de805168e4f513a555. ELF SHA-256: 5d4e13787e1d6f6dd30ef27ca70fd1f7acd42b861000e88f2abb62da8953866f.
- Private VexRiscv revision a62c145aa042a5de874344e0a7683bd7c8c8c870. Native work used vex-simsrv and nice -n 10.
- CIRCT installer --check passed. Top-level installer --with-arcilator --dry-run and bash syntax check passed.
- Fast set before final fetch/rebase: 852 passed, 1 skipped, 7206 deselected. The command-reference check is deferred by the work brief.
- After rebase: CLI import and targeted refusal test passed.
- NOT RUN: full Python suite, BOOM, repeated speed trials, interrupts, CSR snapshots, waves, native checkpoint support and GitHub CI.
- An initial combined pytest invocation hit the existing collection hook restriction on mixing rvw/tests with example tests. Separate runs passed.

## Issues

Refs: #345. BOOM medium/large and broader engine qualification remain open. Short compile-and-run wall times do not establish a simulator speed change.

Roadmap notes: A pinned native Arcilator toolchain and generic scalar model API now support project C1/C2 adapters. The VexRiscv smoke has complete bit-identical C2 evidence against Verilator under seeded ready stalls. No C4 acceptance or BOOM qualification is claimed.


## PR 655

[#655](https://github.com/riscPrint/risc-v-workstation/pull/655). Merged: 2026-11-13T03:44:16Z.

Title: perf(arch): accelerate mixed integer timing in native scheduler

Audit evidence label: unit tests only.

## Summary

Extend the native OoO scheduler to ordered loads/stores, static branches and jumps, branch recovery, correct-path overlap and class issue limits. Keep unsupported configurations on the Python reference. Reuse the existing installer. ABI 2 requires a library rebuild. ComponentSims remains unchanged.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_ooo_native.py -q`: 4 passed, including 250 seeded parity schedules.
- `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`: 856 passed, 1 skipped, 7240 deselected.
- Short warmed alternating benchmark: results in `Arch/ooo/benchmark-results.json`. Kernel and public Python-call rates are separate. C2 parsing is excluded.
- NOT RUN: gem5 builds, RTL, full Python suite, application workload accuracy checks.

## Issues

The fast path still excludes front-end objects, component services, FP, rename policies and memory disambiguation. This is reference schedule parity, not RTL accuracy.

Roadmap notes: Native scheduler supports mixed fixed-latency committed paths. Component-backed full-loop acceleration remains open.


## PR 656

[#656](https://github.com/riscPrint/risc-v-workstation/pull/656). Merged: 2026-11-13T03:45:05Z.

Title: feat(vip): add optional ethernet packet model adapters

Audit evidence label: unit tests only.

## Summary

Add optional Ethernet MAC client-packet adapters. Check payload bytes, descriptor ownership, DMA bounds/effects, declared loss/error outcomes, completion lengths and interrupts. Include an SV UVM native packet-model extension point and coverage.

Roadmap notes: semantic packet adaptation is available. The project supplies its native model and shared host-memory bridge. No MAC RTL or PHY implementation is claimed.

## Testing

- Ethernet Python tests: 2 passed with mock callbacks.
- Verilator lint with pinned Accellera UVM: passed.
- Required fast tests: 861 passed, 1 skipped, 7282 deselected in 77.89s (0:01:17)
- Not run: native packet models, MAC/DMA RTL, UVM runtime builds, PHY tests, BOOM jobs or full Python suite.

## Issues

Refs: #216. Native model and project qualification remain open.


## PR 657

[#657](https://github.com/riscPrint/risc-v-workstation/pull/657). Merged: 2026-11-13T03:45:43Z.

Title: feat(query): add a FIRRTL and CIRCT front end for Chisel

Audit evidence label: unit tests only.

## Summary

- `rvw query build-hdl --frontend chisel` takes one FIRRTL file (`ChiselStage.emitCHIRRTL`). firtool (`--firtool`, `$RVW_FIRTOOL`, `PATH`) writes split Verilog and HGLDD (`-g --emit-hgldd --disable-all-randomization`, plain location comments). The native reader imports the Verilog with `-DSYNTHESIS`; `opt_dff` folds Chisel's synchronous resets into `$sdff`, so registers get `SYNC` domains and reset values.
- Scala origin and emitted RTL are separate bindings: database locations are rebound from firtool's `// Gen.scala:13:20` comments to Scala files captured under `--source-root` (declarations take the first location of a line, assignments the last). No location points at emitted Verilog. The Verilog stays as artifacts `rtl/*.sv`, with `hdl/source-map.json` (Verilog line -> Scala locations) and firtool's `hgldd/*.dd` (`rvw query export hgldd/Top.dd` for SpinalWaves/Surfer).
- HGLDD names become each signal's second spelling: `rvw query where io.a.valid` finds `io_a_valid`.
- Unresolved extern modules are refused by `hierarchy -check`. firtool errors keep an old database.
- Test oracles (`test_query_hdl._yosys_graph`, `test_query_slang._oracle`) now link memory write ports to read ports; before, they missed every path through a memory.
- MCP `query_build_hdl`: `frontend: chisel`, `source_roots`. Docs: `SpinalDB/README.md`, `docs/contracts/query.md`, query README, design note.

## Testing

- `RVW_FIRTOOL=<Chisel's cached firtool 1.62.0> rvw/.venv/bin/python -m pytest rvw/tests/test_query_chisel.py rvw/tests/test_query_hdl.py rvw/tests/test_query_slang.py rvw/tests/test_query_ghdl.py -q`: 25 passed, 1 skipped (NEORV32 needs `RVW_GHDL_PLUGIN`). The Chisel fixture (`rvw/tests/data/chisel/Gen.scala`, `Top.fir`) was emitted by Chisel 6.5.0: two `Acc` instances, a `Mem`, a `Valid` bundle and a `Vec` port. Paths are compared with an independent Yosys traversal of the emitted Verilog.
- Fast set (command-reference tests deselected per the brief): 852 passed, 1 skipped.
- Not run: full Python suite, CI, a second real Chisel design (only the fixture).

## Issues

Refs: #372. Remaining: a second real Chisel design (for example a rocket-chip block), configuration identity of the Chisel generator, extern-module model declarations, statement-level precision where firtool fuses locations.

Roadmap notes: Design database front ends: Chisel designs now build from FIRRTL through firtool (`build-hdl --frontend chisel`); locations point at Scala lines, Chisel names resolve, and the emitted Verilog and HGLDD are stored in the database.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 658

[#658](https://github.com/riscPrint/risc-v-workstation/pull/658). Merged: 2026-11-13T03:47:01Z.

Title: feat(farm): link cost reports to c4 verdict evidence

Audit evidence label: unit tests only.

## Summary
Join attempt charges to schema-checked original C4 reports with paths and SHA-256 links. Attribute each attempt once. Keep missing, invalid and multiple verdict reports explicit, and retain execution state beside recorded verdicts. Skip permanently exhausted owners without blocking other work. Keep jobs queued when only active reservations consume the remaining budget. Retain creation order across queue updates.

## Testing
- All new regression-management/platform feature tests: 39 passed, 0 skipped.
- Cost/queue subset: 13 passed, 0 skipped.
- Final fast set: 865 passed, 1 skipped, 7290 deselected. Main temporarily skips test_command_reference during the parallel push.
- NOT RUN: native RTL, actual cluster accounting, full Python suite, CI.

## Issues
Refs: #57

Remaining: measured aggregate CPU/RSS/disk quotas and Kubernetes cumulative admission. CPU charges remain declared cores times elapsed wall time. Categories are caller-declared. Recorded C4 grouping does not establish acceptance or waive a budget/cleanup fault.

Roadmap notes: queue cost reports now link C4 evidence and retain unmatched/ambiguous costs. Exhausted agents cannot block another owner's admissible jobs.


## PR 659

[#659](https://github.com/riscPrint/risc-v-workstation/pull/659). Merged: 2026-11-13T03:47:21Z.

Title: feat(arch): attribute timing slots to code regions and diff runs

Audit evidence label: unit tests only.

## Summary

Add `rvw arch ooo-profile` and `ooo-diff`, plus cancellable MCP tools. Split commit slots into retiring, front-end, bad speculation, back-end memory and back-end core. Join sized executable ELF symbols or explicit PC ranges. Compare the same trace under two configurations, per run and region. Use the Python reference when profiling, including shared component services.

## Testing

- Targeted region, native and component tests: 12 passed.
- Fast set: 869 passed, 1 skipped, 7291 deselected. Shared temporary-directory cleanup emitted 16 warnings.
- NOT RUN: full Python suite, gem5, RTL, hardware top-down correlation.

## Issues

Slots are model predicates. The oldest unfinished ROB entry and its unfinished dependencies define the memory/core split. Regions are attribution locations, not independent causal bottleneck measurements. Inlined and zero-sized ELF symbols remain unsupported. No relocation is inferred.

Roadmap notes: Region profiling, ELF joins and configuration slot diffs are available. Hardware counter predicate correlation remains open.


## PR 660

[#660](https://github.com/riscPrint/risc-v-workstation/pull/660). Merged: 2026-11-13T03:47:26Z.

Title: test(cosim): verify native vexriscv isa traces with spike

Audit evidence label: ran on real core RTL.

## Summary
Verify the private RV32IM VexRiscv configuration against Spike with the declared platform settings. All 49 complete aligned ISA traces match: 41 RV32UI and 8 RV32UM tests, 17,735 instructions. Each trace synchronizes unspecified initial mscratch once. No new masks or policy exceptions were added.

Allow the normal launcher to select RVW_VEX_LOCK. Add a manifest comparison script which preserves C5 reports and fails on incomplete evidence. Record real counts and settings in the example README.

## Testing
- Private core a62c145aa042a5de874344e0a7683bd7c8c8c870, vex-cosim lock, native outputs under the worker worktree: 49/49 native ISA passes and Spike matches.
- Native mscratch retirement timing: 1 passed in 90.42 seconds.
- Targeted summary tests: 6 passed.
- Fast set: 862 passed, 1 skipped, 7263 deselected. Command-reference check remains deferred by the push brief.
- NOT RUN: BOOM, full Python suite, online DPI lockstep, interrupt synchronization, Sail, second core, RVVI round trip, debug endpoint.

## Issues
No issue is closed by this subset.

Roadmap notes: Native VexRiscv aligned RV32UI/UM comparison is now measured. Other configurations and the remaining integration tasks still need native evidence.


## PR 661

[#661](https://github.com/riscPrint/risc-v-workstation/pull/661). Merged: 2026-11-13T03:48:37Z.

Title: feat(integration): add VexiiRiscv as a third test core

Audit evidence label: unit tests only.

## Summary

Adds VexiiRiscv as a third test core (`examples/vexiiriscv/`), in the form of `examples/vexriscv/`:

- `rvw.toml` with a regression config (`isa`, `smoke`, `quick`, `full`), complete adapter input declarations and a gate source variable `VEXIIRISCV`.
- C1 run adapter (`rvw/run.sh`, `rvwvexii.VexiiAdapter`) for `ParamSimple` RV32IM, machine mode only, cacheless native buses.
- C2 trace: VexiiRiscv has no RVFI port. `C2Backend` turns the upstream `VexiiRiscvProbe` events (committed register writes, loads, stores, commits, traps) into C2 records and trap events. `TrapTapPlugin` exposes the trap state machine's xepc/xtval registers (read only).
- Spike platform JSON, SpinalDB query entry, Konata through the upstream Konata backend.
- Pinned VexiiRiscv `9f70315d`, fetched outside the repository. The build compiles the core's pinned SpinalHDL source (`ext/SpinalHDL` `de72faf6`), because SpinalHDL 1.15.0 cannot compile VexiiRiscv (missing SWD transport; `SimBitVectorPimper.toBigInt` returns `Any`).

### Generic code that assumed BOOM or VexRiscv (fixed, with a test each)

1. `rvw/src/rvw/regress/source.py`: revision checkouts for gates did not include git submodules, so a core that pins a library as a submodule (VexiiRiscv pins SpinalHDL) could not build at its base or candidate revision. Each submodule that the core repo has initialized is now cloned with `--shared` at the recorded commit; nothing is fetched; a missing commit is an error. Test: `rvw/tests/test_regress_submodule_checkout.py` (3 tests, added to the fast set).

No other generic change was necessary for run, regress, gate, cosim, query or perf.

## Testing

Native runs on macOS arm64 (Verilator 5.049, JDK 21), against a VexiiRiscv clone outside the repo:

- `rvw regress run --suite isa --rvfi-trace`: 49 pass, 0 fail, 0 skip. `--suite smoke`: 2 pass.
- `rvw cosim check` (Spike): 49/49 ISA traces and 2/2 smoke traces match.
- Seeded latency (seeds 3, 7) on `lw`, `sb`, `div`: 6 pass, 6 match.
- Negative control: XOR changed to OR in `IntAluPlugin` (separate worktree). `rvw regress run` on `xor`, `xori`, `add`: 1 pass, 2 fail; cosim mismatch at the first `xor` and `xori` (`rd_wdata`).
- `rvw regress gate --tier quick --base-rev 9f70315d --cand-rev HEAD` with a clean tools tree at the pre-rebase commit: `accept`, 4 compared. (An earlier run that I disturbed by committing in the tools tree mid-run was correctly `inconclusive`.)
- `rvw query build --config rv32im`: 2006 signals, 224 registers; `where`, `drivers`, `search`, `hierarchy`, `path` checked.
- `--konata` run and `rvw perf` on the log.
- After the rebase onto main: the adapter and database builds compile against the rebased tree (`sbt root/compile db/compile`). The rebased native run timed out waiting for the shared `vex` lock, so the counts above are from the pre-rebase tree.
- `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`: 821 passed. `examples/vexiiriscv/rvw/tests/test_vexii_project.py`: 3 passed.

Not run: `examples/vexiiriscv/rvw/tests/test_adapter.py` (native; written, not run), the full Python suite, CI.

## Issues

Refs: #377 (remaining: report core bugs upstream after owner approval, if any are found; ROADMAP generality row).

Cosim note for the cosim worker: none for this core; all traces match with the default policies plus `aligned_mem: false`.

Roadmap notes: Integration: VexiiRiscv is the third test core. 49/49 RV32IM ISA tests pass and match Spike; gate accepts; query works. The C2 trace comes from the upstream commit probe, not RVFI. Gate checkouts now include initialized submodules.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 662

[#662](https://github.com/riscPrint/risc-v-workstation/pull/662). Merged: 2026-11-13T03:48:55Z.

Title: feat(vip): add real-number boundary stub contracts

Audit evidence label: unit tests only.

## Summary

Add a real-number boundary stub contract only. Require explicit backend/version, real-handle support, channel names/units and known/valid flags. Check finite samples and monotonic femtosecond time. Always return inconclusive model-not-bound results. Include an SV real interface, UVM contract and inert fixture.

Roadmap notes: the RNM stub interface is available. No analog behavior or native backend qualification is implemented.

## Testing

- RNM stub Python tests: 2 passed.
- Verilator lint with pinned Accellera UVM: passed.
- Required fast tests: 865 passed, 1 skipped, 7301 deselected in 114.57s (0:01:54)
- Not run: native RNM runtime, behavioral analog models, transistor simulation, UVM runtime builds, BOOM jobs or full Python suite.

## Issues

Refs: #217. Native model integration remains open.


## PR 663

[#663](https://github.com/riscPrint/risc-v-workstation/pull/663). Merged: 2026-11-13T03:50:05Z.

Title: test(sim): run whole vexriscv rtl with x reset in icarus

Audit evidence label: ran on real core RTL.

## Summary

Run the whole captured VexRiscv Verilog with native Icarus. Apply X on reset for two falling edges, then five edges of known asserted reset. Run the smoke ELF from RAM to a retired passing tohost store. Change reset away from clock edges to avoid a testbench race. Record native tool version, input hashes, bounds, return code and X observations.

Check unknown validity and active retirement fields. Count unknown inactive memory read/write data separately. Inject X into rvfi_rd_wdata in a second whole-core run and require rejection.

## Testing

- Native Icarus 14.0 devel s20251012-154-g50ca27fdf: 2 tests passed, including the injected-X rejection. Repeated after rebase: 2 passed.
- Baseline whole-core run: 17 retirements, 60 cycles, 2 reset X windows, 0 checked active unknowns, 16 inactive memory-data unknown observations. Retired tohost value was 1. Native execution used vex-simsrv and nice -n 10.
- RTL SHA-256 85901d3da9d45c0860bfa29a902d51fede05d2f7a53e85de805168e4f513a555. Private VexRiscv revision a62c145aa042a5de874344e0a7683bd7c8c8c870.
- Fast set before final fetch/rebase: 865 passed, 1 skipped, 7287 deselected. The command-reference check is deferred by the work brief.
- NOT RUN: full Python suite, BOOM, gate-level timing, binary concretization analysis, pessimistic xprop or GitHub CI.

## Issues

Refs: #295. Icarus preserves four-state values but procedural if can be X-optimistic. Inactive unknowns are unselected values and do not establish X-pessimism. This bounded reset-recovery run does not prove absence of X bugs or provide a production four-state C1 engine.

Roadmap notes: Whole VexRiscv RTL now has an Icarus X-at-reset probe, active/inactive unknown counts and an injected-active-X rejection test. Pessimistic X propagation and broader whole-core qualification remain open.


## PR 664

[#664](https://github.com/riscPrint/risc-v-workstation/pull/664). Merged: 2026-11-13T03:50:38Z.

Title: feat(arch): add oracle store-data renaming bound

Audit evidence label: unit tests only.

## Summary

Add optional `memory_rename.mode=oracle_store_data`. Alias a full-width LD consumer to the data producer of the youngest exactly overlapping SD. Keep normal load issue, translation, memory service and ordered commit. Stop at partial overlaps and control barriers. Do not allocate a new physical register for the aliased destination. Keep this oracle experiment distinct from forwarding and dependence prediction.

## Testing

- Targeted memory rename, regions, native and dependence tests: 16 passed.
- Fast set: 879 passed, 1 skipped, 7306 deselected.
- Dependent chains, nonaliases, partial overlaps, data widths and rename widths eight and ten are covered.
- NOT RUN: native gem5, RTL, compiler builds, full Python suite, fault recovery and failed alias prediction recovery.

## Issues

Refs: #362

This uses correct traced addresses at rename. It has no learned alias prediction or recovery. Speculative dependence replay is refused. It is not a complete implementation of issue #362. See the source paper and limits in the README. No upstream gem5 patch is needed for this own-model-only feature.

Roadmap notes: An oracle store-data rename opportunity experiment is available. Native predictor, alias recovery and fault evidence remain open.


## PR 665

[#665](https://github.com/riscPrint/risc-v-workstation/pull/665). Merged: 2026-11-13T03:52:26Z.

Title: feat(install): share tool inventory and install profiles

Audit evidence label: unit tests only.

## Summary

Add one packaged inventory for optional native and Python tools, source lookup records, environment variables, pins and OS recipes. Installer profiles and doctor reports read it. Preserve the legacy --all scope. Profile all excludes Sail and the IDE. Manual-only recipes fail explicitly rather than claim installation.

## Testing

Targeted inventory, doctor and installer tests. Fast suite run before rebase. Linux and clean-host installation NOT RUN. No native tool downloads or heavy jobs. Tool presence is not runtime qualification.

## Issues

Installation inventory increment. Linux recipes and native qualification remain untested. Some source builds still require manual upstream setup.

Roadmap notes: shared optional tool inventory and profiles added; complete native installation qualification remains open.


### Recorded validation

Targeted tests: 77 passed. Pre-rebase fast command `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`: 868 passed, 1 skipped. The command-reference skip was inherited from main. Full Python suite and new native qualification NOT RUN.


## PR 666

[#666](https://github.com/riscPrint/risc-v-workstation/pull/666). Merged: 2026-11-13T03:53:07Z.

Title: feat(init): scaffold SystemVerilog, VHDL and Chisel core projects

Audit evidence label: unit tests only.

## Summary

- `rvw init --hdl sv|vhdl|chisel --top TOP --isa ISA` scaffolds a non-Spinal core project. Options: `--source` (ordered; default: discovered outside `tb`/`test`/`dv`/`sim`/... with packages first), `-I` (SV), `--library` (VHDL), `--fir` and `--source-root` (Chisel). `--top` must be declared in the sources; candidates are reported.
- Files: `rvw.toml` with `[query] build = ["./rvw/build-db.sh"]` and `db = "rvw/out/design.db"`; `rvw/build-db.sh` (explicit `rvw query build-hdl --frontend slang|ghdl|chisel ...`; `$RVW` selects the executable); `rvw/run.sh` C1 launcher (`info` works, `build` compiles with Verilator plus `rvw/sim/harness.cpp`, through GHDL+Yosys for VHDL and firtool for Chisel, `run` exits 2 until mapped); `rvw/sim/harness.cpp` skeleton (compiles for any top, exits 2); `rvw/.gitignore`; `rvw/README.md` playbook.
- After `rvw query build --config default`, every `rvw query` and `rvw lint` command works on the core. No run, pass or setup verdict is claimed by the scaffold.
- Docs: `rvw/src/rvw/init/README.md` section, one paragraph in `docs/BRING_YOUR_OWN_CORE.md`.

## Testing

- `rvw/.venv/bin/python -m pytest rvw/tests/test_init_hdl.py rvw/tests/test_init.py -q`: 25 passed. `test_init_hdl.py` builds each language end to end through `rvw query build`: SV (slang, includes, package; then `run.sh build` with Verilator 5 and the harness, about 12 s), Chisel (fixture FIRRTL, Scala line mapping), VHDL (GHDL, package first).
- Manual: the same flow on a scratch SV project.
- Fast set (command-reference tests deselected per the brief): 865 passed, 1 skipped.
- Not run: full Python suite, CI, `run.sh build` for VHDL and Chisel scaffolds, a scaffold on Ibex or NEORV32 checkouts.

## Issues

Refs: #55, #26. Remaining: the bus/ELF/completion mapping of the Verilator harness (core-specific; the scaffold refuses `run`), RVFI for non-Spinal cores, generated checks and source-level debug under #26.

Roadmap notes: Non-Spinal cores: `rvw init --hdl sv|vhdl|chisel` scaffolds a project whose design database build works at once (slang, GHDL or firtool) and a Verilator C1 launcher scaffold whose build compiles the design; C1 runs still need the core's bus and completion mapping.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 667

[#667](https://github.com/riscPrint/risc-v-workstation/pull/667). Merged: 2026-11-13T03:53:04Z.

Title: docs(rvw): regenerate the command reference

Audit evidence label: no code.

## Summary
Regenerate `docs/COMMAND_REFERENCE.md` from the current parsers and MCP declarations (sheriff batch).

## Testing
- `scripts/command-reference.py`; fast set on main 12892b19: 878 passed, 1 skipped.

## Issues
None.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 668

[#668](https://github.com/riscPrint/risc-v-workstation/pull/668). Merged: 2026-11-13T03:53:54Z.

Title: fix(uvm): qualify live vexriscv isa programs

Audit evidence label: ran on real core RTL.

## Summary
Fix the live M-only VexRiscv binding and isolate each program's Spike capture. Run six RV32UI programs through the live pyuvm environment. Record actual retirement counts, cycles, trap checks and corruption results in the README.

## Testing
- Native opt-in `test_uvm_vex_live.py`: 2 passed, 0 skipped. Six programs completed and six PC-corruption runs failed as required.
- Private VexRiscv copy at a62c145aa042a5de874344e0a7683bd7c8c8c870, private vex-uvm lock, Verilator 5.049, rebuilt matched Spike ABI 6 shim.
- Fast set: 865 passed, 1 skipped, 7294 deselected.
- NOT RUN: full ISA suite, BOOM, architectural interrupt/debug, C4 acceptance.

## Issues
Refs: #296

Roadmap notes: The live VexRiscv pyuvm environment now has native add, beq, lw, sw, jal and xor results with independent Spike and separate trap synchronization. Full ISA, IRQ/debug and C4 remain open.


## PR 669

[#669](https://github.com/riscPrint/risc-v-workstation/pull/669). Merged: 2026-11-13T03:53:58Z.

Title: feat(arch): add approximate reference core descriptions

Audit evidence label: unit tests only.

## Summary

Add five approximate shared project descriptions: Zen-5-like, M1-like, BOOM large and mega, and a serial VexRiscv-class baseline. Document public source anchors and all remaining assumptions. These are RISC-V exploration starting points, not commercial-core performance models. Keep commercial and core-specific data outside generic code.

## Testing

- Reference description validation and tiny own-model schedules: 5 passed.
- Fast set: 887 passed, 1 skipped, 7321 deselected.
- NOT RUN: gem5, RTL, hardware calibration or commercial ISA execution.

## Issues

The M1 retirement structures are not reproduced. The VexRiscv-class description is a serial baseline, not a pipelined VexRiscv model. Other queue, timing, predictor and cache fields are explicitly assumed. No accuracy claim is made.

Roadmap notes: Approximate reference starting descriptions are available with source and assumption notes. Project-specific extraction and calibration remain required.


## PR 670

[#670](https://github.com/riscPrint/risc-v-workstation/pull/670). Merged: 2026-11-13T03:54:27Z.

Title: feat(formal): lower typed local captures for finite properties

Audit evidence label: ran on seeded RTL fixture.

## Summary
Lower typed captures in named finite SVA properties. Keep overlapping attempts independent through sampled history. Preserve declared widths and signedness and record local-variable metadata. Refuse unsupported variable-flow forms. Keep a separator after generated monitors so an adjacent endmodule token remains legal. Update the support table and the split formal contract file.

## Testing
- Capture and checker-binding tests: 26 passed.
- Final capture/formal/simulation tests: 24 passed, including overlapping requests, signed captures, adjacent endmodule, Icarus and Verilator. These sets overlap.
- Support-table checks: 4 passed, 26 deselected.
- Corrected fast set: 865 passed, 1 main-branch inventory skip, 7316 deselected. Explicit command-reference check passed.
- NOT RUN: full Python suite, BOOM, long formal jobs, general variable-flow or full scheduling qualification, GitHub CI wait.

## Issues
Refs: #61

This subset requires independent captures in one Boolean antecedent followed by one finite implication. Reassignment, local-dependent captures, initializers, flow-sensitive antecedents, slices, sampled uses and additional local types remain unsupported.

Roadmap notes: add typed finite named-property captures with independent overlapping attempts. Keep full local-variable flow and full SVA partial.


## PR 671

[#671](https://github.com/riscPrint/risc-v-workstation/pull/671). Merged: 2026-11-13T03:55:12Z.

Title: feat(csr): fill the 26 pinned aia catalog layout gaps

Audit evidence label: unit tests only.

## Summary
Fill the 26 recorded AIA CSR field-layout gaps from pinned riscv-aia revision 9507866427961d4ec2d2400ea875103b2a09520b. Preserve the existing 416-register UDB data. The combined catalog has 442 registers and 1,974 fields.

Add a reproducible importer, source hashes, alias facts, attribution and the CC-BY-4.0 license. Keep the original gap rows as resolved field definitions. Refuse simple CSR selections that need an interrupt environment instead of treating claims or conditional state as ordinary writes.

## Testing
- CSR catalog and generation tests: 32 passed, no skips.
- Post-rebase fast set: 865 passed, 1 skipped, 7310 deselected. The skip is the coordinator's command-reference batch check.
- Importer ran against the pinned external source checkout.
- NOT RUN: AIA RTL campaign, conditional alias execution, interrupt-controller behavior, full Python suite, BOOM builds.

## Issues
Refs: #85

Roadmap notes: Close the recorded 26 field-layout gaps. Keep AIA behavioral environments, conditional aliases and full privilege/compliance qualification separate. No issue is closed by catalog coverage alone.


## PR 672

[#672](https://github.com/riscPrint/risc-v-workstation/pull/672). Merged: 2026-11-13T03:55:23Z.

Title: build(install): lock extras and generate tool version table

Audit evidence label: unit tests only.

## Summary

Refresh the existing Python lock for cocotb, pyuvm and wellen extras. Generate the observed version and source pin table from the shared inventory. Keep historical macOS probes distinct from clean-host qualification.

## Testing

uv lock and uv lock --check passed. Generated table check and targeted installer tests run. Fast suite run before final rebase. Linux, clean-host installs, native builds and full Python suite NOT RUN.

## Issues

Refs: #40. Complete clean-host pinned combinations remain unqualified.

Roadmap notes: Python extras are locked and the tool version table is generated from the inventory. Full install reproducibility qualification remains open.


### Recorded validation

Targeted tests: 54 passed. Pre-rebase fast command `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`: 886 passed, 1 skipped. The command-reference skip was inherited from main. Full Python suite and new native qualification NOT RUN.


## PR 673

[#673](https://github.com/riscPrint/risc-v-workstation/pull/673). Merged: 2026-11-13T03:56:19Z.

Title: feat(sim): bridge verilator systemc rtl to tlm memory

Audit evidence label: unit tests only.

## Summary

Add a generic blocking TLM-2 memory target with byte enables, range checks, annotated delay and explicit refusal of unsupported streaming bursts. Add a tiny RTL requester built with Verilator --sc and a SystemC initiator bridge. The requester writes a word, reads it back and checks the value in RTL.

Define timing and ordering: one initiator, one outstanding transfer, falling-edge request sampling, 2 ns annotated latency consumed before response, 10 ns clock. The target updates bytes at call time and never waits. It is loosely timed, not a standalone cycle-accurate device model. No DMI, atomics, nonblocking transport, plugin binding or whole-core claim.

## Testing

- Actual Verilator --sc --exe --build against SystemC 3.0.2: 1 native test passed in 18.90 seconds on macOS ARM64 with Verilator 5.049. Build used two jobs and nice -n 10.
- RTL completion, one write, one read, returned value and stored bytes checked. Direct target checks cover repeated byte masks, exact 2 ns delay annotation, out-of-range and unsupported-burst errors.
- The first dependency discovery skipped because the Homebrew SystemC package has no pkg-config file. The test supports explicit SYSTEMC_HOME; the native rerun passed with that prefix.
- Fast set before final fetch/rebase: 878 passed, 1 skipped, 7320 deselected. Command-reference check deferred by the work brief.
- CLI import passed after rebase.
- NOT RUN: full Python suite, BOOM, multi-initiator operation, temporal decoupling, interrupts, whole-core SystemC, checkpoint restore and GitHub CI.

## Issues

Refs: #187. This supplies a native RTL partition and memory-target example. General virtual-platform and whole-core integration remain open.

Roadmap notes: The simulation library now has a blocking TLM-2 target and a native Verilator --sc example with explicit synchronization rules. Loosely timed target behavior is distinct from the example's clocked RTL request/response bridge.


## PR 674

[#674](https://github.com/riscPrint/risc-v-workstation/pull/674). Merged: 2026-11-13T03:57:06Z.

Title: feat(uvm): check a connected spinal soc natively

Audit evidence label: ran on seeded RTL fixture.

## Summary
Add a connected Spinal SoC with APB3 and AXI4-Lite registers plus a UART transmitter. Drive seeded live bus traffic through map-derived RAL and check both bus monitors and UART frames. Add an explicit bus-master composition profile that reports zero CPU checks.

## Testing
- SpinalHDL 1.15.0 elaboration under the sbt lock: passed.
- Native Verilator 5.049 connected test: 2 passed, 0 skipped, seeds 1 and 7. Each checked 9 APB transfers, 9 AXI-Lite transfers and 4 UART frames.
- Composition unit tests: 4 passed.
- Fast set: 890 passed, 1 skipped, 7326 deselected.
- NOT RUN: CPU boot, BOOM, reset during traffic, injected RTL bus errors, C4 acceptance.

## Issues
Refs: #296

Roadmap notes: A connected Spinal bus-master SoC now has native APB, AXI-Lite, map-derived RAL and UART evidence. The default CPU profile still requires CPU comparisons. No CPU execution is claimed for the bus-master profile.


## PR 675

[#675](https://github.com/riscPrint/risc-v-workstation/pull/675). Merged: 2026-11-13T03:57:09Z.

Title: feat(arch): rank local model parameter sensitivity

Audit evidence label: unit tests only.

## Summary

Add `rvw arch ooo-sensitivity` and its cancellable MCP tool. Perturb each selected positive numeric parameter up and down. Rank local IPC elasticity across a trace workload set. Preserve per-trace timing and explicit invalid candidates. Auto-discover numeric fields when paths are omitted.

## Testing

- Targeted tests: 2 passed. A dependent stream ranks ALU latency above ROB capacity. Invalid candidates remain explicit.
- Fast set: 894 passed, 1 skipped, 7331 deselected.
- NOT RUN: full Python suite, gem5, RTL, parameter interaction search or hardware validation.

## Issues

This reports local finite differences. It does not prove that one structure limits physical IPC. Lists, booleans and disabled zero-valued settings are excluded.

Roadmap notes: One-command local parameter sensitivity is available for workload sets.


## PR 676

[#676](https://github.com/riscPrint/risc-v-workstation/pull/676). Merged: 2026-11-13T04:07:46Z.

Title: feat(sim): bind logical progress checks to tilelink messages

Audit evidence label: ran on seeded RTL fixture.

## Summary
Bind logical-request progress checks to complete accepted TileLink A/B/C/D/E messages. Preserve A deadlines through GrantAck, track probes and releases separately, and start release age at the first C beat. Order same-cycle callbacks and identity reuse explicitly. Attach the observer to the existing real CacheFiber smoke and measure B/D environment readiness separately.

## Testing
Nine targeted Scala tests passed, no skips or cancellations: seven observer tests plus the real-cache baseline and corrupt-backing-byte negative test. The native cache observed 7 A requests, 4 grants, 4 GrantAcks, 2 probes, 2 probe acknowledgments and 2 releases/ReleaseAcks. The maximum observed B/D ready gap was 74 cycles against a 256-cycle environment bound. Logical completion used 2048 cycles.

Fast set: 885 passed, 1 skipped. Main temporarily skips command-reference consistency during the parallel documentation batch.

NOT RUN: unbounded liveness, full resource-exhaustion RTL, reset during transactions, generated RTL monitor refinement on the real cache, BOOM builds, full Python suite. A age begins at a complete accepted message. Presentation and partial A data need separate checks. Native corrupt-data rejection remains the independent byte observer's evidence.

## Issues
Refs: #128, #363. Broader resource campaigns and formal RTL refinement remain open.

Roadmap notes: real typed TL-C cache traffic now feeds persistent logical-request deadlines, with environment readiness sampled separately. Model, bounded runtime and unbounded proof claims remain separate.


## PR 677

[#677](https://github.com/riscPrint/risc-v-workstation/pull/677). Merged: 2026-11-13T03:57:58Z.

Title: feat(formal): expand profile clauses and export pinned catalogs

Audit evidence label: unit tests only.

## Summary

Expand profile imports to mandatory base/endian/ECALL clauses, nested Sha constituents, the RVB23 hypervisor pointer-mask condition and attached scope notes. Require explicit implementation declarations for standalone clauses. Preserve implementation, mapped proof and missing evidence as separate states. Accept canonical H in ISA declarations.

Export hash-bound catalogs and a source-span index. Add the pinned 273-row RVA23/RVB23 source index: 49 U64 and 82 S64 rows for RVA23, 54 U64 and 88 S64 rows for RVB23. These include inherited requirements. Checker/test mappings remain unassigned and must be reviewed before catalog adoption. Full ISA/debug/platform catalogs and complete semantic qualification remain open.

Select the conclusive generated VexRiscv forward-PC retry at cycles [5,15] with BTORMC. It passed in 15.8 seconds; retirement cover passed in 11.2 seconds. RTL, wrapper and checker hashes equal the initial campaign. Selected outcomes across attempts are now 43 bounded PASS and one liveness assertion FAIL. Record both earlier forward-PC timeouts and keep C4 reject. The selected rows use different explicit bounds and do not establish an unbounded proof.

## Testing

- Profile, pinned source materialization, ISA consumers and specification diff: 37 passed, no skips.
- Generated VexRiscv plan regression: 1 passed.
- Fast set: 878 passed, 1 existing skip, 7324 deselected.
- Pinned profile run verified all 273 index spans against two exact source hashes.
- Native forward-PC BTORMC and retirement cover: bounded PASS with 90 seconds per check. Earlier BTORMC depth-30 and ABC depth-20 attempts timed out at 110 seconds each.
- NOT RUN: BOOM, full Python suite, full profile/ISA proof, compiler qualification. No source pin or reference model is adopted automatically.

## Issues

Refs: #63, #80, #104, #141

Roadmap notes: Expand profile clause and source-catalog tracking and retain missing checker mappings. The generated VexRiscv instruction/consistency selection has conclusive bounded outcomes across recorded attempts, including an earned liveness failure. Full profile semantics, adapter conformance and non-profile specification catalogs remain open.


## PR 678

[#678](https://github.com/riscPrint/risc-v-workstation/pull/678). Merged: 2026-11-13T03:58:18Z.

Title: feat(install): fetch verified native archives outside repo

Audit evidence label: unit tests only.

## Summary

Declare pinned per-host native archive entries. Verify CIRCT and Sail hashes against upstream release metadata. Keep other tools explicitly unverified with null URLs/hashes. Add a checksum-first fetcher with an external prefix, dry-run and receipt check. Retain the existing private Actions bundle path.

## Testing

Four fixture tests cover manifest entries, dry-run, checksum refusal, external prefixes and archive traversal. Fast suite run before final rebase. No large downloads, native execution, Linux tests, complete offline install or full Python suite.

## Issues

Refs: #71. Runtime dependency packaging, redistribution review and native relocation qualification remain open.

Roadmap notes: upstream native archive manifest and external-prefix fetch path added; only metadata hashes are verified, not runtime support.


### Recorded validation

Targeted tests: 4 passed. Pre-rebase fast command `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`: 895 passed, 1 skipped. The command-reference skip was inherited from main. Full Python suite and new native qualification NOT RUN.


## PR 679

[#679](https://github.com/riscPrint/risc-v-workstation/pull/679). Merged: 2026-11-13T03:58:34Z.

Title: test(rvw): check every cli parser and mcp package in the fast set

Audit evidence label: unit tests only.

## Summary
New fast module `rvw/tests/test_cli_tree.py` (opts in with `pytestmark`):
- every one of the ~320 CLI parsers formats its help, and no command path repeats;
- `Registry.discover()` reports no problems. A broken `mcp_tools.py` (twice today from keep-both rebases of `formal/mcp_tools.py`) made the server skip a whole package with only a stderr line.

## Testing
- `pytest rvw/tests/test_cli_tree.py -m fast`: 2 passed.

## Issues
None. Sheriff maintenance of `main`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 680

[#680](https://github.com/riscPrint/risc-v-workstation/pull/680). Merged: 2026-11-13T03:58:59Z.

Title: fix(farm): require cluster completion evidence during collection

Audit evidence label: unit tests only.

## Summary
Require the exact planned Kubernetes Job IDs and successful Complete conditions during cluster collection. Empty expected-cell plans are refused. Missing/failed Jobs or query errors keep collection inconclusive while retaining C1/C3 artifacts. Route long farm and evidence-index MCP calls through owned workers so stdio cancellation and budgets apply. Retain full recorded commit ranges in triage and handle unknown optional identity fields without inventing flakiness.

## Testing
- All new regression-management/platform feature tests: 45 passed, 0 skipped.
- Final fast set after rebase: 890 passed, 1 skipped, 7346 deselected. Main temporarily skips test_command_reference during the parallel push.
- Remote SSE payload/auth/ownership/budget subset: 5 passed, 0 skipped.
- Offline Job validation passed against Kubernetes v1.34.0 OpenAPI at commit f28b4c9efbca5c5c0af716d9f2d5702667ee8a45. Schema SHA-256: d3b0cdc2fda15c753206d25ab459dc7c12df64e2fd652b6809687471ea751c37. Source: https://github.com/kubernetes/kubernetes/blob/f28b4c9efbca5c5c0af716d9f2d5702667ee8a45/api/openapi-spec/swagger.json
- NOT RUN: real cluster/kind, PVC binding, native RTL, full Python suite, CI.

## Issues
Refs: #59, #25, #54

Remaining limits are recorded in the farm/MCP READMEs. Collection completeness is not a DUT pass or gate accept. Schema validation is not cluster execution. Unknown/short revisions do not create commit ranges.

Roadmap notes: cluster collection now checks execution state; stdio farm/evidence long jobs use the shared owned-worker cancellation/budget path. Triage links full recorded commit ranges without weakening C3 identity checks.


## PR 681

[#681](https://github.com/riscPrint/risc-v-workstation/pull/681). Merged: 2026-11-13T03:59:29Z.

Title: feat(arch): export compiler models from shared descriptions

Audit evidence label: unit tests only.

## Summary

Add `compiler-export` and `compiler-check` commands and cancellable MCP tools. Project the shared O3 description into partial LLVM TableGen, GCC reservation and issue-rate fragments. Parse the generated files back and reject numeric, mapping or reservation drift. Keep omitted opcode classes and assumed unit occupancy explicit.

## Testing

- Targeted export/check test: 1 passed, including detection of a changed latency.
- Fast set: 897 passed, 1 skipped, 7358 deselected.
- NOT RUN: compiler builds, TableGen, GCC DFA, llvm-mca, gem5, RTL or full Python suite.

## Issues

Refs: #367

This implements generated files and the restricted round-trip checker. Native compiler registration/builds and scheduling accuracy remain open under #367. Shared execution-port topology is not projected. No native compiler integration is claimed.

Roadmap notes: Shared project compiler fragments and a parse-back checker are available. Native compiler integration remains open.


## PR 682

[#682](https://github.com/riscPrint/risc-v-workstation/pull/682). Merged: 2026-11-13T04:00:36Z.

Title: feat(formal): add scalar aes sm4 and split hash models

Audit evidence label: ran on seeded RTL fixture.

## Summary

Add AES32/AES64, SM4 and RV32 split SHA-512 C references. Include fixed legal byte selectors and AES key-round immediates. Use arithmetic AES substitution and the standard SM4 table. These are functional unit references, not instruction decoders or timing proofs.

Extend project bindings with explicit constant input ports and unconnected symbolic reference operands for unary units. Keep other ports and driver checks. Retain the full reference input domain. Put the format change in the new area contract file and preserve the platform index.

## Testing

Targeted scalar cipher and existing bounded-datapath tests: 20 passed. Include AES32/64 encryption/decryption known vectors, 20 independent OpenSSL comparisons, SM4 encryption/decryption/key schedule, RV64 sign extension, split SHA-512 reconstruction and compilation of all new wrappers. A symbolic 64-bit AES inverse-MixColumns unit proves. A wrong opcode and a reference that depends on a missing hardware operand produce counterexamples.

The first binding regression run exposed an unnecessary metadata requirement in the no-constant path. The conditional rewrite fixes it. The final combined run passes.

Required fast set after rebase: 885 passed, 1 skipped, 7338 deselected. The skip is the upstream temporary command-reference batch rule.

NOT RUN: BOOM builds, full Python suite, long formal jobs, full AES/SM4 RTL qualification or physical side-channel checks.

## Issues

Refs: #19.

Roadmap notes: Add scalar cipher and RV32 split hash references, constant control bindings and unary argument adaptation. Project crypto RTL qualification, full decoder behavior and timing guarantees remain open. Keep the epic open.


## PR 683

[#683](https://github.com/riscPrint/risc-v-workstation/pull/683). Merged: 2026-11-13T04:00:31Z.

Title: feat(soc): add map driven spinal apb3 composer

Audit evidence label: unit tests only.

## Summary
Add SpinalSoc and `rvw soc compose`. Generate an APB3 RV32 top from an existing map and explicit project core/peripheral binders. Use the Spinal library decoder/router, initialized RAM/ROM, interrupt wires and software exports. Record input hashes and clock/reset intent.

This is the first bounded composer increment. AXI4/TileLink selection, multiple domains, byte accesses, a C1 runner and complete board device trees remain open. IdleCore is an elaboration fixture and does not execute programs.

## Testing
- Targeted composer tests: 7 passed.
- Locked short sbt compile and elaboration: passed with SpinalHDL 1.15.0 and JDK 21.0.13.
- Fast set: 896 passed, 1 skipped, 7344 deselected in 85.62 seconds.
- NOT RUN: CPU simulation, BOOM, full Python suite, long formal runs and CI.

## Issues
Owner's SoC integration work list, first item. No issue closed.

Roadmap notes: add SpinalSoc as a generic map-driven APB3 verification composer. The initial profile compiles and elaborates. Executable CPU/C1 integration and richer fabrics remain open.


## PR 684

[#684](https://github.com/riscPrint/risc-v-workstation/pull/684). Merged: 2026-11-13T04:00:46Z.

Title: feat(uvm): add database-selected project profile scaffolds

Audit evidence label: unit tests only.

## Summary
Add database-selected CPU, APB, AXI4, AXI4-Lite, TileLink, AXI-Stream, UART, SPI and I2C profile scaffolds in pyuvm and SV UVM output. Preserve the automatic single-APB reset bench. Record the selected agent support, ports, clock domains and SoC map.

The additional profiles are customizable scaffolds. They require project wire bindings and behavior checks. Unchanged scenario hooks fail explicitly. They do not implement automatic runnable wiring or native qualification for all bus types.

## Testing
- Profile and existing scaffold tests: 23 passed, 0 skipped.
- Fast set: 913 passed, 1 skipped, 7348 deselected.
- NOT RUN: native qualification of every generated profile, generated SV compilation, CPU/debug/C4 checks.

## Issues
Refs: #296

Roadmap notes: Database-selected pyuvm and SV scaffolds now cover the listed bus types. Only the existing default APB profile has automatic runnable wiring. Project scenario bindings and per-profile native checks remain open.


## PR 685

[#685](https://github.com/riscPrint/risc-v-workstation/pull/685). Merged: 2026-11-13T04:01:16Z.

Title: feat(install): declare untested linux recipes for tool flags

Audit evidence label: unit tests only.

## Summary

Generate Linux package/source instructions for every inventory tool. Add apt/dnf planning and route package-backed optional flags through the existing installer approval path. Keep source-only builds explicit. Preserve combined Python extras in one locked sync at the selected prefix. Document GHDL plugin ABI limits.

## Testing

Targeted inventory and installer tests, shell syntax, generated table and whitespace checks. Fast suite run before final rebase. Linux installs are UNTESTED: only macOS ARM64 is available. No native downloads, long builds or full Python suite.

## Issues

Refs: #17. Fresh Ubuntu/Fedora and clean macOS qualification remain open. Source-only recipes are manual, not a turnkey Linux install claim.

Roadmap notes: all flags have inventory-based Linux recipes; package flags share approval handling. Linux runtime and source build qualification remain open.


### Recorded validation

Targeted tests: 58 passed. Pre-rebase fast command `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`: 901 passed, 1 skipped. The command-reference skip was inherited from main. Full Python suite and new native qualification NOT RUN.


## PR 686

[#686](https://github.com/riscPrint/risc-v-workstation/pull/686). Merged: 2026-11-13T04:02:19Z.

Title: feat(cov): replay sealed candidate elfs without new credit

Audit evidence label: unit tests only.

## Summary

Add `cov campaign --replay N` and the same `cov_campaign` MCP argument. Verify campaign input/state/raw generations, then run the archived candidate ELF through the original C1 options and strict Spike verifier in a fresh result directory. Seal replay evidence separately. Do not change original campaign state or credit new hits.

Require matching execution identity for a qualified replay. Report changed/missing identity as inconclusive. Failed runs remain observations on the current configured model and do not claim original-context failure reproduction. Attempts without an ELF remain unsupported. Replay ignores mutable working output copies and uses the verified archive; normal resume retains working-file checks.

## Testing

Focused campaign, archive/identity, random and command reference tests: 51 passed, 1 skipped. Fast set: 878 passed, 1 skipped, 7324 deselected. The skip is the upstream command-reference check disabled for the parallel push. This PR does not change it.

Tests cover archive-only ELF selection, altered working copies, unchanged original state, zero added credit, new replay archives, changed identity, no-ELF attempts and CLI/MCP error parity.

NOT RUN: native DUT/Spike replay, cross-host replay, full cost accounting, full suite or CI. Fixture results do not qualify native replay.

## Issues

Refs: #349, #352

Keep both issues open for native execution evidence, held-out mutations, total CPU accounting and paired random comparisons.

Roadmap notes: The closure tool can now replay sealed candidate ELFs through CLI/MCP without changing original campaign credit. Replay identity and evidence are explicit. Native and cross-host qualification remain unverified.


## PR 687

[#687](https://github.com/riscPrint/risc-v-workstation/pull/687). Merged: 2026-11-13T04:02:27Z.

Title: feat(arch): export shared gem5 configuration files

Audit evidence label: unit tests only.

## Summary

Add `rvw arch gem5-export` and a cancellable MCP tool. Export a self-contained copy of the existing gem5 adapter, the unchanged shared O3 description, the normalized own-model configuration and an invocation/hash report. Keep one description as the source of shared CPU dimensions.

## Testing

- Targeted test: 1 passed. Generated Python parses, shared ROB/rename dimensions agree and an existing output directory is refused.
- Fast set: 903 passed, 1 skipped, 7371 deselected.
- NOT RUN: gem5 build or simulation, RTL, full Python suite or timing parity.

## Issues

Refs: #72, #357, #359

This provides the requested configuration files. Native timing parity, multi-level front-end recovery and FTQ-directed prefetch remain open. The existing pinned adapter and bare-metal ROI ELF contract still apply.

Roadmap notes: Shared-description gem5 and own-model file export is available. Equal dimensions do not establish equivalent microarchitecture.


## PR 688

[#688](https://github.com/riscPrint/risc-v-workstation/pull/688). Merged: 2026-11-13T04:02:39Z.

Title: feat(query): write SpinalBlocks diagrams for HDL databases

Audit evidence label: unit tests only.

## Summary

- New `rvw/src/rvw/query/blocks.py` derives a SpinalBlocks diagram (format version 1) from any design database's tables. One diagram per module name (first instance in path order, `instanceCount` over all), ports (record fields grouped), instances, one node per named register (`sig:`) or memory (`mem:`), and nets traced backwards through wires, bit nodes and hidden cell hubs to driver endpoints. Register bits stand for their register; a registered output port gets its own node only when no internal register holds its bits; `control` and `clock` flags from edge kinds and clock roles.
- `rvw query build-hdl` (all front ends: native Yosys, slang, GHDL, firtool) stores it as artifact `blocks.json` (gzip, uncompressed `size`), so `rvw query export blocks` and the viewer (`node SpinalBlocks/hosts/web/serve.mjs blocks.json.gz`) work on SV, VHDL and Chisel databases.
- Docs: SpinalBlocks README limits, SpinalDB README, `docs/contracts/query.md` section.

## Testing

- `rvw/tests/test_query_blocks.py`: 1 passed. Checks the exact net set of a two-instance design with a memory, and loads the export with the SpinalBlocks engine itself (`loadDesign` + `buildViewGraph` for every module, Node 26 runs the TypeScript sources).
- Manual: Ibex `ibex_core` (slang) gives 16 module diagrams in 0.6 s; the engine builds view graphs for all (99 blocks, 1489 edges).
- All HDL query tests with native tools (`test_query_blocks/hdl/slang/ghdl/chisel`, `test_init_hdl`, `test_lint_hdl`): 34 passed.
- Fast set (command-reference tests deselected per the brief): 885 passed, 1 skipped.
- Not run: the ELK layout and SVG renderer on these diagrams (elkjs is not installed here), the VS Code extension, CI.

## Issues

Refs: #26, #55. Remaining: Areas and FSM recovery for HDL designs (for example SV `enum` state registers), clock/reset nets for flip-flop pins, layout and screenshot checks.

Roadmap notes: SpinalBlocks: block diagrams now come from any design database, so SV (slang), VHDL (GHDL) and Chisel (firtool) cores get the same diagram viewer as Spinal designs.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 689

[#689](https://github.com/riscPrint/risc-v-workstation/pull/689). Merged: 2026-11-13T04:03:36Z.

Title: feat(riscvsim): inject faults through verilator public access

Audit evidence label: ran on seeded RTL fixture.

## Summary
- Generic `run --fault FILE` (C1 fault injection) in `RiscvSim/src` for any adapter that runs through `SimSession`; no adapter code and no core names.
- Fault jobs use a separate `_fault` model: an elaboration phase tags every register `simPublic`, and Verilator gets `--public-flat-rw` so outside writes re-evaluate readers. Golden runs keep the normal model.
- The injector resolves `site` as the design-database register path, writes the bit after each clock edge in the window (`stuck0`/`stuck1` for `duration` or to the end, `flip` once), and confirms by reading the register back one time unit later. `details.fault` adds `applied_cycle`, `before`, `after`, `writes`. Missing sites, enumeration registers, out-of-range bits, runs that end first and failed read-backs give `applied: false` with a reason. Replay commands carry `--fault`.
- Docs: `docs/contracts/c2-rvfi-trace.md` ("RiscvSim harness hooks"), `RiscvSim/README.md` ("Fault injection"), fault README.

## Testing
- Native, VexRiscv example (`VEXRISCV` = shared checkout at `a62c145a`, under the `vex` lock): `examples/vexriscv/rvw/tests/test_fault_native.py`: 1 passed (flip of `CsrPlugin_mscratch` bit 4 confirmed by read-back; a missing site gives `not_injected`).
- Real campaign with `rvw fault` on VexRiscv (smoke, 91 cycles): plan of 12 faults from the design database (`--exclude '*FORMAL*'`, window 10:80, seed 7). 11 applied and confirmed; 2 detected (asserts), 4 timeouts, 5 safe, 1 `not_injected` (`CsrPlugin_satp_PPN`, absent from the current M-only model; the database came from an older config). Diagnostic coverage 0.33 (95 % 0.10..0.70) over 6 unsafe outcomes.
- `sbt root/compile` of the VexRiscv example (RiscvSim via ProjectRef) under the sbt lock: success.
- Fast set: 900 passed, 1 skipped.
- Not run: BOOM (its adapter uses `SimSession`, so it gets the hook, but it is untested); RiscvSim's own sbt tests (they load BOOM).

## Issues
Refs: #52 (adapter-side injection now exists; FMEDA, memories as sites and lockstep checks remain).

Roadmap notes: functional safety: `rvw fault run` now runs against core RTL through the generic RiscvSim `--fault` hook; first real VexRiscv campaign measured.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

## PR 690

[#690](https://github.com/riscPrint/risc-v-workstation/pull/690). Merged: 2026-11-13T04:04:12Z.

Title: feat(uvm): qualify native vexriscv irq and csr sequences

Audit evidence label: ran on real core RTL.

## Summary
Run seeded MSIP, MTIP and MEIP requests on live VexRiscv with independent Spike trap synchronization. Add a catalog-derived mscratch program and verify its actual CSR retirements through CsrQualification and Spike. Include a reproducible ELF build script and opt-in native tests.

The selected core has no debug unit or request port. Native debug-request qualification remains blocked on a debug-enabled project configuration. No debug pass is claimed.

## Testing
- Native event tests: 3 passed, 0 skipped. IRQ seeds 1 and 3 each checked eight interrupts. CSR seed 1 checked 88 catalog operations and 145 retirements.
- Event and CSR model unit tests: 9 passed.
- Fast set: 927 passed, 1 skipped, 7385 deselected.
- NOT RUN: debug requests, all CSR semantics, denied-access native collector, BOOM, C4 acceptance.

## Issues
Refs: #296

Roadmap notes: Native seeded IRQ synchronization and present M-mode mscratch catalog sequences now have measured VexRiscv evidence. The current VexTop lacks debug hardware. Native debug and full C4 remain open.


## PR 691

[#691](https://github.com/riscPrint/risc-v-workstation/pull/691). Merged: 2026-11-13T04:05:15Z.

Title: feat(arch): fit model parameters to saved probe event counts

Audit evidence label: unit tests only.

## Summary

Add `rvw arch ooo-fit` and a cancellable MCP tool. Fit a declared grid of at most 32 parameter candidates to saved C1/C2 timing and mapped event counts. Consume the probe library's existing `counts` export. Keep identity, split and hash checks. Save all candidate configs, training scores, the winner and final held-out calibration. Re-run with a new output directory for new observations.

## Testing

- Targeted fit tests: 2 passed. Changed held-out timing does not change selection. Missing training counts cause an error.
- Fast set: 937 passed, 1 skipped, 7394 deselected.
- NOT RUN: RTL, gem5, full Python suite, physical accuracy qualification or continuous background monitoring.

## Issues

Refs: #31

The command consumes saved probe-derived counts. It does not launch probes or RTL. Selection uses training scores only. Baseline validation reads held-out inputs, but their scores are not used to select parameters. A finite grid does not establish unique fitted parameters or fidelity.

Roadmap notes: Saved probe/C1/C2 parameter fitting is available. Native calibration campaigns remain separate.


## PR 692

[#692](https://github.com/riscPrint/risc-v-workstation/pull/692). Merged: 2026-11-13T04:05:09Z.

Title: feat(cosim): link native dpi lockstep and verify vexriscv

Audit evidence label: ran on real core RTL.

## Summary
Link the native C2 DPI client into the generic Verilator harness. Add an optional generic mailbox and an RVFI writer callback. Keep the existing Scala transport as the default. Include the DPI source digest in the native cache key.

Enable the mailbox in the VexRiscv example through RVW_COSIM_DPI=1. Initialize it before sending C2 and acknowledge the final report before closing the native model. Preserve control settings in replay. Add an explicit adapter writeback fault for the native negative control. Detect simulator exit before connection without waiting for the whole timeout.

The native clean program matches Spike through all six retirements. The injected writeback bit fault at order 1 is detected at order 1; the trace contains only orders 0 and 1.

## Testing
- Private VexRiscv a62c145aa042a5de874344e0a7683bd7c8c8c870, private vex-cosim lock: native match and first-fault test passed.
- Generic Scala LiveTraceSpec: 2 passed.
- DPI client, blocking transport and online launcher: 18 passed.
- Fast set: 875 passed, 1 skipped, 7312 deselected. Command-reference regeneration remains deferred by the push brief.
- Native overhead: see the measured pairs and limits in the example README. Both paths use 6006 retirements and 24026 cycles.
- NOT RUN: BOOM, full Python suite, interrupt synchronization, extended machine CSR capture, second-core DPI, Sail and RVVI native flows, debug-halt endpoint.

## Issues
No broad issue is closed by these bounded controls.

Roadmap notes: The generic Verilator DPI lockstep transport now has a real VexRiscv clean run, a first-instruction-boundary negative control and measured adapter execution overhead. Interrupt synchronization and the remaining integrations need separate evidence.


## PR 693

[#693](https://github.com/riscPrint/risc-v-workstation/pull/693). Merged: 2026-11-13T04:05:11Z.

Title: feat(install): report bounded release scan and identity counts

Audit evidence label: unit tests only.

## Summary

Add a bounded release scan that reuses the existing credential/path scanner. Report tracked findings, files touched since UTC midnight and local author/committer/tagger counts without credential values. Preserve attribution and history.

Scan result: 1,497 touched files; zero tracked credential/path findings; zero metadata findings; 1,445 locally reachable commits and one tag. No current personal-path replacement was needed. Untracked rvw/out was excluded.

## Testing

Release scanner and hygiene tests: 41 passed. Date-cutoff regression: 1 passed. Fast suite run before final rebase. No publication, identity rewrite, cache deletion, remote-cache audit, native build or full Python suite.

## Issues

Refs: #79. Owner acceptance of identity publication remains open. Remote history/cache work remains #39.

Roadmap notes: current release scan and redacted identity counts are available; no credential absence or publication approval is claimed.


### Recorded validation

Targeted tests: 41 passed. Pre-rebase fast command `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`: 933 passed, 1 skipped. The command-reference skip was inherited from main. Full Python suite and new native qualification NOT RUN.


## PR 694

[#694](https://github.com/riscPrint/risc-v-workstation/pull/694). Merged: 2026-11-13T04:06:19Z.

Title: feat(soc): add bounded spinal peripheral profiles

Audit evidence label: unit tests only.

## Summary
Add eight bounded verification peripheral profiles: UART 16550 register subset, CLINT, PLIC, GPIO, timer/watchdog, tohost finisher, and wrappers for the Spinal SPI and I2C controllers. Export map regions and composer binders through CLI/MCP. Export selected peripheral pins and allow explicit named interrupt outputs.

UART is a fixed 8N1 register subset, not a complete 16550. PLIC has seven level sources and one context with 0/1 priorities. SPI/I2C exports describe register addresses, not every dynamic bit effect. Automatic VIP behavior binding remains open; project pin bindings are explicit.

## Testing
Targeted Python tests: 16 passed. All eight peripheral profiles compiled and elaborated to RTL with SpinalHDL 1.15.0. Native CLINT/PLIC smoke and fast-set results are recorded below.

NOT RUN: full Python suite, BOOM, full UART/SPI/I2C protocol qualification or CI.

## Issues
Owner's SoC integration work list, peripheral item. No issue closed.

Roadmap notes: SpinalSoc has eight bounded peripheral profiles with reusable map exports. Full UART 16550 compatibility and automatic VIP/scoreboard binding remain open.

Native evidence: `rvwsoc.PeripheralSmoke` passed under Verilator at seed 17 (four CLINT and six PLIC assertions). Total sbt/native run: 18 seconds. Updated targeted set: 17 passed.

Fast set: 916 passed, 1 skipped, 7369 deselected in 114.53 seconds.


## PR 695

[#695](https://github.com/riscPrint/risc-v-workstation/pull/695). Merged: 2026-11-13T04:18:56Z.

Title: feat(csr): generate shared aliases and privilege sequences

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add rvw.csr-bank/1 for explicit canonical storage and static masked CSR alias views. All views update one independent expected bank. Check canonical storage, trap decisions, read data and independent hardware clear/set events. Retain the legacy field model for its existing WARL/WLRL and side-effect rules.

Extend the existing formal csr CLI/MCP and checks generate --all CSR path. Emit directed alias and M/S/U privilege sequences with MRET/ECALL transitions, coverage groups and optional wrapper SBY files. Reject undeclared modes, unsupported semantics and program-owned trap-control CSR views.

## Testing
- Bank, legacy CSR/catalog and generation tests with native SBY/Spike: 50 passed, no skips before the final trap-control validation test.
- Final bank regression: 11 passed, no skips. Includes two successful Spike programs and two seeded wrong-comparison programs that must exit with failure.
- SBY shared-bank cases: two good proofs and three seeded state/read/privilege failures passed their expected status checks.
- Post-rebase fast set: 933 passed, 1 skipped, 7410 deselected. The skip is the coordinator's command-reference batch check.
- NOT RUN: real-core alias/privilege RTL campaign, conditional AIA alias behavior, dynamic state-enable controls, full Python suite, BOOM builds.

## Issues
Refs: #85

Roadmap notes: Add static alias execution and generated M/S/U sequences with native reference and monitor-fixture evidence. Keep conditional AIA aliases, dynamic WARL/state controls and real-core alias/privilege campaign qualification open. No full compliance claim.


## PR 696

[#696](https://github.com/riscPrint/risc-v-workstation/pull/696). Merged: 2026-11-13T04:07:32Z.

Title: feat(sec): add dynamic simulation taint tracking

Audit evidence label: unit tests only.

## Summary
Add rvw sec ift and sec_ift MCP for bounded Verilator shadow simulation. Reuse the Yosys Boolean transform, with value-sensitive and conservative modes. Bind internal or port sources, sink signals and a sampled declassifier. Write cycle findings, structural candidate paths, optional C6 name matches and C3 outcomes.

## Testing
- Tiny planted-leak and fixed-control native Verilator tests: 2 passed.
- Fast policy and result tests: 2 passed.
- Fast set: 932 passed, 1 skipped, 7385 deselected.
- CLI import and MCP discovery: no skipped modules.
- NOT RUN: whole-core simulation, BOOM, physical leakage, exhaustive source memory decoding or dynamic provenance.

## Issues
No issue closed. A structural candidate path is not dynamic taint provenance. Memory-region and CSR bindings require project signal declarations. No security proof is claimed.

Roadmap notes: add simulation security as a component. First increment provides dynamic digital IFT with explicit bounded-evidence limits. Paired leakage, gadget, timing, isolation and security fault campaigns follow separately.


## PR 697

[#697](https://github.com/riscPrint/risc-v-workstation/pull/697). Merged: 2026-11-13T04:07:41Z.

Title: docs(site): build local navigation from existing markdown

Audit evidence label: unit tests only.

## Summary

Add a local MkDocs config and nav over the existing Markdown. Generate tool pages from top-level and rvw package READMEs in a temporary staging tree. Keep source files unchanged. Link source-code targets to the exact Git revision. No hosting or publishing configuration.

## Testing

Built 230 HTML pages locally. Targeted site/inventory tests: 11 passed. Final focused site tests: 2 passed. uv lock --check passed. Fast suite run before final rebase. Existing Markdown target/anchor warnings remain in the build log; no clean link-check result is claimed. No browser, hosted site, native tools or full Python suite.

## Issues

Refs: #58. Worked-path qualification, CI link/code-block checks and legacy Markdown link repairs remain open.

Roadmap notes: local docs site generation and tool navigation are available. No hosting is configured.


### Recorded validation

Targeted tests: 11 passed. Pre-rebase fast command `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`: 936 passed, 1 skipped. The command-reference skip was inherited from main. Full Python suite and new native qualification NOT RUN.


## PR 698

[#698](https://github.com/riscPrint/risc-v-workstation/pull/698). Merged: 2026-11-13T04:07:50Z.

Title: feat(arch): run own-model timing on shared simulation points

Audit evidence label: unit tests only.

## Summary

Add `rvw arch ooo-sampled` and a cancellable MCP tool. Join the own model to `rvw csim simpoint` output. Verify the normalized trace hash and instruction count. Run each point with bounded warmup, aggregate weighted CPI and optionally quantify the gap against a complete model run. Reuse ComponentSims conversion and point selection.

## Testing

- Targeted sampled-run tests: 2 passed. The actual ComponentSims point format joins, a changed hash is refused, and a full-trace point has zero gap against the full model.
- Fast set: 938 passed, 1 skipped, 7403 deselected.
- NOT RUN: large workload sampling, gem5, RTL, checkpoint restore, full Python suite or RTL sampling-error qualification.

## Issues

Sampling boundaries can bias timing. Warmup starts cold and the end drains without future instructions. Error is unmeasured unless a full model run is requested. This provides shared sampled timing, not #201 system-power modeling or #196 custom-extension trade-offs.

Roadmap notes: ComponentSims SimPoint plans can drive own-model timing and optional full-run error reports. Native workload calibration remains open.


## PR 699

[#699](https://github.com/riscPrint/risc-v-workstation/pull/699). Merged: 2026-11-13T04:09:20Z.

Title: feat(uvm): bind compiled bench matrices to c4 gates

Audit evidence label: unit tests only.

## Summary
Add `rvw uvm gate-config` and a source-bound C1 build/identity adapter for compiled pure SV benches. Use the existing C4 build-suite path. Each build job executes every declared UVM test and seed. Bind its result claim to selected source hashes, binary hash, build metadata, pinned UVM and matrix. Refuse source mismatch and custom native dependencies.

This is bounded bench acceptance. A component fixture does not qualify CPU or ISA behavior. Standalone UVM C3 identity remains incomplete. C4 supplies its existing captured source and interpreter identity.

## Testing
- Targeted binding/refusal tests: 3 passed.
- Native Verilator 5.049 build passed. A clean committed same-revision C4 gate returned accept. Base and candidate each ran adapter_smoke at seeds 1 and 3.
- Fast set: 936 passed, 1 skipped, 7394 deselected.
- NOT RUN: CPU C4 qualification, DPI benches, arbitrary imported VIP, changed-source revision builds.

## Issues
Refs: #296

Roadmap notes: Source-bound compiled pure SV UVM matrices can use the existing C4 build-suite path. Current source bytes must match the compiled bench. CPU and custom native-dependency acceptance remain open under #296.


## PR 700

[#700](https://github.com/riscPrint/risc-v-workstation/pull/700). Merged: 2026-11-13T04:10:00Z.

Title: feat(sec): compare and reduce architectural contract pairs

Audit evidence label: unit tests only.

## Summary
Add seeded ALU program pairs, project RTL adapter execution, independent C2 agreement checks, architectural PC/address/branch contracts, observation comparisons and replay-based instruction deletion. Write a counterexample pair and C3 outcomes. Add sec_contract MCP.

## Testing
- Targeted fast tests: 3 passed.
- Tiny native Verilator timing leak and fixed control: 2 passed.
- Fast set: 953 passed, 1 skipped, 7409 deselected.
- NOT RUN: whole-core RTL, Spike campaigns, BOOM, speculative core campaigns.

## Issues
No issue closed. Contract names describe project intent; project programs and adapters supply sandbox and speculative semantics. The default generator covers ALU instructions. The native fixture uses a synthetic NOP architectural stream and a real timing RTL model. It is not core validation. The reducer is bounded and does not claim a global minimum.

Roadmap notes: simulation security now supports paired contract testing and bounded witness reduction. Core adapter integrations and broad fuzz grammars remain open.


## PR 701

[#701](https://github.com/riscPrint/risc-v-workstation/pull/701). Merged: 2026-11-13T04:10:36Z.

Title: docs(install): guide fresh cores through verified tool stages

Audit evidence label: unit tests only.

## Summary

Add the fresh-repository integration guide in the requested 14-stage order. Cover Spinal and non-Spinal init paths, adapters, runs, regression, cosim, probes, coverage, formal, lint/CDC, waves/debug, architecture, UVM/VIP and farm use. Each stage states commands, working evidence, optional tools and limits.

Read the tool READMEs and 310 merged PR bodies from the requested date query. Keep native RTL, RTL fixture, Spike-only and Python fixture evidence separate. Include newer VexRiscv UVM, IRQ/CSR, DPI and fault results without promoting them to whole-core qualification. Add the guide to local site navigation.

## Testing

Command syntax and evidence-boundary tests: 2 passed. All guide rvw commands parse without executing tools. The test caught and corrected a missing required debug --out argument in an older README example. Local MkDocs guide build passed. Fast suite run before final rebase.

NOT RUN: new-core bring-up, core simulations, native tools, Linux, full Python suite or hosting. Existing unrelated site link/anchor warnings remain.

## Issues

Integration guide requested by the owner. Refs: #58, #27. End-to-end fresh-core runtime qualification remains open.

Roadmap notes: ordered integration guide now links per-tool evidence scopes and limits. This is documentation and syntax validation, not new native qualification.


### Recorded validation

Targeted tests: 2 passed. Pre-rebase fast command `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`: 952 passed, 1 skipped. The command-reference skip was inherited from main. Full Python suite and new native qualification NOT RUN.


## PR 702

[#702](https://github.com/riscPrint/risc-v-workstation/pull/702). Merged: 2026-11-13T04:12:17Z.

Title: perf(arch): scan native branch and memory state once per phase

Audit evidence label: unit tests only.

## Summary

Replace repeated older-branch walks in the native scheduler with one prefix-state scan. Preserve branch overlap, recovery, memory ordering and all counters. Keep the historical benchmark and record new warmed trials with 500,000-instruction raw kernel inputs.

## Testing

- Native parity tests: 4 passed, including 250 seeded integer/mixed schedules. The prefix implementation also passed those checks before replacement.
- Mixed raw kernel: about 2.8 million instructions/s on this shared host. Public Python call: about 0.66 million instructions/s including validation and packing. C2 parsing is excluded from both.
- Raw trials and public-call alternating trials: `Arch/ooo/benchmark-results-prefix.json`. The two saved benchmark files are not a controlled before/after study.
- Fast set: 954 passed, 1 skipped, 7412 deselected.
- NOT RUN: application throughput, component-backed acceleration, RTL, gem5 or full Python suite.

## Issues

The raw scheduler reaches the several-million range on this synthetic mixed stream. Python validation/packing and C2 parsing still limit full-path throughput. Unsupported model features still use Python. No RTL accuracy is established.

Roadmap notes: Mixed native issue scanning is linear in ROB occupancy per phase. End-to-end C2 and component-backed acceleration remain open.


## PR 703

[#703](https://github.com/riscPrint/risc-v-workstation/pull/703). Merged: 2026-11-13T04:13:54Z.

Title: feat(sec): generate speculative gadget receiver templates

Audit evidence label: unit tests only.

## Summary
Generate RV64 v1, v2, v4 and return-predictor gadget templates with a seeded 256-line cycle receiver and an explicit project ABI. Export CLI and MCP entry points. Expect no observed leak on all cores, including in-order cores.

## Testing
- Generator test: 1 passed.
- All four emitted assembly files compiled with RISC-V GCC, rv64i_zicsr/lp64.
- Fast set: 957 passed, 1 skipped, 7413 deselected.
- NOT RUN: core speculation, training/flush hooks, covert-channel calibration or self-checking native core suites.

## Issues
No issue closed. This is generation only. The project must implement training, cache reset, address-delay setup and paired receiver controls. The threshold flag alone is not a leakage verdict. Executed whole-core gadget suites remain open.

Roadmap notes: add four speculative test templates and receiver ABI. Record execution coverage as pending.


## PR 704

[#704](https://github.com/riscPrint/risc-v-workstation/pull/704). Merged: 2026-11-13T04:14:07Z.

Title: feat(uvm): record refreshable native qualification evidence

Audit evidence label: unit tests only.

## Summary
Add a refreshable SV UVM qualification matrix from native CPU C3 and engine probe results. Record the successful long-timeout SV CPU build and its five checks. Keep the Verilator 5.049 transition-bin runtime gap and pyuvm coverage workaround explicit. Add a 600-second default build timeout to the CPU runner.

## Testing
- Native SV CPU build completed in about 109 seconds. Two normal seed runs and three corruption checks passed. It was built once in the background during this task.
- Matrix refusal/missing-evidence test: 1 passed.
- Fast set: 956 passed, 1 skipped, 7410 deselected.
- NOT RUN: VexRiscv SV CPU environment, full SV language qualification, HDL backdoor/VPI.

## Issues
Refs: #296

Roadmap notes: Native ADDI/MISA SV CPU fixture evidence and the transition coverage gap now have a refreshable measured matrix. Use pyuvm observed bins and functional coverage as the transition-bin workaround. Full VexRiscv SV qualification remains open.


## PR 705

[#705](https://github.com/riscPrint/risc-v-workstation/pull/705). Merged: 2026-11-13T04:14:20Z.

Title: fix(cosim): sample vexriscv events before dpi synchronization

Audit evidence label: ran on real core RTL.

## Summary
Sample the VexRiscv trap, RVFI record and CSR snapshot before any DPI call can yield simulation time. This fixes a real missed retirement at interrupt entry without weakening the strict order check.

Add native MSIP and MTIP lockstep tests. The positive controls initialize mtval to zero, assert the input at cycle 200, deassert it at cycle 220, check the real trap cause, execute the handler and MRET, and require a complete Spike match.

Keep negative controls for the pinned core's retained mtval behavior. With mtval initialized to 7, both interrupts must mismatch at the trap boundary: Spike expects zero, RTL reports 7. No mask, fabricated trap value or core-source change is used. General interrupt correctness is not claimed.

## Testing
Native counts are recorded in the example README. Fast-set results are recorded below before publication.
NOT RUN: BOOM, full Python suite, other VexRiscv configurations, general interrupt compliance.

## Issues
The pinned VexRiscv CSR implementation writes mtval only on an exception; interrupt entry retains its previous value. This core/reference difference remains open. The native negative controls preserve it as a visible mismatch.

Roadmap notes: Native VexRiscv MSIP/MTIP lockstep synchronization is exercised through handler entry and MRET with explicit mtval preconditions. A retained-mtval mismatch remains; it is not waived.

Validation: native controls 4 passed. The two zero-mtval runs each matched 50 instructions and one interrupt trap, including the cycle-220 input deassertion. The two nonzero-mtval runs each detected the real tval mismatch. Fast set: 934 passed, 1 skipped, 7399 deselected.


## PR 706

[#706](https://github.com/riscPrint/risc-v-workstation/pull/706). Merged: 2026-11-13T04:15:16Z.

Title: feat(formal): extend bit permutation and word reference models

Audit evidence label: unit tests only.

## Summary

Extend the C reference library with single-bit operations, shift/add, crossbar permutations, packing, byte-bit reversal, RV32 ZIP/UNZIP and RV64 word/unsigned-word forms. Preserve RV64 word sign extension. Keep functional transforms separate from instruction and immediate decoding.

## Testing

Targeted bit/hash model suite: 15 passed. Include independent integer and bit-expression checks, signed word extension, zero shift/count boundaries and complete symbolic XPERM fixtures. Nibble/byte selector mutants produce counterexamples.

Required fast set after rebase: 958 passed, 1 skipped, 7419 deselected. The skip is the upstream temporary command-reference batch rule.

NOT RUN: BOOM builds, full Python suite, long formal jobs, whole-core extension compliance or instruction timing qualification.

## Issues

Refs: #19.

Roadmap notes: Add functional Zba/Zbb/Zbs/Zbkb/Zbkx forms alongside the existing carryless multiply models. Decoder legality, project-wide unit bindings and timing properties remain separate obligations. Keep the epic open.


## PR 707

[#707](https://github.com/riscPrint/risc-v-workstation/pull/707). Merged: 2026-11-13T04:14:28Z.

Title: fix(doctor): probe managed tool paths and plugin files

Audit evidence label: unit tests only.

## Summary

Correct inventory diagnostics for managed prefixes and shared libraries. Put presence probes in the same data file. Honor authoritative environment selectors. Do not treat yosys-config as an installed slang plugin. Require the GHDL plugin file as well as its executable. Reuse the all profile for doctor installation. Refuse package installation success when the selected tool remains missing.

## Testing

Targeted doctor/inventory tests: 37 passed. Final inventory tests: 14 passed, including the arcilator check path without a venv. Generated version table check and whitespace check passed. Pre-rebase fast suite: see final recorded count below. Tests cover missing plugins, invalid explicit selectors and CIRCT binaries in a prefix outside PATH.

NOT RUN: loading native plugins, runtime ABI checks, native downloads, clean installs, Linux or full Python suite. Presence stays separate from runtime qualification.

## Issues

Refs: #17, #40. This fixes diagnostic accuracy. It does not close native qualification.

Roadmap notes: shared inventory now defines managed-prefix and plugin-file probes; explicit invalid selections cannot silently fall back to host tools.

Final pre-rebase fast command `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q`: 961 passed, 1 skipped, 7412 deselected. The inherited command-reference skip remains.


## PR 708

[#708](https://github.com/riscPrint/risc-v-workstation/pull/708). Merged: 2026-11-13T04:15:13Z.

Title: feat(arch): estimate workload system energy by power state

Audit evidence label: unit tests only.

## Summary

Add `rvw arch system-energy` and a cancellable MCP tool. Combine a workload model's event counts with project-declared power states and transition energy for CPU, cache, memory and interconnect components. Require state cycles to partition the workload cycles. Report component and system energy separately from cell-level power.

## Testing

- Targeted test: 1 passed. State, event and transition energy have the expected units and total. Incomplete state residency is refused.
- Fast set: 961 passed, 1 skipped, 7416 deselected.
- NOT RUN: RTL, physical power measurement, external calibration, gem5 or full Python suite.

## Issues

Refs: #201

This is an abstract energy study. State residency and coefficients are project declarations. No sleep-state inference, activity propagation, wake latency or physical power model is claimed. Calibration against measured sources remains open under #201.

Roadmap notes: Workload event/state energy studies are available for system components. Physical and measurement-calibrated power remain separate.


## PR 709

[#709](https://github.com/riscPrint/risc-v-workstation/pull/709). Merged: 2026-11-13T04:15:06Z.

Title: feat(soc): run composed rv32 stub programs through c1

Audit evidence label: ran on seeded RTL fixture.

## Summary
Add a project-owned RV32 instruction stub and a composed APB3 SoC with RAM, UART, CLINT, PLIC and tohost. Add hello-world, timer-interrupt and PLIC-interrupt ELF sources, a C1 adapter, serialized run-many and a regression project.

The stub supports only the listed instruction/CSR subset. It is not an ISA-qualified core. The UART decoder samples the actual TX pin. The example README records real local results and the dirty source boundary.

## Testing
- 18 targeted SoC Python tests passed.
- `rvw regress` quick tier: 3 passed at seed 17 in Verilator. Hello: 1313 measured loop cycles and 436 retired instructions, with `hello` and newline on TX. External IRQ: 224 cycles, 74 retired instructions. Timer IRQ: see README.
- Runner property smoke: timer IRQ passed again at seed 19, 111 cycles and 37 retired instructions.
- Fast set result below.
- NOT RUN: BOOM, full Python suite, ISA conformance, MRET behavior, debug, RVFI/C2, long formal or CI.

## Issues
Owner's SoC work list, end-to-end example item. No issue closed.

Roadmap notes: composed APB3 RV32 stub now runs hello-world and CLINT/PLIC interrupt programs through C1 and `rvw regress`. Results establish the bounded example only. A production core, broader buses and full peripheral qualification remain open.

Fast set: 949 passed, 1 skipped, 7405 deselected in 73.84 seconds.


## PR 710

[#710](https://github.com/riscPrint/risc-v-workstation/pull/710). Merged: 2026-11-13T04:16:42Z.

Title: feat(formal): model custom state memory and trap effects

Audit evidence label: unit tests only.

## Summary

Add `rvw.custom-isa/2`, `rvw formal custom-effects` and `formal_custom_effects`. Declare explicit result, PC, extra-state, load/store and trap effects. Generate SystemVerilog transition kernels, normalized interface data and boundary/alias/fault plans. Keep all normal state updates atomic from pre-state. Traps suppress normal commits and apply explicit trap updates. x0 suppresses only the destination write.

Require complete memory fault semantics. A fault without an attempted access is an error and an RTL assertion. Add independent vectors and effect mutants for store, accumulator wrap, x0, misalignment, fault cause and trap target. The pure version-1 encoding validator is reused.

## Testing

- Custom effects and existing pure-custom tests with native tools: 25 passed, no skips.
- Latest non-native effect tests, including the added missing-fault-semantics case: 12 passed, 3 native cases deselected.
- Native independent formula: correct kernel bounded PASS, wrong accumulator update FAIL. An unsolicited fault also produces FAIL. Each proof had a 20/30-second limit. These are model fixtures, not a DUT proof.
- Earlier CLI/MCP/reference integration set: 26 passed, 1 existing command-reference skip.
- Fast set: 952 passed, 1 existing skip, 7425 deselected.
- NOT RUN: actual DUT binding, compiler backend builds, full Python suite, bus-handshake or AMO qualification. No BOOM/VexRiscv build or simulation ran.

## Issues

Refs: #122, #155

Roadmap notes: Add versioned extra-state, single-memory-access and trap semantics with generated kernels and verification inputs. Project state setup/observation, actual core bindings, multiple-access/AMO behavior, partial fault side effects and full instruction qualification remain open. Generated expectations share the declared model; independent vectors and mutants remain separate evidence.


## PR 711

[#711](https://github.com/riscPrint/risc-v-workstation/pull/711). Merged: 2026-11-13T04:17:41Z.

Title: feat(uvm): add soc virtual scenario libraries

Audit evidence label: unit tests only.

## Summary
Add boot, seeded interrupt-storm, bus-error and reset-during-traffic virtual scenarios in Python/pyuvm and SV UVM. Projects supply live execution and comparison callbacks. Require positive checked evidence. Clear requests/injection and stop traffic on Python failure or cancellation. Use the Python boot sequence in the connected Spinal SoC example.

## Testing
- Scenario unit tests: 7 passed.
- Connected native SoC boot path: 2 passed, 0 skipped, seeds 1 and 7.
- SV package: native Verilator 5.049 lint passed with pinned Accellera UVM.
- Fast set: 967 passed, 1 skipped, 7414 deselected.
- NOT RUN: SV scenario runtime, native SoC interrupt storm/error/reset backends, CPU boot.

## Issues
Refs: #296

Roadmap notes: SoC virtual sequence libraries now have explicit project callback contracts, refusal checks and Python cleanup. The native bus-master example uses the boot sequence for peripheral bring-up. Native architectural SoC IRQ/error/reset qualification remains open.


## PR 712

[#712](https://github.com/riscPrint/risc-v-workstation/pull/712). Merged: 2026-11-13T04:18:05Z.

Title: feat(arch): join custom instruction timing cost and rtl evidence

Audit evidence label: unit tests only.

## Summary

Add `rvw arch custom-tradeoff` and a cancellable MCP tool. Compare baseline and extension timing under one declared workload identity. Join source/config/ELF/trace hashes, software cost, optional saved C1 timing, optional early-PPA reports and independent-check references. Keep missing evidence as `no_checks`. Report model and RTL speedup separately.

## Testing

- Targeted tests: 2 passed. Model-only results retain missing RTL/PPA status. Saved C1 timing gives the expected speedup. A changed ELF hash is refused. PPA source metrics stay separate.
- Fast set: 969 passed, 1 skipped, 7425 deselected.
- NOT RUN: custom instruction execution, new RTL/PPA measurements, compiler builds, gem5 or full Python suite.

## Issues

Refs: #196

Workload equivalence is declared, not proven from different ELF bytes. C1 pass is timing evidence, not a custom-instruction semantic proof. PPA metrics and software costs remain producer declarations. Check artifacts are hashed references and give no aggregate pass. Independent extension correctness and measured PPA campaigns remain open.

Roadmap notes: A single report can join extension timing, software cost and saved RTL/PPA evidence. Missing measurements remain explicit.


## PR 713

[#713](https://github.com/riscPrint/risc-v-workstation/pull/713). Merged: 2026-11-13T04:18:19Z.

Title: feat(soc): export captured implementation handoff data

Audit evidence label: unit tests only.

## Summary
Export captured implementation inputs from SpinalDB as one SoC handoff directory. Include input/dependency copies, RTL file lists, clock/reset and frequency inventories, memory/port inventories, hierarchy, blackbox generics and unresolved blackboxes. Generate SDC with the existing rvw lint backend and retain its findings.

Reject missing or stale RTL content bindings before output. Preserve source/database provenance and validation scope. Ordinary Scala constructor parameters are not captured by SpinalDB; the bundle explicitly records that limit. No implementation or signoff result is claimed.

## Testing
Two targeted export tests passed: a real generated SDC and copied RTL file, and rejection of stale RTL before output. Fast-set result below.

NOT RUN: implementation tools, timing signoff, BOOM, full Python suite or CI.

## Issues
Refs: #193. Ordinary Scala constructor parameter capture remains open.

Roadmap notes: generic SoC handoff export now packages captured inputs and logical SDC intent. Parameter capture and external implementation validation remain separate work.

Fast set: 969 passed, 1 skipped, 7420 deselected in 95.14 seconds.


## PR 714

[#714](https://github.com/riscPrint/risc-v-workstation/pull/714). Merged: 2026-11-13T04:18:32Z.

Title: feat(sim): bisect native vex history with project adapters

Audit evidence label: ran on real core RTL.

## Summary

Allow a captured debug configuration to select core.adapter_versions from a project registry outside historical source trees. Capture that registry and its support files. Resolve its commands inside the captured directory. Preserve exact revision selection, fail closed on unsupported revisions, record manifest_scope in adapter identity and prevent registry state from leaking to another core configuration.

Add a native VexRiscv history recipe. Compile each real revision's VexTop.scala with the fixed private VexRiscv library and SpinalHDL 1.15.0. Bind each generated port inventory, including the old externalInterruptS input. Use matched legacy and M-only project adapters. Add explicit hardware trap-event support to the bounded project probe, retaining trap refusal by default.

## Testing

- Real rvw bisect with endpoint verification found expected commit 6c891a7615b843308e94efb4b4ff5551177f3bda. Its parent 78ba8c540cb0f81030936cefce2faaf6abd65fd7 passed the supervisor-CSR compatibility program: 13 retirements, 38 cycles, 15.7 s adapter time. The M-only endpoint reproduced fail:1: 9 retirements, 36 cycles, 9.2 s. No endpoints skipped. Adjacent revisions required no intermediate trial.
- Correct legacy/m-only adapter selection is recorded in both C1 source identities. C8 includes historical source and project registry dependencies. The outer vex-simsrv lock and nice -n 10 covered native execution. No shared vex lock or sbt compile was used.
- Seven targeted registry and endpoint tests passed, including frozen external registry use and no cross-core registry leak. Repeated after rebase: 7 passed.
- Existing real-core Arcilator/Verilator regression passed in 11.51 s after the optional trap-event changes. Complete C2 byte equality retained.
- Fast set before final fetch/rebase: 893 passed, 1 skipped, 7350 deselected. Command-reference check deferred by brief.
- Initial experiments are explicit: a later CSR-cleanup pair failed the compatibility test on both sides and did not establish a guilty commit. An initial parser refused --mem-latency 1; it was fixed before the successful run.
- NOT RUN: full Python suite, BOOM history, historical regression gates, a non-adjacent search campaign or GitHub CI.

## Issues

Refs: #335, #45. The observed change is the intentional M/S/U-to-M-only configuration transition. It is not a new core bug. This bisects real example configuration history against one fixed upstream VexRiscv library; it does not bisect upstream VexRiscv sources. Core-side interface-stability policy, historical gate support and BOOM qualification remain open.

Roadmap notes: Project-owned captured revision registries now cover source revisions predating adapter manifests. Real native VexRiscv example history has a measured conclusive bisect with matched adapters and actual C1/C2 outputs. No C4 acceptance or cache reuse is claimed.


## PR 715

[#715](https://github.com/riscPrint/risc-v-workstation/pull/715). Merged: 2026-11-13T04:18:44Z.

Title: feat(sec): measure paired operand latency in rtl simulation

Audit evidence label: ran on seeded RTL fixture.

## Summary
Measure operand-paired synchronous RTL unit latency in Verilator. Bind clock, reset, start, done, operands and declared operations. Reset each case independently. Emit measured completion cycles, C3 outcomes and CLI/MCP interfaces. Add required C3 failure signatures to security reports.

## Testing
- Native planted operand-dependent latency and fixed control: 2 passed.
- Targeted policy, result and aggregate tests: 5 passed.
- Fast set: 959 passed, 1 skipped, 7418 deselected.
- NOT RUN: whole-core timing, all Zkt operands, crypto functional validation, warm pipelines or backpressure.

## Issues
No issue closed. Operations and instruction wrappers are project declarations. The tool does not independently validate decoding. A clean sample never means Zkt compliance or security.

Roadmap notes: add native paired latency measurement for declared Zkt wrappers and crypto units. Full operand and pipeline coverage remains open.


## PR 716

[#716](https://github.com/riscPrint/risc-v-workstation/pull/716). Merged: 2026-11-13T04:20:32Z.

Title: feat(soc): link external implementation feedback

Audit evidence label: unit tests only.

## Summary
Import timing, area, CDC and DFT report links bound to an exact SpinalDB hash. Hash report files, preserve tool/scope/constraints, and resolve RTL signals to Scala source locations. Preserve unmatched or ambiguous names with diagnostics. Report imported claims, never workstation signoff.

## Testing
Targeted feedback test passed for matched/unmatched endpoints and rejection of a different database identity. Fast set: 982 passed, 1 skipped, 7452 deselected in 87.86 seconds.

NOT RUN: external implementation/signoff tools, BOOM, full Python suite or CI.

## Issues
Closes: #206

Roadmap notes: external implementation feedback now links typed findings to design identities and retains unmatched names. Imported reports remain external claims.


## PR 717

[#717](https://github.com/riscPrint/risc-v-workstation/pull/717). Merged: 2026-11-13T04:21:22Z.

Title: feat(sec): compare post-boundary isolation observations

Audit evidence label: unit tests only.

## Summary
Add paired PMP/ePMP and privilege-boundary campaign bindings. Require a declared policy, boundary and post-boundary contract start PC. Compare the public suffix while retaining complete per-case RTL/reference checks. Add sec isolation and sec_isolation MCP.

## Testing
- Boundary and missing-binding tests: 2 passed.
- Native Verilator private-state timing leak and clearing control: 2 passed.
- Fast set: 985 passed, 1 skipped, 7456 deselected.
- NOT RUN: native PMP/ePMP, whole-core privilege switches, predictors, caches or BOOM.

## Issues
No issue closed. Project programs and adapters must implement protection setup, mode switches, state cleanup and observation windows. The generic runner does not certify policy or infer CSR semantics. The native fixture is a tiny state model, not a RISC-V core.

Roadmap notes: simulation security can compare post-boundary isolation observations. Native core PMP/ePMP and predictor/cache campaigns remain open.


## PR 718

[#718](https://github.com/riscPrint/risc-v-workstation/pull/718). Merged: 2026-11-13T04:22:09Z.

Title: feat(privilege): add rv32 timer and independent event checks

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add RV32 Sstc low/high CSR matrices and virtual timer pending tests. Add independent timer observation checks to the C1 adapter flow. Require phase witnesses and preserve missing evidence as inconclusive. Keep the contract in the new privilege contract file.

## Testing
- Targeted timer, extension and campaign tests: 37 passed.
- Short native Spike smoke: 140 program/profile runs passed across RV32, RV64, H and environment-control profiles.
- Fast set: 958 passed, 1 skipped. The command reference check is skipped upstream during the parallel push.
- No RTL, BOOM, physical clock or full Python suite run. C1 observer tests use fixtures.

## Issues
Refs: #159, #177. Project adapters must capture an independent timer clock for DUT qualification. Optional latency bounds are project assumptions.

Roadmap notes: Sstc now has RV32 split accesses and positive/negative virtual offsets. C1 qualification requires independent pending observations. Native results establish Spike self-check behavior only.


## PR 719

[#719](https://github.com/riscPrint/risc-v-workstation/pull/719). Merged: 2026-11-13T04:22:55Z.

Title: feat(soc): export memory bist handoff requirements

Audit evidence label: unit tests only.

## Summary
Export memory BIST handoff requirements from the design database: dimensions, ports, clocks/resets, one-bit test mode and declared repair interfaces. Check memory dimensions and control/repair endpoint consistency. Resolve declared isolation connections with the existing formal connectivity reader.

Functional mode isolation remains an explicit unrun proof obligation. The command returns inconclusive. No BIST insertion or manufacturing readiness claim is made.

## Testing
Targeted memory requirement test passed for dimension/endpoint metadata and rejection of a wrong width. Fast set result below.

NOT RUN: functional isolation proofs, BIST insertion, manufacturing tests, full Python suite or CI.

## Issues
Refs: #208. Functional-mode isolation proof remains open.

Roadmap notes: memory BIST metadata and isolation obligations now export from SpinalDB. Metadata consistency is separate from an isolation proof.

Fast set: 982 passed, 1 skipped, 7475 deselected in 94.78 seconds.


## PR 720

[#720](https://github.com/riscPrint/risc-v-workstation/pull/720). Merged: 2026-11-13T04:23:50Z.

Title: feat(sec): check critical faults against security observations

Audit evidence label: unit tests only.

## Summary
Reuse rvw fault for declared critical-register single-bit flips. Require injection confirmation and either a declared detection mechanism or equal architectural and security observations. Keep generic failures, missing observations and unconfirmed injections unresolved. Add CLI/MCP and C3 security outcomes.

## Testing
- Classification boundary tests: 3 passed.
- Native Verilator planted debug-observation leak and parity-protected variant: 2 passed.
- Fast set: 987 passed, 1 skipped, 7474 deselected.
- NOT RUN: whole-core faults, physical attacks, multi-bit faults, clock or voltage glitches.

## Issues
No issue closed. The project owns detection names and observation coverage. Detection alone does not establish that no data escaped before detection. Native tests use a small key register with a synthetic NOP architecture, not a full core.

Roadmap notes: security fault campaigns now reuse the generic fault tool with a separate digital-observation criterion. Physical fault injection remains out of scope.


## PR 721

[#721](https://github.com/riscPrint/risc-v-workstation/pull/721). Merged: 2026-11-13T04:24:49Z.

Title: feat(cosim): capture full vexriscv machine csr state at retirement

Audit evidence label: ran on real core RTL.

## Summary
Add opt-in full machine CSR capture through RVW_VEX_CSR_FULL=1. Select all readable machine CSR mappings from the actual plugin, publish the exact C2 address set, and capture every declared field per retirement. The default remains mscratch-only capture.

Fix capture timing: retain RVFI at the firing edge, then read CSR storage after that edge settles. The native counters exposed the previous pre-edge timing. Across the no-trap probe, mcycle now equals the sampled cycle and minstret equals order+1 without masks or reference overwrites.

## Testing
- Private VexRiscv a62c145aa042a5de874344e0a7683bd7c8c8c870, vex-cosim lock: 2 native capture tests passed. The full inventory has 17 addresses over 17 retirements. Consecutive mscratch writes 7 and 9, mtvec/mepc/mtval writes and reads, counter phase, and four machine identities were checked.
- Full-CSR Spike comparison was run and reports real differences. It is not labelled a match. Unspecified reset storage, implementation identity/trap-vector reset values and clock-driven counters remain separate reference-model work.
- NOT RUN: BOOM, full Python suite, multi-slot RTL, counter rollover and software counter writes, full machine CSR equivalence.

## Issues
No broad issue is closed. The capture is real native evidence; it does not establish complete CSR compliance.

Roadmap notes: The VexRiscv single-slot capture has native post-retirement timing evidence and an optional complete readable machine CSR inventory. Multiple-slot RTL timing and full reference-model alignment remain open.

Fast-set result: 959 passed, 1 skipped, 1 failed, 7414 deselected. The sole failure was rvw/tests/test_docs_site.py::test_docs_staging_does_not_write_sources, in unchanged documentation staging code outside this area. Per the push brief, that unrelated failure does not block publication.

After the timing fix, native DPI regression passed 3 selected tests: clean/fault lockstep and the two complete interrupt cases. Two retained-mtval controls were deselected in that regression because the timing change does not change the known CSR behavior.


## PR 724

[#724](https://github.com/riscPrint/risc-v-workstation/pull/724). Merged: 2026-11-13T04:25:59Z.

Title: feat(soc): bind fabric checks and audit soc connectivity

Audit evidence label: ran on seeded RTL fixture.

## Summary
Bind APB phase/control/data stability assertions to every composed fabric port. Assert exact map decode, one-hot selects and error completion for unmapped requests. Add `rvw soc audit` for exact map interval arithmetic, complete pin bindings, formal IRQ connectivity and rvw lint clock/reset inventory. Export IRQ connection declarations for separate formal campaigns.

Keep structural, map arithmetic and RTL proof results separate. Audit returns inconclusive. Fix the stub to keep the bus idle during interrupt entry, before it starts the next instruction fetch.

## Testing
- Targeted audit test passed for complete ports and rejection of a missing fabric port.
- Native PLIC interrupt example passed with Verilator `--assert` at seed 23: 224 measured loop cycles and 74 retired instructions. This exercised the generated endpoint/decode assertions.
- Fast set result below.
- NOT RUN: RTL decode formal proof, IRQ value-transfer proofs, full Python suite, BOOM or CI.

## Issues
Owner's SoC-level check item. Complete formal proof remains open.

Roadmap notes: all composed APB endpoints now have protocol obligations. Decode/error behavior has bound assertions. The audit combines complete bindings, structural IRQ checks and lint domains without inventing proof results.

Fast set: 987 passed, 1 skipped, 7488 deselected in 100.85 seconds.


## PR 725

[#725](https://github.com/riscPrint/risc-v-workstation/pull/725). Merged: 2026-11-13T04:28:09Z.

Title: feat(privilege): test cfi recovery and shadow stack boundaries

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add landing-pad recovery after a repaired PMP fetch fault. Check saved MPELP, exact PCs, x7 restoration and LPE changes on MRET. Include two-byte-aligned targets when C is present. Expand ordinary landing tests to M-mode MLPE. Cross shadow-stack tests with x1/x5 and add guard, pointer alignment, ordinary load and forbidden fetch cases.

## Testing
- Targeted tests: 33 passed.
- Short native Spike smoke: 82 programs passed: 18 ordinary landing, 16 recovery and 48 shadow-stack programs.
- Fast set: 987 passed, 1 skipped. The command reference check is skipped upstream during the parallel push.
- No RTL, BOOM or full Python suite run. Asynchronous interrupts, Debug Mode, guest CFI, SSAMOSWAP and compressed shadow instructions remain open.

## Issues
Refs: #174, #175. Native self-check results establish reference behavior only.

Roadmap notes: CFI suites now test synchronous interrupted landing state, M-mode MLPE and stack boundary protection with both architectural registers. Project adapters and DUT qualification remain required.


## PR 726

[#726](https://github.com/riscPrint/risc-v-workstation/pull/726). Merged: 2026-11-13T04:28:06Z.

Title: feat(sec): expose security suites with bounded c3 outcomes

Audit evidence label: unit tests only.

## Summary
Expose all security techniques through CLI and MCP. Collect executed security reports into C3 outcomes with per-report failure signatures. Preserve incomplete evidence and reject generated-only gadget manifests. Refuse a clean IFT result when no sink sample was enabled. Resolve optional C6 source-to-sink structural paths with captured database identity. Document each technique's evidence limits and remaining integrations.

## Testing
- Targeted result, C6 path, CLI and MCP tests: 9 passed.
- Native Verilator no-enabled-sink regression: 1 passed.
- All seven security MCP tools load, with no skipped modules.
- Fast set: 991 passed, 1 skipped, 7487 deselected.
- NOT RUN: BOOM, whole-core security campaigns, exhaustive operands, native PMP/ePMP or executed speculative gadget suites.

## Issues
No issue closed. These are bounded simulation techniques. No clean result means secure. Dynamic taint provenance, automatic memory-region bindings, broad fuzz grammars, executed gadget suites and native core PMP/ePMP/Zkt bindings remain open. The C6 path is a structural candidate, not dynamic provenance.

Roadmap notes: add simulation security CLI/MCP and C3 report aggregation. Record the implemented bounded capabilities and retain the listed integration gaps. Physical power and EM remain out of scope.


## PR 727

[#727](https://github.com/riscPrint/risc-v-workstation/pull/727). Merged: 2026-11-13T04:29:52Z.

Title: feat(soc): adopt explicit config fragments from chipyard study

Audit evidence label: unit tests only.

## Summary
Study Chipyard's config fragments, IO/harness binders and simulation flow. Add a short design note with primary documentation links and concrete C1/C2 contribution candidates. Adopt ordered JSON fragments in the SoC composer. Record fragment hashes and the effective configuration. Retain the existing RTL/harness separation.

Follow-up issues: #722 and #723. No upstream issue or PR was sent.

## Testing
11 targeted config/composer tests passed, including merge order, nested-fragment rejection and effective config identity. Fast set result below.

NOT RUN: Chipyard builds/simulations, FireSim, FPGA/ASIC/PPA flows, full Python suite or CI.

## Issues
Closes: #379

Roadmap notes: Chipyard study is complete. Cheap configuration/harness ideas are adopted in the composer. C1 and retirement/C2 adapter contributions are tracked separately.

Fast set: 991 passed, 1 skipped, 7491 deselected in 171.79 seconds.


## PR 728

[#728](https://github.com/riscPrint/risc-v-workstation/pull/728). Merged: 2026-11-13T04:32:39Z.

Title: feat(memory): bind generated model checks to real typed cache ports

Audit evidence label: ran on seeded RTL fixture.

## Summary

Generate the finite permission relation from the exhausted coherence model and record its source SHA256. Bind the generated monitor to real Spinal TileLink ports selected from a real C6 database. Accept C6 simple Bus names only with a declared family, ChannelA through ChannelE structure and exact member paths. Correct B/D param carrier widths and require reset before checking traffic.

Add a small real CacheFiber test with two coherent clients. Extract the database, generate the bind, compile it beside the cache RTL and run owner intervention, racing acquires, releases and backpressure.

## Testing

- Python targeted monitor/model tests: 6 passed. Scripted native Verilator tests include missing reset, stale data, incomplete messages and changed headers.
- `testOnly riscvsim.TypedCacheBindSpec`: 1 passed, seed 42. Observed 2 probes, 4 grants, 4 GrantAcks and 69 stalled cycles.
- Separate native negative run: a changed backing-memory byte caused the generated RTL monitor to stop at its grant-data rule. The library reference accepted the changed byte in that negative case so it could not preempt the generated monitor.
- Fast set: 955 passed, 1 skipped, 7408 deselected. CLI import and MCP listing succeeded without skipped tools.
- Not run: BOOM, production multicore RTL, full Python/Scala suites, long formal, TLC/Murphi, full channel refinement or CI. The generated finite relation checks permission safety only; data and channel checks remain separate.

## Issues

Refs: #363, #128, #361

Roadmap notes: real typed TileLink ports now reach a generated finite-model permission monitor through C6 extraction and SV bind. Full coherent-fabric refinement, production core integration and larger directory campaigns remain open.


## PR 729

[#729](https://github.com/riscPrint/risc-v-workstation/pull/729). Merged: 2026-11-13T04:33:28Z.

Title: feat(privilege): exercise state hierarchy and zeroing behavior

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add RV64 Smstateen hierarchy probes across M/S/U and VS/VU, all four state-enable CSR indices, ENVCFG and Zfinx FCSR gates. Check cause 2 versus cause 22 and preserve access to other indices. Add CBO.ZERO behavior through machine, hypervisor and supervisor CBZE gates. Check the full block, both neighbors and unchanged data on denial. Select the native reference block size from project data.

## Testing
- Targeted tests: 29 passed.
- Short native Spike smoke: 234 programs passed across four profiles. One initial 1-second timeout passed on the final 2-second bounded run.
- Fast set: 1005 passed, 1 skipped. Command reference verification is skipped upstream during the parallel push.
- No RTL, BOOM or full Python suite run.

## Issues
Refs: #176, #177. Other extension-state gates, Ssstateen-only implementations, cache clean/flush/invalidate observations and DUT qualification remain open.

Roadmap notes: State-enable now tests real guest entry, hierarchy priority and independent CSR indices. Environment suites now check a memory-changing extension operation instead of CSR readback alone. Project declarations select writable gates and block size.


## PR 730

[#730](https://github.com/riscPrint/risc-v-workstation/pull/730). Merged: 2026-11-13T04:33:32Z.

Title: feat(formal): run sva progress through liveness-to-safety

Audit evidence label: ran on seeded RTL fixture.

## Summary
Add `formal liveness --backend l2s` for the supported SVA eventual-response front end. Reuse the existing finite-state liveness-to-safety engine. Preserve its state and clock refusals. Record the startup-reset assumption and per-property engine evidence. Engine PASS stays inconclusive until fairness feasibility and non-vacuity have evidence. Engine FAIL reports a lasso counterexample.

## Testing
- 13 frontend tests passed.
- Six native adapter tests passed. These cover paired progress/fault RTL, justice binding, state-range refusal, bounded evidence and the real CLI JSON output.
- Fast set: 978 passed, 1 skipped, 7473 deselected. The skip is the shared command-reference inventory check.
- MCP inventory loaded without skipped modules.
- Not run: full Python suite, BOOM builds or simulation, long formal jobs, fairness feasibility certification, non-vacuity certification or complete SVA qualification. Native Suprove is absent. Native adapter tests used ABC PDR and bounded SMT through the existing engine.

## Issues
Refs: #61
General unbounded SVA and multi-clock sequences remain outside this adapter.

Roadmap notes: The SVA front end can now send Boolean eventual-response obligations to the finite-state liveness-to-safety engine. Results distinguish bounded searches, conditional unbounded engine results and lasso counterexamples. This is a front-end adapter; the deep-proof engine is unchanged.


## PR 731

[#731](https://github.com/riscPrint/risc-v-workstation/pull/731). Merged: 2026-11-13T04:33:39Z.

Title: feat(soc): export register models and scaffold soc projects

Audit evidence label: unit tests only.

## Summary
Add strict IP-XACT register export and `rvw soc new` with CLI/MCP. Include IP-XACT and existing CMSIS-SVD in composed SoC outputs. Add a CPU/memory/known-peripheral device tree and a basic linker section script. Create editable map, binder, sbt, wrapper and project files for a new SoC.

The IP-XACT output is the existing register memoryMap subset, not a full component or bus-interface interchange. The scaffold wrapper is idle. Startup, drivers, production core integration and C1 adapter selection remain project-owned. UART uses a custom subset-compatible string.

## Testing
- 15 targeted composer/config/export/project tests passed. Extended export set: 4 passed, including access/reset/side-effect round trips through the strict importer.
- New scaffold: short locked sbt compile and RTL elaboration passed, 13 seconds after lock acquisition.
- `dtc` accepted board.dts without diagnostics.
- RISC-V GCC linked hello-world with the generated link.ld and memory.ld.
- Fast set result below.
- NOT RUN: Linux boot, full IP-XACT/SVD schema conformance, full Python suite, BOOM or CI.

## Issues
Owner's final SoC export/scaffold item. No issue closed.

Roadmap notes: composition now emits software descriptions and both register interchange subsets. New projects have an editable idle-wrapper scaffold. Full IP-XACT topology, drivers and production-core bindings remain open.

Fast set: 1004 passed, 1 skipped, 7491 deselected in 117.77 seconds.


## PR 732

[#732](https://github.com/riscPrint/risc-v-workstation/pull/732). Merged: 2026-11-13T04:34:31Z.

Title: feat(checks): bind project streams and power in all generation

Audit evidence label: unit tests only.

## Summary
Make checks generate --all emit real instance bindings for reviewed Stream/Flow properties and literal UPF inputs. Resolve Stream/Flow ports, widths and clock/reset controls from the captured database. Require explicit Stream stability contracts and Flow ranges. Preserve per-instance unsupported reasons and unmonitored power domains.

Retain legacy source-only inputs as unbound. Add strict manifest-kind handling and JSON error output. Keep the existing checks_generate MCP tool on the same path.

## Testing
- Project bindings, Stream/Flow generation, CLI JSON errors, native bind elaboration and existing channel-binding cases: 17 passed, no skips.
- Verilator accepted the generated Stream instance bind against a small Top fixture. This is interface-fixture evidence, not extracted design qualification.
- rvw mcp --list exposes checks_generate.
- Post-rebase fast set: 986 passed, 1 skipped, 7496 deselected. The skip is the coordinator's command-reference batch check.
- NOT RUN: project-wide DUT proofs, real extracted Stream campaign, analog/physical power, full Python suite, BOOM builds.

## Issues
Refs: #65, #66, #85, #146

Roadmap notes: One-command generation now supports bound Stream/Flow and UPF inputs in addition to buses, CSR wrappers and microarchitecture rules. Missing contracts and source-only artifacts retain unbound/unsupported status. Generation is not a proof verdict.


## PR 733

[#733](https://github.com/riscPrint/risc-v-workstation/pull/733). Merged: 2026-11-13T04:38:30Z.

Title: feat(memory): build seeded per-hart elf inputs for project adapters

Audit evidence label: unit tests only.

## Summary

Add `rvw memory concurrent-build` and MCP `memory_concurrent_build`. Compile the seeded races, lock loops, AMOs and fences into a separate ELF for each hart. Emit the pinned image manifest, entry and completion PCs, private tohost addresses and the axiomatic initial-state file.

Use disjoint private load segments and identical shared BSS segments. Retain assembly, linker scripts, hashes and compiler logs. Bound all compiler commands by one total budget. The result says `built`, `executed:false`, `rtl:not_run`, `ordering:not_checked`.

## Testing

- Targeted tests: 11 passed. Native RISC-V GCC built seed 7 with 3 harts and 20 generated actions per hart. Tests checked ELF hashes, entry/completion symbols, private segment separation, identical shared BSS segments and all initial locations.
- Fast set: 1014 passed, 1 skipped, 7489 deselected.
- CLI help and MCP discovery passed without skipped tools.
- Not run: RTL execution of these generated images, production multicore integration, BOOM, full suites, CI or long formal. The project adapter must capture complete physical memory dependencies for the axiomatic checker.

## Issues

Refs: #90, #91, #97, #170

Roadmap notes: generated concurrent programs now have ready-to-load per-hart ELF inputs and checker initial state. Project adapters still own runtime bindings, completion capture, dependency observations and declared progress policy. Compilation is separate from memory-ordering evidence.


## PR 734

[#734](https://github.com/riscPrint/risc-v-workstation/pull/734). Merged: 2026-11-13T04:39:07Z.

Title: feat(privilege): schedule reset during in-flight activity

Audit evidence label: unit tests only.

## Summary
Add cold/warm/local reset programs across fetch, load, store, trap and debug phases. Prepare a project operation, wait for independent in-flight state and apply reset on a later reference tick. Release held resources after success or failure. Require phase receipts as well as pulse/state capture before C1 qualification. Match C1 inputs before result uniqueness.

## Testing
- Targeted tests: 42 passed.
- Compiled 15 reset programs. Spike CLI cannot drive project reset pulses or in-flight device/debug phases.
- Fast set: 1023 passed, 1 skipped. The command reference check is skipped upstream during the parallel push.
- No RTL, BOOM, full Python suite or physical reset run. Driver and C1 evidence checks use fixtures.

## Issues
Refs: #111. Project adapters must implement the declared preparation, cleanup and state bindings. Missing observations remain inconclusive. A RAM cookie requires actual restart; simulator construction is not reset evidence.

Roadmap notes: Reset suites now cover repeated reset during declared transaction, trap and debug activity. The generic driver checks preparation and observed state before the pulse. No DUT qualification is claimed.


## PR 735

[#735](https://github.com/riscPrint/risc-v-workstation/pull/735). Merged: 2026-11-13T04:39:25Z.

Title: feat(formal): prove safety with global uninterpreted arithmetic

Audit evidence label: ran on seeded RTL fixture.

## Summary
Add typed global uninterpreted multiplication and division to native SMTBMC safety jobs. One function per operator and operand width preserves consistency across states and properties. An abstract failure stays inconclusive. An empty operator list checks the original arithmetic. Add CLI, MCP, doctor feature and shared report contracts.

## Testing
- Fast set before final fetch/rebase: 907 passed, 1 expected command-reference skip, 7358 deselected.
- Targeted transformer, portfolio and doctor tests: 19 passed. After rebase: transformer and doctor 11 passed. MCP list has no skipped warning.
- Native pipeline and fault test: passed. Four native solvers (Yices, Z3, cvc5, Bitwuzla) each proved the two-operation registered multiplier pipeline. Signed division also proved. A division identity stayed unknown with UFs and proved concretely. A faulty pipeline stayed unknown with UFs and failed concretely. Each stage used a 12 s timeout and nice priority.
- Full suite, BOOM, long proofs, capacity comparison and CI waits NOT RUN.

## Issues
Refs: #21, #294. IC3 lemma reuse and native fair liveness remain open. This is not a whole-core or performance result.

Roadmap notes: native typed UF overapproximations now prove safety with globally consistent arithmetic functions. Reports preserve SMT witness metadata and retain source assumption limits. No arithmetic speedup or full-block capacity claim.


## PR 736

[#736](https://github.com/riscPrint/risc-v-workstation/pull/736). Merged: 2026-11-13T04:40:55Z.

Title: feat(formal): export compiler patches and spike custom models

Audit evidence label: unit tests only.

## Summary
Generate compiler patches and a loadable Spike extension from pure custom instruction manifests. Pinned source inputs enable GCC unspec and builtin registration and LLVM instruction and IR intrinsic includes. Unpinned output records a fragment-only gap. Preserve exact source revisions and hashes. Add RV32/RV64 examples and calling convention checks.

## Testing
- Targeted custom/backend/command tests: 20 passed, 1 skipped. Native checks compile generated plugins, check all seven expression operators at both XLENs, execute cross-compiled C calls in Spike, and reject execution without the plugin. Captured shim and extension identities remain required.
- Patches apply with git apply to hash-pinned GCC 15.2 and LLVM 21.1 sources at both XLENs.
- Fast set: 978 passed, 1 skipped, 7472 deselected in 151.72s (0:02:31).
- NOT RUN: GCC or LLVM builds, DUT execution, stateful version-2 backend generation, full Python suite, BOOM jobs, GitHub CI wait.

## Issues
Refs: #169, #155

Compiler build and runtime feature qualification remain open. These exports support pure R-type RV32I/RV64I instructions only. Generated artifact licensing is not specified; upstream compiler licenses are recorded and the installed Spike license is not verified.

Roadmap notes: Custom instruction manifests now export pinned compiler patches and native Spike extensions. Native compiled calls work at both XLENs. Full compiler builds and stateful backend support remain open.


## PR 737

[#737](https://github.com/riscPrint/risc-v-workstation/pull/737). Merged: 2026-11-13T04:43:09Z.

Title: feat(cosim): verify native dpi flow on vexiiriscv

Audit evidence label: ran on real core RTL.

## Summary
Exercise the generic native DPI client and C2/Spike flow on the different VexiiRiscv core. Add only project-owned mailbox bindings and native controls. Allow a private lock and preserve controls in C1 replay.

Preserve the probe's one-retirement next-PC lookahead. Buffer events until that unresolved retirement permits cycle-ordered publication. Run transport after probe callbacks sample the core, and drain the final record before native shutdown. Report the actual observed interrupt trap value instead of fabricating zero.

## Testing
- Private core 9f70315deb3390b283995c5b8f1bd38215ecf52b, SpinalHDL de72faf6062206a89b445e5cc07e32ed982712c8, rvls 847ce99fd2b28a5c0ccb1ec2683311cf97a9fefc. Fetch complete private Spinal history rather than waiving C8's shallow-history rejection.
- Native ISA: 49 passes, 49 complete Spike matches, 17,637 instructions, zero synchronizations or masks.
- Native DPI clean/fault control passed: complete clean match, injected writeback difference at order 1 with only orders 0 and 1 published. The stated lookahead permits an additional RTL retirement before the stop.
- Scala C2BackendSpec: 2 passed.
- Fast set: 985 passed, 1 skipped, 1 failed, 7485 deselected. The unchanged out-of-area failure is test_docs_site.py::test_docs_staging_does_not_write_sources. It does not block publication under the push brief.
- NOT RUN: BOOM, full Python suite, multi-lane configurations, VexiiRiscv CSR snapshots, Debug Module comparison.

## Issues
No broad genericity issue is closed by two bounded configurations. The README records the lookahead and capture limits.

Roadmap notes: A second core now runs through the same native DPI transport and Spike checker, with independent ISA and fault controls. Its source is a whitebox retirement probe rather than RVFI. Per-retirement CSR capture and debug remain separate bindings.

Native interrupt controls: 2 passed. Both begin with mtval=7, compare the actual trap value and an actual handler CSR readback of zero, execute MRET, and require complete Spike matches. Input assertion at 200 and deassertion at 220 were checked in C2.


## PR 738

[#738](https://github.com/riscPrint/risc-v-workstation/pull/738). Merged: 2026-11-13T04:43:17Z.

Title: feat(formal): lower unbounded sva progress automata

Audit evidence label: ran on seeded RTL fixture.

## Summary
Extend `formal liveness` with Boolean until operators and single-clock unbounded sequence progress automata. Support unbounded delay, consecutive repetition, literal goto/nonconsecutive counts, one Boolean completion and outer first_match. Support non-overlapped implication. Preserve the implicit weak sequence default and explicit strong completion. Retain overlapping requests with count buckets and a separate set for old obligations. Extend the generated support table from the tested corpus.

## Testing
- 41 frontend, oracle and support-table tests passed.
- 24 paired native engine jobs passed across 12 operator forms. After a declaration-order fix for Icarus, all 12 emitted-monitor trace tests passed. Fourteen paired native jobs also passed after that fix.
- The trace tests distinguish weak/strong, goto/nonconsecutive and inclusive/exclusive until. Exhaustive short lasso oracles cover overlapping goto obligations for counts 1, 2 and 3.
- Fast set: 1040 passed, 1 skipped, 7530 deselected. The skip is the shared command-reference inventory check.
- CLI import and MCP inventory passed after rebase. No skipped MCP module.
- Not run: full Python suite, BOOM builds/simulation, long formal jobs, native Suprove, fairness feasibility certification or complete SVA qualification. Each native engine job uses a small finite-state fixture and a 30-second limit.

## Issues
Refs: #61
General nested sequence composition, repetition count ranges, multi-clock sequences, reset cancellation and local captures or sampled functions inside this unbounded adapter remain refused. Existing finite lowering retains its separate support for those sampled functions and bounded local captures.

Roadmap notes: The formal frontend now lowers a tested unbounded single-clock SVA subset through native live predicates or the existing liveness-to-safety engine. It preserves strong and weak language semantics and overlapping requests. Engine passes retain the frontend's conditional/inconclusive limits.


## PR 739

[#739](https://github.com/riscPrint/risc-v-workstation/pull/739). Merged: 2026-11-13T04:45:28Z.

Title: feat(privilege): probe pma crossings and atomic access policies

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add explicit project PMA scalar and atomic probes with cause/PC/mtval checks and optional write readback. Compare complete probe-window bus sequences, including split transfers at other addresses. Permit small MMIO regions. Add PMP capability selection for granularity/address modes and initialize the fallback TOR lower bound.

## Testing
- Targeted tests: 31 passed.
- Short native Spike smoke: 14 CLINT PMA programs, 394 base PMP programs and 264 programs with coarse PMP regions passed. Spike itself uses its installed grain; the coarse-region run does not qualify a hardware grain.
- Paired stale-pmpaddr6 reproduction: old bootstrap failed; explicit lower-bound initialization passed.
- Two custom crossing programs compiled. Native reference remains inconclusive for that project map.
- Fast set: 1047 passed, 1 skipped. Command reference verification is skipped upstream during the parallel push.
- No RTL, BOOM or full Python suite run. Independent bus/device capture tests use fixtures.

## Issues
Refs: #112, #138. Custom PMA conflicts use project-declared outcomes. Cacheability, idempotency and physical device effects still require project observation. Native results do not earn DUT groups.

Roadmap notes: PMA suites can test declared crossing/conflict and atomic access policies with complete bus observations. PMP supports selected granularity and excludes unavailable NA4. The fallback no longer depends on an unstated address-register reset value.


## PR 740

[#740](https://github.com/riscPrint/risc-v-workstation/pull/740). Merged: 2026-11-13T04:46:10Z.

Title: feat(cov): guide stimulus with native code coverage goals

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary

Guide the bounded stimulus controller with native Verilator counter holes through an optional pinned `code_plan`. Use the existing UCB recipe policy and complete C1/Spike qualifier. Require exact ELF/trace/plan/RTL/sample receipts and fresh-counter reset evidence. Preserve point semantics, source hashes and the complete native denominator. Capture the template and source files before initial state publication.

Report unsupported targets, unobserved RTL/code goals, uncompleted RTL sequences and pending activations separately from ISA hits. Intersect generator support with the declared semantic plan. Read owned C1/C3 members rather than captured input fixtures named result.json.

## Testing

- Targeted controller/guidance/ownership tests: 67 passed. Repeated after rebase.
- Required fast set: 965 passed, 1 skipped, 7412 deselected. The skip is the main branch's deferred command-reference comparison.
- Initial fast run: 963 passed, 1 failed, 1 skipped. Existing docs staging discovered the generated root `.pytest_cache/README.md` as a tool README. Removed this worktree's generated cache and reran successfully. No docs tool source was changed.
- `rvw mcp --list`: no skipped registrations. `git diff --check`: passed.
- NOT RUN: DUT/native Spike feedback campaigns, paired random comparisons, CPU descendant qualification, core builds, full Python suite, GitHub CI. Native counter ingestion tests use a C1 fixture and real counter reader. They do not establish adapter collection/reset behavior.

## Issues

Refs: #353, #349. Native adapter hooks and paired closure-rate acceptance remain open. The existing campaign CLI/MCP settings carry the new optional code plan. No cosim or core sources changed.

Roadmap notes: Code and RTL goals now guide the bounded integer/sequence controller with separate full denominators and unsupported goals. Native feedback validation, complete cost accounting and comparative closure measurements remain unverified.


## PR 741

[#741](https://github.com/riscPrint/risc-v-workstation/pull/741). Merged: 2026-11-13T04:47:03Z.

Title: feat(sim): add generic n-hart shared-memory execution loop

Audit evidence label: unit tests only.

## Summary

Add `MultiHartExecutor` in the generic RiscvSim harness. A project binds reset, shared memory, boot vectors, cycle steps, completion and parking through `MultiHartBackend`. The loop loads all captured images before release and captures independent per-hart RVFI through C2/2. It can also capture accepted boundary events.

A completed hart is parked while other harts continue. Cycle and wall limits record unfinished harts as timeout. Failed harts retain their status. Missing probes fail before memory loading or release. Dependency and physical-address declarations remain unavailable unless the project supplies them.

## Testing

- Executor unit tests: 7 passed. Covers three sparse hart IDs, per-hart order, shared load before release, failure, cycle limits, wall limits, late completion and the driver's timeout flag.
- Native Verilator smoke: 1 passed, seed 7, three RV64 subset RTL harts from three ELF images and one RAM. The public Python serialized-memory checker confirmed all 6 accepted memory actions. This is a subset fixture, not a production core or weak-memory design.
- Fast set: 1026 passed, 1 skipped, 7510 deselected.
- CLI import and MCP listing succeeded without skipped tools.
- Not run: production multicore core bindings, BOOM, full suites, dynamic HSM in this fixed-hart loop, weak-memory RTL qualification, long formal or CI. The first native test attempt timed out in a fixture reset wait; raw clock-edge waits fixed it.

## Issues

Refs: #90, #151

Roadmap notes: the generic production harness now owns the N-hart image-load, reset/release, per-hart capture, completion and timeout loop. Project signal bindings remain necessary. A three-hart native subset validates the shared-memory path. Dynamic lifecycle transitions remain a separate observer and project binding task.


## PR 742

[#742](https://github.com/riscPrint/risc-v-workstation/pull/742). Merged: 2026-11-13T04:47:28Z.

Title: feat(formal): check mixed-width datapaths and rtl definedness

Audit evidence label: ran on seeded RTL fixture.

## Summary

Check mixed-width unit ports against the symbolic C reference. Input padding adds fresh symbolic high bits; result padding adds zeros. Add source-format case widths and the normal FP input class. Include the SoftFloat exception source called by RISC-V NaN conversion macros.

Track literal X/Z propagation through the Boolean C model. Require defined outputs, flags and completion before either proof or DUT counterexample. Observable unknowns stay inconclusive. Initial registers keep their existing arbitrary binary state.

## Testing

- Native mixed-width, definedness and bounded datapath tests: 23 passed. Includes full-domain F32-to-F64 conversion against pinned SoftFloat, normal/subnormal splits, a signaling-NaN flags mutant, one-bit F32 equality, symbolic input padding and reachable-X negatives.
- Existing native datapath tests: 9 passed.
- Required fast set: 976 passed, 1 skipped. The command-reference check is deferred by the parallel-push brief.
- MCP discovery after rebase: no skipped modules.
- Not run: BOOM builds/simulations, full Python suite, project FPU qualification or long formal runs.

## Issues

Refs: #19

Roadmap notes: mixed-width FP bindings and literal-definedness obligations now work in the Boolean C backend. F32 conversion fixtures pass with values and flags. Project FPU implementations and all-operation qualification remain open. Reconvergent unknown propagation can conservatively return inconclusive.


## PR 743

[#743](https://github.com/riscPrint/risc-v-workstation/pull/743). Merged: 2026-11-13T04:47:44Z.

Title: feat(formal): run native fair liveness reductions

Audit evidence label: ran on seeded RTL fixture.

## Summary
Add native fair AIGER justice checks with exact full-state liveness-to-safety, sufficient k-liveness, and the experimental rIC3 rlive adapter. Preserve invariant constraints and all fairness goals. Require a fair infinite path before a proof with constraints or fairness can pass. Add CLI, MCP, doctor features and report contract.

## Testing
- Fast set before final fetch/rebase: 1061 passed, 1 expected command-reference skip, 7518 deselected.
- Targeted adapter, exhaustive small-model reductions and doctor: 22 passed, also after rebase.
- Native reference adapter tests: 3 passed. L2S proved toggle and fair input progress, found accepting cycles for stuck and unfair progress, and kept impossible fairness inconclusive. K-liveness at k=4 proved both good cases, kept both reached bounds inconclusive, and rejected impossible fairness. Each stage used nice priority and a 12 s timeout. Raw results: /tmp/deep-aiger-native4/.
- Important native limitation: pinned rIC3 rlive errors on all five references because its internal --no-ic3-pred-prop option is unsupported. Tests check that those engine errors stay inconclusive. No engine source patch was made.
- Full suite, BOOM, long proofs, SVA translation, independent certificate validation and CI waits NOT RUN.

## Issues
Refs: #21, #294. IC3 invariant export/reuse and broader capacity remain open. This does not certify whole-core liveness.

Roadmap notes: exact native finite-state fair liveness and sufficient k-liveness now run through rIC3 IC3 on pinned AAG inputs. An infeasible environment cannot earn pass. Native rlive is wired but not qualified at the pinned revision.


## PR 744

[#744](https://github.com/riscPrint/risc-v-workstation/pull/744). Merged: 2026-11-13T04:51:57Z.

Title: feat(formal): replay raw asynchronous property events

Audit evidence label: ran on seeded RTL fixture.

## Summary
Add explicit top-input raw property events to Icarus timed simulation: input changes, falling edges and event lists. Sample all supported top-level property clocks before each input update in such a job. Preserve old values of event inputs and other changing clocks. Record the event bindings in C1. Remove stale coverage and runtime logs before each run.

## Testing
- 23 native replay and guard tests passed across the final targeted runs. These include the existing two-backend suite, paired old-value assertions, mixed-clock sampling, four-state edge observations and failed-compile artifact clearing. The last guard update separately passed 13 tests.
- Fast set: 1084 passed, 1 skipped, 7559 deselected. The skip is the shared command-reference inventory check.
- Not run: full Python suite, BOOM builds/simulation, long formal jobs or raw-event qualification on Verilator. Internal/hierarchical events, checker/bind replay, same-event disable cancellation and general asynchronous formal state semantics remain refused.

## Issues
Refs: #46, #61
This adds finite native event observations. Multi-clock formal state loading, general multi-clock sequences and additional async state types remain separate gaps.

Roadmap notes: Timed assertion simulation now supports explicit top-input asynchronous events with pre-update sampling and four-state edge rules. It records finite pass/fail/cover observations in C1 and retains the existing coverage route. This does not change the solver's sampled event model.


## PR 745

[#745](https://github.com/riscPrint/risc-v-workstation/pull/745). Merged: 2026-11-13T04:52:02Z.

Title: fix(memory): refuse axiomatic verdicts across unmodelled events

Audit evidence label: unit tests only.

## Summary

Refuse scalar axiomatic verdicts across independent reset epochs, trap events and external maintenance events. The checker previously discarded these capture records. In particular, it could pair an LR before reset with an SC after reset and return `allowed`.

These unsupported profiles now return `inconclusive` with a reason. Initial reset records and ordinary single-epoch RVWMO/Ztso executions remain supported.

## Testing

- Reproduced all three gaps before the fix: 3 regression failures, 1 ordinary execution passed. Each unsupported execution incorrectly returned `allowed`.
- Targeted tests after the fix: 31 passed. Covers both models, ordinary execution, all 12 pinned outcome sets and existing axiomatic tests. Native RISC-V GCC fragment compilation also passed.
- Fast set: 1113 passed, 1 skipped, 7581 deselected.
- Not run: production multicore RTL, BOOM, full suites, CI, native herd differential or reset/maintenance axiomatic semantics. Those semantics remain unsupported; this change does not invent them.

## Issues

Refs: #90, #91, #103

Roadmap notes: scalar ordering verdicts now refuse unsupported reset, trap and maintenance domains. A full model across those domains remains open.


## PR 746

[#746](https://github.com/riscPrint/risc-v-workstation/pull/746). Merged: 2026-11-13T04:54:04Z.

Title: feat(formal): prove finite state encoding relations

Audit evidence label: ran on seeded RTL fixture.

## Summary

Add finite state-encoding tables to `rvw formal equiv` and MCP. Observe the captured internal registers without changing their logic. Prove their table membership and decoded relation together with all original outputs. Never assume the relation or add internal equality cutpoints. This supports binary-to-one-hot state changes.

Capture mapping input, normalized models, widths and evidence. A failed mapping query stays inconclusive because a bad hint does not prove an original output difference.

## Testing

- New state-encoding tests: 10 passed. Native binary/one-hot equality, wrong mapping, missing reachable value, output mutant and no-hint cases. Unit checks reject ambiguous value tables.
- Existing native equivalence tests: 22 passed.
- Required fast set: 1091 passed, 1 skipped. The command-reference check is deferred by the parallel-push brief.
- MCP discovery: no skipped modules.
- Not run: BOOM builds/simulations, full Python suite, long formal jobs or project FSM qualification.

## Issues

Refs: #18

Roadmap notes: explicit finite state-encoding relations now become checked closed proof obligations. Existing automatic register matching remains available. Automatic state recoding inference, memory refinement and scalable internal partition dependency proofs remain open.


## PR 747

[#747](https://github.com/riscPrint/risc-v-workstation/pull/747). Merged: 2026-11-13T04:55:11Z.

Title: feat(privilege): check plic interrupt delivery with native spike

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add actual M/S PLIC interrupt-delivery programs for global masking, local masking and threshold blocking. Check pending state, trap cause/PC/status, claim/complete, return and retained registers. Add bounded native Spike ISA execution with a Python PLIC and captured shim inputs. Preview side-effecting reads so an IRQ before a claim cannot consume it.

## Testing
- Targeted tests: 37 passed.
- Six programs compiled and passed native Spike ISA self-checks with the Python PLIC. M-mode and S-mode IRQ entry and full stimulus completion were observed. Results are model-based.
- Python controller expectations passed for all six scenarios.
- Fast set: 1089 passed, 1 skipped. Command reference verification is skipped upstream during the parallel push.
- No RTL, BOOM or full Python suite run. This does not qualify native Spike PLIC behavior, RTL arbitration or real-core delivery.

## Issues
Refs: #131. Concurrent context races and a connected RTL/core adapter remain open.

Roadmap notes: PLIC suites now include firmware interrupt delivery and return through machine/supervisor vectors. The native backend uses the captured Spike ISA model and an explicitly identified Python controller. Model results never earn DUT coverage.


## PR 748

[#748](https://github.com/riscPrint/risc-v-workstation/pull/748). Merged: 2026-11-13T04:55:36Z.

Title: perf(sim): capture and measure native verilator profiles

Audit evidence label: ran on real core RTL.

## Summary

Add captured opt-in scalar native build profiles: private ccache, explicit hierarchical Verilation, threads 2/4 and Clang compiler PGO capture/reuse. Freeze configuration, RTL, SDK settings, make rules, training ELF and raw/merged profile bytes with the capture library. Bind reuse to exact input/tool hashes and flags. Reject stale digests, PROFOUTOFDATE and compiler outdated/unprofiled diagnostics. Use scalar-native-profile-v3. Keep the production Spinal collector and its external-input refusals unchanged. These probe build records cannot earn C4 acceptance or model-cache reuse.

Link the Make-produced runtime archive directly. This avoids a duplicate runtime compilation and includes zero-count runtime units in compiler training. Preserve the C++ driver name and selected SDK. Pass the captured launcher to hierarchical sub-builds. Report build/setup time, execution plus C2 time, child-process RSS and applied probe profile metadata.

## Testing

- Eight actual VexRiscv profiles passed 17 retirements in 81 cycles with seed 7. Every complete C2 file was byte-identical to the earlier independent Arcilator reference. The README contains exact measurements, cache counters, source/input hashes and a build-time chart.
- Final ccache sample: cold build/setup 15.221 s; warm 4.429 s with 3 direct hits and 1 miss. These are individual build observations, not a qualified runtime speedup.
- Hierarchical external port access passed. Compiler PGO wrote raw counters, merged them and reused the bound profile successfully with strict warnings retained. The first training path omitted an unused runtime unit and was rejected; archive linkage fixed the cause instead of waiving the diagnostic.
- Native profile/scalar/report regressions: 6 passed in 10.82 s. Existing real-core paired-engine regression: 1 passed in 10.25 s. After rebase: 4 capture/report tests passed.
- Fast set before final fetch/rebase: 977 passed, 1 skipped, 1 failed, 7451 deselected. The untouched test_docs_site.py::test_docs_staging_does_not_write_sources includes untracked .pytest_cache/README.md as a tool page, but staging copies tracked files only. The work brief permits unrelated fast failures. The command-reference check is deferred.
- Native runs used vex-simsrv, nice -n 10 and two build jobs. Tools: Verilator 5.049, Apple Clang 21.0.0, ccache 4.14.3, macOS ARM64.
- NOT RUN: full Python suite, held-out/long alternating runtime pairs, intervals, winner confirmation, thread-scheduling PGO, Scala/elaboration costs, BOOM presets or GitHub CI.

## Issues

Refs: #74, #344. Short execution samples do not qualify a runtime winner. No runtime optimization is retained. The experiment qualifies captured profile plumbing and records measured build samples. Production Spinal hierarchy/internal bridge access, production PGO, broader input closure and BOOM speed qualification remain open.

Roadmap notes: VexRiscv has measured before/after compiler-cache builds and native thread, hierarchy and compiler-PGO profiles with complete C2 equality. The scalar profile namespace binds training inputs and rejects stale profiles. Default build options remain flat and unprofiled.


## PR 749

[#749](https://github.com/riscPrint/risc-v-workstation/pull/749). Merged: 2026-11-13T04:57:06Z.

Title: feat(formal): export and reuse cone-matched pdr invariants

Audit evidence label: ran on seeded RTL fixture.

## Summary
Export ABC PDR invariant cubes, map supported cubes to named RTL bits, and certify them in a separate unbounded job with the original assertions removed. Save the predicates with complete transition-cone hashes. Select matching entries for related properties and design revisions. Helpers stay assertions and every target needs a fresh native proof. Add CLI, MCP, doctor feature and shared contracts.

## Testing
- Fast set before final fetch/rebase: 1112 passed, 1 expected command-reference skip, 7584 deselected.
- Targeted cone, PLA mapping, portfolio and doctor tests: 18 passed, also after rebase. MCP list has no skipped warning.
- Native test: 1 passed in 3.63 s. It covers export and separate certification, reuse across a related property and a revision with an unrelated output counter, stale-cone rejection followed by a concrete target failure, and refusal of source assumptions. Each stage used a 12 s timeout and nice priority. Raw results: /tmp/deep-ic3-native-tests/.
- Full suite, BOOM, long proofs, performance comparison and CI waits NOT RUN.

## Issues
Refs: #21, #294. The supported library is for mapped zero-based RTL bit predicates without source assumptions. Auxiliary/inverted/unmapped PDR state, memories and unsupported cones cannot be reused. No whole-block capacity or speedup claim.

Roadmap notes: property-directed PDR invariant export and fresh certification now produce a reusable cone-keyed predicate library. Cached predicates are selected across related properties and revisions only when their full transition dependencies match. No cached verdict or unchecked assumption is introduced.


## PR 750

[#750](https://github.com/riscPrint/risc-v-workstation/pull/750). Merged: 2026-11-13T04:57:41Z.

Title: feat(formal): export sail fp csr and privileged entry slices

Audit evidence label: ran on seeded RTL fixture.

## Summary
Compile 18 pinned Sail kernels and project-bound result checkers: H/S/D FSGNJ/FSGNJN/FSGNJX, RV32 CSR write values and access intents, and MRET/SRET/WFI entry decisions. Record source text, lines, hashes, compiler identity, widths and excluded effects. Add CLI and MCP registration in a separate command module.

Keep reachable packed types and enum constants in generated SV. Namespace them per kernel. Use named instance ports because typed enum inputs were reordered during native Yosys elaboration. Refuse live exception logic and remove only unreferenced exception output declarations.

## Testing
- Native Sail 0.20.1 generation from sail-riscv 549e723031b34b5ffea5bbb56367be15c7a38a9e: all 18 kernels generated.
- Native state-slice tests: 40 passed, zero skipped. This includes 18 arbitrary-input correct-kernel checks and 18 deliberately wrong-result failures. Each proof has a 60-second limit. Combined compilation of all 18 generated models: 1 passed, zero skipped.
- Regenerated Zicond regression: 13 passed, zero skipped. Zicond model files remain byte-identical to the prior native baseline.
- Regenerated bit-manipulation regression: 39 passed, zero skipped. Zbc retains its explicit zero/one-hot multiplier basis restriction.
- Fast set: 1045 passed, 1 skipped, 7559 deselected. The command reference check is deferred by the worker brief. MCP discovery has no skipped-module errors.
- NOT RUN: full Sail-machine compilation/proof, full FP arithmetic/rounding/flags, DUT binding, FP unboxing, CSR legality/WARL/destination effects, return-state/target checks, WFI timeout/wakeup, BOOM jobs, full Python suite, CI wait.

## Issues
Refs: #64

This does not close #64. CSR and privileged exports cover declared slices, not complete architectural transitions. Each checker needs a project binding to decoded operands and observed effects. Full FP arithmetic still needs a bit-exact export without SoftFloat.

Roadmap notes: Sail generation now covers SoftFloat-free H/S/D sign results, RV32 CSR value/access intents and privileged entry decisions. Correct and deliberately wrong kernels have native bounded checks. Full machine state and DUT qualification remain open.


## PR 751

[#751](https://github.com/riscPrint/risc-v-workstation/pull/751). Merged: 2026-11-13T04:58:43Z.

Title: feat(formal): load trace state for timed event replay

Audit evidence label: ran on seeded RTL fixture.

## Summary
Let timed simulation load explicit flat register state from a captured VCD or FST. Check every initial input against the trace, including clock phase and reset level. Require complete DUT register-bit coverage. Preserve four-state values and report the loaded registers and trace hash in C1. Start property histories after setup and state deposit, so setup cannot count as an assertion attempt.

## Testing
- 37 targeted tests passed across state loading, existing timed simulation and raw-event replay. Six state-loader unit tests also passed after the final nested-width declaration fix.
- Native tests cover two clocks, an asynchronous reset pulse, unknown loaded state resolved on another clock, VCD/FST decoding, incomplete-state refusal, input-phase refusal, assertion continuation and a high initial clock with no setup assertion.
- Fast set: 1124 passed, 1 skipped, 7592 deselected. The skip is the shared command-reference inventory check.
- Not run: full Python suite, BOOM builds/simulation, long formal jobs or formal solver state loading. No reachability proof is claimed. Memories, child-module state, derived clocks and internal asynchronous controls remain refused.

## Issues
Refs: #46
This adds finite native multi-clock continuation and X analysis from trace state. Formal from-sim state loading for multi-clock models and additional async state types remain open.

Roadmap notes: Timed event replay can resume complete flat register state from simulation traces and measure four-state outputs across independent clock and asynchronous reset events. C1 records exact state inputs and coverage. The formal solver's state-loading scope is unchanged.


## PR 752

[#752](https://github.com/riscPrint/risc-v-workstation/pull/752). Merged: 2026-11-13T04:59:34Z.

Title: feat(formal): audit internal reset values and initial-state paths

Audit evidence label: unit tests only.

## Summary

Add `rvw formal reset-audit` and automatically discovered MCP `formal_reset_audit`. Apply one synchronous reset clock to a Boolean abstract model. Inventory fixed zero/one values per retained register bit. Distinguish nonconstant reset data from remaining dependencies on initial state.

Follow possible initial-state and literal-X/Z influence to outputs for 0..64 further clocks. Controlling values remove masked paths. The result stays inconclusive: this is a conservative analysis, not reachable-counterexample or whole-design proof evidence. Existing initialization pair proofs remain the route for native observation-independence proof.

## Testing

- Native reset-audit tests: 9 passed. Both reset polarities, fixed/data/X reset values, masked state, later overwrite, and unsupported clock/latch/assumption/init cases.
- Required fast set: 1132 passed, 1 skipped. Command-reference regeneration is deferred by the parallel-push brief.
- MCP discovery: no skipped modules.
- Not run: BOOM builds/simulations, full Python suite, long formal jobs or project reset qualification. This app invokes Yosys but no solver.

## Issues

Refs: #20

Roadmap notes: internal-register reset-value coverage and bounded conservative initial-state output paths now complement xprop and the native initialization pair app. Counts cover retained mapped state only. Correlations can leave extra paths. Dynamic reset sequences and whole-design qualification remain open.


## PR 753

[#753](https://github.com/riscPrint/risc-v-workstation/pull/753). Merged: 2026-11-13T05:00:18Z.

Title: feat(memory): connect concurrent programs to project run and checker

Audit evidence label: unit tests only.

## Summary

Add `rvw memory concurrent-run` and MCP `memory_concurrent_run`. Build seeded per-hart programs, invoke an explicit project C1 adapter and feed captured C2 to the independent RVWMO or Ztso checker. One total budget bounds compilation, adapter execution and candidate search.

Require matching C1 config, seed, cycle limit and image hashes. Require matching C2 image hashes, entry PCs, completion PCs and retired instruction bytes from pre-launch ELF snapshots. Missing observations, timeouts and inconsistent checker exit codes cannot return `allowed`. Keep compiler, adapter and checker reports and logs.

## Testing

- Targeted campaign/build tests: 31 passed. Control tests use synthetic C1/C2 adapters and the actual scalar checker. They cover both models, forbidden reads, incomplete harts, missing dependencies, input and instruction mismatches, replaced input files, process failures and total-budget expiry.
- Native RISC-V GCC built seed 7, 3 harts, length 20 and verified all ELF/load/reference metadata in the targeted build test.
- CLI help and MCP discovery passed without skipped tools.
- Fast set: 1146 passed, 1 skipped, 7586 deselected.
- Not run: this full campaign on a production multicore adapter, BOOM, full suites, CI, native herd differential or long formal. The earlier three-hart executor smoke is separate native evidence. The workflow unit tests do not establish a production DUT result. Project adapters still own full physical dependency capture and architectural reference comparisons.

## Issues

Refs: #90, #91, #97, #170

Roadmap notes: the random concurrent-program generator now has one bounded build/run/check command. It binds the generated images to a C1/C2 capture before checking finite ordering. Production multicore signal bindings and runtime qualification remain open.


## PR 754

[#754](https://github.com/riscPrint/risc-v-workstation/pull/754). Merged: 2026-11-13T05:03:18Z.

Title: feat(privilege): exercise reri status transactions and counters

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add RERI v1.0 status-write protection, SRDP/SINV race, logging-disable and 16-bit CE counter programs. Initialize records explicitly. Bind wide expected values as hex strings. Run the actual ELF through captured native Spike ISA execution with the Python RERI device. Share the bounded MMIO runner with PLIC while keeping device models separate.

## Testing
- Targeted tests: 43 passed.
- Seven RERI programs passed native Spike ISA self-checks with the Python RERI model and a nonzero valid starting record. Results are model-based.
- Rechecked all six PLIC delivery programs through the shared runner: passed, model-based.
- Reference tests cover four starting record values, valid-write protection and counter signaling expectations.
- Fast set: 1142 passed, 1 skipped. Command reference verification is skipped upstream during the parallel push.
- No RTL, BOOM, full Python suite, physical error injection or RAS signal delivery run.

## Issues
Refs: #181. Other counter widths, information-register payloads, poison propagation and DUT recovery remain open. The native device model does not claim a universal reset value or a physical RAS signal route.

Roadmap notes: RERI now has executable firmware tests for status transactions and counter rollover. Captured Spike ISA execution checks the program while an explicitly identified Python model supplies the absent RERI device. No DUT coverage is earned by these reference passes.


## PR 755

[#755](https://github.com/riscPrint/risc-v-workstation/pull/755). Merged: 2026-11-13T05:02:53Z.

Title: feat(formal): integrate certified counter and ram abstractions

Audit evidence label: ran on seeded RTL fixture.

## Summary
Carry the tested implementation from still-open PRs #535, #575 and #646 onto current main. Add exhaustive RTL initial-state splitting, lazy addressed-word RAM refinement, typed smaller-counter simulation-relation certificates, and the pinned PicoRV32 benchmark manifest and measured table. Register commands in separate modules and place contracts in formal-deep.md. Add a locked-dependency check before the installer replaces the venv.

## Testing
- Fast set before final fetch/rebase: 1156 passed, 1 expected command-reference skip, 7671 deselected.
- Targeted tests with the qualified OSS CAD Suite and optional engine prefix: 28 passed in 11.73 s. Counter/RAM native subset: 11 passed in 9.01 s. After rebase: partition/command/installer tests 8 passed. MCP list has no skipped warning.
- Fresh native initial-split CLI: all four initial-value cases passed, /tmp/deep-initial-integration/result.json. Short native jobs use nice priority.
- Initial run with Homebrew tools: 25 passed, 1 skipped, 2 failed. The Homebrew SBY trace tool lacks Python click; those failures do not qualify that toolchain. The OSS CAD Suite rerun passed.
- Earlier RAM/counter fault and PicoRV32 measurements remain in README with their exact limits. Existing source assumptions, bounded results, EBMC unsupported $initstate and missing/crashed engines stay explicit.
- Full suite, BOOM, long proofs, independent RTL-capacity qualification and CI waits NOT RUN.

## Issues
Refs: #21, #294. Original PRs #535/#575/#646 remain open after earlier conflict retries or merge refusal. This PR carries their code, keeps current main's other changes, and updates the command/contract layout. Counter certificates cover only the supplied reset-qualified leaf's projected bits. They do not replace a parent design automatically.

Roadmap notes: exhaustive initial-state decomposition, lazy RAM word restoration, and fresh native counter projection certificates are now integrated with the current formal command discovery. The PicoRV32 property set has measured conditional engine outcomes, not whole-core qualification. Full flags installation was blocked by the baseline lock mismatch; the preflight now fails before replacing the environment.


## PR 756

[#756](https://github.com/riscPrint/risc-v-workstation/pull/756). Merged: 2026-11-13T05:05:51Z.

Title: feat(cosim): adjudicate native vexriscv runs with sail

Audit evidence label: ran on real core RTL.

## Summary
Run the real VexRiscv ISA campaign against Spike and Sail 0.15 and save both C5 reports in an adjudication report. All 49 fresh C2/1 traces match both references under the declared profile: 17,735 instructions per reference, zero synchronizations and no applied bit masks.

Support Sail M-only/MU profiles and native zero-usable-entry PMP CSR banks. Add explicit sail_reference_isa selection and report reference_limits. The VexRiscv profile selects its common instruction ISA, disables absent timer devices, and selects its read-only MISA.M and direct-vector behavior. Counter/MMIO reads remain rejected.

Add RVW_VEX_CSR_CAPTURE=0 for a fresh native common-scope capture. Existing CSR-bearing traces are not silently stripped or qualified. Raw Sail writes zero on ECALL; the example's existing exact 0x73 event policy is recorded as a quirk once per program. No arbitrary trap bits are copied. Sail CSR state is not fabricated: later mtval reads are refused until an independent full write or another trap restores common state. The raw zero-valued profile still reports the native 0x73 value as a mismatch in both references.

## Testing
- Private pinned VexRiscv, vex-cosim lock: 49 native passes, 49 complete two-reference adjudication matches in the stated common GPR/memory/trap scope.
- Three native controls passed: actual absent-PMP reads/ignored writes plus a changed-GPR negative control; unsupported post-ECALL mtval read yields inconclusive adjudication; independent overwrite restores a match.
- Targeted Sail/config/platform set: 99 passed. Fast guard and campaign summary tests: 17 passed.
- Fast set: 1052 passed, 1 skipped, 1 failed, 7520 deselected. The unchanged out-of-area failure is test_docs_site.py::test_docs_staging_does_not_write_sources. The push brief permits publication with that failure named.
- The original real CSR-bearing trace remains inconclusive for Sail. The common C2/1 capture is explicit, not an automatic downgrade.
- NOT RUN: BOOM, full Python suite, Sail external interrupt synchronization, full machine CSR equivalence.

## Issues
These are matches under a declared observation/profile scope. They do not establish standard zero-valued ECALL behavior or full privileged/CSR compliance.

Roadmap notes: Native VexRiscv now has Spike/Sail adjudication with complete common-scope traces, explicit model ISA, exact quirk reporting and native negative controls. General Sail CSR readback and external input synchronization remain open.


## PR 757

[#757](https://github.com/riscPrint/risc-v-workstation/pull/757). Merged: 2026-11-13T05:04:52Z.

Title: test(formal): check seeded speculation and zkt timing contracts

Audit evidence label: ran on seeded RTL fixture.

## Summary

Add reusable two-copy security fixtures with manifests. Two seeded fixed-program fetch/resolve pipelines model a younger load squashed by a branch. Safe variants block its cache request. Leaky variants expose an operand-derived cache address while architectural observations agree.

Add a SHA-256 small-sigma-zero unit with fixed or operand-dependent busy/completion timing. Check declared Zkt timing observations without an architectural guard. These are small fixtures, not general RISC-V cores or decoder qualification.

## Testing

- Six native pair checks passed: two safe seeded pipelines prove, two leakage mutants fail with traces, fixed unit timing proves, and the timing mutant fails with a trace.
- Required fast set: 1172 passed, 1 skipped. The command-reference check is deferred by the parallel-push brief.
- MCP discovery: no skipped modules.
- Not run: BOOM builds/simulations, full Python suite, arbitrary-program/ISA validation, production-core security qualification or physical leakage checks. Functional data correctness of the SHA unit is outside this timing proof.

## Issues

Refs: #20

Roadmap notes: native speculation-contract and declared-Zkt timing fixtures now provide reproducible positive and negative observations. Seeds select two fixed address mappings for the same small program. Core bindings, full architectural observation policies, physical timing and analog leakage remain open.


## PR 758

[#758](https://github.com/riscPrint/risc-v-workstation/pull/758). Merged: 2026-11-13T05:05:10Z.

Title: feat(soc): observe rtl request response and retirement tags

Audit evidence label: unit tests only.

## Summary
Generate a read-only simulation monitor from project signal paths. Sample accepted RTL requests, responses and independent memory-retirement tags. Package raw pin observations with binding/run/RTL/ELF/seed identity and pin/C2 hashes for the existing SoC pair checker. Add separate CLI/MCP command modules and a binding template.

The producer never reads C2 or derives a retirement link from equal addresses. It requires unique tags and one known bus transaction per memory retirement. Unsupported counts stop simulation. Matching observations remain inconclusive.

## Testing
- Targeted observer and pairing tests: 15 passed, zero skipped. Native Icarus bridge fixtures record a stalled request, a store and a load, with separate architectural effect expectations. A corrupted read response produces a mismatch. CLI packaging exits 3 for consistent observations and 1 for mismatches. Tests cover identity drift, absent observations, no-clobber output and required tag bindings.
- The example binding generates through the CLI. MCP discovery has no skipped-module errors.
- Fast set: 1148 passed, 1 skipped, 7641 deselected in 94.85s (0:01:34).
- NOT RUN: actual VexRiscv/BOOM tag capture, ELF execution, full Python suite, BOOM builds or simulations, GitHub CI wait.

## Issues
Refs: #134

Remaining: bind probes for real core projects; support split transactions, finite tag reuse, multi-hart tags, speculative kills and posted-store errors. The native bridge fixture does not qualify a core or a complete bridge protocol implementation.

Roadmap notes: SoC pairing now has a project-bound RTL transaction producer and identity-checked packaging. Native bridge fixture captures catch corrupted read data. Core probe wiring and fresh C1/C2 DUT captures remain open.


## PR 759

[#759](https://github.com/riscPrint/risc-v-workstation/pull/759). Merged: 2026-11-13T05:06:00Z.

Title: feat(formal): replay boolean cross-clock sva properties

Audit evidence label: ran on seeded RTL fixture.

## Summary
Add finite native replay of Boolean two-clock SVA implication. Respect simultaneous target events for |-> and strictly later target events for |=>. Retain each activated request until its target event and collect separate assert/assume/cover observations. Keep ordinary formal lowering's cross-clock refusal. Extend the generated support table with the qualified native scope.

## Testing
- 58 targeted tests passed across the initial cross-clock set, state replay, raw events, existing two-backend simulation and the support table.
- Final cross-clock set: 26 passed. This adds falling edges, unknown operands, inactive requests and pending requests with no target event. The final unit/table check separately passed 11 tests.
- Native paired cases cover both operators, simultaneous/unrelated edges and two requests completed at one target edge. Exhaustive short event calendars use an independent nearest-event oracle.
- Fast set: 1161 passed, 1 skipped, 7652 deselected. The skip is the shared command-reference inventory check.
- Not run: full Python suite, BOOM builds/simulation, long formal jobs or formal engine qualification of cross-clock properties. Verilator cross-clock replay, named cross-clock properties, sequence operands, sampled functions and disable cancellation remain refused.

## Issues
Refs: #61, #46
General multi-clock formal sequence lowering remains open. This route collects finite activated-obligation observations and does not discharge requests still pending at the trace end.

Roadmap notes: Timed Icarus assertion replay now supports explicit Boolean two-clock implication with overlap/nonoverlap and four-state event semantics. C1 records property clock mappings and pass/fail/cover counts. The solver's multi-clock property limits are unchanged.


## PR 760

[#760](https://github.com/riscPrint/risc-v-workstation/pull/760). Merged: 2026-11-13T05:08:54Z.

Title: feat(formal): direct bounded engine campaigns at rtl covers

Audit evidence label: ran on seeded RTL fixture.

## Summary
Direct bounded engine/depth/rIC3-seed campaigns at elaborated RTL cover cells. Each target retains its enable and source assumptions and becomes the only negated safety check in its job. A counterexample reports a bounded cover hit. It never reports a safety pass, an unreachable cover or a DUT bug. Add CLI, MCP, README and report contract.

## Testing
- Fast set before final fetch/rebase: 1178 passed, 1 expected command-reference skip, 7676 deselected.
- Targeted cover transformation and bug-hunt tests: 5 passed, also after rebase. MCP list has no skipped warning.
- Native Yices and rIC3 tests: 2 passed in 5.99 s. Depth 4 stayed inconclusive for a counter's value-12 cover; depth 20 reached it. The impossible value-16 cover stayed inconclusive. A deliberately failing source assertion did not count as a hit. rIC3 used seeds 0 and 1 at the shallow depth. Stage timeout 6 s, nice priority, raw results /tmp/deep-cover-native4/.
- Full suite, BOOM, long proofs, physical/reset/multi-clock qualification, capacity comparison and CI waits NOT RUN.

## Issues
Refs: #21, #294. This completes the cover-directed part of the bounded bug-hunting increment. The epics remain open for broader capacity and qualification work.

Roadmap notes: bounded search can now focus engine and seed diversity on selected cover holes. Captured target problems, source locations, hashes, attempt results and native witnesses are retained. Bounded exhaustion stays inconclusive.


## PR 761

[#761](https://github.com/riscPrint/risc-v-workstation/pull/761). Merged: 2026-11-13T05:09:51Z.

Title: feat(privilege): verify rnmi frames and native mnret semantics

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add Smrnmi 1.0 entry matrices across M/S/U, ordinary exception nesting and pending ordinary interrupts. Check saved frame, NMIE masking and MPRV suppression. Require declared RNMI/exception vectors and PMP capabilities. Add native MNRET programs for privilege, PC, NMIE, MPRV and retained register restoration.

## Testing
- Targeted tests: 31 passed.
- Short native Spike smoke: 12 MNRET program/profile runs passed across base and H-enabled ISA configurations.
- Twelve external-entry programs compiled and passed the Python state-model reference. External entry remains model-based because Spike does not model RNMI sources/project exception vectors.
- Fast set: 1187 passed, 1 skipped. Command reference verification is skipped upstream during the parallel push.
- No RTL, BOOM, full Python suite or actual external RNMI injection run.

## Issues
Refs: #166. Reset interaction, double-trap profiles, guest/CFI RNMI frames and DUT machine-error recovery remain open. Native return tests do not substitute software CSR setup for hardware entry.

Roadmap notes: Smrnmi now covers lower privilege entry expectations, ordinary trap nesting, pending IRQ masking and native return semantics. Project data selects implementation-defined vectors. Model-based entry results do not earn DUT coverage.


## PR 762

[#762](https://github.com/riscPrint/risc-v-workstation/pull/762). Merged: 2026-11-13T05:09:41Z.

Title: feat(checks): bind axi transaction trackers from design data

Audit evidence label: unit tests only.

## Summary

Bind independent AXI4 and AXI4-Lite transaction trackers to typed design-database instances. Check per-ID read bursts, read interleaving, RLAST, ordered write packets including W-before-AW, WLAST, response IDs, request geometry and exclusive lock/EXOKAY rules. Check AXI4 WSTRB against FIXED, INCR and WRAP geometry, including unaligned first beats. Retain incomplete transaction fields as named unbound checks.

Expose tracker depth and strobe history limits through CLI, MCP and project `checks generate --all`. Capacity assertions are instrumentation bounds. Memory data and exclusive reservation state remain outside the tracker. TileLink database checks remain opcode-only.

## Testing

- 45 targeted tests passed in 69 seconds, including 30 native SBY prove-mode good and seeded bad cases. Exact PASS/FAIL status is required; elaboration errors do not count as detected faults. Native fixtures use two slots and four history beats.
- Default four-slot, 256-beat AXI4 monitor elaborated with Yosys in 9.5 seconds; CHECK reported zero problems.
- 21 binding/project tests passed. CLI import and MCP inventory passed after rebase, with no skipped tool modules.
- Fast set: 1016 passed, 1 coordinator skip, 7540 deselected. The transient escape warning in the new bounds test was fixed and the targeted test rerun.
- No BOOM build, full suite, physical hardware, connected-design proof or complete protocol qualification was run.

## Issues

Refs: #66

Roadmap notes: AXI database instances now receive bounded transaction and strobe checks when their fields bind. Per-instance output states exact coverage and capacity limits. Full TileLink tracking and independent exclusive reservation/data models remain open.


## PR 763

[#763](https://github.com/riscPrint/risc-v-workstation/pull/763). Merged: 2026-11-13T05:10:15Z.

Title: feat(formal): expand named unbounded and cross-clock properties

Audit evidence label: ran on seeded RTL fixture.

## Summary
Expand module-local zero-argument named properties and aliases before unbounded and cross-clock lowering. Preserve labels and reject duplicate or recursive definitions. Keep unselected finite named properties in place, including their typed local-capture scope.

## Testing
- 33 targeted frontend and native tests passed.
- Native paired checks cover a named unbounded goto obligation on the safety engine and named cross-clock replay beside a finite local-capture property.
- Fast set: 1213 passed, 1 skipped, 7703 deselected. The skip is the shared command-reference inventory check.
- CLI/MCP inventory checks passed after rebase.
- Not run: full Python suite, BOOM builds/simulation, long formal jobs or complete SVA qualification. Property arguments and general local-variable flow remain unsupported. Cross-clock properties retain their native simulation scope. Engine passes retain the existing inconclusive frontend status.

## Issues
Refs: #61

Roadmap notes: Unbounded liveness and finite cross-clock replay now accept reusable named properties and alias chains. The same normalization helper preserves finite named-property scope and rejects recursive definitions. This is a language-front-end increment, not broader engine qualification.


## PR 764

[#764](https://github.com/riscPrint/risc-v-workstation/pull/764). Merged: 2026-11-13T05:14:18Z.

Title: feat(checks): retain exact tilelink bus types for binding

Audit evidence label: unit tests only.

## Summary

Retain the actual qualified TileLink type, live RTL signal names and library options in the SpinalChecks report. Resolve an ambiguous database `Bus` only with one exact top, component path and signal-set match. Leave stale or duplicate matches unsupported.

Expose the matching report through `formal buses --type-report`, MCP and project bus generation entries.

## Testing

- Native `testOnly spinalchecks.BusTypeReportSpec`: 1 passed. The Scala sources compiled and the real TileLink library object elaborated to Verilog in a seven-second sbt run under the sbt lock.
- 20 targeted Python binding tests passed.
- Fast set: 1212 passed, 1 coordinator skip, 7741 deselected in 75 seconds.
- MCP inventory loaded without skipped tool modules.
- No BOOM build, complete suite, connected-design proof or physical hardware run.

## Issues

Refs: #66

Roadmap notes: Exact elaborated TileLink type metadata now resolves database simple-name ambiguity. Missing metadata remains explicit. This addition does not add transaction or cache-coherence qualification.


## PR 765

[#765](https://github.com/riscPrint/risc-v-workstation/pull/765). Merged: 2026-11-13T05:14:51Z.

Title: feat(formal): lower ordered local capture assignments

Audit evidence label: ran on seeded RTL fixture.

## Summary
Lower ordered local assignments inside a finite capture antecedent. A later assignment can read or reassign an earlier local. Apply declared width and sign at every assignment. Keep earlier values available to locals that already read them. Preserve per-attempt history across overlapping requests. Extend the generated support table.

## Testing
- 32 targeted tests passed.
- Paired native formal jobs check changing overlapping captures, assignment dependencies, byte overflow and signed narrow-value extension.
- Icarus and Verilator each check positive/fault capture-list reassignment, including byte overflow.
- Fast set: 1225 passed, 1 skipped, 7747 deselected. The skip is the shared command-reference inventory check.
- Not run: full Python suite, BOOM builds/simulation, long formal jobs or general local-variable flow qualification. Reads before assignment, local sampled-history use, initialized declarations and sequence-local control flow remain refused.

## Issues
Refs: #61

Roadmap notes: Finite typed local captures now support ordered assignment dependencies and reassignment within one Boolean capture list. Every assignment preserves the local type. The existing per-attempt history still prevents a later request from overwriting an earlier obligation.


## PR 766

[#766](https://github.com/riscPrint/risc-v-workstation/pull/766). Merged: 2026-11-13T05:19:01Z.

Title: feat(formal): lower sampled values in unbounded sva

Audit evidence label: ran on seeded RTL fixture.

## Summary
Reuse clock-local sampled history in unbounded SVA operands. Support $past, $rose, $fell, $stable and $changed in requests, responses and supported repetition units. Preserve finite frontend width/sign, depth, nesting and four-state comparison rules. Include sampled history state in the existing native-live or liveness-to-safety model. Extend the generated support table from the native corpus.

## Testing
- All 10 paired native engine cases passed across the five sampled functions. Each uses a small periodic positive fixture and a fault fixture.
- The final non-engine set passed 52 tests, including nested signed history in Icarus, frontend refusals, existing liveness cases, lasso oracles and the generated support table.
- An initial trace assertion included Icarus's finish message. The corrected test filters value records and passed. No implementation change was needed for that test correction.
- Fast set: 1235 passed, 1 skipped, 7764 deselected. The skip is the shared command-reference inventory check.
- Not run: full Python suite, BOOM builds/simulation, long formal jobs, native Suprove, fairness feasibility certification or complete SVA qualification. Cross-clock history, gated sampled calls and local-variable history remain refused. Engine passes retain the existing unknown frontend status.

## Issues
Refs: #61

Roadmap notes: The unbounded single-clock frontend now shares sampled-value lowering with finite SVA. Native paired engine cases cover all five functions. The frontend retains explicit capacity and semantic limits, with conditional engine evidence.


## PR 767

[#767](https://github.com/riscPrint/risc-v-workstation/pull/767). Merged: 2026-11-13T05:22:29Z.

Title: feat(privilege): generate fast preemption and jump table suites

Audit evidence label: unit tests only.

## Summary
Add v0.20 ACLIC/Smnip nested-preemption programs and Smijt interrupt-jump-table programs. Cross zero/full/partial grouping with higher, lower, equal and same-group priorities. Save and restore the outer threshold and exception PC in software. Test signed major offsets, external minor offsets, vector fallback, IALIGN masking and table strides. Extend functional coverage domains for the new CSRs and interrupt causes.

## Testing
- Targeted tests: 39 passed.
- Compiled 48 programs: 12 nested-preemption, 18 IALIGN=32 vector and 18 IALIGN=16 vector cases.
- Python expected outcomes passed for all 48, explicitly model-based. Unit cases independently check priority-group boundaries and table offsets/masks.
- Fast set: 1222 passed, 1 skipped. Command reference verification is skipped upstream during the parallel push.
- No native extension execution: installed Spike has no v0.20 Smidctrl/Smnip/Smijt model. No RTL, BOOM or full Python suite run.

## Issues
Refs: #186. Supervisor variants, table permission faults, aborted trap entry and DUT qualification remain open. The v0.20 pin is distinct from old CLIC drafts.

Roadmap notes: Fast-interrupt suites now generate real nested-handler and hardware-vector scenarios, with project-owned stimulus schedules and model-based expected results. Zero grouping bits are supported. Model agreement does not earn DUT coverage.


## PR 768

[#768](https://github.com/riscPrint/risc-v-workstation/pull/768). Merged: 2026-11-13T05:24:47Z.

Title: fix(cosim): verify native rvvi round trips and state consistency

Audit evidence label: ran on real core RTL.

## Summary
Export fresh native VexRiscv retirement/trap traces to RVVI-TEXT 0.5 and re-import them with full C2 record equality. Cover default one-CSR capture and all 17 machine CSRs. Preserve actual reference mismatches instead of converting them into matches.

Reject contradictions between RVVI and its rvw.c2 STATE extension: cumulative cycle, hart, order, mode, XLEN, hart count and IRQ NET values now join existing PC/instruction/write checks. Reject mixed sparse retirements that would otherwise be discarded. Conversion remains explicitly not an independent architectural check.

## Testing
- Private pinned VexRiscv under vex-cosim: 2 native round-trip controls passed. Each had nine retirements and an ECALL trap. Every decoded C2 record matched before/after conversion.
- The default capture matched Spike before/after import with equal comparison counts. Full-CSR input retained identical real reference-model differences before/after import.
- Exchange tests: 12 passed, including contradictory-field and mixed-input controls. The pure format tests now opt into the fast set.
- Fast set: 1217 passed, 1 skipped, 1 failed, 7695 deselected. The unchanged out-of-area failure is test_docs_site.py::test_docs_staging_does_not_write_sources; the push brief permits publication with it named.
- Refresh the existing DPI execution-time table after the CSR sampling fix. Both measured baselines and both checked traces match Spike completely. Equal cycle/instruction counts were checked. The shared-host timings remain bounded workload evidence.
- NOT RUN: debug-halt comparison. No generic RTL harness DMI endpoint is present on main, and this VexRiscv configuration has no debug unit. The reference Debug Module model is not labelled an RTL endpoint.
- NOT RUN: BOOM, full Python suite, external-tool RVVI interoperability, general CSR equivalence.

## Issues
The RVVI STATE extension carries fields outside the exported standard subset. The native round trip proves preservation for these captures, not universal RVVI support or independent correctness.

Roadmap notes: Native VexRiscv default/full CSR traces now have measured RVVI export/import round trips with strict duplicate-field consistency. Debug-halt integration still needs an actual harness DMI binding. Current DPI timing evidence was refreshed after the capture-phase change.


## PR 769

[#769](https://github.com/riscPrint/risc-v-workstation/pull/769). Merged: 2026-11-13T05:23:22Z.

Title: feat(sim): measure native instruction and irq reduction

Audit evidence label: ran on real core RTL.

## Summary

Add a project adapter and two real whole-core RTL failure recipes for `rvw reduce`. Instruction reduction keeps one of eight replaceable slots. Concurrent IRQ reduction keeps one of six removable events plus the required initial event. Each candidate executes captured VexRiscv RTL through Arcilator in a fresh process. C8 captures the source, ELF and project assets. Both empty controls pass. These are intentional failing fixtures, not newly found core defects.

Native trials exposed missing `config` and `elf` C2 header fields and an incorrect trap `interrupt` key in the experimental Python probe. Add the required headers and canonical `intr` key. Validate complete Python traces before C1 publication. Fix the live checkpoint header too. Re-run paired engines, checkpoint/reverse replay, history bisect and all eight native build profiles. Replace the earlier profile/history samples with validated evidence. No shared format change and no C4 acceptance are claimed.

## Testing

- Native reduction: instructions 8 -> 1 in 9.6 s, seven conclusive trials; IRQ removable events 6 -> 1 in 10.9 s, seven conclusive trials. Both `one_minimal`, neither a global minimum. Fresh best-candidate confirmations reproduced `fail:1`.
- Native positive and negative fixture controls: 2 passed in 6.65 s. Invalid/absent IRQ inputs: 3 passed in 1.77 s. C1 is not published for rejected inputs.
- Native Arcilator/Verilator pair: 1 passed in 6.78 s. Both retire 17 instructions in 81 cycles at seed 7. Shared C2 parser accepts both complete traces; all bytes match.
- Native live checkpoint and reverse replay: 2 passed in 90.52 s. Continuation C2 bytes match; replayed state matches an independent reset run at retirement 10.
- Native history bisect: both real adjacent endpoints execute and select their project adapters. Finds expected configuration transition 6c891a7615b843308e94efb4b4ff5551177f3bda. Both complete C2 traces validate. This is an intentional M/S/U to M-only change.
- Native profile campaign: all eight profiles pass and match the schema-validated independent Arcilator reference. Records ccache cold/warm, threads, hierarchy and compiler PGO. No runtime winner is retained.
- Targeted reducer, adapter-version and profile tests: 27 passed in 30.44 s.
- Final fast set: 1134 passed, 1 skipped, 7592 deselected; 1 unrelated failure in `rvw/tests/test_docs_site.py::test_docs_staging_does_not_write_sources` (74.46 s). The docs builder includes local `.pytest_cache/README.md` in its page list while Git-based staging excludes it. This file and builder are unchanged. The brief permits merging with this unrelated failure.
- NOT RUN: full Python suite, BOOM, heavy formal, CI waits, general multi-hart or device-transaction stimulus reduction, long throughput qualification, RTL Linux.
- All native jobs use the private VexRiscv copy/output and `vex-simsrv` lock. No shared `vex` lock wait.

## Issues

Refs: #152, #345, #335, #45, #74, #344

The instruction and concurrent IRQ native reduction piece is measured. General stimulus streams and unknown upstream failures remain outside this recipe. The source capture omits the unused VexRiscv regression-data submodule in a pinned private local commit. The report retains the actual captured revision and fingerprint.

Roadmap notes: native instruction/IRQ delta debugging now has complete C1/C2 trial evidence, passing empty controls and local minimality. Experimental scalar and checkpoint headers comply with the existing C2 contract. New profile/history samples supersede the earlier incomplete-header samples. Keep C4 reuse, global minimum, throughput qualification and broader stimulus coverage open.


## PR 770

[#770](https://github.com/riscPrint/risc-v-workstation/pull/770). Merged: 2026-11-13T05:26:02Z.

Title: feat(checks): track tilelink transactions and coherent probes

Audit evidence label: ran on seeded RTL fixture.

## Summary

Bind independent TileLink transaction state from complete bus fields. Check A/D sources, response kinds, parameters, masks and multibeat headers. Cover Get, Put, ArithmeticData, LogicalData and Hint. Coherent channels add Acquire/Grant, Release/ReleaseAck, GrantAck sinks and Probe/ProbeAck pairs. Multiple addresses can share one probe source. Unaccepted first offers can change.

Add native Spinal Probe checks for source/address matching, size, cap transitions, ProbePerm no-data responses, parameters and alignment. The native tracker has 16 pending probe slots. The SV generator uses the explicit `--depth` instrumentation bound. Exact type options support zero-bit source and sink fields.

The generated profile restricts coherent B to probes. Negotiated address regions, endpoint operation capabilities, cache permission/data state and progress remain project obligations. No full protocol or cache-coherence qualification is claimed.

## Testing

- 65 targeted Python tests passed in 33 seconds. These include 41 native SBY prove-mode good and seeded bad cases. Exact PASS/FAIL is required; errors do not count as faults. Cases cover burst stability, reordered IDs, atomics, hints, same-source probes, capacity and reset with pending requests/probes/releases/grants.
- Native `testOnly spinalchecks.TileLinkProbeSpec spinalchecks.TileLinkCoherentSpec spinalchecks.TileLinkTransactionsSpec`: 11 passed in a ten-second sbt run under the sbt lock. Sources compiled and real Spinal library buses ran with Verilator.
- Fast set: 1219 passed, 1 coordinator skip, 7782 deselected in 63 seconds.
- CLI import and MCP tool inventory checked. No BOOM build, full suite, connected-design proof or physical hardware run.

## Issues

Refs: #66

Roadmap notes: Typed TileLink bindings now emit independent transaction and coherent probe tracking, with exact per-instance coverage and missing-binding reasons. Full cache-state models and negotiated capability checks remain open. The BOOM boundary has not been run or qualified by these fixtures.


## PR 771

[#771](https://github.com/riscPrint/risc-v-workstation/pull/771). Merged: 2026-11-13T05:27:54Z.

Title: feat(formal): lower unbounded repetition count ranges

Audit evidence label: ran on seeded RTL fixture.

## Summary
Support positive literal count ranges for unbounded goto and nonconsecutive repetition. Retain later permitted completions when an earlier count does not satisfy the completion operand. Keep separate count buckets and old-obligation state for overlapping requests. Record the optional maximum count and extend the generated support table.

## Testing
- 53 targeted tests passed, with 24 unrelated paired cases deselected.
- Native engine pairs cover both repetition types with a legal later completion and a fault. The fixture gates requests during startup reset; reset cancellation is not inferred.
- Emitted Icarus automata matched an independent language oracle on 69 deterministic looping traces, four operator/range variants each. Existing unbounded trace tests also passed.
- Fast set: 1243 passed, 1 skipped, 7769 deselected. The skip is the shared command-reference inventory check.
- Not run: full Python suite, BOOM builds/simulation, long formal jobs, native Suprove or complete SVA qualification. Count limits are 64 without a completion and 63 with one. Zero and unbounded count ranges remain refused. Engine passes retain the existing unknown frontend status.

## Issues
Refs: #61

Roadmap notes: The unbounded frontend now supports literal goto/nonconsecutive count ranges, including a single Boolean completion. Native tests cover alternate permitted endpoints, overlap preservation and finite impossibility at the maximum count. General nested sequence composition remains open.


## PR 772

[#772](https://github.com/riscPrint/risc-v-workstation/pull/772). Merged: 2026-11-13T05:29:21Z.

Title: feat(formal): add native flags and qualified benchmark counts

Audit evidence label: unit tests only.

## Summary
Add direct native installer flags for Pono, Avy, suprove, Bitwuzla, cvc5 and Yices. Reuse an installed backend or fetch checksum-pinned OSS CAD Suite 2026-10-22 outside the repository and publish selected backend launchers. Pono includes its btorsim dependency. Record native installation results and fresh HWMCC/PicoRV32 engine tables. Benchmark solved counts now require conclusive problem results; unchecked conditional native passes have a separate count.

## Testing
- Fast set before final fetch/rebase: 1214 passed, 1 expected command-reference skip, 7703 deselected.
- Installer/benchmark targeted set: 60 passed. After rebase: helper, engine installer and benchmark qualification tests 10 passed. Shell syntax and MCP list passed; no skipped MCP warning.
- Actual rIC3/EBMC flags installation and --check passed. Pono/Avy/Bitwuzla/cvc5/Yices flags and checks passed with installed tools. The suprove helper downloaded and checksum-verified the 501 MiB macOS ARM64 archive outside the repository. The archive has no suprove; installation failed explicitly. The locked dev/MCP environment was restored.
- Fresh pinned-suite HWMCC prove and BMC runs, 12 s per stage: ABC PDR and rIC3 solved 2/2; each SMT backend and EBMC solved 1/2. Avy errors and missing suprove remain explicit. Bounded successes are separate.
- Fresh pinned PicoRV32 property set: PDR and rIC3 native passes remain conditional. Qualified solved count is zero. Tables include timeouts/errors and BMC observations. Raw reports: /tmp/deep-pinned-refresh-{hwmcc-small,picorv32}-{prove,bmc}/result.json.
- Native feature tests with earlier suite: 18 passed. With the pinned suite: 17 passed, 1 failed. test_counter_quotient.py::test_native_reset_qualified_relation_and_refuted_candidate fails because the shared runner does not decode Yosys 0.70 interned RTLIL module names. SBY PASS stays an error/inconclusive certificate. No guard was relaxed and no frontend/runner file was edited.
- Full suite, BOOM, long proofs, commercial comparison and CI waits NOT RUN.

## Issues
Refs: #21, #294. Remaining qualification limits: Avy errors, suprove absent on this platform, rIC3 rlive's unsupported internal option, EBMC unsupported $initstate on PicoRV32, and shared runner support for Yosys 0.70 twines names. The runner fix should resolve interned module and instance names in prepared RTLIL, or use a structured prepared-model export. It must retain the assertion-count guard.

Roadmap notes: optional backend flags now have an external pinned-bundle route and explicit missing-engine failure. Native tables distinguish solved problems, conditional native passes and bounded observations. The source-restricted PicoRV32 set is not whole-core qualification. Counter certificates still qualify with the earlier suite; the pinned full frontend needs the shared runner's RTLIL format support.


## PR 773

[#773](https://github.com/riscPrint/risc-v-workstation/pull/773). Merged: 2026-11-13T05:34:24Z.

Title: feat(privilege): measure dvfs clock periods and pulse bounds

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add independent digital clock-edge capture and observation for DVFS. Check stable-state periods with exact fractions, minimum pulse widths, optional edge-gap bounds and switch acknowledgement limits. Require the capture before C1 qualification when the project selects clock_measure. Mark missing ticks and unknown levels incomplete.

## Testing
- Targeted tests: 29 passed. Fixtures cover runt pulses, missing edges, wrong periods, switch bounds, incomplete captures and C1 evidence/hash gates.
- Compiled the updated DVFS example. Python reference describes the expected digital sequence only and is model-based.
- Fast set: 1244 passed, 1 skipped, 1 failed. Unchanged upstream failure: rvw/tests/test_release_hygiene.py::test_tracked_text_has_no_personal_paths reports examples/vexriscv/rvw/reduction/measurements.json lines 144 and 267. The failure is not waived.
- No RTL, BOOM, full Python suite or physical clock run.

## Issues
Refs: #197. Project adapters must sample the actual core clock from an independent reference. Sampled checks do not detect sub-tick pulses or qualify analog voltage, physical timing or PLL behavior.

Roadmap notes: DVFS qualification can now require measured clock periods and pulse/switch bounds, alongside handshake order, voltage-state constraints and strict architectural evidence. Missing or short observations remain inconclusive.


## PR 774

[#774](https://github.com/riscPrint/risc-v-workstation/pull/774). Merged: 2026-11-13T05:33:26Z.

Title: test(sim): measure native server recovery and teardown

Audit evidence label: ran on real core RTL.

## Summary

Record the native JVM process ID in C1 simulation-session metadata. Keep it separate from model identity and C2. Use the private `RVW_VEX_LOCK` override in the fresh-process half of the native server test. Check actual JVM exit after EOF and after SIGTERM during a running second ELF. Cancellation requires observed retirement, so request setup alone cannot count as an active native run.

This adds native teardown and recovery evidence for the persistent server. Existing cancellation semantics stay in use. The reduction sample exporter also keeps only source identity fields, so local C8 paths do not enter the public sample.

## Testing

- Targeted Scala `riscvsim.ServerSpec`: 9 passed. Checks refusal of undeclared reset, compiled-model reuse after failure, abandoned-worker refusal and process metadata.
- Native server reset/equivalence and initial cancellation controls: 2 passed in 69.35 s. One server executes timeout/fail/pass/pass. Four passing traces across server and persistent batch match the fresh-process C2 bytes. All complete sample traces pass the shared C2 parser. Native JVM PIDs are absent after EOF.
- Tightened native cancellation check with actual retirement before SIGTERM: 1 passed in 11.30 s. Launcher exit 143; native JVM stopped; cancelled ELF has no pass.
- Persistent regression Python tests: 8 passed in 6.45 s.
- Final fast set: 1238 passed, 1 skipped, 7764 deselected; 1 unchanged failure in `rvw/tests/test_docs_site.py::test_docs_staging_does_not_write_sources` (58.94 s). The brief permits this unrelated docs-builder failure. The first run also found two local C8 paths in the reduction sample. The exporter and sample now omit paths and retain the captured revision and hashes. Targeted release-hygiene and persistent tests: 9 passed in 16.02 s.
- Native work uses the private VexRiscv source, `vex-simsrv` lock and private output/cache directories. No shared `vex` wait.
- NOT RUN: full Python suite, BOOM, CI waits, device-wide reset coverage, per-request thread census, forced native thread abandonment, native crash, SIGKILL or forced-cancel workspace cleanup.

## Issues

Refs: #14

The native reset sequence and process teardown checks are measured. Device-wide reset, per-request native thread accounting and fault cases outside this short sequence remain open. JVM exit establishes that its threads stopped; it does not establish thread release between requests in a live process.

Roadmap notes: persistent VexRiscv server runs recover after cycle timeout and fail, retain fresh-process C2 equality, exit on EOF and stop their JVM after SIGTERM during an active ELF. C1 session process metadata supports caller-side teardown checks. Keep broader device reset and native fault/abandonment campaigns open.


## PR 775

[#775](https://github.com/riscPrint/risc-v-workstation/pull/775). Merged: 2026-11-13T05:36:27Z.

Title: test(checks): execute csr and hpm monitors on native vexriscv

Audit evidence label: ran on real core RTL.

## Summary

Execute generated scratch-CSR programs and an RV32 counter-write/wrap program on real VexRiscv RTL with optional CSR and HPM monitors enabled. Reuse the existing ELF loader and tohost decoder. Run the same programs on Spike. The counter reference declares Zicntr explicitly.

Add seeded CSR-state and HPM-observation faults. Fixture completion requires the expected firing. Their run reports retain fail status. Clean runs require program success, five inserted monitors, zero firings and executed scratch/counter instructions. This tests the project binding rather than only its elaboration.

## Testing

- Private VexRiscv copy at a62c145aa042a5de874344e0a7683bd7c8c8c870. Native Scala compile passed in 19 seconds under sbt/private Vex locks.
- `test_vex_generated_checks.py`: 3 passed, no skips, in 26 seconds. Each native invocation has a 110-second timeout. Three ELFs passed Spike and clean native Vex execution.
- Clean runs: 50, 27 and 118 retired instructions; 114, 90 and 349 cycles. Five monitors per run, zero firings. Eight scratch CSR instructions and eight machine-counter instructions executed across the programs.
- CSR observation fault fired csr.state:mscratch. HPM observation faults fired hpm.count:mcycle and hpm.count:minstret. Reports retain fail status.
- Fast set: 1250 passed, 1 coordinator skip, 7805 deselected; one unrelated failure in `test_release_hygiene.py::test_tracked_text_has_no_personal_paths`. It flags untouched `examples/vexriscv/rvw/reduction/measurements.json` lines 144 and 267. Per the work brief this does not block delivery.
- No BOOM build, full suite, physical hardware or general CSR/HPM compliance run. Privilege filters, programmable HPM events and AIA semantics remain unqualified.

## Issues

Refs: #85, #98

Roadmap notes: Optional Vex CSR/HPM bindings now have native execution and seeded observation-fault evidence. The M-only example covers scratch accesses, absent supervisor-CSR trapping, clock/last-stage events and counter half writes. It does not establish architectural retirement-event equivalence or general privilege/alias coverage.


## PR 776

[#776](https://github.com/riscPrint/risc-v-workstation/pull/776). Merged: 2026-11-13T05:39:28Z.

Title: feat(formal): resume hierarchical register state in replay

Audit evidence label: ran on seeded RTL fixture.

## Summary
Resume complete elaborated flip-flop state through module instances in timed Icarus replay. Keep each instance's state distinct. Force all loaded registers while derived-clock and asynchronous-control events settle, then release them before logical replay begins. Read actual RTLIL flip-flop destination names so combinational register aliases cannot stand in for loaded state. Permit repeated use of the owned output directory.

## Testing
- 38 targeted tests passed, including hierarchical state, existing VCD/FST replay, raw events and cross-clock assertion replay.
- Native checks use repeated child instances, two clocks, a derived clock, an asynchronous reset pulse and X state. Both register loading orders preserve X through setup. A combinational register alias is refused while the actual flop loads correctly.
- Fast set: 1260 passed, 1 skipped, 7811 deselected, 1 failed. The failure is outside this patch: `test_release_hygiene.py::test_tracked_text_has_no_personal_paths`, reporting `examples/vexriscv/rvw/reduction/measurements.json` lines 144 and 267. No file in that area was edited. The skip is the shared command-reference inventory check.
- Not run: full Python suite, BOOM builds/simulation, long formal jobs or formal solver state loading. Memories, black boxes and unsupported asynchronous state types remain refused. Native continuation observations are not a reachability or design proof.

## Issues
Refs: #46

Roadmap notes: Native timed replay now resumes hierarchical flip-flop state and handles setup events from derived clocks. Exact state coverage uses instance identities and real RTLIL register destinations. Memory state and multi-clock formal from-sim loading remain open.


## PR 777

[#777](https://github.com/riscPrint/risc-v-workstation/pull/777). Merged: 2026-11-13T05:42:40Z.

Title: feat(checks): bind resource rules and report incomplete checks

Audit evidence label: unit tests only.

## Summary

Bind existing resource templates through project-owned `rvw.micro-checks/1` data: ROB/credit count conservation, allocation pools, legacy free-list disjointness, CAM matches and counter bounds. Add `freelist_conservation` with independent accepted allocation/release events and a free/live partition of literal usable tags. Initial ownership and reserved tags are explicit project intent.

Retain per-instance unbound transaction checks in the overall `checks generate --all` summary. Its direct `unbound` list gives each missing kind, instance/check and reason. Partial channel generation cannot make the overall summary complete.

## Testing

- 52 targeted tests passed, including existing microarchitecture SBY proofs, resource simulation fixtures, project binding and summary tests.
- After strengthening reserved-tag allocation checks, 22 targeted tests passed. These include six exact-status native SBY cases for good/nonempty-reset ownership and seeded missing-free, duplicate-free, lost-live and reserved-tag faults.
- Fast set: 1271 passed, 1 coordinator skip, 7829 deselected in 64 seconds.
- CLI/MCP inventory loaded without skipped tool modules.
- No BOOM build, full suite, connected-design proof or physical hardware run. Project mappings, multi-entry recovery and architectural retirement semantics remain project obligations.

## Issues

Refs: #65

Roadmap notes: The project command now binds resource conservation templates and reports missing transaction bindings directly. Free-list expected ownership is independent of observed live/free state. Full recovery, killed effects and whole-core qualification remain open.


## PR 778

[#778](https://github.com/riscPrint/risc-v-workstation/pull/778). Merged: 2026-11-13T05:48:11Z.

Title: feat(checks): verify hpm alias reads from independent events

Audit evidence label: ran on seeded RTL fixture.

## Summary

Bind VexRiscv machine and user-alias counter read responses to independent expected event state. `HpmChecks.track` returns the same expected state used by existing `bind`; existing Unit-returning bind calls remain intact. Check both RV32 halves without feeding read data back into expected state.

Extend the bounded native counter program and add a separate read-observation fault. Clean runs require nine monitors and zero firings. Seeded read faults must fire all four machine/user-alias read monitors and retain fail status. Require eight executed half reads to prevent an inactive fixture from succeeding.

## Testing

- Native `test_vex_generated_checks.py`: 4 passed, no skips, in 36 seconds. Each invocation is bounded to 110 seconds and uses sbt/private Vex locks. Private source is pinned at a62c145aa042a5de874344e0a7683bd7c8c8c870.
- Three programs passed Spike and clean Vex execution. The counter reference declares Zicntr. Clean native runs retired 50, 27 and 122 instructions in 114, 90 and 361 cycles. Nine monitors per run, zero firings. The programs executed eight scratch instructions, ten machine-counter instructions and eight machine/user half reads.
- Seeded HPM read data fired hpm.read:mcycle_machine, hpm.read:minstret_machine, hpm.read:mcycle_user and hpm.read:minstret_user. CSR-state and counter-state fault cases still passed their expected-result checks.
- Native `testOnly spinalchecks.HpmChecksSpec`: 3 passed in 12 seconds under the sbt lock, including masked writes and carry behavior.
- Fast set: 1273 passed, 1 coordinator skip, 7834 deselected in 65 seconds. CLI/MCP inventory loaded.
- No BOOM build, full suite, physical hardware, lower-mode counter-enable or programmable HPM event-selector qualification.

## Issues

Refs: #85, #98

Roadmap notes: The M-only Vex example now checks actual machine and user-alias read responses against independent expected events, including both RV32 halves and wrap/write sequences. Lower-mode access filters and general programmable HPM mappings remain open.


## PR 779

[#779](https://github.com/riscPrint/risc-v-workstation/pull/779). Merged: 2026-11-13T05:48:17Z.

Title: feat(formal): guard unbounded sequences with throughout

Audit evidence label: ran on seeded RTL fixture.

## Summary
Apply Boolean throughout guards to the supported unbounded sequence forms. Require the guard on all active samples, including completion. Keep completed attempts independent of later idle guard changes. Support nested guards and first_match wrappers without changing weak/strong completion rules. Record the modifier and extend the generated support table.

## Testing
- 25 targeted tests passed, with four unrelated engine cases deselected.
- Native engine pairs cover delay, consecutive repetition, literal goto/nonconsecutive counts and count ranges. Tests cover guard failure while waiting, a false guard after legal completion and weak infinite waiting.
- The emitted guarded range monitors matched an independent language oracle on 71 looping traces, four operator/range variants each. The existing 69 unguarded traces also passed.
- Fast set: 1281 passed, 1 skipped, 7829 deselected. The skip is the shared command-reference inventory check.
- Not run: full Python suite, BOOM builds/simulation, long formal jobs, native Suprove or complete SVA qualification. General unbounded within/intersect composition, sequence guards, reset cancellation and cross-clock liveness remain unsupported. Engine passes retain the existing unknown frontend status.

## Issues
Refs: #61

Roadmap notes: The unbounded frontend now supports Boolean throughout guards with per-attempt active intervals and completion-inclusive checks. Native cases retain the weak/strong distinction and verify that idle guard changes do not invalidate completed attempts.


## PR 780

[#780](https://github.com/riscPrint/risc-v-workstation/pull/780). Merged: 2026-11-13T05:51:16Z.

Title: feat(privilege): compare model observations with c2 traces

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Compare C1 C2 observations with versioned Python expectations for RERI transactions and v0.20 fast interrupts. Bind read sites to ELF instructions, CSR/MMIO addresses, modes, masks and value sequences. Require selected vector PCs, complete traces and C1 identity. Report model_subset/model_groups separately. Keep full architectural qualification inconclusive without a complete ISA reference. Reject reference traces for C1 groups.

Also fix the native RERI backend registration changed by an earlier broad campaign-kind edit. Add routing regression tests. Native Spike/Python-device runs now emit tagged reference C2 traces.

## Testing
- Targeted tests: 43 passed, including changed values/bindings, missing observations, wrong identity, reference reuse and all-member group gates.
- Seven RERI programs passed native Spike/Python-model execution; all 45 status observations matched their reference C2 traces.
- Six PLIC programs passed again through the trace-exporting runner.
- Recompiled all 48 fast-interrupt programs; model references passed.
- Fast set: 1278 passed, 1 skipped. Command reference verification is skipped upstream during the parallel push.
- Native results remain model-based reference evidence. No RTL, BOOM or full Python suite run.

## Issues
Refs: #181, #186. These checks cover named reads and code addresses. They do not compare the full instruction stream or earn strict architectural coverage. DUT execution and complete extension qualification remain open.

Roadmap notes: Model-only extensions now have a scoped C1 observation path. Known subset mismatches fail; missing evidence stays inconclusive. Strict architectural pass remains unchanged and cannot be replaced by a model subset pass.


## PR 781

[#781](https://github.com/riscPrint/risc-v-workstation/pull/781). Merged: 2026-11-13T05:55:16Z.

Title: fix(checks): require prior axi request handshakes for responses

Audit evidence label: ran on seeded RTL fixture.

## Summary

Require AR acceptance on an earlier edge before RVALID. Require AW and the complete W packet accepted on earlier edges before BVALID. Apply this to generated AXI4/AXI4-Lite trackers and native Spinal AXI4 read/write trackers. The old current-edge response bypass accepted a timing violation.

Keep internal AW/W pairing, W-before-AW and cross-ID ordering behavior. Preserve TileLink's separate same-cycle semantics. Document the read/write dependency rules from [Arm IHI 0022H](https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/IHI0022H_amba_axi_protocol_spec.pdf).

## Testing

- 44 targeted tests passed in 51 seconds, including 34 native SBY prove-mode good and seeded bad cases. Same-edge responses now require FAIL. Added legal restart after reset and orphan-after-reset cases for AXI4 and AXI4-Lite. Exact FAIL is required; tool errors do not count as detected faults.
- Native `testOnly spinalchecks.AxiReadSpec spinalchecks.AxiWriteSpec`: 9 passed in 11 seconds under the sbt lock. Both new same-edge response mutations fired the required match checks. Existing legal bursts, error responses, omitted options, W-before-AW and ID reorder cases passed.
- Fast set: 1281 passed, 1 coordinator skip, 7853 deselected in 66 seconds. CLI/MCP inventory loaded.
- No BOOM build, full suite, physical hardware or complete AXI compliance run. The independent memory-data and exclusive-reservation models remain outside these trackers.

## Issues

Refs: #66

Roadmap notes: AXI response precedence now follows accepted earlier request handshakes. Native and generated regression fixtures cover this timing rule and reset with pending state. Full endpoint capability and data-state qualification remains open.


## PR 782

[#782](https://github.com/riscPrint/risc-v-workstation/pull/782). Merged: 2026-11-13T06:00:28Z.

Title: feat(checks): add queue flush and age-selected forwarding rules

Audit evidence label: unit tests only.

## Summary

Add project-instantiated FIFO flush and age-selected store-forwarding variants. Flush discards queued data and current-edge events before the next push. Forwarding uses an explicit store age matrix to choose the unique youngest eligible source, so circular slot layouts need no static index-age assumption.

Keep the existing higher-index-is-younger variant for projects that declare that contract. Reject nonempty eligibility with no candidate or multiple candidates. Both new kinds use the existing template CLI/MCP and project generation paths. Data units can be bytes for separate per-byte merging checks. Speculation, recovery and address-match observations remain project declarations.

## Testing

- 40 targeted tests passed in 7.4 seconds, including 17 exact-status native SBY prove cases. Good/bad cases cover all eight microarchitecture templates. New fixtures exercise flush with current-edge events, stale post-flush data, a youngest entry at slot zero, stale forwarding and cyclic age relations.
- Project signal binding tests passed for both new kinds. Both CLI template commands emitted their SV modules. MCP inventory loaded without skipped tool modules.
- Fast set: 1288 passed, 1 coordinator skip, 7860 deselected in 59 seconds.
- No BOOM build, full suite, connected-design proof or physical hardware run. The generator does not infer a project's age, flush or speculative-execution semantics.

## Issues

Refs: #65

Roadmap notes: Project data can now bind flush-aware FIFO ordering and age-selected forwarding for circular layouts. Generic template proofs cover seeded failures. Core-specific recovery, dependency violations, fences and architectural killed effects remain open.


## PR 783

[#783](https://github.com/riscPrint/risc-v-workstation/pull/783). Merged: 2026-11-13T06:02:15Z.

Title: feat(formal): preserve event sampling on both simulators

Audit evidence label: ran on seeded RTL fixture.

## Summary
Preserve pre-event samples through runtime nonblocking driver phases on both Icarus and Verilator. Enable two-state raw-event and Boolean cross-clock replay on Verilator. Keep input timestamps unchanged. Preserve four-state input/X-check refusals and Icarus-only trace-state replay.

## Testing
- 51 targeted tests passed across raw events, cross-clock replay, existing simulation, typed local flow and hierarchical trace-state replay.
- A second set passed 14 tests, including Verilator overlap/nonoverlap distinctions, falling edges and four-state refusal guards. The sets overlap.
- Both simulators pass paired old-value raw checks and paired cross-clock assertion/cover counts.
- Fast set: 1281 passed, 1 skipped, 7864 deselected. The skip is the shared command-reference inventory check.
- Not run: full Python suite, BOOM builds/simulation, long formal jobs, Verilator four-state behavior or trace-state loading on Verilator. Verilator compile logs retain expected private-clock multiple-driver warnings. No DUT lint or general scheduling conformance claim is made.

## Issues
Refs: #61, #46

Roadmap notes: Finite raw-event and Boolean two-clock SVA replay now runs on both native backends with pre-update samples and common assertion/cover counts. Verilator remains two-state. Four-state observation and trace-state continuation remain Icarus capabilities.


## PR 784

[#784](https://github.com/riscPrint/risc-v-workstation/pull/784). Merged: 2026-11-13T06:11:49Z.

Title: feat(probes): wire vexriscv probes and fix btfn not-taken targets

Audit evidence label: ran on real core RTL.

## Summary

- VexRiscv `ProbePlugin` (example only, no core source change): branch outcomes with the STATIC prediction (`BRANCH_DO xor BRANCH_COND_RESULT` at write-back), D/X/M/W stages with one ID per instruction, flushes, retire, inferred stall causes, 11 counters (3 with HPM selectors) and interrupt-taken entries. Off unless the run uses C1 `--probes`.
- Adapter wiring (`supportsProbes`, `ProbeCollector` open/sample/close/abandon), `--probes` for the database build, `branches.S` and `irqs.S` programs, BTFN and gshare studies for `rvw csim compare-rtl`.
- `ProbeCollector.abandon()` closes a stream of an unfinished run without an end record.
- **Bug fix found by the probes:** `rvw csim` C2 and Spike converters wrote the fall-through as the target of a not-taken conditional branch. The BTFN rule reads the target, so a loop exit looked forward and BTFN reported no miss there. The converters now write the decoded target; `docs/contracts/csim.md` says so.
- "Instrument your core" section in `docs/BRING_YOUR_OWN_CORE.md`; "Probes" section with the real results in `examples/vexriscv/README.md`.

## Testing

Native runs on a private VexRiscv copy (core sources `baf7dc82`), lock `vex-csims`, seed 1, random memory timing:

- `branches --probes --rvfi-trace`: pass, 35659 instructions, 195928 cycles. `probe-events.jsonl` complete; 9002 branch events (6001 cond).
- `rvw probes convert --to bp-events` + `rvw csim compare-rtl`:
  - `btfn.json`: before the fix 1 disagreement (loop exit at `0x8000006c`); after the fix 0 of 6001, 3355 misses each (94.1 MPKI).
  - `gshare.json` (1024 entries, 10 bits): agreement 44.3 %, 1199 model misses (33.6 MPKI).
- `--to kanata` + `rvw perf`: IPC 0.182, exact cycle/instret match with `result.json`; 160269 inferred `fetch/empty` cycles.
- `irqs --irq-schedule '1:0x0,2000:0x80,2200:0x0,4000:0x800,4200:0x0,6000:0x80,6200:0x0'`: pass; `--to interrupts` consistent (3 probe events, 3 C2 interrupts); `--to counts` and `--to hpm` (3 bindings) written. Re-run after the rebase onto main with the same result.
- `rvw/.venv/bin/python -m pytest rvw/tests/test_csim_formats.py -q`: 17 passed (2 new tests; the not-taken target test fails before the fix).
- Fast set: 880 passed, 1 skipped.

Not run: the VexRiscv example pytest suite, sbt test suites, the full Python suite, CI.

## Issues

Refs: probes follow-up (VexRiscv wiring, item 1 of 6).

Roadmap notes: SpinalProbes now has a second user (VexRiscv example) with real BTFN/gshare, Kanata, interrupt, counts and HPM conversions. Component sims: the C2/Spike converters keep decoded targets on not-taken branches.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 785

[#785](https://github.com/riscPrint/risc-v-workstation/pull/785). Merged: 2026-11-13T06:13:20Z.

Title: docs(cli): refresh the generated command reference

Audit evidence label: no code.

## Summary
Regenerate the command reference from the current CLI and MCP registrations.

## Testing
Parser construction, MCP listing without warnings, and all 42 top-level help commands pass. The docs staging tests pass (2 tests). The fast set is running. The command-reference test remains skipped. No native jobs ran.

## Issues
Sheriff maintenance. Roadmap notes: no feature or milestone change.


## PR 786

[#786](https://github.com/riscPrint/risc-v-workstation/pull/786). Merged: 2026-11-13T06:13:18Z.

Title: docs(rvw): regenerate the command reference

Audit evidence label: no code.

## Summary
Regenerate `docs/COMMAND_REFERENCE.md` from the current parsers and MCP declarations (sheriff batch).

## Testing
- `scripts/command-reference.py`; fast set on main 12892b19: 878 passed, 1 skipped.

## Issues
None.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 787

[#787](https://github.com/riscPrint/risc-v-workstation/pull/787). Merged: 2026-11-13T06:14:35Z.

Title: feat(init): add mapped core adapters and bounded doctor checks

Audit evidence label: unit tests only.

## Summary
Recover the existing mapped C1 adapter, init scaffold and bounded doctor option checks. Keep core signal names in project mappings. Add the PicoRV32 example. Preserve the four local commits after rebase.

## Testing
- Targeted init and doctor tests: 12 passed.
- Fast set: 1299 passed, 1 skipped, 7876 deselected. Unrelated failure: test_docs_site.py::test_docs_staging_does_not_write_sources. No docs-site files changed.
- CLI import and MCP discovery pass, with no skipped tool warning.
- Native runs and Scala tests NOT RUN in this recovery. PicoRV32 measurements in its README were recorded by the previous worker. Fresh Spinal native proof remains to be added.
- Full C1/C2 qualification is not established by these bounded doctor tests.

## Issues
Refs: #26, #35, #55

Roadmap notes: mapped init and bounded doctor checks are available. Fresh Spinal runtime, probe scaffold, full conformance and the --hdl sv mapped path remain follow-up work.


## PR 788

[#788](https://github.com/riscPrint/risc-v-workstation/pull/788). Merged: 2026-11-13T06:15:39Z.

Title: test(query): validate slang connectivity on the SERV core

Audit evidence label: unit tests only.

## Summary
Validate a second complete core with slang. SERV at f200eb2ed7b69ac1c6b8eddd47654522aeee5ce8 yields 11 components, 2420 signals, 177 registers, 1778 assignments and 6028 edges. All 16 cross-instance path checks agree with an independent native netlist traversal. The test also checks hierarchy and the elaborated W parameter.

## Testing
Native slang SERV test: 1 passed, 6 deselected. The fast set result is appended below. Not run: full Python suite, CI, simulation, statement-level source validation.

## Issues
Refs: #370. Statement precision and exact/conservative edge labels remain open. No issue closure is claimed.

Roadmap notes: The slang front end now has native connectivity evidence for both Ibex and SERV.

Fast set: 1288 passed, 1 skipped, 7876 deselected in 89.87 s.


## PR 789

[#789](https://github.com/riscPrint/risc-v-workstation/pull/789). Merged: 2026-11-13T06:16:57Z.

Title: feat(formal): generate fair command response environments

Audit evidence label: ran on seeded RTL fixture.

## Summary
Generate explicit fair environments for project-declared stream-response buses. Record service bounds and input constants. Add VexRiscv declarations and native outcomes: liveness bounded PASS at [1,10,30], retirement cover reached at [1,20]. No trap or instruction-data restriction is added.

## Testing
Targeted generator tests: 16 passed, 3 native prerequisite skips. Native VexRiscv: liveness PASS in 21.9 seconds and cover reached in 5.6 seconds under vex-conn and nice -n 10. Fast set: 1296 passed, 1 skipped, 7875 deselected. No BOOM jobs or unbounded proofs ran.

## Issues
The environment supports ordered response pulses for read commands. Writes need no response. It is not an AXI environment. Capacity is asserted rather than assumed. This finite liveness result applies only to the recorded service restrictions.

Roadmap notes: Generated RVFI wrappers now accept explicit protocol service assumptions. VexRiscv generated liveness passes at cycle 30 under the recorded fair environment. Unbounded proof and complete ISA signoff remain open.


## PR 790

[#790](https://github.com/riscPrint/risc-v-workstation/pull/790). Merged: 2026-11-13T06:17:49Z.

Title: fix(formal): decode interned rtlil hierarchy names

Audit evidence label: ran on seeded RTL fixture.

## Summary
Decode old escaped RTLIL names and Yosys 0.70 public/private interned names. Resolve leaf and suffix table entries before counting assertions across instances. Unresolved names cannot qualify a proof.

## Testing
- Decoder regressions: 3 passed.
- Pinned suite native counter tests at nice priority: 6 passed in 6.99 s. Includes valid projection and seeded bad increment.
- Required fast set: 1293 passed, 1 skipped, 7875 deselected.
- MCP listing: no skipped tool warning.
- Full suite and core proofs NOT RUN.

## Issues
Refs: #21, #294

Roadmap notes: the pinned Yosys 0.70 counter certificate now passes its native good/bad checks. This is a small counter proof, not core capacity evidence.


## PR 791

[#791](https://github.com/riscPrint/risc-v-workstation/pull/791). Merged: 2026-11-13T06:18:45Z.

Title: feat(privilege): check extension-state access gates

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Recover the interrupted state-enable work. Add JVT, AIA, indirect CSR, IMSIC, trigger-context and Zfinx instruction probes across M/S/U/VS/VU. Check model observations at named instructions, including cause/PC, virtual mode and denied retirement. Keep model subset groups separate from strict architectural groups.

## Testing
- Targeted tests: 16 passed.
- Native Spike: 30 non-H and 100 H self-check programs passed.
- All 208 model-profile programs compiled; Python reference expectations passed. These results are model-based.
- Fast set: 1294 passed, 1 skipped, 7849 deselected. The command-reference check is skipped upstream during the parallel push.
- NOT RUN: RTL, BOOM, full Python suite, long formal or CI. No DUT coverage is claimed.

## Issues
Refs: #176. Ssstateen-only implementations, RV32 high-half access and complete DUT qualification remain open. Project data must declare writable gates and extension support.

Roadmap notes: Extend state-enable generation to extension state and named C2 observations. Keep access-only CSR masks distinct from value checking. Retain the unsupported implementation profiles and DUT evidence gaps.


## PR 792

[#792](https://github.com/riscPrint/risc-v-workstation/pull/792). Merged: 2026-11-13T06:20:33Z.

Title: fix(agent): align playbook with integration evidence rules

Audit evidence label: unit tests only.

## Summary
Align the JSON agent playbook with INTEGRATION_GUIDE.md. Check artifact identities before diagnosis. Require repair workloads before the committed gate. Preserve unknown causes when dynamic evidence is missing. CLI, MCP and the generated setup guide use the same data.

## Testing
Guide tests: 6 passed. Public fast set: 1303 passed, 1 skipped, 7903 deselected. Native RTL and external agent trials NOT RUN for this documentation and playbook change.

## Issues
Refs: #27, #106.

Roadmap notes: The five existing guide workflows now state the integration evidence limits and the repair sequence. This does not establish automatic root cause.


## PR 793

[#793](https://github.com/riscPrint/risc-v-workstation/pull/793). Merged: 2026-11-13T06:20:51Z.

Title: feat(query): add semantic navigation for agents

Audit evidence label: unit tests only.

## Summary
Add CLI and MCP queries for definitions, references, per-instance parameters, structural module explanations, hierarchy diffs, captured signal types and port connection status. Native HDL builders retain constant port bindings, including unknown bits. Older databases report unavailable for missing bindings. Arbitrary HDL expressions remain unsupported. No intent or equivalence claim is inferred from structure.

## Testing
Targeted semantic tests: 3 passed. Fast set result below. Not run: full Python suite, CI, whole-core simulation.

## Issues
Refs: #26, #55, #370. Remaining: a full HDL expression type checker, token-level source references, general Spinal tied-port classification. Frontend validation limits recorded in the existing frontend PRs remain open.

Roadmap notes: CLI and MCP now expose structural module summaries, cross-hierarchy references, captured instance parameters and hierarchy diffs for agents.
Native HDL plus semantic tests: 11 passed, 2 skipped. MCP discovery: no skipped modules on stderr.
Fast set: 1305 passed, 1 skipped, 7917 deselected in 157.84 s.


## PR 794

[#794](https://github.com/riscPrint/risc-v-workstation/pull/794). Merged: 2026-11-13T06:21:18Z.

Title: feat(formal): collect native unbounded assertion observations

Audit evidence label: ran on seeded RTL fixture.

## Summary
Collect native finite observations for Boolean eventual-response and until SVA on both simulators. Retain every activated request and report pass/fail/cover/pending counts. Keep final non-overlapped requests pending. Prevent unresolved assumptions from producing a design-fault verdict. Feed witnessed completions to C1 coverage and reuse shared cancellation cleanup.

## Testing
- First set: 51 passed, including a 40-case native matrix across both simulators, five operators, both implication forms and positive/fault-or-pending cases.
- Additional native set: 17 passed. It covers completion-inclusive semantics, final non-overlapped requests, sampled activation, assumptions, unknown responses and bare until.
- Pending-assumption priority plus frontend guards: 12 passed. Existing simulation/hierarchical replay and frontend/table regression: 23 passed. These sets overlap.
- Positive C1 results imported two assertion/cover points through rvw cov.
- Fast set: 1299 passed, 1 skipped, 7933 deselected. The skip is the shared command-reference inventory check.
- Not run: full Python suite, BOOM builds/simulation, long formal jobs or full simulator scheduling qualification. General unbounded sequence simulation, local captures, cross-clock eventual response and disable cancellation remain refused. Pending obligations are inconclusive, not finite-deadline failures or liveness proofs.

## Issues
Refs: #61, #46

Roadmap notes: Native assertion-based simulation now accepts s_eventually and Boolean until families, with overlapping obligation counts and explicit pending evidence. Both backends share the source set. C1 and rvw cov receive witnessed completions. Unresolved assertion and assumption obligations keep the result inconclusive.


## PR 795

[#795](https://github.com/riscPrint/risc-v-workstation/pull/795). Merged: 2026-11-13T06:21:42Z.

Title: feat(regress): plan generated suites from project capabilities

Audit evidence label: unit tests only.

## Summary
Add `rvw regress plan` and MCP `regress_plan`. Read explicit project capabilities and list applicable generated suite families with missing requirements. Accept a project requirement catalog. Selection grants no execution evidence.

## Testing
Targeted tests: 2 passed. Fast set: 1292 passed, 1 skipped, 7877 deselected. MCP list: no skipped tools. No RTL runs are claimed by this change.

## Issues
Roadmap notes: generated-suite applicability has CLI and MCP support. Scenario selection within each family remains project-owned. No issue is closed.


## PR 796

[#796](https://github.com/riscPrint/risc-v-workstation/pull/796). Merged: 2026-11-13T06:22:46Z.

Title: test(formal): add private real-source revision recipes

Audit evidence label: ran on seeded RTL fixture.

## Summary
Add a private real-source revision recipe and a runner through `rvw formal equiv --gold-rev/--gate-rev`. Capture a SpinalHDL divider mux refactor and an unchanged VexRiscv square-root module across two core revisions. Keep source archives, committed generator identity and native logs.

## Testing
- Recipe unit test: 1 passed.
- Fast set: 1291 passed, 1 skipped, 7875 deselected.
- Native divider and square-root revision commands: both inconclusive at 180 seconds. Export timed out in the shared sbt queue before compilation. No eqy proof ran.
- NOT RUN: pipeline retiming, FSM recoding, clock gating, full-width arithmetic, core equivalence and CI.

## Issues
Refs: #18. This adds a reproducible integration case, not completed real-module proof evidence. The VexRiscv module is unchanged between the selected core revisions. The divider refactor is arithmetic control, not pipeline retiming.

Roadmap notes: Real-source revision recipes are available. Native proof evidence and the requested pipeline/FSM/clock-gate transformations remain open because source export did not obtain the sbt lock within the budget.


## PR 797

[#797](https://github.com/riscPrint/risc-v-workstation/pull/797). Merged: 2026-11-13T06:22:59Z.

Title: fix(formal): report native backend input limits

Audit evidence label: unit tests only.

## Summary
Retain exact failure diagnostics for native engines. Avy SIGSEGV rows include the folded AIG dimensions and observed zero-latch or multi-output input class. rIC3 rlive reports its internal removed-option CLI mismatch. Su Prove remains not_installed on the pinned macOS ARM64 suite. Do not replace errors with proof answers.

## Testing
- Targeted diagnostic and portfolio tests: 10 passed, 1 skipped.
- Native liveness references: 3 passed in 1.70 s at nice priority. rlive errors remain inconclusive.
- Fast set: 1319 passed, 1 skipped, 7903 deselected.
- Native Avy probe reproduced SIGSEGV with default and alternate SAT options on the zero-latch folded HWMCC input.
- Full core proofs and full suite NOT RUN. Internal Avy root cause is not established. These are observed failed input classes, not general support claims.

## Issues
Refs: #21, #294

Roadmap notes: backend limitations are now machine-readable. No new native engine qualification is claimed. Avy internal repair remains upstream work; l2s and k-live remain available for rIC3 liveness.


## PR 798

[#798](https://github.com/riscPrint/risc-v-workstation/pull/798). Merged: 2026-11-13T06:25:04Z.

Title: feat(query): add a design database language server and editor client

Audit evidence label: unit tests only.

## Summary
Add `rvw lsp` for stdio LSP navigation over captured Spinal and HDL design databases. Support definitions, hover with type/width/clock/drivers, structural references, captured source document symbols, full text sync and UTF-16 positions. `--lint-settings` runs the shared lint report on open/save and publishes active located findings. Expose navigation to agents through MCP `lsp_request`.

Add a VS Code feature using vscode-languageclient. Start it with `RVW: Start Design Database Language Server`. Configure lsp.database, lsp.executable and lsp.lintSettings. Require workspace trust before process launch.

## Testing
LSP tests: 3 passed. VS Code typecheck and build passed. VS Code tests: 27 passed, 0 skipped. MCP discovery stderr has no skipped modules. Fast set result below.

Not run: VS Code editor UI, full Python suite, CI, native frontend extraction in this PR. Captured source symbols do not include generated RTL files that have only Scala locations. Macro tokens and repeated instance declarations can be ambiguous. Navigation is captured, not live elaboration.

## Issues
Refs: #26, #55. Remaining: token maps, completion, rename, incremental per-module elaboration.

Roadmap notes: CLI/MCP design navigation now has an LSP interface and an opt-in VS Code client. Source edits require a database rebuild.
Fast set: 1323 passed, 1 skipped, 1 failed (`test_docs_site.py::test_docs_staging_does_not_write_sources`), 7918 deselected. The staging check uses tracked files and ran before the new README was committed. Targeted staging re-check after commit is recorded below.
After commit: docs staging tests 2 passed. The fast-set staging failure was due to the untracked new README and is resolved.


## PR 799

[#799](https://github.com/riscPrint/risc-v-workstation/pull/799). Merged: 2026-11-13T06:25:10Z.

Title: fix(init): stream external adapter build progress

Audit evidence label: unit tests only.

## Summary

Stream sbt output and lock messages to stderr from the generated Spinal adapter launcher. A fresh external core build previously hid all progress while waiting for the shared sbt lock. Keep stdout reserved for C1 JSON and preserve build failure refusal.

## Testing

- Targeted init tests: 22 passed.
- Fast set: 1289 passed, 1 skipped, 1 failed, 7876 deselected. The unrelated failure is test_docs_site.py::test_docs_staging_does_not_write_sources, an assertion in scripts/build-docs.py:48.
- Native scratch-core build is in progress. No full Python suite, BOOM build or long formal run was run.

## Issues

Refs: #34

Roadmap notes: external adapter setup now shows build and lock progress. This does not establish new-core runtime support.


## PR 800

[#800](https://github.com/riscPrint/risc-v-workstation/pull/800). Merged: 2026-11-13T06:26:40Z.

Title: feat(checks): bind native buses with declared clocks

Audit evidence label: ran on seeded RTL fixture.

## Summary
Bind captured buses with explicit project clock domains when combinational ports have no database domain. Preserve recorded domains and instance scope. Add a native five-bus capture and Verilator elaboration test. Finish inherited CDC generation by reusing lint obligations and retaining missing bindings.

## Testing
- Targeted Python: 28 passed.
- Fast suite: 1334 passed, 1 skipped, 1 failed, 7985 deselected. Unrelated failure: test_release_hygiene.py::test_tracked_text_has_no_personal_paths, examples/formal/equiv-real/README.md:7.
- CLI import and MCP discovery pass; no skipped modules.
- The sbt-based native test timed out in the shared lock queue. A later private compile of current SpinalChecks, SpinalDB and capture sources passed. Native capture found five buses; explicit binding generation was complete; Verilator --lint-only --assert passed all five bound instances. This was a direct native rerun, not an additional pytest pass.
- Full suite, core ISA qualification and formal bus proofs NOT RUN in this PR.

## Issues
Refs: #66

Roadmap notes: explicit bus clocks and CDC generation are available. Bus elaboration alone does not qualify protocol behavior or a connected core.


## PR 801

[#801](https://github.com/riscPrint/risc-v-workstation/pull/801). Merged: 2026-11-13T06:27:25Z.

Title: feat(sim): wire live uart clint and plic devices to core pins

Audit evidence label: ran on real core RTL.

## Summary

Connect project-configured UART, CLINT and PLIC models to real VexRiscv bus requests and interrupt pins. Add UART RX/TX and a 16-byte RX FIFO. Keep addresses, input bytes and pin routes in the captured simulation map.

Add an interrupt-driven UART echo program. It requires software, timer and external interrupt handlers before success. Record a real-core pass, a no-RX timeout control and another pass in the same persistent server. Both passing C2 streams have the same digest.

## Testing

- Scala `testOnly riscvsim.LiveDevicesSpec`: 3 passed, 0 skipped.
- Compile the generic devices and example adapter with the cached Scala compiler into an isolated output directory: passed.
- Direct JVM launch with native identity capture under `vex-simsrv`, `nice -n 10`, private core revision a62c145aa042a5de874344e0a7683bd7c8c8c870: echo pass at 4,079 cycles / 868 retirements; no-RX control timeout at 20,000 cycles; fresh echo pass with identical C2 SHA-256. Both passes have MSIP, MTIP and MEIP C2 traps. No inconclusive result.
- Fast Python set: 1,289 passed, 1 skipped, 1 failed, 7,875 deselected. Existing unrelated failure: `rvw/tests/test_docs_site.py::test_docs_staging_does_not_write_sources` (staging assertion in `scripts/build-docs.py`).
- `import rvw.cli` and `rvw mcp --list`: passed with no skipped tools.
- Standard launcher native pytest was cancelled while queued on shared sbt. Full Python suite, BOOM, Linux and device snapshot qualification: NOT RUN.

## Issues

No issue closed. UART baud timing, modem pins, multiple PLIC contexts, device snapshots and OS boot remain open.

Roadmap notes: live-core MMIO device wiring now has bounded VexRiscv RTL evidence with UART RX FIFO, TX echo, CLINT and PLIC interrupt handlers. The no-input control times out, and a later request resets device state. This does not qualify OS boot or full device semantics.


## PR 802

[#802](https://github.com/riscPrint/risc-v-workstation/pull/802). Merged: 2026-11-13T06:28:04Z.

Title: fix(formal): retain exact conditional proof predicates

Audit evidence label: ran on seeded RTL fixture.

## Summary
Retain exact elaborated assumption predicates and enables in portfolio and benchmark results. Pin the captured model and source text by hash. Record a fresh PicoRV32 measurement with the memory-progress and initial-reset restrictions in each row. Keep conditional answers inconclusive.

## Testing
- Targeted tests: 11 passed, 1 skipped.
- Fresh pinned native PicoRV32 PDR and rIC3: both native pass, both qualified inconclusive. Eight-second stage limit at nice priority.
- Required fast set: 1338 passed, 1 skipped, 1 failed, 7977 deselected. Unrelated pre-existing failure: test_release_hygiene.py::test_tracked_text_has_no_personal_paths reports examples/formal/equiv-real/README.md:7.
- Full suite and whole-core qualification NOT RUN.

## Issues
Refs: #21, #294

Roadmap notes: PicoRV32 conditional observations now carry their precise restrictions and predicate/model identities. Assumption activation and environment qualification remain unchecked.


## PR 803

[#803](https://github.com/riscPrint/risc-v-workstation/pull/803). Merged: 2026-11-13T06:28:10Z.

Title: perf(arch): parse c2 and schedule shared components in native code

Audit evidence label: unit tests only.

## Summary

Add a narrow native C2/1 reader that validates and packs integer timing records without per-retirement Python objects. Unsupported formats and fields fall back to the shared C2 validator. Add a native component issue service for direction prediction, BTB/RAS/indirect prediction, ordered data-cache and TLB timing. Preserve Python scheduling as the reference and fallback.

Add four warmed full-public-call measurements per 500,000-instruction synthetic stream. These include file reads, C2 validation, packing, scheduling and input/engine hashes. Raw seconds and input identities are committed in `Arch/ooo/benchmark-results-e2e.json`. CPU seconds are separate from elapsed throughput. The component path has not met the requested millions/s wall-time target on this shared host. This is partial performance work, not native-speed or RTL qualification.

Roadmap notes: native integer C2 parsing/packing and component-backed scheduling are implemented. Further end-to-end speed work, FTQ/FDIP, Spike wrong-path comparison, live RTL held-out calibration and larger workload evaluation remain open.

## Testing

- Targeted native/parser tests: 22 passed, including compressed RV32/RV64 and component reference parity. Earlier targeted scheduler/components/core set: 30 passed.
- Fast set: 1,308 passed, 1 skipped, 7,875 deselected in 179.32 seconds. The skip is the command reference check deferred by the worker brief.
- `import rvw.cli` and `rvw mcp --list` checked.
- Short native synthetic throughput runs used `nice -n 10`.
- NOT RUN: gem5 builds/runs, RTL builds/runs, Spike wrong-path replay, held-out RTL accuracy or speed qualification, full Python suite, GitHub CI wait.

## Issues

Refs: #356

Keep #356 open. Synthetic throughput is not the held-out RTL speed and accuracy evidence that issue requires.


## PR 804

[#804](https://github.com/riscPrint/risc-v-workstation/pull/804). Merged: 2026-11-13T06:30:20Z.

Title: feat(query): cache HDL databases by source and tool hashes

Audit evidence label: unit tests only.

## Summary
Add opt-in source-hash database reuse with `rvw query build-hdl --cache-dir DIR` and MCP `query_build_hdl(cache_dir=DIR)`. Hash sources, includes, options, selected executable and plugin contents, Scala roots and translator/schema code. Verify stored database hashes before reuse. Publish output with temporary-file rename. Changed designs rebuild as a whole; this is not per-module incremental elaboration.

## Testing
Cache unit tests: 2 passed. A native small-design smoke rebuilt in 0.4614 s and hit the cache in 0.0033 s. These times are for a small smoke only. Fast set and native regression results below.

Not run: full Python suite, CI, core simulation. Shared tool libraries and the complete process environment are not in the key; clear the cache after those change. Keep cache and outputs outside source trees.

## Issues
Refs: #26, #55. Per-module incremental elaboration remains unsupported.

Roadmap notes: HDL database builds now reuse whole-design results when source, options, selected tools and translator hashes match.
Native frontend, blocks, semantic and cache tests: 33 passed in 72.53 s. Fast set: 1341 passed, 1 skipped, 1 failed, 7978 deselected. The unrelated failure is `test_release_hygiene.py::test_tracked_text_has_no_personal_paths`, which reports `examples/formal/equiv-real/README.md:7:personal_path`. That file is outside this change. MCP discovery has no skipped module on stderr.


## PR 805

[#805](https://github.com/riscPrint/risc-v-workstation/pull/805). Merged: 2026-11-13T06:30:05Z.

Title: feat(soc): add bus ingress bridges and peripheral clock domains

Audit evidence label: unit tests only.

## Summary

Add AXI4, AXI4-Lite and TileLink ingress bridges to the APB composer. Keep the existing APB3 wrapper trait stable. Preserve memory byte strobes. Reject partial legacy MMIO writes before peripheral selection. Add named peripheral clock/reset domains with a library toggle handshake and synchronized level IRQs. Use device clock values in device-tree exports.

The fabric still uses the Spinal APB decoder/router. Native AXI/TileLink crossbars, AXI width conversion, arbitrary peripheral bus conversion and independent reset recovery remain open. TileLink width conversion uses the library adapter but wider traffic is not yet simulated.

## Testing

- Targeted composer tests: 17 passed.
- Fast set: 1299 passed, 1 skipped, 7875 deselected.
- SpinalHDL 1.15.0 compile passed. Follow-up Scala compilation used the cached compiler and IDSL plugin under the private vex-soc lock.
- AXI4, TileLink and CDC fixtures elaborated. Generated APB3 composition with a separate RAM clock domain elaborated.
- Verilator with assertions: BusSmoke passed seed 31 on one clock and across periods 10 and 14. Checked byte/halfword writes, zero strobes, legacy MMIO rejection, unmapped access errors and response backpressure.
- CLI import and MCP listing passed after rebase. No skipped MCP module.
- NOT RUN: AXI/TileLink traffic simulation, wider TileLink traffic, structural lint extraction, formal CDC/reset/decode proofs, real CPU tests, full Python suite, GitHub CI.

## Issues

Refs: #130. No issue is closed.

Roadmap notes: SoC composition now accepts three additional core bus types and named peripheral domains. Memory byte writes and bounded asynchronous bus traffic have RTL smoke evidence. Native crossbars and broader bus/core qualification remain open.


## PR 806

[#806](https://github.com/riscPrint/risc-v-workstation/pull/806). Merged: 2026-11-13T06:30:24Z.

Title: feat(agent-bench): qualify project-owned native mutation tasks

Audit evidence label: unit tests only.

## Summary
Add a generic native seeded-task runner with CLI and MCP entries. Task data pins the source and owns all core paths, mutations and workloads. Supply ten VexRiscv tasks. Copy sources into disposable Git workspaces, reproduce failures, reverse each mutation and check repaired workloads plus passing controls. Require matching C1/C2 identities and different RTL hashes. Keep every attempted result.

## Testing
Targeted native-runner tests: 5 passed. Public fast set: 1323 passed, 1 skipped, 7904 deselected in 174.19s (0:02:54). MCP discovery has no skipped-module warnings.

Native attempts used the private pinned source copy and vex-agent lock. Attempts with 110- and 300-second limits produced no C1 result. The longer retry also produced no C1 result. A thread dump showed Scala compilation still active after more than ten minutes. That retry was stopped because it exceeded the brief's short native smoke limit. Shared sbt resources were contended, but no single timeout cause is established. All native attempts remain inconclusive. All ten mutation definitions apply and reverse against the source pin. No native task qualification is claimed. BOOM, the full Python suite and full native repair campaigns NOT RUN.

## Issues
Refs: #364. Dynamic Scala cause joins, native synthetic designs and external agent repairs remain open. The evaluator supplies the repair during task qualification.

Roadmap notes: Native task qualification now has a generic implementation and ten pinned VexRiscv mutations. Qualification is separate from agent reasoning and C4 acceptance.


## PR 807

[#807](https://github.com/riscPrint/risc-v-workstation/pull/807). Merged: 2026-11-13T06:30:27Z.

Title: feat(formal): run unbounded rvfi instruction portfolios

Audit evidence label: ran on real core RTL.

## Summary
Add `rvw formal riscv-proof` and MCP `formal_riscv_proof`. Capture upstream prove-mode instruction checkers with RISCV_FORMAL_UNBOUNDED and hash each source. Reuse the native engine-race portfolio. Keep source-assumption activation limits and per-engine outcomes. Do not relabel bounded checks as proofs.

## Testing
Twelve targeted tests passed. MCP discovery has no skipped-tool stderr. Fast set: 1320 passed, 1 skipped, 7905 deselected. Native outcomes: ADD and AND with fair buses did not close through PDR/Yices at 180 seconds. Unconstrained AND PDR timed out at 180 seconds. Unconstrained LUI PDR timed out at 240 seconds. No unbounded proof closed. Native attempts use private copies, vex-conn and nice -n 10. No BOOM jobs, full Python suite, Vexii formal jobs or full 37-check induction campaign ran.

## Issues
Only instruction checks are supported by this capture. It refuses requested consistency checks rather than dropping them. Source assumptions keep the portfolio campaign inconclusive without activation evidence. Retirement cover is a separate bounded job. No formal ISA signoff is granted.

Roadmap notes: Upstream unbounded instruction checkers can now run through the engine portfolio from a selected project. Record actual engine closures separately from bounded campaign success. Full adapter conformance and complete-machine ISA signoff remain open.


## PR 808

[#808](https://github.com/riscPrint/risc-v-workstation/pull/808). Merged: 2026-11-13T06:33:10Z.

Title: feat(formal): compare finite ram and register implementations

Audit evidence label: ran on seeded RTL fixture.

## Summary
Add exact finite-memory lowering to `rvw formal equiv --memory-map --unmatched-state prove`. This permits RAM versus register-array comparisons with the existing per-output latency contract. Preserve mapped bit connections and initialization attributes. Give array/debug names legal state inventory aliases. Expose the option through the existing MCP tool. Correct a personal path in the real-source recipe documentation.

## Testing
- Native targeted memory and existing equivalence tests: 26 passed in 197.96 seconds. Each proof uses a short budget and `nice -n 10`.
- Native controls: RAM versus explicit registers proved at zero lag and one read cycle of lag. An injected result bit change produced a counterexample.
- Fast set after the documentation correction: 1339 passed, 1 skipped, 7981 deselected in 177.45 seconds.
- MCP discovery: no skipped-tool warning.
- NOT RUN: real core memory proofs, large memories, internal partition cut proofs, CI or full suite.

## Issues
Refs: #18. This is exact finite storage lowering, not an automatic memory abstraction or a complete memory refinement engine. Automatic internal partition proofs remain open.

Roadmap notes: Finite RAM and explicit register implementations can now use closed output equivalence with fixed read-latency differences. State equality is not assumed. Larger memory abstraction and automatic cut-point dependency proofs remain open.


## PR 809

[#809](https://github.com/riscPrint/risc-v-workstation/pull/809). Merged: 2026-11-13T06:34:29Z.

Title: feat(agent-bench): score misleading and incomplete evidence

Audit evidence label: unit tests only.

## Summary
Add five fixture tasks for stale RTL, wrong ELF, unsupported fields, incomplete coverage and missing completion. Score whether clients reject misleading evidence and preserve inconclusive outcomes. Even a correct expression cannot earn a repair result when required evidence is missing. Keep required/preserved counts and false-fix denominators.

## Testing
Targeted fixture and misleading-evidence tests: 11 passed. Scripted dry runs exercised both careful and careless clients. Public fast set: 1390 passed, 1 skipped, 7990 deselected, 1 unrelated failure. `test_release_hygiene.py::test_tracked_text_has_no_personal_paths` finds paths in existing formal result files and formal READMEs. This change does not edit those files. The brief permits delivery with failures outside the assigned area.

Native artifact parsing, RTL repairs and LLM trials NOT RUN in this fixture change.

## Issues
Closes: #106. These are fixture evidence challenges. Actual native artifact identity and dynamic source joins remain tracked separately by #364 and #27.

Roadmap notes: Agent benchmark fixtures now score unsupported observations, incomplete workload coverage and inconclusive outcomes as well as stale hashes and wrong repairs.


## PR 810

[#810](https://github.com/riscPrint/risc-v-workstation/pull/810). Merged: 2026-11-13T06:35:13Z.

Title: feat(formal): measure compiled core property portfolios

Audit evidence label: ran on real core RTL.

## Summary
Run the three-engine portfolio on all 43 captured VexRiscv riscv-formal safety models. Add pinned RTLIL input support, at most three workers, and conservative compiled cell-output cuts. Record per-case native results, wall times and model hashes. Apply RAM and adder/state cuts to all models and UF to the eight models with a multiply cell. No qualified solve or abstraction gain was earned.

## Testing
- Targeted portfolio/compiled tests: 10 passed, 1 skipped.
- Native baseline: 129 jobs. PDR/rIC3 each timed out on 43; Yices timed out on 29 and returned inconclusive on 14. Eight-second total SBY limit.
- Native variants: 172 observations. RAM/adder cuts timed out on 43 each. State cuts returned five abstract failures and 38 witness reconstruction errors. UF remained inconclusive on eight; 35 had no operator. Four-second native stage limits. All ran at nice priority, at most three concurrent jobs.
- Fast set: 1343 passed, 1 skipped, 1 unrelated failure, 7987 deselected. test_release_hygiene.py::test_tracked_text_has_no_personal_paths reports examples/formal/equiv-real/README.md:7.
- Post-rebase targeted tests and MCP discovery checked.
- Core build, full suite, longer proofs and absent generated formal autocheck/protocol/CSR bundles NOT RUN. Different limits prevent a speed comparison.

## Issues
Refs: #21, #294

Roadmap notes: real generated core models now have measured capacity and abstraction tables. All remain unqualified/unsolved. Source restrictions, fixed check-cycle activation and witness reconstruction are explicit limits. Adder cuts are broader than leaf counter quotients. The inspected example has no generated formal autocheck/protocol/CSR bundle; those property classes remain pending their generation and binding flow.


## PR 811

[#811](https://github.com/riscPrint/risc-v-workstation/pull/811). Merged: 2026-11-13T06:35:24Z.

Title: test(query): qualify a second real VHDL design and record graph limits

Audit evidence label: unit tests only.

## Summary
Exercise a second real VHDL design: NEORV32 UART at 7bd0858bed243e5e32521a8ffbeef8c68b68c653, with RX_FIFO_DEPTH=4 and TX_FIFO_DEPTH=4. It produces 3 components, 1013 signals, 131 registers, 2 memories, 805 assignments and 3398 edges. The RX declaration maps to the original VHDL line.

The independent native connectivity comparison is inconclusive. The conservative database graph contains a path from uart_ctsn_i to uart_rtsn_o that is absent in the GHDL bit graph. The test fails on missing native paths and explicitly reports xfail when extra conservative paths remain. No exact connectivity match is claimed.

## Testing
Native UART test and fast set results below. Not run: runtime UART simulation, full Python suite, CI.

## Issues
Refs: #371, #370. Exact bit connectivity through packed aliases remains open. Per-instance VHDL generics and foreign-model contracts also remain open.

Roadmap notes: Second-design VHDL extraction has native evidence. Exact connectivity qualification is inconclusive because packed aliases add paths.
Native UART: 1 xfailed, 5 deselected in 36.27 s. The sole extra path is uart_ctsn_i -> uart_rtsn_o; no native paths are missing across the 16 comparisons. Fast set: 1370 passed, 1 skipped, 1 failed, 7988 deselected. The unrelated release hygiene failure reports personal paths under examples/formal/deep/picorv32-conditions-results.json. Those files are unchanged here.


## PR 812

[#812](https://github.com/riscPrint/risc-v-workstation/pull/812). Merged: 2026-11-13T06:35:20Z.

Title: feat(privilege): add seeded trap and return sequences

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add seeded RV64 privilege transitions. Each step selects M/S/U, a trap instruction and legal exception delegation. Check cause, exact PC, saved privilege, retained register and MRET/SRET return. Record the full seed plan and functional groups in the campaign manifest. Bind denied state-enable instructions to the expected ELF opcode even when they do not retire.

## Testing
- Targeted tests: 46 passed.
- Native Spike: four actual self-checking programs passed, with 32 transitions per program and 13 mode/operation/handler groups.
- Fast set: 1326 passed, 1 skipped, 7903 deselected. Three temporary-directory cleanup warnings; no test failure.
- NOT RUN: DUT/RTL, BOOM, full Python suite, long formal or CI. Fixture observation tests do not establish DUT coverage.

## Issues
Refs: #139, #176. Random generation covers synchronous M/S/U traps and returns only. Interrupts, nested handlers, guest transitions, arbitrary CSR writes and full DUT qualification remain open. State-enable extension probes were merged separately in #791.

Roadmap notes: Add reproducible seeded trap/return/delegation programs to the existing privilege C1 suite path. Keep strict architectural evidence requirements and model-subset limits.


## PR 813

[#813](https://github.com/riscPrint/risc-v-workstation/pull/813). Merged: 2026-11-13T06:35:34Z.

Title: feat(arch): connect ftq runahead to shared instruction prefetch

Audit evidence label: unit tests only.

## Summary

Expose explicit instruction prefetch requests through the ComponentSims C/Python interface. Connect the own-model FTQ to that service with optional `frontend.fdip`. Admit one actual-path target per cycle, bound runahead by FTQ capacity, and delay fetch by target prediction latency. Keep native MSHR limits, memory hierarchy and prefetch statistics.

This is a partial implementation of the requested FTQ/FDIP item. It uses oracle committed-path targets. It does not replay wrong paths or claim measured error bounds. The current Spike adapter exposes no PC redirect or architectural checkpoint/restore interface. Implementing that producer needs changes in `Cosim/` and `rvw/cosim/`, outside this worker's assigned files. Debug snapshots contain debug registers and cannot restore an architectural execution state and memory image.

Roadmap notes: FTQ-directed shared instruction prefetch is implemented and tested. Predicted target admission, target discard/repair on a miss, Spike wrong-path replay, measured error bounds and RTL correlation remain open.

## Testing

- Targeted FTQ/component/frontend set: 10 passed.
- Fast set: 1,362 passed, 1 skipped, 7,987 deselected, 1 failed in 172.10 seconds. The unrelated failure is `rvw/tests/test_release_hygiene.py::test_tracked_text_has_no_personal_paths`. It reports personal paths in `examples/formal/deep/picorv32-conditions-results.json` and `examples/formal/equiv-real/README.md`. Those files are outside this change. The skip is the deferred command reference check. The worker brief permits merge for unrelated fast-set failures.
- `import rvw.cli` and `rvw mcp --list` checked with no skipped-tool errors.
- NOT RUN: Spike wrong-path replay, measured wrong-path bounds, RTL runs, gem5, full Python suite, GitHub CI wait.

## Issues

Refs: #357

Keep #357 open for the missing wrong-path and prediction work.


## PR 814

[#814](https://github.com/riscPrint/risc-v-workstation/pull/814). Merged: 2026-11-13T06:35:31Z.

Title: feat(sim): boot freertos on rtl with live device checkpoints

Audit evidence label: ran on real core RTL.

## Summary

Boot pinned FreeRTOS V11.2.0 on real VexRiscv RTL. Two tasks write UART output and use timer-driven delays. Success requires both tasks and at least six kernel ticks.

Extend the existing live bridge checkpoint harness with project-mapped MMIO devices. Save and restore UART FIFO/output/input position, CLINT timer/deadline and PLIC claim state beside RTL, RAM, pending responses and C2 prefix. Bind device implementation and map identity in the envelope. Add build instructions, native regression and a measured result record.

## Testing

- Build clean external FreeRTOS kernel 0adc196d4bd52a2d91102b525b0aafc1e14a2386 with RISC-V GCC: passed.
- Direct captured native JVM run, private VexRiscv a62c145aa042a5de874344e0a7683bd7c8c8c870, Verilator, seed 1, fixed memory latency 0: pass at 28,881 cycles and 8,667 retirements. UART ends with `FreeRTOS PASS`.
- Live checkpoint at retirement 5,000 / cycle 7,206 in the manual-clock bridge harness. Save and fresh-process restore both finish at cycle 9,421 / 6,480 retirements. Full C2 bytes and UART output are equal. Each native command used `vex-simsrv` and `nice -n 10`.
- Four Scala device tests passed, including pending FIFO, claimed PLIC and timer restore, using isolated compiler output and ScalaTest.
- Fast Python set: 1,338 passed, 1 skipped, 2 failed, 7,987 deselected. Unrelated failures: `test_docs_staging_does_not_write_sources` and `test_tracked_text_has_no_personal_paths` (the latter reports examples/formal/equiv-real/README.md).
- Standard launcher pytest collected and skipped without FREERTOS_KERNEL. Its equivalent native build/save/restore was run directly with the compiled example classes to avoid the shared sbt queue.
- CLI import and MCP tool discovery passed. Full Python suite, BOOM, Linux and OpenSBI: NOT RUN.

The standard and bridge harnesses use different bus timings. Their cycle counts are not a speed comparison.

## Issues

No issue closed. Cross-build or cross-machine checkpoint portability remains open. No Linux-capable VexiiRiscv configuration was built. This M-mode example does not supply supervisor mode or an MMU.

Roadmap notes: a real FreeRTOS kernel now boots on VexRiscv RTL, runs two timer-driven tasks and resumes from live device/RTL state in a fresh process with complete C2 equality. Linux/OpenSBI, portable replay bundles and general OS qualification remain open.


## PR 815

[#815](https://github.com/riscPrint/risc-v-workstation/pull/815). Merged: 2026-11-13T06:37:02Z.

Title: feat(formal): add isa kit signoff command

Audit evidence label: unit tests only.

## Summary
Add `rvw formal isa` and MCP `formal_isa`. Run the selected bounded kit and optional unbounded instruction portfolio. Print per-check scope and explicit unsupported machine and adapter gaps. Preserve timeout and unreachable-cover results as inconclusive.

## Testing
Five targeted tests passed. Fast set results are recorded below. Native proofs, BOOM builds and full Python suite NOT RUN for this item.

## Issues
No issue is closed. Complete-machine bindings and adapter conformance remain gaps.

Roadmap notes: ISA kit front command is available. It does not grant full ISA signoff.

Fast set: 1392 passed, 1 skipped, 1 failed, 7992 deselected. The failure is `test_release_hygiene.py::test_tracked_text_has_no_personal_paths` in existing example evidence files. This PR adds no personal paths.


## PR 816

[#816](https://github.com/riscPrint/risc-v-workstation/pull/816). Merged: 2026-11-13T06:37:59Z.

Title: fix(formal): report invalid autocheck inputs as json

Audit evidence label: unit tests only.

## Summary

Return exit 2 and structured JSON for invalid autocheck manifests and port bindings. A fresh core manifest that omitted clock/reset input declarations previously raised an uncaught Python exception.

## Testing

- Three targeted CLI tests pass: missing file, invalid schema and missing clock/reset bindings.
- Fast set: 1341 passed, 1 skipped, 2 unrelated failures, 7979 deselected. Failures: test_docs_site.py::test_docs_staging_does_not_write_sources and test_release_hygiene.py::test_tracked_text_has_no_personal_paths.
- Native scratch-core invocation reproduced the original error. No whole-core proof, full Python suite or BOOM build was run.

## Issues

Refs: #34

Roadmap notes: invalid autocheck inputs now give an actionable error. No proof capability changes.


## PR 817

[#817](https://github.com/riscPrint/risc-v-workstation/pull/817). Merged: 2026-11-13T06:39:16Z.

Title: feat(agent-bench): run bounded external mcp client trials

Audit evidence label: unit tests only.

## Summary
Launch an external client CLI with wall-time and MCP call budgets. The evaluator owns the private fixture pack and independent scores. Pass only the authenticated loopback MCP endpoint and token to the child. Keep partial transcripts on timeout or disconnect. Store repeated trials, client configuration, machine profile, pack digest and score denominators. Test the same path with a scripted external client.

## Testing
External client tests: 6 passed. The tests include repeated MCP trials, false repairs, disconnects, process-group timeout, exhausted call budgets and a missing executable. MCP discovery reports no skipped modules. Public fast set: 1397 passed, 1 skipped, 7994 deselected, 1 unrelated release-hygiene failure. `test_release_hygiene.py::test_tracked_text_has_no_personal_paths` finds personal paths in existing formal files. Those files are outside this change. The brief permits delivery with this unrelated failure. The CLI smoke trial on the incomplete-coverage task preserved the inconclusive result.

LLM/API calls, native RTL repair trials and OS sandboxing NOT RUN. The external CLI must disable its own non-MCP tools. The runner exposes no shell or file tools over MCP. Hostile clients are outside C8 scope.

## Issues
Refs: #366, #27. This completes the bounded fixture-client runner. Provider-specific CLI configuration and scored LLM/native trials remain separate work.

Roadmap notes: External agent CLI trials now use independent fixture scoring, repeated attempts and bounded execution. Fixture results do not earn native repair acceptance or replace human review.


## PR 818

[#818](https://github.com/riscPrint/risc-v-workstation/pull/818). Merged: 2026-11-13T06:40:10Z.

Title: test(query): validate FIRRTL ingestion on the standard Chisel queue

Audit evidence label: unit tests only.

## Summary
Add a second Chisel design using the standard Chisel 6.5.0 Queue, with 8-bit data and four entries. Preserve its emitted FIRRTL and a pinned Scala generator. Record the source artifact SHA-256 and reproduction command. Extraction gives 3 components, 220 signals, 25 register nodes, 1 memory, 163 assignments and 637 edges.

The native test checks wrapper and standard-library Scala mappings, synchronous pointer resets and all nine path queries against an independent traversal of emitted RTL. The standard library source check runs when its matching external sources are present. Missing library sources do not create a claimed binding.

## Testing
Generator: `nice -n 10 scala-cli run Queue.scala --server=false` with Scala 2.13.14, Chisel and plugin 6.5.0. Native firtool/Yosys Queue test: 1 passed, 5 deselected in 2.59 s. Fast set result below.

Not run: runtime Queue simulation, full Python suite, CI. This is static database and source-map evidence, not execution qualification.

## Issues
Refs: #372. Remaining: external-module model contracts, generator configuration identity beyond the pinned fixture and fused-location precision.

Roadmap notes: FIRRTL ingestion now has native source-map and connectivity evidence for an accumulator design and the standard Chisel Queue.
Fast set: 1402 passed, 1 skipped, 1 failed, 7995 deselected. The unrelated failure remains `test_release_hygiene.py::test_tracked_text_has_no_personal_paths`, reporting examples/formal/deep/picorv32-conditions-results.json. No change to that file is included.


## PR 819

[#819](https://github.com/riscPrint/risc-v-workstation/pull/819). Merged: 2026-11-13T06:40:47Z.

Title: feat(formal): select strategies from features and proof history

Audit evidence label: unit tests only.

## Summary
Add formal strategy CLI and MCP planning from elaborated feature counts and qualified benchmark history. Choose engine order and candidate RAM, UF, counter-leaf or state-cut abstractions. Liveness requires a reduction. Conditional and bounded passes cannot train the order. Retain input hashes and a native model planning example. Remove local tool paths accidentally recorded in the earlier PicoRV32 sample, keeping tool hashes.

## Testing
- Strategy tests: 3 passed.
- Native VexRiscv model planning: 1553 state bits, two memory cells, 13 adders. HWMCC qualified history ranks PDR then rIC3. PicoRV32 conditional history is excluded.
- Fast set: 1408 passed, 1 skipped, 1 release hygiene failure, 7996 deselected. Fixed this area's six local paths after that run. Targeted release hygiene rerun reports only unrelated examples/vexriscv/formal/GENERATED_RESULTS.md lines 104 and 132-135.
- MCP discovery: no skipped warning. Full suite and strategy-selected core proofs NOT RUN. The command plans only.

## Issues
Refs: #21, #294

Roadmap notes: automatic explainable strategy plans use real recorded proof outcomes and feature rules. No ML framework or unearned proof result. Cross-design prediction and automatic counter leaf binding remain outside this slice.


## PR 820

[#820](https://github.com/riscPrint/risc-v-workstation/pull/820). Merged: 2026-11-13T06:41:22Z.

Title: feat(init): prove mapped setup on a fresh spinal core

Audit evidence label: ran on seeded RTL fixture.

## Summary
Make mapped init usable for a fresh Spinal core. Add the missing SpinalDB build dependency, RVFI and SpinalProbes templates, optional probe collection and a small sequential RV32I integration fixture. Reuse build-wiring checks to reject an incompatible Scala version before writing files.

Generic assumptions fixed: the generated query entry previously lacked its runtime library; mapped init assumed Scala 2.13 compatibility without checking the core build. Tests cover both defects. Signal names remain project data.

## Testing
- Targeted mapped init: 8 passed.
- Fast set: 1302 passed, 1 skipped, 7877 deselected. Existing unrelated failure: test_docs_site.py::test_docs_staging_does_not_write_sources. No docs-site files changed.
- Fresh scratch core scaffolded with one init command. Generated launcher compiled and ran smoke: pass, 15 instructions, 67 cycles; Spike match.
- add, beq, lw, sw and seeded random-latency smoke: 5 C1 passes without inconclusive markers; 5 complete Spike matches, 1380 instructions total. Used the already compiled classpath with the native/source identity collector for the batch, to avoid another sbt queue wait.
- Generated query entry built schema rvw.designdb/20: 112 signals, 52 registers, PDG/blocks/HGLDD artifacts. query where pc resolves the Scala source and reset value.
- Probe path compiled during query build. Native probe capture NOT RUN. Opt-in temporary-directory pytest was not run as a whole; the same fixture and commands were exercised manually in a scratch project.
- Full ISA/interrupt/CSR qualification, BOOM and full Python/Scala suites NOT RUN. The tiny fixture has no CSR/interrupt/trap implementation.

## Issues
Refs: #26, #35, #55, #70

Roadmap notes: fresh Spinal mapped setup now has native runtime, C2/reference and query evidence. Probe collection is optional; native event capture and broader core/version qualification remain open.


## PR 821

[#821](https://github.com/riscPrint/risc-v-workstation/pull/821). Merged: 2026-11-13T06:41:59Z.

Title: feat(privilege): check rv32 state-enable split banks

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add RV32 Smstateen low/high bank programs with and without H. Check all four SE indices, ENVCFG, indirect CSR and Zfinx gates. Verify selected writable-bit readback, higher-level masking, opposite-half retention and independent banks. Check M/S/U/VS/VU access with exact exception cause and PC. Add high-half CSRs to functional coverage domains.

## Testing
- Targeted tests: 45 passed.
- Native Spike: 208 actual self-check programs passed (48 without H, 160 with H). One initial non-H case was inconclusive because dtc_output could not start; the exact ELF passed on a single retry. This infrastructure error is retained in the test record.
- Fast set: 1410 passed, 1 skipped, 7994 deselected, 1 unrelated failure: test_release_hygiene.py::test_tracked_text_has_no_personal_paths. It reports existing formal example artifacts: examples/formal/deep/picorv32-conditions-results.json and examples/vexriscv/formal/GENERATED_RESULTS.md. No waiver or edit to those files.
- NOT RUN: DUT/RTL, BOOM, full Python suite, long formal or CI.

## Issues
Refs: #176. Project data must declare writable gates and implemented extensions. Ssstateen-only implementations, other extension-state gates and DUT qualification remain open. The compiler ISA omits unsupported assembler extension names; reference ISA keeps them.

Roadmap notes: Extend the state-enable suite to RV32 high-half state and guest transitions. Keep native self-check evidence separate from strict C1/DUT comparison.


## PR 822

[#822](https://github.com/riscPrint/risc-v-workstation/pull/822). Merged: 2026-11-13T06:43:16Z.

Title: feat(formal): cancel native assertion obligations asynchronously

Audit evidence label: unit tests only.

## Summary
Cancel native eventual-response and until obligations asynchronously from stable top-input disable controls. Record cancelled counts without adding passes or erasing earlier failures. Include delayed non-overlapped requests in cancellation. Treat only Boolean-true disable values as cancellation. Apply the same true-only rule to finite temporal monitors so X/Z cannot suppress a fault.

## Testing
- 61 targeted tests passed across new cancellation and existing temporal cases.
- 25 frontend/table/simulation regression tests passed.
- Six native X/Z disable tests passed. Both simulators cover cancellation/restart and preservation of earlier failures. A native input-limit test refuses a disable change at the property event timestamp even when both ports are declared clocks.
- Fast set: 1341 passed, 1 skipped, 7987 deselected, 1 failed. The failure is outside this patch: `test_release_hygiene.py::test_tracked_text_has_no_personal_paths` reports `examples/formal/equiv-real/README.md:7`. No equivalence-area file was edited. The skip is the shared command-reference inventory check.
- After rebase: 17 frontend/table tests passed; CLI and MCP inventory loaded without skipped modules.
- Not run: full Python suite, BOOM builds/simulation, long formal jobs or full scheduling conformance. Internal and sampled native unbounded disable controls, same-event disable changes and formal unbounded cancellation remain refused.

## Issues
Refs: #61, #46

Roadmap notes: Native unbounded assertion observations now support asynchronous input-controlled cancellation with explicit cancelled counts. Pending and delayed requests are removed without a pass. Earlier failed observations persist. Finite and unbounded native monitors do not treat X/Z disable values as true. The formal liveness engine adapter's asynchronous-state limits are unchanged.


## PR 823

[#823](https://github.com/riscPrint/risc-v-workstation/pull/823). Merged: 2026-11-13T06:43:27Z.

Title: fix(formal): remove personal paths from committed evidence

Audit evidence label: no code.

## Summary
`test_release_hygiene.py::test_tracked_text_has_no_personal_paths` failed on main after #802 and #807. Replace the home directory in `examples/formal/deep/picorv32-conditions-results.json` with `~` and the local worktree path in `examples/vexriscv/formal/GENERATED_RESULTS.md` with `<local evidence>`. The recorded tool paths are informational; no test or tool reads these files.

## Testing
- `pytest rvw/tests/test_release_hygiene.py`: all passed.

## Issues
None. Sheriff maintenance of `main`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 824

[#824](https://github.com/riscPrint/risc-v-workstation/pull/824). Merged: 2026-11-13T06:45:17Z.

Title: feat(formal): generate machine transition checks

Audit evidence label: unit tests only.

## Summary
Generate eight RV32 machine-transition property slices from project observations. Add CLI/MCP and connect them to `formal isa --machine`. Check catalog CSR address, privilege and read-only state with declared storage masks. Add a VexRiscv project map and measured outcomes.

VexRiscv x0 values and current writeback flush checks pass at bound 20, with trigger covers reached. Exception, interrupt, return and CSR rules have no applicable controller in this FormalSimple snapshot. Compressed instruction-memory pairing and PC chains across real traps remain unsupported. These are transition slices, not complete privileged-machine signoff.

## Testing
10 targeted tests passed. All eight generated monitors passed native Yosys parsing and checking. Native VexRiscv jobs used private source, `vex-conn`, and `nice -n 10`. ABC returned ERROR for a combinational flush cone; the explicit SMT retry passed.

Fast set: 1415 passed, 1 skipped, 1 failed, 7998 deselected. The existing personal-path hygiene failure remains in prior example evidence. Full Python suite and BOOM NOT RUN.

## Issues
No issue closed. Missing bindings and full-machine semantics remain explicit in the report.

Roadmap notes: generated machine transition slices and bounded native evidence are available. CSR-enabled VexRiscv elaboration, compressed memory pairing and a persistent kill tracker remain work.


## PR 825

[#825](https://github.com/riscPrint/risc-v-workstation/pull/825). Merged: 2026-11-13T06:44:16Z.

Title: fix(formal): restore valid picorv32 condition results

Audit evidence label: no code.

## Summary
#823 rebased over #819 with keep-both and left `examples/formal/deep/picorv32-conditions-results.json` as invalid JSON. Restore the #819 version and remove the personal paths again.

## Testing
- `json.load` on the file succeeds; no home-directory path remains.

## Issues
None. Sheriff maintenance of `main`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 826

[#826](https://github.com/riscPrint/risc-v-workstation/pull/826). Merged: 2026-11-13T06:44:54Z.

Title: feat(sim): support wide native ports and public wave capture

Audit evidence label: ran on real core RTL.

## Summary

Support packed ports through 65,536 bits in the native Arcilator and Verilator API. Use explicit byte transfer for Verilator ports wider than 64 bits. Add optional two-state public-port VCD capture after each evaluation. Preserve the scalar fast path.

Add a whole-core comparison campaign with alternating engine order, complete C2 equality and separate wave-enabled controls. Record a VexRiscv sample. Arcilator is slower here: median 4,332 instructions/s against Verilator's 5,015, ratio 0.864. This is not a speed gain claim.

## Testing

- Native scalar and wide-model tests: 3 passed. Widths 31, 32, 63, 64, 65, 129 and 257 match an independent arithmetic expectation on both engines. Public-port VCD files are byte-identical.
- Fast public-wave test: 1 passed. Production waveform parser retains bit 128 and overwrite is refused.
- Real captured VexRiscv RTL at private source revision a62c145aa042a5de874344e0a7683bd7c8c8c870, six native runs under vex-simsrv / nice -n 10: all pass with 15,007 retirements and 40,307 cycles. Complete C2 files are byte-identical. Two wave files are also byte-identical, about 13 MiB each.
- Untraced execution includes Python bus/RVFI handling and C2 write/validation. Build time is separate. Only two untraced samples per engine were measured. No general engine ranking is claimed.
- Fast Python set: 1,402 passed, 1 skipped, 2 unrelated failures, 7,995 deselected. Failures: docs staging and personal-path hygiene in examples/formal/equiv-real/README.md.
- CLI import and MCP discovery passed with no skipped tools.
- Internal-signal waves, four-state waves, full Python suite, BOOM and C4 acceptance: NOT RUN.

## Issues

No issue closed. These waves contain public ports and evaluation timestamps. They do not claim internal-signal coverage or physical time.

Roadmap notes: native Arcilator and Verilator now support wide packed ports and public-port waves. Wide-register controls and a real whole-core C2/wave comparison passed. The measured Arcilator sample was slower than Verilator. General speed qualification and internal-wave support remain open.


## PR 827

[#827](https://github.com/riscPrint/risc-v-workstation/pull/827). Merged: 2026-11-13T06:45:09Z.

Title: fix(cosim): dispatch capture doctor through mcp

Audit evidence label: unit tests only.

## Summary

Fix MCP dispatch for cosim_doctor. The registered synchronous tool used a long-job handler and failed with a missing job argument. Use the importable inspection function in an isolated read-only call. Large inputs can continue as a cancellable job.

## Testing

- Five capture-doctor tests passed, including a real Registry dispatch.
- External stdio client: query, cosim doctor, probes, perf, coverage, wave and fault-site calls all succeeded on the fresh scratch core artifacts.
- Fast set: 1413 passed, 1 skipped, 2 unrelated failures, 7996 deselected. Failures remain documentation-site staging and release hygiene in examples/formal/equiv-real/README.md.
- No full Python suite, BOOM build or extended-state RTL campaign was run.

## Issues

Refs: #34

Roadmap notes: cosim capture inspection is callable through MCP on a fresh external core. This does not extend the reference comparison scope.


## PR 828

[#828](https://github.com/riscPrint/risc-v-workstation/pull/828). Merged: 2026-11-13T06:45:07Z.

Title: test(rvw): parse every tracked python, json and toml file

Audit evidence label: unit tests only.

## Summary
Add `test_tracked_python_json_and_toml_files_parse` to the fast module `rvw/tests/test_cli_tree.py`. It parses every tracked `*.py` (`ast.parse`), `*.json` and `*.toml` file (about 1,400 files, about 3 s). `tsconfig*.json` is skipped because it is JSON with comments. A keep-both rebase left invalid JSON on main today (#823, fixed by #825), and keep-both breaks Python modules that no fast test imports.

## Testing
- `pytest rvw/tests/test_cli_tree.py -m fast`: 3 passed on main.

## Issues
None. Sheriff maintenance of `main`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 829

[#829](https://github.com/riscPrint/risc-v-workstation/pull/829). Merged: 2026-11-13T06:45:13Z.

Title: feat(probes): add bus and csr-write probes with c2 consistency checks

Audit evidence label: unit tests only.

## Summary

- SpinalProbes: new `Probe.bus(bus, valid, address, write, data, mask, size)` kind `bus` (one accepted request at a core port, before any cache). Contract text in `docs/contracts/sim.md`.
- VexRiscv `ProbePlugin`: `bus ibus` / `bus dbus` on accepted `iBus`/`dBus` commands; `csrWrite csr` from `csrMapping.onAnyWrite` (the CSR plugin's own `writeEnable`), the instruction's CSR field and `writeDataSignal`. New `memcsr.S` program (word/half/byte loads and stores, all six CSR forms, one illegal `csrw satp`).
- `rvw probes convert --to bus` (`rvw.probe-bus-check/1`): data bus writes against retired C2 stores one to one (bytes and values, in order); each retired C2 load covered by a later bus read in order; `unretired_reads` counts speculative reads.
- `rvw probes convert --to csr-writes` (`rvw.probe-csr-writes/1`): each retired C2 CSR write matches the next write event by address, and by value when C2 operands give it. An extra event is accepted only for an access that trapped (trapped C2 record, or a C2 exception before the next retirement whose illegal-instruction `tval` names the same CSR).
- New consumer rows `bus-check` and `csr-write-check` in `rvw probes list`. Code in a new module `rvw/src/rvw/probes/checks.py`.

## Testing

Native, private VexRiscv copy (core sources `baf7dc82`), lock `vex-csims`, seed 1:

- `memcsr --probes --rvfi-trace`: pass, 382 instructions, 1855 cycles. Re-run after the rebase: same result.
- `--to bus`: consistent. 61 bus writes = 61 C2 stores (bytes and values), 60 reads cover 60 loads, 0 unretired reads.
- `--to csr-writes`: first run found a mismatch: the core strobes the write port for the illegal `csrw satp` (C2 records only a trap event, cause 2). After the trap rule: consistent, 123 events, 122 retired writes, 122 values checked, 1 trapped strobe.
- `--to hpm`: loads 60, stores 61, mispredicts 1.
- Per-slot CSR capture: `rvw cosim check` against Spike (shim rebuilt with `Cosim/build.sh`): `match`, 382 instructions, `csr_snapshot` `0x340` on all 382 steps.
- `rvw/.venv/bin/python -m pytest rvw/tests/test_probes_checks.py rvw/tests/test_probes.py -q`: 18 passed (8 new). The trapped-strobe test fails before the fix.
- Fast set: 1297 passed, 1 skipped, 1 failed: `rvw/tests/test_docs_site.py::test_docs_staging_does_not_write_sources` (README staging; not in files this PR touches).

Not run: cache probes. This VexRiscv config has no caches (`IBusSimplePlugin`, `DBusSimplePlugin`), and VexiiRiscv on main is cacheless too. A cached config would change the bus type that the other VexRiscv example tools drive, so the cache observer check stays without input. Not run either: sbt test suites, the VexRiscv example pytest suite, the full Python suite, CI.

## Issues

Refs: probes follow-up (item 2 of 6: CSR writes and bus transactions done; cache access/miss not possible on the cacheless configs).

Roadmap notes: SpinalProbes has a `bus` kind; `rvw probes` checks bus and CSR-write probes against C2 on VexRiscv (both consistent). Cache probes still need a cached core config.

🤖 Generated with [Claude Code](https://claude.com/claude-code)


## PR 830

[#830](https://github.com/riscPrint/risc-v-workstation/pull/830). Merged: 2026-11-13T06:45:46Z.

Title: feat(agent-bench): check native repairs with independent workloads

Audit evidence label: unit tests only.

## Summary
Prepare a reproduced seeded failure in a disposable core project. Copy project-owned adapters, programs and private-lock data so an agent can use rvw tools there. Retain bundle and cosim diagnostic outputs. Check only candidate source changes in a fresh seeded copy against evaluator-owned fail-to-pass and pass-to-pass workloads. Retain a patch and evidence for human review. Reject changed packs and mismatched harness revisions.

## Testing
Native runner and repair-loop fixture tests: 9 passed. Tests cover reproduced failures, wrong-fix rejection, correct source repairs, ignored test/project edits, missing reproduction and changed evaluator packs. MCP discovery has no skipped modules. Public fast set: 1 failed, 1422 passed, 1 skipped, 7999 deselected in 260.47s (0:04:20). The only failure is `test_release_hygiene.py::test_tracked_text_has_no_personal_paths` in existing formal result files and READMEs, outside this change. The brief permits this unrelated failure.

Native repair acceptance, dynamic C6 source joins and scored LLM repairs NOT RUN. Earlier native attempts exhausted their wall limits without C1 results. Inspection of the longer retry found Scala compilation active after more than ten minutes. That retry was stopped under the brief's short native smoke limit. No native qualification is claimed here.

## Issues
Refs: #27, #364. Dynamic statement joins and cause ranking remain open. The checker leaves root cause unknown and claims no C4 acceptance. Human review is required.

Roadmap notes: The bounded native repair loop now retains reproduced failures, independent candidate workloads, ignored edits and a concrete review patch. This is distinct from automatic root cause and C4 gate acceptance.


## PR 831

[#831](https://github.com/riscPrint/risc-v-workstation/pull/831). Merged: 2026-11-13T06:46:17Z.

Title: feat(formal): measure incremental revision proof costs

Audit evidence label: ran on seeded RTL fixture.

## Summary
Add revision-bench CLI/MCP for alternating fresh target proofs with and without certified cone-matched lemma assertions. Record separate export time and signed median savings. Include a pinned RTL edit sample and native results. Fix strategy MCP to read its plan file and planned status, with a direct handler test.

## Testing
- Targeted revision and strategy tests: 7 passed.
- Native pinned counter revision: six fresh target proofs passed; all three reuse jobs selected one cone-matched lemma. Cold median 1.623 s; reuse median 1.801 s; saved -0.178 s. Export cost 4.906 s. No speed gain observed. Eight-second stage limits, nice priority.
- Fast set: 1425 passed, 1 skipped, 1 unrelated release hygiene failure, 8002 deselected. test_release_hygiene.py::test_tracked_text_has_no_personal_paths reports examples/vexriscv/formal/GENERATED_RESULTS.md.
- Post-rebase tests and MCP discovery checked.
- Full suite and core-scale incremental proofs NOT RUN.

## Issues
Refs: #21, #294

Roadmap notes: incremental lemma selection across a small RTL edit now has a reproducible timing experiment. Reuse was slower on this small sample. Helpers remain assertions, and no cached verdict replaces the fresh target proof. No core-scale speedup claim.


## PR 832

[#832](https://github.com/riscPrint/risc-v-workstation/pull/832). Merged: 2026-11-13T06:47:04Z.

Title: fix(query): stop packed HDL aliases from connecting unrelated lanes

Audit evidence label: unit tests only.

## Summary
Fix cross-lane paths introduced by packed HDL aliases. A multi-bit HDL signal is an endpoint view of the bit nodes. Query traversal can start or end there, but must not traverse through that view to connect different lanes. Keep memory and synchronous read-state nodes as actual boundaries. This also handles generated packed aliases.

The new fast tests construct two independent scalar lanes with a packed alias and check paths, fanin and fanout. They retain real connections and aggregate endpoint queries while rejecting cross-lane paths.

## Testing
Fast alias regression tests: 2 passed. Native and fast-set results below. Not run: full Python suite, CI, RTL simulation.

## Issues
Refs: #370, #371. This changes query navigation only. Stored raw edges used by other consumers are unchanged. Whole-cell dependencies remain conservative; no bit-exact or logic-equivalence claim is made.

Roadmap notes: HDL query graph traversal no longer treats packed-vector endpoint views as internal cross-lane connections.
Native frontend and diagram set: 32 passed, 0 skipped in 169.96 s. Standalone UART oracle: 1 passed, 5 deselected; all 16 comparisons now agree. Replace its earlier explicit xfail with strict equality. Fast set: 1421 passed, 1 skipped, 1 failed, 7998 deselected in 281.12 s. The failure is the unchanged `test_release_hygiene.py::test_tracked_text_has_no_personal_paths`, including examples/formal/deep/picorv32-conditions-results.json and examples/vexriscv/formal/GENERATED_RESULTS.md. MCP discovery stderr has no skipped module.


## PR 833

[#833](https://github.com/riscPrint/risc-v-workstation/pull/833). Merged: 2026-11-13T06:47:12Z.

Title: fix(formal): check real multiplier cones through hierarchy

Audit evidence label: ran on real core RTL.

## Summary
Fix hierarchical datapath export by omitting Yosys `$scopeinfo` metadata. Add a reproducible arithmetic check that extracts the real VexRiscv MulSimplePlugin product cell and compares it with the M model. Preserve the original cell and sign-extension wiring. Record the exact supplied RTL hash and operand/result projection.

## Testing
- Extraction and native hierarchical regression: 3 passed.
- Native real 32-bit MUL product check: inconclusive, CBMC timeout at 120 seconds.
- Native real eight-bit operands and low-eight-bit result projection: proved. This is a restricted projection, not full RV32 MUL.
- Fast set: final result recorded below.
- NOT RUN: plugin transaction/control proof, divider plugin, high-product signed modes, VexiiRiscv units, FPU versus SoftFloat, fresh core elaboration, CI and full suite.

## Issues
Refs: #19. Whole-plugin MUL/DIV and open FPU checks across rounding modes and flags remain open.

Roadmap notes: Real exported arithmetic now reaches the symbolic backend through hierarchy. The eight-bit projection of the real multiplier product cell closes. The full 32-bit check times out within the short native budget. Real divider and floating-point unit coverage is still missing.

Final fast set: 1395 passed, 1 skipped, 7995 deselected. One inherited failure: `test_release_hygiene.py::test_tracked_text_has_no_personal_paths`, in `examples/formal/deep/picorv32-conditions-results.json` and `examples/vexriscv/formal/GENERATED_RESULTS.md`. Neither file is changed here.


## PR 834

[#834](https://github.com/riscPrint/risc-v-workstation/pull/834). Merged: 2026-11-13T06:48:04Z.

Title: fix(doctor): validate c2 configs and failed replay commands

Audit evidence label: unit tests only.

## Summary
Check C2 output for every advertised adapter config. Require a passing, bound C1 run plus a complete C2 stream with the selected core, config, ISA and XLEN. Report missing, malformed, wrong-config and truncated traces with named checks and fixes. Use the reviewed smoke platform for independent reference checks.

Reject replay commands that fail even when a passing result file exists. Keep full C1/C2 conformance inconclusive; report the bounded requested checklist separately. This fixes an unearned full-C1 ready verdict in the recovered implementation.

## Testing
- Targeted C1/C2/doctor artifact tests: 31 passed.
- Fast set: 1427 passed, 1 skipped, 8001 deselected. Two failures in unchanged files: test_docs_site.py::test_docs_staging_does_not_write_sources and test_release_hygiene.py::test_tracked_text_has_no_personal_paths (examples/vexriscv/formal/GENERATED_RESULTS.md lines 104, 132-135). These do not block delivery under the worker brief.
- CLI import and MCP discovery: pass, no skipped-tool warning.
- Native full doctor campaigns, all option interactions, interrupt delivery, BOOM and full suites NOT RUN. Native core/C2 evidence for the mapped integration is in PR #820; it does not qualify this whole checklist.

## Issues
Refs: #35

Roadmap notes: per-config C2 diagnostics and replay failure detection are implemented. Full C1/C2 qualification remains open; bounded checks must not claim full conformance.


## PR 835

[#835](https://github.com/riscPrint/risc-v-workstation/pull/835). Merged: 2026-11-13T06:48:57Z.

Title: feat(memory): add a cacheless multi-hart rtl example

Audit evidence label: ran on real core RTL.

## Summary

Add `examples/smp/` with pinned external VexiiRiscv sources, RV64IMA configurations for two to eight harts, one shared simulation RAM and atomic service, simulated CLINT/PLIC registers, and per-hart C2/2 capture. Each hart uses its own ELF, reset entry and retirement completion. C1 reports every hart's status. Add hart/epoch-aware IRQ and trap methods to the C2/2 writer.

SpinalSoc's single-core APB interface cannot host this native atomic LSU interface. The example uses a small project-owned Spinal top. RAM, atomics and devices are simulation models. There is no synthesized shared interconnect or coherent cache.

## Testing

- Native pinned-source Scala compilation and Verilator elaboration passed.
- Three-hart native smoke, seed 17: pass, 86 cycles, 35 retirements (11/12/12). All three C2/2 hart completions pass. The C1 count equals the parsed C2 count. Hashes are committed.
- Five targeted Python tests passed.
- Fast set: 1291 passed, 1 skipped; unchanged `test_docs_site.py::test_docs_staging_does_not_write_sources` failed before this change and after it. The final pre-push run gave the same result: 1291 passed, 1 skipped and that one failure.
- The initial native smoke exposed an inaccessible child-port binding and asserted before retirement. The top now exports typed ports. The subsequent native runs use that binding.
- Added Scala IRQ/trap unit case: NOT RUN as a standalone test. CPU-level device, HSM/IPI, FENCE.I and complete RVWMO dependency checks: NOT RUN. No coherent cache or TileLink-C channel exists in this profile.

## Issues

Refs: #90. This adds a production-core multicore adapter and native execution evidence. It does not close the full memory verification scope. Later PRs will record the ordering-suite runs and remaining gaps.

Roadmap notes: Add the cacheless VexiiRiscv SMP example as native multicore execution evidence. Keep shared fabric RTL, coherent caches, dependency capture and lifecycle verification open. ROADMAP.md and TODO.md are unchanged.


## PR 836

[#836](https://github.com/riscPrint/risc-v-workstation/pull/836). Merged: 2026-11-13T06:50:22Z.

Title: feat(privilege): add ssstateen-only access profiles

Audit evidence label: unit tests only.

## Summary
Add Ssstateen-only RV64 profiles without machine state-enable CSRs. Cover all supervisor banks, ENVCFG, indirect CSR and user-state gates across M/S/U/VS/VU. Reuse named C2 instruction and trap observations. Pin Ssstateen-1.0 in project data. Include shared observation helper hashes in model evidence.

## Testing
- Targeted tests: 43 passed.
- All 104 actual programs compiled (24 without H, 80 with H). Python expected-access models passed. These results are model-based.
- Native capability probe: installed Spike rejects Ssstateen as unsupported. No native Ssstateen pass is claimed.
- Fast set: 1436 passed, 1 skipped, 8014 deselected, 1 unrelated failure: test_release_hygiene.py::test_tracked_text_has_no_personal_paths in examples/vexriscv/formal/GENERATED_RESULTS.md. No waiver or change to that file.
- NOT RUN: DUT/RTL, BOOM, full Python suite, long formal or CI. Fixture observation passes are not DUT results.

## Issues
Refs: #176. RV32 Ssstateen-only, other extension-state gates and DUT qualification remain open. Native Smstateen evidence is separate from this model-backed profile.

Roadmap notes: Add projects that implement supervisor state-enable controls without a machine bank. Keep model subset groups separate from full architectural comparison and unsupported native evidence.


## PR 837

[#837](https://github.com/riscPrint/risc-v-workstation/pull/837). Merged: 2026-11-13T06:50:45Z.

Title: feat(formal): stream measured native proof progress events

Audit evidence label: unit tests only.

## Summary
Stream per-manifest-property native engine progress as JSONL. Include engine, elapsed time, observed solver steps, separate PDR frames, sampled process-group RSS and terminal native status. Unknown measurements remain null. Native observations cannot override source conditions or the problem verdict. No dashboard UI change.

## Testing
- Progress/portfolio/compiled/strategy/revision targeted set: 19 passed, 1 skipped.
- Native portfolio regression: 9 passed in 0.50 s at nice priority, including EBMC FORMAL branch failure.
- Native five-second bounded timeout: six events with live memory and step samples. Final observed step 720 versus requested 10000. Native timeout; problem inconclusive. Checked-in JSONL sample retains those observations.
- Required fast set: 1460 passed, 1 skipped, 8021 deselected in 201.70 s.
- MCP discovery checked with no skipped warning.
- Full suite, long core proofs and dashboard integration NOT RUN. Property IDs identify manifest problems, which can bundle assertions. RSS samples are not peak memory. PDR frames are not unrolled depth.

## Issues
Refs: #21, #294

Roadmap notes: engine-race and engine-bench now expose live measured JSON events for dashboard consumers. The stream does not claim per-assertion progress inside a bundled native proof and cannot confer proof qualification.


## PR 838

[#838](https://github.com/riscPrint/risc-v-workstation/pull/838). Merged: 2026-11-13T06:53:09Z.

Title: feat(formal): compare picorv32 architectural state with rvfi

Audit evidence label: ran on real core RTL.

## Summary
Add a pinned PicoRV32 architectural-state map builder and native RVFI stream comparison. Extend generic state maps with optional halt and active-low reset. Read source values from saved architectural register state. Do not alias native RVFI into the monitor.

Three simulations compare 30 retirements each without a mismatch. Full bounded equivalence FAILS at cycle 10 on a misaligned JAL target: native RVFI retains a destination write on the trap while the architectural monitor suppresses it and detects the changed register frame. This unresolved result is retained. No equivalence certificate is granted.

## Testing
Three targeted option tests passed. Native state exposure and monitor generation succeeded. All three Icarus programs passed stream comparisons. SBY depth-35 comparison failed; fourth-retirement cover reached cycle 18. Private source copies, vex-conn and nice -n 10 were used. Full Python suite and BOOM NOT RUN.

## Issues
No issue closed. The misaligned-JAL trap/write difference remains open. This map is not qualified for signoff.

Roadmap notes: PicoRV32 no-RVFI prototype has real simulation comparisons and a retained formal counterexample. Adapter equivalence is not established.

Fast set: 1453 passed, 1 skipped, 8017 deselected in 201.13 seconds.


## PR 839

[#839](https://github.com/riscPrint/risc-v-workstation/pull/839). Merged: 2026-11-13T06:53:19Z.

Title: fix(query): retain omitted and empty instance port bindings

Audit evidence label: unit tests only.

## Summary
Complete the native instance-port inventory used by `query port-status`. Enumerate declared ports, not only connections present in a cell. Retain omitted and empty connections as unconnected with their declared width. Continue to reject nonempty width mismatches. Keep unknown bits separate from known tie-offs.

Add a producer metadata marker and query coverage field. Older captures report legacy-connections-only; new builds report all-instance-ports. No complete open-port inventory is claimed for older databases.

## Testing
Port binding and semantic tests: 5 passed. Short native Yosys smoke: a is tied low, width 1; y is unconnected, width 4. MCP discovery stderr has no skipped module. Fast set below.

Not run: full Python suite, CI, core simulation. This inventories lowered netlist connections. A compiler-created wire can hide a source-level open connection, so this does not claim complete source-level open-port recovery.

## Issues
Refs: #370, #55. Source-level open-port recovery and full expression typing remain open.

Roadmap notes: Agent semantic port queries now include omitted and empty native instance connections and state whether their capture is complete.
Fast set: 1462 passed, 1 skipped, 8021 deselected in 206.29 s. The earlier unrelated release hygiene failures are no longer present in this run.


## PR 840

[#840](https://github.com/riscPrint/risc-v-workstation/pull/840). Merged: 2026-11-13T06:53:51Z.

Title: feat(checks): record connected qualification evidence

Audit evidence label: ran on real core RTL.

## Summary
Add `rvw checks report` and MCP `checks_report`. Keep missing execution counts null. Match C1, ELF hashes and monitor inventories. Require all formal properties associated with a check to pass before counting that check.

Add generation manifests for VexRiscv, VexiiRiscv and the composed stub SoC. Add reviewed VexRiscv external command contracts, an optional checked database capture and ISA runner, and a bounded formal preparation script. Record per-kind evidence and all eleven open fetch-contract findings in examples/vexriscv/checks-qualification.json.

## Testing
- Targeted Python: 18 passed. CLI import and MCP discovery passed with no skipped modules.
- Fast set: 1350 passed, 1 skipped, 1 failed, 7989 deselected. The unrelated existing failure is test_release_hygiene.py::test_tracked_text_has_no_personal_paths in examples/formal/equiv-real/README.md:7.
- Private Scala compile of current SpinalChecks, VexRiscv and runtime sources passed. Native Verilator compiled with --assert. All 49 aligned ISA programs completed successfully at the program level. All 49 C1 results correctly stayed fail: 11 internal fetch valid-hold checks fired 8768 times. Other 46 inserted checks had zero firings. No checks were waived or disabled. Source inspection indicates cancellable flush/halt offers, but cancellation correlation was NOT independently traced.
- Current SpinalDB and checked database entry compiled. Real VexRiscv capture and two generated command-stream bindings passed Verilator elaboration.
- `rvw formal regress`, jobs 3, Yices/SBY: eight properties bounded-pass at depth 6 with two reset clocks. Four packed command checks covered. Activation NOT measured. No unbounded proof claimed.
- The original five-bus capture was reproduced with private compilation: five bound buses passed Verilator elaboration.
- Shared sbt native attempt timed out in its lock queue. Native evidence above came from private current-source Scala compilation with cached dependency jars under vex-csr.
- VexiiRiscv and composed-SoC native captures and qualification, full Python suite, and whole-core proof NOT RUN. Their generation summaries retain missing capture/binding reasons.

## Issues
Refs: #65, #66, #85
The connected-design item remains incomplete. Internal fetch cancellation contracts, VexiiRiscv and SoC bindings and native campaigns remain open. No issue is closed.

Roadmap notes: connected evidence reporting and the VexRiscv checked ISA runner are available. Record the failed qualification and bounded external-port results separately. The internal stream contract mismatch must be resolved before a clean result can be earned.


## PR 841

[#841](https://github.com/riscPrint/risc-v-workstation/pull/841). Merged: 2026-11-13T06:54:03Z.

Title: feat(mcp): add static interface audit and debt baseline

Audit evidence label: unit tests only.

## Summary
Add a static MCP interface audit and a fast baseline test. Keep existing tool names and argument names. Declare empty required lists in shared schemas.

## Testing
Targeted tests: 2 passed. Fast set: 1469 passed, 1 skipped, 8022 deselected.
Native tools, RTL and full suite NOT RUN.

## Issues
Recorded metadata debt remains visible in the audit. No existing names were removed.

Roadmap notes: MCP interface audit is implemented. Profiles and common results follow.


## PR 842

[#842](https://github.com/riscPrint/risc-v-workstation/pull/842). Merged: 2026-11-13T06:56:51Z.

Title: feat(formal): bound real-core security and reset controls

Audit evidence label: ran on real core RTL.

## Summary
Add bounded two-copy security and initialization checks through manifest `mode: bmc` and a depth. Preserve unbounded PDR as the default. Report bounded and unbounded proof scopes explicitly. Add a real VexRiscv export runner for a memory response source/sink IFT attempt, a two-copy observation contract and initial-state independence.

## Testing
- Bounded settings and native initialization regression: 6 passed.
- Fast set: 1469 passed, 1 skipped, 8027 deselected.
- Real VexTop export: both depth-eight two-copy checks and the IFT attempt were inconclusive before solving. `check -assert` found two undriven bits in `CsrPlugin_stvec_mode`. The input hash and exact fault are recorded. No constants or assumptions were added to bypass it.
- NOT RUN: fresh core elaboration, CSR secret injection, region-specific policies, PMP isolation, physical leakage, CI or full suite.

## Issues
Refs: #20. The source is the external memory response data port, not CSR state or one selected region. The bundled VexRiscv and VexiiRiscv configurations declare no PMP. This does not close real-core security or initialization.

Roadmap notes: Small-bound two-copy checks now have an explicit evidence scope. Real VexRiscv security and reset controls are reproducible, but a supplied RTL export has undriven CSR bits and earns no proof. CSR/region binding, PMP/ePMP and real-core initialization remain open.


## PR 843

[#843](https://github.com/riscPrint/risc-v-workstation/pull/843). Merged: 2026-11-13T06:56:16Z.

Title: feat(regress): read declared isa and privilege features

Audit evidence label: unit tests only.

## Summary
Read explicit ISA, privilege, satp, PMP, hart and interrupt fields in the generated-suite planner. Add Zacas and cache-block requirements. Permit FENCE selection without A. Link the selection contract from the index.

## Testing
Targeted tests: 3 passed. Fast set: 1335 passed, 1 skipped, 7977 deselected. Selection grants no RTL evidence. Native suites are separate work.

## Issues
Roadmap notes: project-owned feature declarations can select bounded generated suite families through CLI and MCP. Scenario-level selection remains project-owned. No issue is closed.


## PR 844

[#844](https://github.com/riscPrint/risc-v-workstation/pull/844). Merged: 2026-11-13T06:56:31Z.

Title: docs(integration): record the independent core dry run

Audit evidence label: ran on real core RTL.

## Summary

Record a fresh-core dry run in docs/DRY_RUN_2026-11-13.md and correct the integration guide. The independent RV32I core lives in a separate local repository. Final native smoke and scalar Spike cosim pass. Four selected upstream ISA tests pass through regress with matching C1 RTL identity. Native probes, queries, diagram export, waves, coverage and an injected-fault bundle also run.

State the remaining limits for architecture ISA selection, custom-bus UVM/SoC binding, the absent VIP command and security IFT X/Z handling. Keep bounded formal and incomplete evidence separate from proof and gate acceptance.

## Testing

- Fast set: 1436 passed, 1 skipped, 1 unrelated failure, 8015 deselected. Failure: test_docs_site.py::test_docs_staging_does_not_write_sources, scripts/build-docs.py:48.
- Native external-core runs and twenty stdio MCP calls are detailed in the report and local journal.
- No full Python suite, BOOM simulation, full ISA qualification, whole-core proof or hardware run was performed.

## Issues

Refs: #34

Roadmap notes: independent scratch-core smoke, scalar cosim and a four-test regression slice now have native evidence. The report ranks the remaining integration limits. The guide makes input completeness and compiled RTL identity requirements explicit.


## PR 845

[#845](https://github.com/riscPrint/risc-v-workstation/pull/845). Merged: 2026-11-13T06:57:44Z.

Title: feat(vscode): add navigation views

Audit evidence label: unit tests only.

## Summary
Add navigation support in the thin Workstation extension. Read the feature README for commands and limits.

## Testing
VS Code typecheck and build passed. npm test: 28 passed, zero skipped.
No simulations, sbt, core builds, native tools or live VS Code checks ran. Python tests did not run because this change touches no Python code and the task limits tests to touched files.

## Issues
No issue closure claimed.

Roadmap notes: Add the navigation extension capability. Saved producer data does not establish new verification evidence.


## PR 846

[#846](https://github.com/riscPrint/risc-v-workstation/pull/846). Merged: 2026-11-13T06:58:37Z.

Title: feat(mcp): add profiles and searchable tool catalog

Audit evidence label: unit tests only.

## Summary
Add core, verification, formal, arch, debug, soc and all tool profiles and agent workflow selection. Keep search, describe and job controls available. Remote catalogs stay inside client allowlists. Update the fixture client's exact tool list.

## Testing
Profile tests: 4 passed. Fast set: 1489 passed, 1 skipped, 5 failures in test_agent_external.py from the new meta-tool names. Updated the client's exact list and reran that module with the profile tests.
Native tools, full suite and external production clients NOT RUN.

## Issues
Default remains all. Record checks_report metadata debt from concurrent main.
Roadmap notes: profile and workflow discovery is implemented.


## PR 847

[#847](https://github.com/riscPrint/risc-v-workstation/pull/847). Merged: 2026-11-13T06:58:26Z.

Title: fix(init): create output before native HDL scaffold build

Audit evidence label: unit tests only.

## Summary
Create the output directory before the generated HDL launcher calls Verilator. Use an absolute harness path for the generated makefile. A fresh PicoRV32 repository failed its first build because rvw/out did not exist.

## Testing
Targeted test: 1 passed. Required fast set: 1475 passed, 1 skipped, 8022 deselected. Native PicoRV32 scaffold build failed before creating rvw/out and completed after creating it. Full suite and whole-core formal NOT RUN.

## Issues
Found during the external Verilog dry run. No issue closure.

Roadmap notes: Fresh non-Spinal scaffold builds no longer require an earlier query build.


## PR 848

[#848](https://github.com/riscPrint/risc-v-workstation/pull/848). Merged: 2026-11-13T06:59:12Z.

Title: feat(vscode): add project-results views

Audit evidence label: unit tests only.

## Summary
Add project-results support in the thin Workstation extension. Read the feature README for commands and limits.

## Testing
VS Code typecheck and build passed. npm test: 29 passed, zero skipped.
No simulations, sbt, core builds, native tools or live VS Code checks ran. Python tests did not run because this change touches no Python code and the task limits tests to touched files.

## Issues
No issue closure claimed.

Roadmap notes: Add the project-results extension capability. Saved producer data does not establish new verification evidence.


## PR 849

[#849](https://github.com/riscPrint/risc-v-workstation/pull/849). Merged: 2026-11-13T06:59:44Z.

Title: perf(sim): snapshot settled ports and measure server throughput

Audit evidence label: ran on real core RTL.

## Summary

Reduce the native Python adapter's individual port-read calls with one settled snapshot per evaluation. Keep an explicit direct-read control. Input writes invalidate the snapshot. Add reproducible alternating performance controls and a 49-test persistent-JVM comparison.

The profile found 525,969 port reads and 401,655 writes against 120,497 evaluations. The follow-up measured 1.222x CPU throughput with snapshots and exact complete C2 equality. Wall throughput in that sample was lower, ratio 0.862, so no snapshot wall-time gain is claimed. Preserve the earlier noisy campaign too.

The 49-test ISA suite took 16.84 seconds in one server and 422.41 seconds in separate JVMs. All tests passed and all complete C2 files matched. This is a measured 25.08x JVM-reuse throughput ratio, not an isolated RTL kernel speedup.

## Testing

- Final scalar input-invalidation control: 2 passed.
- Native scalar and wide-port controls: 3 passed on Arcilator and Verilator. Seeded arithmetic and public waves match.
- Follow-up snapshot campaign: eight passing whole-core runs, including one warm pair and three measured alternating pairs. All C2 bytes match. CPU throughput 16,449 -> 20,094 instructions/CPU-second. Wall throughput 8,263 -> 7,126 instructions/s. No wall winner qualified.
- Initial campaign: ten passing C2-identical runs. Wall times were noisy and paired directions mixed. Full sample retained.
- Persistent ISA comparison: 49 conclusive passes per mode, 49 complete C2 matches, 17,735 retirements. One warm native-cache run preceded measurement. Whole-suite throughput: 41.99 -> 1,053.09 instructions/s. Scala compilation and common tool/source capture excluded.
- Private core a62c145aa042a5de874344e0a7683bd7c8c8c870, vex-simsrv lock, nice -n 10.
- Fast Python set: 1,434 passed, 1 skipped, 1 unrelated docs-staging failure, 8,015 deselected.
- CLI import and MCP discovery passed with no skipped tools.
- Full Python suite, BOOM, general thread-profile qualification and isolated generated-code kernel timing: NOT RUN.

## Issues

No issue closed. The CPU result applies to this Python native adapter. The wall-time snapshot result is inconclusive as a gain. The suite result is one warmed 49-test sample on a shared macOS arm64 host.

Roadmap notes: profiling found per-port Python/native overhead. Settled snapshots reduce measured CPU cost with complete C2 preserved. The persistent server now has a real 49-test comparison, with 25.08x suite throughput and exact C2 equality against separate JVMs. No Verilator thread profile or general RTL-kernel speed gain is qualified.


## PR 850

[#850](https://github.com/riscPrint/risc-v-workstation/pull/850). Merged: 2026-11-13T07:00:26Z.

Title: feat(vscode): add cosim-mismatch views

Audit evidence label: unit tests only.

## Summary
Add cosim-mismatch support in the thin Workstation extension. Read the feature README for commands and limits.

## Testing
VS Code typecheck and build passed. npm test: 30 passed, zero skipped.
No simulations, sbt, core builds, native tools or live VS Code checks ran. Python tests did not run because this change touches no Python code and the task limits tests to touched files.

## Issues
No issue closure claimed.

Roadmap notes: Add the cosim-mismatch extension capability. Saved producer data does not establish new verification evidence.


## PR 851

[#851](https://github.com/riscPrint/risc-v-workstation/pull/851). Merged: 2026-11-13T07:01:21Z.

Title: feat(soc): integrate real cores with composed peripheral examples

Audit evidence label: ran on real core RTL.

## Summary

Add real VexRiscv and VexiiRiscv examples that implement AxiCoreWrapper. Use upstream instruction/data bridges and the Spinal shared arbiter. Connect machine software, timer and external interrupts. Keep private core sources outside the repository. The Vexii PMA covers the exact composed RAM and device windows, including low-address CLINT and PLIC.

VexRiscv has a C1 adapter and a setup script that resolves the external core and captures adapter inputs. VexiiRiscv has a separate build for its pinned Spinal source dependencies, a standalone runner, captured ELF input preparation and a serial/result checker. Both examples have 64 KiB byte-enabled RAM and active-high asynchronous reset. Debug transport and debug modules remain open.

## Testing

- Targeted fast tests: 23 passed. Checked ELF word images and bounds, capture-path resolution, missing observations and UART byte failures.
- VexRiscv private source compile passed at baf7dc82f855eddaf5b0a20a6802c526f127e38a with SpinalHDL 1.15.0.
- VexRiscv through rvw regress: 4 smoke programs passed and 49 aligned RV32UI/UM tests passed. Verilator assertions were enabled. The UART interrupt test sent I after checking cause/IIR and disabling the interrupt.
- VexiiRiscv wrapper and composed SoC compiled and elaborated against private cached dependencies. Standalone Verilator with assertions passed the same 4 smoke programs and 49 ISA programs at seed 31. The checker confirmed hello newline and I.
- The Vexii core and pinned Spinal dependencies were copied privately from cached compiled outputs. They were NOT rebuilt. This does not qualify a clean source build.
- Fast set: 1374 passed, 1 failed, 1 skipped, 7987 deselected. Its unrelated release-hygiene failure names examples/formal/deep/picorv32-conditions-results.json and examples/formal/equiv-real/README.md. No changes were made to those files.
- NOT RUN: normal sbt source launchers, Vexii C1 regression, misaligned-data tests, full Python suite, RVFI co-simulation, debug, formal proofs, hardware, GitHub CI.

## Issues

Refs: #130. No issue is closed.

Roadmap notes: Both real-core wrappers now run on composed peripheral SoCs. VexRiscv has C1 regression evidence for four smoke programs and 49 aligned ISA tests. Vexii has equivalent standalone observations from privately copied cached dependencies. Debug and clean Vexii source-build qualification remain open.


## PR 852

[#852](https://github.com/riscPrint/risc-v-workstation/pull/852). Merged: 2026-11-13T07:01:45Z.

Title: feat(vscode): add coverage-lines views

Audit evidence label: unit tests only.

## Summary
Add coverage-lines support in the thin Workstation extension. Read the feature README for commands and limits.

## Testing
VS Code typecheck and build passed. npm test: 31 passed, zero skipped.
No simulations, sbt, core builds, native tools or live VS Code checks ran. Python tests did not run because this change touches no Python code and the task limits tests to touched files.

## Issues
No issue closure claimed.

Roadmap notes: Add the coverage-lines extension capability. Saved producer data does not establish new verification evidence.


## PR 853

[#853](https://github.com/riscPrint/risc-v-workstation/pull/853). Merged: 2026-11-13T07:02:00Z.

Title: test(vip): qualify sv agent runtime on verilator

Audit evidence label: ran on seeded RTL fixture.

## Summary

Add a repeatable SV UVM protocol campaign with one Verilator build per agent, a long build timeout, source hashes and retained per-case logs. Measure good and corrupt fixtures at seeds 1, 2 and 3. Keep manager faults separate from corrupt-DUT checks. Empty native-model bridges cannot qualify from compilation.

Set UVM fatal actions to return a nonzero exit in the runtime fixtures. Inject APB reset only after the monitor has observed setup.

## Testing

- Verilator 5.052 compiled all 20 protocol packages and fixtures with pinned Accellera UVM 2020.3.1.
- 13 fixtures passed all three normal good-DUT seeds and all three corrupt-DUT seeds. APB also passed three reset-abort and three malformed-manager cases after its fix.
- Targeted qualification checks: 4 passed.
- Worker checkout fast set: 1304 passed, 1 skipped, 7879 deselected. The skipped command-reference check is deferred by the worker brief. The checkout also contains preparation for later assigned items.
- All commands, source hashes, per-case results and observed failures are recorded in Uvm/vip/qualification/native-2026-11-13.json and the Markdown matrix.
- NOT RUN: Accellera DPI/backdoors, external native packet/DRAM/PCIe/RNM models, physical links, commercial VIP, CPU/ISA qualification in this campaign.
- Open native gaps: AXI B response before a complete monitored write, TileLink unexpected response, UART frame mismatch, AHB malformed-manager diagnostic mismatch. No engine bug is inferred from those observations.

## Issues

Refs: #204
Refs: #205
Refs: #215
Refs: #216
Refs: #217

Roadmap notes: Add the measured SV protocol runtime matrix. Keep native-model stubs, unsupported profiles and runtime failures open. No CPU, ISA, physical-link or commercial-VIP qualification follows from this campaign.


## PR 854

[#854](https://github.com/riscPrint/risc-v-workstation/pull/854). Merged: 2026-11-13T07:02:49Z.

Title: fix(init): run mapped sv cores with matching query options

Audit evidence label: unit tests only.

## Summary
Let `rvw init --hdl sv --top MODULE --source FILE --reset-pc ADDRESS` select the working mapped adapter. Preserve the existing query/harness skeleton when reset PC is omitted. Update the PicoRV32 example.

Generic defects fixed, with tests:
- Resolve absolute Verilog files as absolute paths in Scala and in the generated query script.
- Apply parameter overrides before discovering port widths.
- Forward defines and parameters to query, using sized Verilog literals for unsigned values above the signed 32-bit range.
- Keep unsupported include paths explicit errors. Use process-group timeout handling for the native port reader.

Strengthen the opt-in Spinal fixture test to seed its own Git repository and reject missing input capture or incomplete reference matches.

## Testing
- Targeted init, SV routing and native Yosys tests: 14 passed.
- Scala MappedAdapterSpec: 3 passed, including the absolute source path control.
- PicoRV32 ef203c2b: fresh SV scaffold, native C1 smoke pass without inconclusive markers, 15 retired instructions / 76 cycles; complete Spike match.
- Generated parameter-matched slang query build passed; query where mem_addr resolves the original Verilog source.
- Fast set before final rebase: 1471 passed, 1 skipped, 8023 deselected; unchanged failure test_docs_site.py::test_docs_staging_does_not_write_sources.
- Full Python/Scala suites, BOOM, full SV syntax, included source trees and fresh native subword ISA campaign NOT RUN. The six older PicoRV32 subword trace mismatches remain documented.

## Issues
Refs: #26, #55

Roadmap notes: the mapped --hdl sv path now has bounded native PicoRV32 C1/C2/reference and query evidence. Full SV port discovery, includes and broad core/configuration qualification remain open.


## PR 855

[#855](https://github.com/riscPrint/risc-v-workstation/pull/855). Merged: 2026-11-13T07:03:17Z.

Title: feat(vscode): add formal-properties views

Audit evidence label: unit tests only.

## Summary
Add formal-properties support in the thin Workstation extension. Read the feature README for commands and limits.

## Testing
VS Code typecheck and build passed. npm test: 32 passed, zero skipped.
No simulations, sbt, core builds, native tools or live VS Code checks ran. Python tests did not run because this change touches no Python code and the task limits tests to touched files.

## Issues
No issue closure claimed.

Roadmap notes: Add the formal-properties extension capability. Saved producer data does not establish new verification evidence.


## PR 856

[#856](https://github.com/riscPrint/risc-v-workstation/pull/856). Merged: 2026-11-13T07:04:05Z.

Title: fix(init): capture wired inputs and share elaboration policy

Audit evidence label: unit tests only.

## Summary
Generate standard input capture for wired Spinal projects. Generate both RTL identity hooks and one project-owned Elaboration entry shared by simulation and SpinalDB. Formal and lint use the database RTL.

## Testing
Targeted init tests: 23 passed. Native generated scaffold compiled against the scratch core under the private sbt-cosim lock. Full Python suite, BOOM and long formal runs NOT RUN.

## Issues
Refs: dry-run edges 1, 3, 4. Core-specific run mapping still requires implementation.

Roadmap notes: wired init declares its standard inputs and shares top/clock/reset configuration across simulation and database generation.

Fast set: 1,497 passed, 1 skipped, 2 unrelated failures: test_docs_staging_does_not_write_sources and test_discovery_audit_baseline. MCP discovery reports no skipped modules.


## PR 857

[#857](https://github.com/riscPrint/risc-v-workstation/pull/857). Merged: 2026-11-13T07:04:21Z.

Title: feat(mcp): wrap transport results in a common envelope

Audit evidence label: unit tests only.

## Summary
Add an additive result envelope in the registry transport wrapper. Preserve legacy fields. Use a shared honest verdict vocabulary and retain older terms in legacy_verdict. Completion alone never earns a pass. Update query parity tests to compare full envelopes.

## Testing
Initial targeted MCP tests: 12 passed. Fast set found 27 exact-shape query assertions that needed the additive fields. Updated those tests. Query/MCP targeted rerun recorded in the work log.
Native tools and full suite NOT RUN.

## Issues
Raw Python Registry.call stays compatible. Envelope fields can carry existing provider values.
Roadmap notes: shared MCP transport results are implemented.


## PR 858

[#858](https://github.com/riscPrint/risc-v-workstation/pull/858). Merged: 2026-11-13T07:04:16Z.

Title: feat(vscode): add lint-rule-groups views

Audit evidence label: unit tests only.

## Summary
Add lint-rule-groups support in the thin Workstation extension. Read the feature README for commands and limits.

## Testing
VS Code typecheck and build passed. npm test: 33 passed, zero skipped.
No simulations, sbt, core builds, native tools or live VS Code checks ran. Python tests did not run because this change touches no Python code and the task limits tests to touched files.

## Issues
No issue closure claimed.

Roadmap notes: Add the lint-rule-groups extension capability. Saved producer data does not establish new verification evidence.


## PR 859

[#859](https://github.com/riscPrint/risc-v-workstation/pull/859). Merged: 2026-11-13T07:04:23Z.

Title: fix(query): join slang parameter override arguments

Audit evidence label: unit tests only.

## Summary
Pass each slang parameter override as one argument. Multiple separated -G values cause Slang to reject a valid parameter assignment. The external PicoRV32 run reproduced this with ENABLE_MUL and ENABLE_DIV.

## Testing
Native targeted two-parameter test: 1 passed. Fast set: 1498 passed, 1 skipped, 1 unrelated failure in test_mcp_coherence.py::test_discovery_audit_baseline, 8026 deselected. Full suite NOT RUN.

## Issues
No issue closure. Roadmap notes: Slang query extraction now accepts multiple project-owned top parameters.


## PR 860

[#860](https://github.com/riscPrint/risc-v-workstation/pull/860). Merged: 2026-11-13T07:04:31Z.

Title: feat(privilege): gate wake inputs on observed wfi stop

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add an opt-in WFI stop campaign with a reference-clock driver. Wait for actual WFI activity at the bound ELF PC and a stopped core clock before asserting the selected input. Cover local software, timer, external and project interrupts with global MIE off/on. Require retained state, no stopped retirement, observed pending input, bounded restart, release and resumed execution. The program publishes a delivery witness before input release and waits for the release acknowledgment. Keep legal early WFI returns inconclusive for this project pause check.

## Testing
- Targeted tests: 48 passed.
- All eight actual programs compiled. Python expected outcomes passed. These results are model-based.
- Tests cover early return without input, wrong PC, missing samples, stopped retirement, state corruption, no restart, callback cleanup, exact expected observations and C1 gating. Cleanup preserves a captured restart failure.
- Fast set: 1482 passed, 1 skipped, 8022 deselected.
- NOT RUN: actual input/clock adapter, native Spike clock-stop execution, DUT/RTL, BOOM, full Python suite, long formal or CI. Fixtures and model expectations do not establish physical clock gating or DUT coverage.

## Issues
Refs: #149. Projects must bind the generic driver callbacks and independent snapshots. Complete ISA comparison, NMI/reset wake, guest-mode stop and DUT qualification remain open. Named C2 results earn only explicitly model-based subset groups.

Roadmap notes: Add observed WFI-phase gating to the existing C1 privilege path, beyond fixed-cycle input schedules. Keep project clock-stop checks separate from architectural permission for early WFI return.


## PR 861

[#861](https://github.com/riscPrint/risc-v-workstation/pull/861). Merged: 2026-11-13T07:04:40Z.

Title: feat(checks): bind native vexii scratch csr reads

Audit evidence label: ran on real core RTL.

## Summary
Bind VexiiRiscv accepted scratch CSR reads to independent last-write tracking. Validate the generated catalog model before running. Keep instrumentation off in the default adapter. Add generated machine-scratch and absent-supervisor-CSR controls, slow native tests, project data and recorded results.

## Testing
- Fast set: 1491 passed, 1 skipped, 8026 deselected.
- Post-rebase targeted model and evidence tests: 12 passed. CLI import and MCP discovery passed without skipped modules.
- Compiled current SpinalChecks, new adapter files and the full pinned private VexiiRiscv source tree under vex-csr with nice priority 10 and cached dependency jars.
- Spike passed both generated programs.
- Verilator --assert: clean scratch program passed, 49 retired instructions, 203 cycles, zero firings. Absent sscratch program passed, 26 retired instructions, 158 cycles, zero firings.
- Seeded read-observation fault fired the scratch read monitor and preserved fail status. Absent-CSR control stayed clean. Four native run reports recorded.
- Native evidence came from a direct private Scala compile. The new sbt-based slow pytest module, full Python suite and formal proof were NOT RUN.

## Issues
Refs: #85
One scratch storage word is bound. Broader catalog binding, aliases, lower modes, WARL and autonomous hardware updates remain open. No issue closure or complete CSR qualification is claimed.

Roadmap notes: VexiiRiscv now has native generated CSR instruction controls and an optional accepted-read binding. Keep the one-word transaction-storage evidence separate from full CSR RAM and instruction-decoder correctness.


## PR 862

[#862](https://github.com/riscPrint/risc-v-workstation/pull/862). Merged: 2026-11-13T07:05:13Z.

Title: feat(arch): correlate in-order timing with native rtl

Audit evidence label: ran on real core RTL.

## Summary

Add explicit in-order issue and Minor project descriptions for VexRiscv and VexiiRiscv. Run six identical RV32IM programs on both real RTL adapters. Record whole-program C1/C2 identity, VexRiscv probe counts, training-only fitting and held-out IPC errors in Arch/ooo/correlation/README.md and results.json.

VexRiscv held-out fitted errors are +3.41%, +11.34%, -6.20%. VexiiRiscv errors are -23.57%, -30.13%, -4.76%. The reports retain inconclusive accuracy status. The fit does not establish unique physical parameters. VexiiRiscv has no SpinalProbes binding, so it uses IPC-only calibration. Accept an inactive initial IRQ declaration, but continue to reject asserted interrupts and traps.

## Testing

- Native RTL: 12 passing runs, six per core, seed 1, fixed memory latency zero. Private core copies and vex-arch lock. No gem5 build.
- Convert all six VexRiscv probe streams with rvw probes convert --to counts. Mapped branch counts agree.
- Run rvw arch ooo-fit, 16 candidates per core, three training and three distinct held-out programs.
- Targeted model/evidence tests: 39 passed before the inactive-IRQ test; the later targeted in-order/fit/project set has 11 passed.
- Fast set: 1,412 passed, 1 skipped, 1 failed, 7,998 deselected. The failure is test_release_hygiene.py::test_tracked_text_has_no_personal_paths in untouched formal files. Main has since changed those files. The full suite was NOT RUN.
- MCP discovery reports no skipped modules. A 1,010-instruction chain trace matches Spike with one declared mscratch reset synchronization.

## Issues

Refs: #355. Event-family coverage, larger applications, repeatability and accurate RTL pipeline mapping remain open.

Roadmap notes: add native in-order correlation and training-only fit measurements for both external cores. Keep general model accuracy unqualified. VexiiRiscv event correlation remains unavailable.


## PR 863

[#863](https://github.com/riscPrint/risc-v-workstation/pull/863). Merged: 2026-11-13T07:05:38Z.

Title: feat(vscode): add architecture-reports views

Audit evidence label: unit tests only.

## Summary
Add architecture-reports support in the thin Workstation extension. Read the feature README for commands and limits.

## Testing
VS Code typecheck and build passed. npm test: 34 passed, zero skipped.
No simulations, sbt, core builds, native tools or live VS Code checks ran. Python tests did not run because this change touches no Python code and the task limits tests to touched files.

## Issues
No issue closure claimed.

Roadmap notes: Add the architecture-reports extension capability. Saved producer data does not establish new verification evidence.


## PR 864

[#864](https://github.com/riscPrint/risc-v-workstation/pull/864). Merged: 2026-11-13T07:07:06Z.

Title: feat(vscode): add pipeline-window views

Audit evidence label: unit tests only.

## Summary
Add pipeline-window support in the thin Workstation extension. Read the feature README for commands and limits.

## Testing
VS Code typecheck and build passed. npm test: 35 passed, zero skipped.
No simulations, sbt, core builds, native tools or live VS Code checks ran. Python tests did not run because this change touches no Python code and the task limits tests to touched files.

## Issues
No issue closure claimed.

Roadmap notes: Add the pipeline-window extension capability. Saved producer data does not establish new verification evidence.


## PR 865

[#865](https://github.com/riscPrint/risc-v-workstation/pull/865). Merged: 2026-11-13T07:09:01Z.

Title: feat(vexii): add supervisor profiles and native device binding

Audit evidence label: reference model only (Spike/Sail/Python).

## Summary
Add cacheless RV32/RV64 supervisor configurations with A, MMU and eight PMP entries. Add RV64 suite selection, platform settings, interrupt routes and CLINT/PLIC bindings through the existing DeviceApiV1 plugin library. Preserve observed AMO and I/O effects in C2. Record the pinned core's RV64 PMP elaboration limits with a minimal reproduction. The RV64 profile uses 16-byte PMP granularity.

## Testing
Six Scala tests passed for C2 and native ABI controls. Four project tests and three planner tests passed. The CLINT plugin passed a JNA host smoke. The RV32 supervisor model built with Verilator in 26.2 seconds. RV64 elaboration passed at 16-byte granularity. Spike self-checks passed for 145 selected Sv39 programs, 30 privilege programs and five ordering programs.

The current RTL batch is waiting on shared sbt access. No supervisor RTL program pass or strict Spike match is claimed here. Device-to-core wiring, PMP suites, scheduled interrupts and page-walk fault suites still need native execution. The startup allowance covers queued builds; each program retains its 60-second timeout.

Latest fast set: 1492 passed, 1 skipped, 1 unrelated failure in `rvw/tests/test_mcp_coherence.py::test_discovery_audit_baseline`. Its new debt is missing metadata on `checks_report`, which this PR does not change. The preceding fast set passed 1335 tests before those upstream additions. MCP discovery has no skipped tools.

## Issues
Roadmap notes: supervisor and DeviceApiV1 adapter profiles now exist. This is an experimental integration, not suite qualification. Native execution and per-family counts follow separately. No issue is closed. Keep the recorded 4-byte/8-byte RV64 PMP limits distinct from the selected 16-byte configuration.


## PR 866

[#866](https://github.com/riscPrint/risc-v-workstation/pull/866). Merged: 2026-11-13T07:07:40Z.

Title: fix(formal): report unsupported SVA lowering without traceback

Audit evidence label: unit tests only.

## Summary
Return structured unsupported or error results from sva-lower. Macro-bearing external Verilog previously raised an uncaught exception. Keep an existing output file when lowering refuses the source.

## Testing
Targeted error tests: 2 passed. Fast set: 1519 passed, 1 skipped, 1 unrelated failure in test_release_hygiene.py::test_tracked_text_has_no_personal_paths, 8029 deselected. Native source refusal reproduced on PicoRV32. Full suite and whole-core proof NOT RUN.

## Issues
No issue closure. Roadmap notes: Unsupported temporal SVA input now has an explicit CLI result.


## PR 867

[#867](https://github.com/riscPrint/risc-v-workstation/pull/867). Merged: 2026-11-13T07:09:09Z.

Title: feat(mcp): add error codes and inventory install hints

Audit evidence label: unit tests only.

## Summary
Add machine-readable error codes, diagnostic records and next-action hints. Resolve exact install flags from the shared optional-tool inventory. Missing input files remain input errors.

## Testing
238 targeted tests passed. Fast set: 1518 passed, 1 skipped, 1 unrelated failure in test_release_hygiene.py::test_tracked_text_has_no_personal_paths from Uvm/vip/qualification/native-2026-11-13.json.
Native tools and full suite NOT RUN.

## Issues
Unknown dependencies point to doctor; installer flags are never guessed.
Roadmap notes: uniform MCP errors and inventory installation hints are implemented.


## PR 868

[#868](https://github.com/riscPrint/risc-v-workstation/pull/868). Merged: 2026-11-13T07:08:14Z.

Title: feat(vscode): add workstation-checklist views

Audit evidence label: unit tests only.

## Summary
Add workstation-checklist support in the thin Workstation extension. Read the feature README for commands and limits.

## Testing
VS Code typecheck and build passed. npm test: 36 passed, zero skipped.
No simulations, sbt, core builds, native tools or live VS Code checks ran. Python tests did not run because this change touches no Python code and the task limits tests to touched files.

## Issues
No issue closure claimed.

Roadmap notes: Add the workstation-checklist extension capability. Saved producer data does not establish new verification evidence.


## PR 869

[#869](https://github.com/riscPrint/risc-v-workstation/pull/869). Merged: 2026-11-13T07:08:08Z.

Title: perf(init): reuse the captured external runtime classpath

Audit evidence label: unit tests only.

## Summary
Cache the external adapter runtime classpath after the first compile. Reuse Java directly when source, build, environment and runtime file hashes match. Use a private sbt lock per project. Keep live native identity capture on each launch.

## Testing
Targeted init and cache tests: 24 passed. Scratch core native build passed. Cached native smoke run in progress; result recorded below. Full Python suite, BOOM and long formal runs NOT RUN.

## Issues
Refs: dry-run edge 2. Nonstandard build inputs still need explicit project capture.

Roadmap notes: external launcher avoids repeated sbt startup and rebuilds after captured source or runtime changes.

Cached native smoke passed: 19 instructions / 29 cycles, 20.63 s launch, no sbt output. Unit tests verify invalidation for source, runtime bytecode and build environment changes, plus failed compile refusal.

Fast set: 1,516 passed, 1 skipped, 2 unrelated failures: documentation staging and personal paths in Uvm/vip/qualification/native-2026-11-13.json.


## PR 870

[#870](https://github.com/riscPrint/risc-v-workstation/pull/870). Merged: 2026-11-13T07:09:17Z.

Title: feat(vscode): add coverage-gutter views

Audit evidence label: unit tests only.

## Summary
Add coverage-gutter support in the thin Workstation extension. Read the feature README for commands and limits.

## Testing
VS Code typecheck and build passed. npm test: 36 passed, zero skipped.
No simulations, sbt, core builds, native tools or live VS Code checks ran. Python tests did not run because this change touches no Python code and the task limits tests to touched files.

## Issues
No issue closure claimed.

Roadmap notes: Add the coverage-gutter extension capability. Saved producer data does not establish new verification evidence.
