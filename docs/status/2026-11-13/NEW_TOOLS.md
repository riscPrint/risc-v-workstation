# New tools and command families

Current census: 865 merged PR bodies, through 2026-11-13T16:37:04Z.
Each row reports the strongest executed slice. Native evidence is read from PR bodies. It was not rerun. A real-core report consumed by an index or plan is analysis of that report, not execution of a new core workflow. Full bodies are in [PR_EVIDENCE.md](PR_EVIDENCE.md).

## ComponentSims / rvw csim

Path: `ComponentSims/; rvw/src/rvw/csim/`.

Purpose: Trace-driven predictor, cache, prefetch and timing studies.

Evidence level: ran on real core RTL. Scope: VexRiscv and VexiiRiscv cached; BOOM small has earlier probe comparisons. Source: [#1219](https://github.com/riscPrint/risc-v-workstation/pull/1219).

What remains: The component models are approximate. Instruction-cache model alignment retains the completion/commit tail difference. Direct non-link jumps and ordinary indirect jumps are outside the declared predictor scope. Cache spans can overlap and do not measure a total of lost CPU cycles. The data-cache model does not reproduce the final dirty-line clean. Neither timing study establishes fidelity. Source: [#1219](https://github.com/riscPrint/risc-v-workstation/pull/1219).

## SpinalProbes / rvw probes

Path: `SpinalProbes/; rvw/src/rvw/probes/`.

Purpose: Optional simulation probes and consumer conversion.

Evidence level: ran on real core RTL. Scope: Stepper; VexRiscv, VexiiRiscv, NaxRiscv and BOOM small in earlier campaigns. Source: [#1230](https://github.com/riscPrint/risc-v-workstation/pull/1230).

What remains: Check stubs need actual semantic signals and activation conditions. Native optional probe regression needs an external mapped fixture. It does not qualify whole-core probes. Source: [#1230](https://github.com/riscPrint/risc-v-workstation/pull/1230).

## rvw sec

Path: `rvw/src/rvw/sec/`.

Purpose: Dynamic simulation security experiments and contract suites.

Evidence level: ran on real core RTL. Scope: VexRiscv and VexiiRiscv; Stepper paired and 42-cycle flow controls. Sources: [#955](https://github.com/riscPrint/risc-v-workstation/pull/955), [#1240](https://github.com/riscPrint/risc-v-workstation/pull/1240).

What remains: Finite Stepper flow and operand pairs complete. Whole-core and all-operand security remain open. Source: [#1248](https://github.com/riscPrint/risc-v-workstation/pull/1248).

## rvw fault

Path: `rvw/src/rvw/fault/; RiscvSim/`.

Purpose: Fault plans, native public-access injection and C2 classification.

Evidence level: ran on real core RTL. Scope: NaxRiscv; VexRiscv, VexiiRiscv and BOOM small in earlier injections. Source: [#1143](https://github.com/riscPrint/risc-v-workstation/pull/1143).

What remains: OoO Mini adds four confirmed flips, two detected and two safe. Selected register bits do not qualify broad fault coverage or hardware reliability. Source: [#1245](https://github.com/riscPrint/risc-v-workstation/pull/1245).

## rvw bugmem

Path: `rvw/src/rvw/bugmem/`.

Purpose: Store failure patterns and find similar reports.

Evidence level: unit tests only. Source: [#484](https://github.com/riscPrint/risc-v-workstation/pull/484).

What remains: - Signatures are weighted features from an `rvw bundle` summary (or a C1 result): C3 signature, assertion file, suspected unit, oldest unretired instruction class, traps, stalled channels, last function, spin loop, old open requests, message words without numbers. - Store: JSON lines (`rvw.bugmem/1`) outside the repository (`--store`, `RVW_BUGMEM`, `~/.local/share/rvw/bugmem.jsonl`), with the report SHA-256 and recorded source/core/config/ELF identity. Duplicate report bytes are refused; a cause is required. - Not run: matching accuracy on real held-out defects (no labelled defect set exists yet). Refs: #32. Stores failure signatures with causes, fixes and scope with source identities, and measures leave-one-out accuracy. Remaining: build a held-out set of real defects and tune the weights on it. Source: [#484](https://github.com/riscPrint/risc-v-workstation/pull/484).

## SpinalSoc / rvw soc compose

Path: `SpinalSoc/; rvw/src/rvw/soc/`.

Purpose: Compose map-driven peripheral SoCs and generate software data.

Evidence level: ran on real core RTL. Scope: VexRiscv composed SoC; Stepper. Source: [#1195](https://github.com/riscPrint/risc-v-workstation/pull/1195).

What remains: Stepper protocol and decode consumers close their fabric-only scopes. Five other consumers and automatic native preparation remain open. Vex CDC/RDC findings remain separate. Source: [#1248](https://github.com/riscPrint/risc-v-workstation/pull/1248).

## rvw vip / protocol families

Path: `rvw/src/rvw/vip/; Uvm/vip/`.

Purpose: Protocol agents, RTL controls and optional external-model contracts.

Evidence level: ran on real core RTL. Scope: VexRiscv CPU/DMA profile; peripheral RTL fixtures. Source: [#1165](https://github.com/riscPrint/risc-v-workstation/pull/1165).

What remains: Add a pinned OpenCores UART example outside the repository. Its 8-bit Wishbone interface becomes a word-spaced composer peripheral. No upstream source is edited. The descriptor intentionally describes two ordinary registers, not the complete UART model. Roadmap notes: external Verilog IP with a small TOML now has a composed native example. IP-XACT bus import, port inference, parameters, active-low reset and pipelined/retry Wishbone remain open. Source: [#1181](https://github.com/riscPrint/risc-v-workstation/pull/1181).

## rvw uvm / CPU and RAL families

Path: `rvw/src/rvw/uvm/; Uvm/`.

Purpose: Project benches, RAL and CPU verification sequences.

Evidence level: ran on real core RTL. Scope: Stepper; VexRiscv live CPU in earlier campaigns. Source: [#1229](https://github.com/riscPrint/risc-v-workstation/pull/1229).

What remains: Extended architectural observations and other bus protocols still need project bindings. These finite workloads do not establish whole-core or VIP qualification. Source: [#1229](https://github.com/riscPrint/risc-v-workstation/pull/1229).

## rvw lsp

Path: `rvw/src/rvw/lsp/`.

Purpose: Database-backed language navigation and an editor client.

Evidence level: unit tests only. Source: [#577](https://github.com/riscPrint/risc-v-workstation/pull/577).

What remains: - Not run: real core waves with a workload ELF. Refs: #24. Starts "join symbols, workload phases and hardware events in one time-aligned report". Remaining: DWARF line/stack views, multi-hart joins, flame views. Source: [#577](https://github.com/riscPrint/risc-v-workstation/pull/577).

## rvw plan

Path: `rvw/src/rvw/plan/`.

Purpose: Roll up project verification evidence and trends.

Evidence level: unit tests only. Scope: VexRiscv retained C1/C3/C4 evidence. Source: [#1182](https://github.com/riscPrint/risc-v-workstation/pull/1182).

What remains: The guide states the remaining cluster image/storage/RBAC/quota/cleanup work. Coverage ranking alone missed the planted fault. The original native bisection endpoint check did not reach simulation. A separate small real trap-cause negative control is being completed as a follow-up; it does not expand the XOR comparison evidence. Source: [#1182](https://github.com/riscPrint/risc-v-workstation/pull/1182).

## rvw agent guide

Path: `rvw/src/rvw/agent/`.

Purpose: Expose the agent playbook through CLI and MCP.

Evidence level: ran on real core RTL. Scope: Stepper. Source: [#1230](https://github.com/riscPrint/risc-v-workstation/pull/1230).

What remains: 52 targeted tests passed. Fast set: 2977 passed, one skipped. An opt-in native terminal-probe regression passed in 8.40 seconds on Stepper: C1 and C2 each had 15 retirements; the converted probes had 15 retirements and zero open IDs. Actual stdio MCP mapped init dry run and checks_plan returned successfully in 0.819 and 0.872 seconds. MCP discovery printed no skipped module. Full Python, BOOM and long proofs NOT RUN. Source: [#1230](https://github.com/riscPrint/risc-v-workstation/pull/1230).

## rvw evidence

Path: `rvw/src/rvw/evidence/`.

Purpose: Index original cross-tool evidence and dependencies.

Evidence level: unit tests only. Scope: VexRiscv retained reports, no new CPU run for indexing. Source: [#1182](https://github.com/riscPrint/risc-v-workstation/pull/1182).

What remains: The guide states the remaining cluster image/storage/RBAC/quota/cleanup work. Coverage ranking alone missed the planted fault. The original native bisection endpoint check did not reach simulation. A separate small real trap-cause negative control is being completed as a follow-up; it does not expand the XOR comparison evidence. Source: [#1182](https://github.com/riscPrint/risc-v-workstation/pull/1182).

## Standard device plugins

Path: `rvw/src/rvw/sim/; RiscvSim/`.

Purpose: Device models, live input wiring and device-aware checkpoints.

Evidence level: ran on real core RTL. Scope: VexiiRiscv RV64 supervisor. Source: [#1119](https://github.com/riscPrint/risc-v-workstation/pull/1119).

What remains: Final native control: OpenSBI v1.6 with the project-owned UART/CLINT platform passed at cycle 304429 with 126162 retirements. It observed 14 S-mode instructions, the supervisor ecall and SBI version 2.0. Complete C2 passed the shared parser. No PMP warning remained. The native pytest passed in 107.56 seconds. Eight Scala tests passed. A real store of 1 under the bounded Linux profile did not pass; C2 validated that store and C1 timed out at cycle 500. Failed discovery runs are retained locally: generic DTB firmware exceeded 240/600/900-second limits. The fixed-map platform exposed missing 64-bit CLINT MMIO, which is fixed and tested. Its initial narrow PMP ranges were corrected to the standard compare bank. The final control rejects PMP warnings. Latest fast set: 2052 passed, 1 skipped, 8323 deselected. One unrelated failure: `rvw/tests/test_docs_site.py::test_docs_staging_does_not_write_sources`. Release hygiene: 40 passed. MCP discovery emitted no skipped tools. Full Linux boot, initramfs/user-space checks, native checkpoint restore and second-machine replay were not run or implemented. The native Spinal adapter's checkpoint gap remains open. Source: [#1119](https://github.com/riscPrint/risc-v-workstation/pull/1119).

## Arcilator adapter

Path: `rvw/src/rvw/sim/; RiscvSim/`.

Purpose: Alternate native engine and controlled comparison with Verilator.

Evidence level: ran on real core RTL. Scope: VexRiscv. Source: [#769](https://github.com/riscPrint/risc-v-workstation/pull/769).

What remains: The instruction and concurrent IRQ native reduction piece is measured. General stimulus streams and unknown upstream failures remain outside this recipe. The source capture omits the unused VexRiscv regression-data submodule in a pinned private local commit. The report retains the actual captured revision and fingerprint. Source: [#769](https://github.com/riscPrint/risc-v-workstation/pull/769).

## slang front end

Path: `rvw/src/rvw/query/`.

Purpose: Build a database from elaborated SystemVerilog.

Evidence level: ran on real core RTL. Scope: riscv-mini static import plus native simulation. Source: [#1069](https://github.com/riscPrint/risc-v-workstation/pull/1069).

What remains: No issue is closed. The report ranks the remaining bus-check, tool-version, lowering, query-semantics and full-qualification gaps. Source: [#1069](https://github.com/riscPrint/risc-v-workstation/pull/1069).

## GHDL front end

Path: `rvw/src/rvw/query/`.

Purpose: Build a database from the supported VHDL synthesis subset.

Evidence level: ran on real core RTL. Scope: NEORV32 via GHDL and Verilator. Source: [#1069](https://github.com/riscPrint/risc-v-workstation/pull/1069).

What remains: No issue is closed. The report ranks the remaining bus-check, tool-version, lowering, query-semantics and full-qualification gaps. Source: [#1069](https://github.com/riscPrint/risc-v-workstation/pull/1069).

## FIRRTL/CIRCT front end

Path: `rvw/src/rvw/query/`.

Purpose: Build a database from Chisel-generated FIRRTL through CIRCT.

Evidence level: ran on real core RTL. Scope: riscv-mini via CIRCT and Verilator. Source: [#1069](https://github.com/riscPrint/risc-v-workstation/pull/1069).

What remains: No issue is closed. The report ranks the remaining bus-check, tool-version, lowering, query-semantics and full-qualification gaps. Source: [#1069](https://github.com/riscPrint/risc-v-workstation/pull/1069).

## rvw checks

Path: `rvw/src/rvw/checks/`.

Purpose: Generate project checks and report connected qualification gaps.

Evidence level: ran on real core RTL. Scope: NaxRiscv RV32IMA; VexRiscv and VexiiRiscv. Source: [#1167](https://github.com/riscPrint/risc-v-workstation/pull/1167).

What remains: Six current activation gaps, retained backpressure findings, unbounded OoO conservation and NaxRiscv activation remain open. The short proof limits did not close them. Source: [#1171](https://github.com/riscPrint/risc-v-workstation/pull/1171).

## Farm service and workflows

Path: `rvw/src/rvw/farm/`.

Purpose: Queue work, plan shards and retain recovery and cost evidence.

Evidence level: ran on real core RTL. Scope: VexRiscv. Source: [#1189](https://github.com/riscPrint/risc-v-workstation/pull/1189).

What remains: This completes the native trap-cause observation left unexercised by the XOR failures. A cause fingerprint is not a root-cause diagnosis. Original-core bisection still stops on its unsupported gitlink. Kubernetes runtime and a reduced selection that catches the planted bug remain unqualified. Source: [#1189](https://github.com/riscPrint/risc-v-workstation/pull/1189).

## Debug Module campaign commands

Path: `rvw/src/rvw/debug/`.

Purpose: Reference Debug Module, DMI/JTAG drivers and trace campaigns.

Evidence level: ran on real core RTL. Scope: VexRiscv rv32im_dmi and rv32im_jtag. Source: [#1186](https://github.com/riscPrint/risc-v-workstation/pull/1186).

What remains: Roadmap notes: composed DMI halt/resume and all nine public TAP checks now have native evidence. The exported ndmreset request needs a system reset-controller binding. Complete debug compliance and composed OpenOCD/GDB remain open. - Public rvw debug tap: 9 passed, 0 failed, 0 inconclusive through composed JTAG pins. Final run drove 5,140 pin writes. No reference DTM served the socket. - No BOOM, long proof, full Python suite, complete debug/ISA compliance, system reset, composed OpenOCD/GDB, C1 acceptance or hardware run. Refs: #134. Owner retains closure. Standalone debug defects and unsupported capabilities remain distinct from this finite integration test. Source: [#1186](https://github.com/riscPrint/risc-v-workstation/pull/1186).

## Native HDL project scaffolds

Path: `rvw/src/rvw/init/`.

Purpose: Generate mapped external-core projects and launchers.

Evidence level: ran on real core RTL. Scope: Stepper RV32IM. Source: [#1217](https://github.com/riscPrint/risc-v-workstation/pull/1217).

What remains: Reviewed add/lw/sw cycles have bounded passes with activation. Trace-selected depth 22 remains inconclusive. Five SoC consumers and automatic native preparation remain open. Source: [#1248](https://github.com/riscPrint/risc-v-workstation/pull/1248).

## Agent trial and evidence benchmark

Path: `rvw/src/rvw/agent_bench/`.

Purpose: Score fixture tasks and run bounded external MCP client trials.

Evidence level: unit tests only. Source: [#817](https://github.com/riscPrint/risc-v-workstation/pull/817).

What remains: External client tests: 6 passed. The tests include repeated MCP trials, false repairs, disconnects, process-group timeout, exhausted call budgets and a missing executable. MCP discovery reports no skipped modules. Public fast set: 1397 passed, 1 skipped, 7994 deselected, 1 unrelated release-hygiene failure. `test_release_hygiene.py::test_tracked_text_has_no_personal_paths` finds personal paths in existing formal files. Those files are outside this change. The brief permits delivery with this unrelated failure. The CLI smoke trial on the incomplete-coverage task preserved the inconclusive result. LLM/API calls, native RTL repair trials and OS sandboxing NOT RUN. The external CLI must disable its own non-MCP tools. The runner exposes no shell or file tools over MCP. Hostile clients are outside C8 scope. Refs: #366, #27. This completes the bounded fixture-client runner. Provider-specific CLI configuration and scored LLM/native trials remain separate work. Source: [#817](https://github.com/riscPrint/risc-v-workstation/pull/817).

## MCP profiles and tool catalog

Path: `rvw/src/rvw/mcp/`.

Purpose: Authenticated sessions, profile filtering and common result envelopes.

Evidence level: unit tests only. Source: [#1075](https://github.com/riscPrint/risc-v-workstation/pull/1075).

What remains: No issue closure requested. These are static and unit checks. They do not qualify a native core workflow. Source: [#1075](https://github.com/riscPrint/risc-v-workstation/pull/1075).

## Cacheless multi-hart example

Path: `examples/smp/`.

Purpose: Run two to eight external VexiiRiscv harts with simulation RAM and devices.

Evidence level: ran on real core RTL. Scope: VexiiRiscv two to eight cacheless harts; two cached harts. Source: [#1133](https://github.com/riscPrint/risc-v-workstation/pull/1133).

What remains: No issue is closed. The documented limits remain open. Source: [#1154](https://github.com/riscPrint/risc-v-workstation/pull/1154).

## rvw memory

Path: `rvw/src/rvw/memory/`.

Purpose: Serialized and axiomatic memory observation checks and concurrent campaigns.

Evidence level: ran on real core RTL. Scope: VexiiRiscv SMP. Source: [#917](https://github.com/riscPrint/risc-v-workstation/pull/917).

What remains: No issue is closed. The documented limits remain open. Source: [#1154](https://github.com/riscPrint/risc-v-workstation/pull/1154).

## rvw privilege

Path: `rvw/src/rvw/privilege/`.

Purpose: Project-owned privilege and interrupt programs with independent observation checks.

Evidence level: ran on real core RTL. Scope: VexRiscv RV32IM, VexiiRiscv RV32/RV64 supervisor. Source: [#1194](https://github.com/riscPrint/risc-v-workstation/pull/1194).

What remains: The fresh VexRiscv replay reports five matches and three known interrupt-mtval findings. Its documented reset/IRQ input synchronization policy remains explicit. The audit also records the CLINT/PLIC feature plan; device reset remains excluded. Final pre-rebase fast set: 2,896 passed, one skipped, 8,074 deselected. Rebase applied cleanly. The final fresh RV64 reference replay finished: 459 matches and 11 known findings, with no unexpected failure, mismatch or inconclusive row. The same retained RTL captures supply these reference checks; they are not new RTL runs. Final reference replay summary: RV32 151 matches and eight known findings; RV64 459 matches and 11 known findings; VexRiscv five matches and three known findings. All 22 known records report their finding IDs and retain the original failure or mismatch. The reset campaign adds three strict matches over 507 instructions and nine pulses. Total across these selected reports: 618 matches, 22 known findings, zero unexpected failures and zero inconclusive rows. IRQ/reset synchronization policies remain explicit for the retained interrupt rows; this total is not a claim of zero synchronization across every family. Source: [#1194](https://github.com/riscPrint/risc-v-workstation/pull/1194).

## rvw verification-plan

Path: `rvw/src/rvw/verification_plan/`.

Purpose: Versioned extension and environment-control verification plans.

Evidence level: unit tests only. Source: [#736](https://github.com/riscPrint/risc-v-workstation/pull/736).

What remains: Compiler build and runtime feature qualification remain open. These exports support pure R-type RV32I/RV64I instructions only. Generated artifact licensing is not specified; upstream compiler licenses are recorded and the installed Spike license is not verified. Source: [#736](https://github.com/riscPrint/risc-v-workstation/pull/736).
