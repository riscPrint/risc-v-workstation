# TODO replacement proposal

Snapshot collected at 2026-11-13T07:16:42.340567+00:00. PR merge window starts at 2026-11-13T00:00:00Z. This is a reading audit. No tests, builds, simulations or proofs ran for this report. PR bodies report the evidence. Their artifacts were not independently rerun.

This is literal proposed TODO text. Open issues stay listed. Closed issues that need scope review stay in a separate review block. This proposal does not reopen issues. New issues are included. Milestone assignments come from PR #381, not from an inferred area-to-milestone conversion.

## Current area layout

Replace the current issue-list sections with the following block.

```markdown
## ARCH: architecture exploration

- [#72](https://github.com/riscPrint/risc-v-workstation/issues/72) gem5: model features for wide cores. M3. Disposition: keep open — remaining scope.
- [#124](https://github.com/riscPrint/risc-v-workstation/issues/124) feat(arch): model soc cache and memory topology. M3. Disposition: keep open — remaining scope.
- [#125](https://github.com/riscPrint/risc-v-workstation/issues/125) feat(perf): analyze memory and interconnect performance. M3. Disposition: keep open — remaining scope.
- [#160](https://github.com/riscPrint/risc-v-workstation/issues/160) feat(arch): manage design-space exploration experiments. M4. Disposition: keep open — remaining scope.
- [#183](https://github.com/riscPrint/risc-v-workstation/issues/183) feat(arch): support representative workload sampling. M5. Disposition: keep open — remaining scope.
- [#196](https://github.com/riscPrint/risc-v-workstation/issues/196) feat(arch): explore custom instruction trade-offs. M2. Disposition: keep open — remaining scope.
- [#201](https://github.com/riscPrint/risc-v-workstation/issues/201) feat(arch): model system power-state workloads. M2. Disposition: keep open — remaining scope.
- [#282](https://github.com/riscPrint/risc-v-workstation/issues/282) chore(workloads): choose open alternatives to SPEC CPU2017. M6. Disposition: keep open — remaining scope.

## Coverage

- [#42](https://github.com/riscPrint/risc-v-workstation/issues/42) Coverage: FSM coverage and Scala line mapping. M2. Disposition: keep open — remaining scope.
- [#62](https://github.com/riscPrint/risc-v-workstation/issues/62) Formal: proof-core and cone-of-influence reports (FV 6). M3. Disposition: keep open — remaining scope.
- [#82](https://github.com/riscPrint/risc-v-workstation/issues/82) feat(cov): generate expected isa coverage bins. M2. Disposition: keep open — remaining scope.
- [#167](https://github.com/riscPrint/risc-v-workstation/issues/167) feat(cov): track reusable block verification evidence. M4. Disposition: keep open — remaining scope.
- [#180](https://github.com/riscPrint/risc-v-workstation/issues/180) feat(cov): exchange coverage through ucis. M4. Disposition: keep open — remaining scope.

## DBG: debug and waveforms

- [#24](https://github.com/riscPrint/risc-v-workstation/issues/24) Integrated debug GUI and VS Code panels. M5. Disposition: keep open — remaining scope.
- [#43](https://github.com/riscPrint/risc-v-workstation/issues/43) SpinalWaves needs a forked Surfer. M2. Disposition: keep open — remaining scope.
- [#45](https://github.com/riscPrint/risc-v-workstation/issues/45) Run `rvw bisect` on real core history. M4. Disposition: keep open — remaining scope.
- [#49](https://github.com/riscPrint/risc-v-workstation/issues/49) Konata: stall causes and predicated-off commits. M2. Disposition: keep open — remaining scope.
- [#144](https://github.com/riscPrint/risc-v-workstation/issues/144) feat(debug): verify trigger modules. M2. Disposition: keep open — remaining scope.
- [#168](https://github.com/riscPrint/risc-v-workstation/issues/168) feat(debug): verify e-trace encoder streams. M2. Disposition: keep open — remaining scope.
- [#172](https://github.com/riscPrint/risc-v-workstation/issues/172) feat(debug): verify trace loss and resynchronization. M2. Disposition: keep open — remaining scope.
- [#173](https://github.com/riscPrint/risc-v-workstation/issues/173) feat(debug): query large waveforms through indexed storage. M3. Disposition: keep open — remaining scope.
- [#191](https://github.com/riscPrint/risc-v-workstation/issues/191) feat(debug): add reverse-step through checkpoint replay. M4. Disposition: keep open — remaining scope.
- [#194](https://github.com/riscPrint/risc-v-workstation/issues/194) feat(debug): verify n-trace encoder streams. M2. Disposition: keep open — remaining scope.
- [#195](https://github.com/riscPrint/risc-v-workstation/issues/195) feat(debug): verify trace control and security filters. M2. Disposition: keep open — remaining scope.
- [#207](https://github.com/riscPrint/risc-v-workstation/issues/207) feat(debug): verify vendor trace format adapters. M2. Disposition: keep open — remaining scope.
- [#297](https://github.com/riscPrint/risc-v-workstation/issues/297) feat(debug): extend open debug tools to match or beat Verdi. M5. Disposition: keep open — remaining scope.
- [#375](https://github.com/riscPrint/risc-v-workstation/issues/375) Owner review: upstream SpinalTrace work (ccromjongh/SpinalHDL, SigTrail). M2. Disposition: untouched.

## Documentation

- [#58](https://github.com/riscPrint/risc-v-workstation/issues/58) Documentation site. M3. Disposition: keep open — remaining scope.

## EMU: emulation and FPGA prototyping

- [#23](https://github.com/riscPrint/risc-v-workstation/issues/23) Emulation and FPGA prototyping. M7. Disposition: untouched.

## FV: formal verification

- [#18](https://github.com/riscPrint/risc-v-workstation/issues/18) Formal: sequential equivalence. M3. Disposition: keep open — remaining scope.
- [#19](https://github.com/riscPrint/risc-v-workstation/issues/19) Formal: datapath checking against a C model. M3. Disposition: keep open — remaining scope.
- [#20](https://github.com/riscPrint/risc-v-workstation/issues/20) Formal: security and information flow. M3. Disposition: keep open — remaining scope.
- [#21](https://github.com/riscPrint/risc-v-workstation/issues/21) Formal: deeper proofs. M3. Disposition: keep open — remaining scope.
- [#46](https://github.com/riscPrint/risc-v-workstation/issues/46) Formal: multi-clock designs and asynchronous resets. M4. Disposition: keep open — remaining scope.
- [#60](https://github.com/riscPrint/risc-v-workstation/issues/60) Formal: counterexample debugging (FV 8). M3. Disposition: keep open — remaining scope.
- [#61](https://github.com/riscPrint/risc-v-workstation/issues/61) Formal: full SVA and a SymbiYosys regression runner (FV 9). M3. Disposition: keep open — remaining scope.
- [#63](https://github.com/riscPrint/risc-v-workstation/issues/63) Formal: generic riscv-formal harness. M3. Disposition: keep open — remaining scope.
- [#107](https://github.com/riscPrint/risc-v-workstation/issues/107) feat(formal): prove declared connectivity. M3. Disposition: keep open — remaining scope.
- [#294](https://github.com/riscPrint/risc-v-workstation/issues/294) feat(formal): extend open formal engines to match or beat JasperGold and VC Formal. M5. Disposition: keep open — remaining scope.

## FV: generated checks

- [#5](https://github.com/riscPrint/risc-v-workstation/issues/5) Triage the 24 SpinalChecks firings on BOOM. M2. Disposition: untouched.
- [#65](https://github.com/riscPrint/risc-v-workstation/issues/65) SpinalChecks: more check rules. M2. Disposition: keep open — remaining scope.
- [#66](https://github.com/riscPrint/risc-v-workstation/issues/66) SpinalChecks: TileLink and AXI protocol checks. M2. Disposition: keep open — remaining scope.
- [#98](https://github.com/riscPrint/risc-v-workstation/issues/98) feat(checks): verify zihpm counter behavior. M2. Disposition: keep open — remaining scope.
- [#142](https://github.com/riscPrint/risc-v-workstation/issues/142) feat(checks): verify register-map side-effect transactions. M3. Disposition: keep open — remaining scope.
- [#146](https://github.com/riscPrint/risc-v-workstation/issues/146) feat(checks): verify clock-gating controls. M2. Disposition: keep open — remaining scope.
- [#157](https://github.com/riscPrint/risc-v-workstation/issues/157) feat(checks): verify isolation and power-off behavior. M2. Disposition: keep open — remaining scope.
- [#163](https://github.com/riscPrint/risc-v-workstation/issues/163) feat(checks): verify retention and power sequencing. M2. Disposition: keep open — remaining scope.
- [#198](https://github.com/riscPrint/risc-v-workstation/issues/198) feat(checks): verify test-mode functional isolation. M3. Disposition: keep open — remaining scope.
- [#200](https://github.com/riscPrint/risc-v-workstation/issues/200) feat(checks): report rtl dft access constraints. M3. Disposition: keep open — remaining scope.

## Functional safety

- [#52](https://github.com/riscPrint/risc-v-workstation/issues/52) Fault injection for functional safety. M1. Disposition: keep open — remaining scope.

## IDE: design entry and navigation

- [#70](https://github.com/riscPrint/risc-v-workstation/issues/70) SpinalBlocks and SpinalDB: check on more designs. M2. Disposition: keep open — remaining scope.
- [#77](https://github.com/riscPrint/risc-v-workstation/issues/77) Decide what the IDE needs beyond VS Code and Metals. M2. Disposition: untouched.

## Ideas

- [#27](https://github.com/riscPrint/risc-v-workstation/issues/27) Idea: agent bug-fix loop. M5. Disposition: keep open — remaining scope.
- [#28](https://github.com/riscPrint/risc-v-workstation/issues/28) Idea: self-explaining design diff. M4. Disposition: keep open — remaining scope.
- [#29](https://github.com/riscPrint/risc-v-workstation/issues/29) Idea: spec-to-test generation from Sail. M2. Disposition: keep open — remaining scope.
- [#31](https://github.com/riscPrint/risc-v-workstation/issues/31) Idea: continuous model calibration. M3. Disposition: keep open — remaining scope.
- [#32](https://github.com/riscPrint/risc-v-workstation/issues/32) Idea: bug-pattern memory. M4. Disposition: keep open — remaining scope.
- [#33](https://github.com/riscPrint/risc-v-workstation/issues/33) Idea: random instruction streams with cosim. M2. Disposition: untouched.
- [#95](https://github.com/riscPrint/risc-v-workstation/issues/95) feat(platform): query verdict evidence across all tools. M2. Disposition: keep open — remaining scope.
- [#100](https://github.com/riscPrint/risc-v-workstation/issues/100) feat(platform): adjudicate independent reference disagreements. M2. Disposition: keep open — remaining scope.
- [#119](https://github.com/riscPrint/risc-v-workstation/issues/119) feat(platform): benchmark agent and human engineering tasks. M3. Disposition: untouched.
- [#123](https://github.com/riscPrint/risc-v-workstation/issues/123) feat(platform): expose agent workflow plans and completion events. M2. Disposition: keep open — remaining scope.

## Integration with cores

- [#1](https://github.com/riscPrint/risc-v-workstation/issues/1) Integrate risc-v-workstation with BOOM. M1. Disposition: untouched.
- [#34](https://github.com/riscPrint/risc-v-workstation/issues/34) Integration model: how core projects install and use the workstation. M1. Disposition: keep open — remaining scope.
- [#134](https://github.com/riscPrint/risc-v-workstation/issues/134) feat(integration): verify memory-map and bridge consistency. M2. Disposition: keep open — remaining scope.
- [#193](https://github.com/riscPrint/risc-v-workstation/issues/193) feat(integration): export rtl implementation handoff data. M2. Disposition: keep open — remaining scope.
- [#208](https://github.com/riscPrint/risc-v-workstation/issues/208) feat(integration): describe memory bist handoff requirements. M3. Disposition: keep open — remaining scope.
- [#211](https://github.com/riscPrint/risc-v-workstation/issues/211) feat(integration): describe jtag and test access topology. M3. Disposition: keep open — remaining scope.
- [#377](https://github.com/riscPrint/risc-v-workstation/issues/377) feat(integration): add VexiiRiscv as a test core. M2. Disposition: keep open — remaining scope.

## LINT: lint and clock-domain crossing

- [#22](https://github.com/riscPrint/risc-v-workstation/issues/22) Lint and clock-domain crossing. M4. Disposition: keep open — remaining scope.

## PLAT: platform

- [#15](https://github.com/riscPrint/risc-v-workstation/issues/15) Owner decisions from the simplicity audit. M1. Disposition: untouched.
- [#16](https://github.com/riscPrint/risc-v-workstation/issues/16) CI: GitHub Actions. M4. Disposition: untouched.
- [#17](https://github.com/riscPrint/risc-v-workstation/issues/17) Installer: full Linux installs with --with-riscv-gcc, --with-cosim, --with-formal, --with-gem5 and --all. M2. Disposition: keep open — remaining scope.
- [#26](https://github.com/riscPrint/risc-v-workstation/issues/26) Non-Spinal cores. M3. Disposition: keep open — remaining scope.
- [#35](https://github.com/riscPrint/risc-v-workstation/issues/35) `rvw doctor`: check (and optionally install) the setup. M3. Disposition: keep open — remaining scope.
- [#54](https://github.com/riscPrint/risc-v-workstation/issues/54) Remote MCP server with authentication. M2. Disposition: keep open — remaining scope.
- [#55](https://github.com/riscPrint/risc-v-workstation/issues/55) SystemVerilog and Verilog cores: design queries. M2. Disposition: keep open — remaining scope.
- [#57](https://github.com/riscPrint/risc-v-workstation/issues/57) Agent run budgets and cost reports. M4. Disposition: keep open — remaining scope.
- [#71](https://github.com/riscPrint/risc-v-workstation/issues/71) Native tool bundle: pinned binaries per OS. M4. Disposition: keep open — remaining scope.
- [#80](https://github.com/riscPrint/risc-v-workstation/issues/80) feat(platform): track implemented isa versions and options. M2. Disposition: keep open — remaining scope.
- [#104](https://github.com/riscPrint/risc-v-workstation/issues/104) feat(platform): track rva23 and rvb23 profile obligations. M2. Disposition: keep open — remaining scope.
- [#122](https://github.com/riscPrint/risc-v-workstation/issues/122) feat(platform): define custom instruction semantics. M2. Disposition: keep open — remaining scope.
- [#141](https://github.com/riscPrint/risc-v-workstation/issues/141) feat(platform): track risc-v specification changes. M2. Disposition: keep open — remaining scope.
- [#162](https://github.com/riscPrint/risc-v-workstation/issues/162) feat(platform): define explicit low-power intent. M2. Disposition: keep open — remaining scope.
- [#169](https://github.com/riscPrint/risc-v-workstation/issues/169) feat(platform): generate custom instruction software hooks. M2. Disposition: keep open — remaining scope.
- [#203](https://github.com/riscPrint/risc-v-workstation/issues/203) feat(platform): track cryptographic entropy interfaces. M3. Disposition: keep open — remaining scope.

## PPA estimates

- [#51](https://github.com/riscPrint/risc-v-workstation/issues/51) PPA estimates: synthesis, timing, area and power. M7. Disposition: untouched.

## Release (v0.1 public)

- [#37](https://github.com/riscPrint/risc-v-workstation/issues/37) Choose a license. M7. Disposition: keep open — remaining scope.
- [#38](https://github.com/riscPrint/risc-v-workstation/issues/38) Community files: CONTRIBUTING, SECURITY, issue and PR templates. M3. Disposition: untouched.
- [#39](https://github.com/riscPrint/risc-v-workstation/issues/39) Ask GitHub Support to purge cached old commits. M7. Disposition: keep open — remaining scope.
- [#40](https://github.com/riscPrint/risc-v-workstation/issues/40) Reproducible installs: Python lock file and tested tool versions. M2. Disposition: keep open — remaining scope.
- [#41](https://github.com/riscPrint/risc-v-workstation/issues/41) Fast and slow test sets for CI. M4. Disposition: untouched.
- [#78](https://github.com/riscPrint/risc-v-workstation/issues/78) chore(release): define the public release checklist. M3. Disposition: untouched.
- [#79](https://github.com/riscPrint/risc-v-workstation/issues/79) test(release): scan credentials and publication metadata. M1. Disposition: keep open — remaining scope.
- [#83](https://github.com/riscPrint/risc-v-workstation/issues/83) test(waves): validate interactive typed rendering. M2. Disposition: keep open — remaining scope.

## SIM: regression

- [#25](https://github.com/riscPrint/risc-v-workstation/issues/25) Regression farm and web dashboard. M6. Disposition: keep open — remaining scope.
- [#59](https://github.com/riscPrint/risc-v-workstation/issues/59) Run jobs on Kubernetes for scale tests. M6. Disposition: keep open — remaining scope.
- [#76](https://github.com/riscPrint/risc-v-workstation/issues/76) Cleanup: drop the generic input_commands fields. M1. Disposition: keep open — remaining scope.

## SIM: simulation

- [#14](https://github.com/riscPrint/risc-v-workstation/issues/14) Speed: persistent simulation server. M4. Disposition: keep open — remaining scope.
- [#48](https://github.com/riscPrint/risc-v-workstation/issues/48) More test sources through RiscvSim: ACT4, riscv-dv, TestRIG. M2. Disposition: keep open — remaining scope.
- [#74](https://github.com/riscPrint/risc-v-workstation/issues/74) Simulation: measure and cut Verilator build and run times for large configs. M5. Disposition: keep open — remaining scope.
- [#84](https://github.com/riscPrint/risc-v-workstation/issues/84) feat(sim): verify sv39 translation behavior. M2. Disposition: keep open — remaining scope.
- [#90](https://github.com/riscPrint/risc-v-workstation/issues/90) feat(sim): define multi-hart run and trace contracts. M2. Disposition: keep open — remaining scope.
- [#91](https://github.com/riscPrint/risc-v-workstation/issues/91) feat(sim): verify lr/sc reservations and progress. M2. Disposition: keep open — remaining scope.
- [#97](https://github.com/riscPrint/risc-v-workstation/issues/97) feat(sim): verify amo atomicity and ordering. M2. Disposition: keep open — remaining scope.
- [#99](https://github.com/riscPrint/risc-v-workstation/issues/99) feat(sim): verify tlb invalidation and asid behavior. M2. Disposition: keep open — remaining scope.
- [#102](https://github.com/riscPrint/risc-v-workstation/issues/102) feat(sim): verify memory fence ordering. M2. Disposition: untouched.
- [#103](https://github.com/riscPrint/risc-v-workstation/issues/103) feat(sim): verify instruction visibility and fence.i. M3. Disposition: keep open — remaining scope.
- [#109](https://github.com/riscPrint/risc-v-workstation/issues/109) feat(sim): verify instruction and data cache behavior. M2. Disposition: keep open — remaining scope.
- [#111](https://github.com/riscPrint/risc-v-workstation/issues/111) feat(sim): verify reset lifecycle and warm reset. M2. Disposition: keep open — remaining scope.
- [#112](https://github.com/riscPrint/risc-v-workstation/issues/112) feat(sim): verify physical memory attributes. M2. Disposition: keep open — remaining scope.
- [#128](https://github.com/riscPrint/risc-v-workstation/issues/128) feat(sim): verify coherence forward progress. M2. Disposition: keep open — remaining scope.
- [#129](https://github.com/riscPrint/risc-v-workstation/issues/129) feat(sim): verify page access and dirty updates. M2. Disposition: keep open — remaining scope.
- [#131](https://github.com/riscPrint/risc-v-workstation/issues/131) feat(sim): verify plic arbitration and delivery. M2. Disposition: keep open — remaining scope.
- [#132](https://github.com/riscPrint/risc-v-workstation/issues/132) feat(sim): add deterministic checkpoints and replay. M4. Disposition: keep open — remaining scope.
- [#137](https://github.com/riscPrint/risc-v-workstation/issues/137) feat(sim): verify cache-block operation extensions. M2. Disposition: keep open — remaining scope.
- [#138](https://github.com/riscPrint/risc-v-workstation/issues/138) feat(sim): verify epmp security policy. M2. Disposition: keep open — remaining scope.
- [#139](https://github.com/riscPrint/risc-v-workstation/issues/139) feat(sim): verify supervisor privilege controls. M2. Disposition: keep open — remaining scope.
- [#140](https://github.com/riscPrint/risc-v-workstation/issues/140) feat(sim): verify two-stage guest translation. M2. Disposition: keep open — remaining scope.
- [#145](https://github.com/riscPrint/risc-v-workstation/issues/145) feat(sim): verify shared tlb shootdown scenarios. M3. Disposition: keep open — remaining scope.
- [#147](https://github.com/riscPrint/risc-v-workstation/issues/147) feat(sim): verify sv48 translation behavior. M2. Disposition: keep open — remaining scope.
- [#148](https://github.com/riscPrint/risc-v-workstation/issues/148) feat(sim): verify svpbmt page attributes. M2. Disposition: keep open — remaining scope.
- [#149](https://github.com/riscPrint/risc-v-workstation/issues/149) feat(sim): verify wfi sleep and wakeup behavior. M2. Disposition: keep open — remaining scope.
- [#150](https://github.com/riscPrint/risc-v-workstation/issues/150) feat(sim): define portable resource-aware scenarios. M5. Disposition: keep open — remaining scope.
- [#151](https://github.com/riscPrint/risc-v-workstation/issues/151) feat(sim): verify hart lifecycle and shared resources. M2. Disposition: keep open — remaining scope.
- [#152](https://github.com/riscPrint/risc-v-workstation/issues/152) feat(sim): reduce instruction and concurrent stimulus failures. M2. Disposition: keep open — remaining scope.
- [#154](https://github.com/riscPrint/risc-v-workstation/issues/154) feat(sim): verify sv32 translation behavior. M2. Disposition: keep open — remaining scope.
- [#155](https://github.com/riscPrint/risc-v-workstation/issues/155) feat(sim): generate custom extension verification plans. M2. Disposition: keep open — remaining scope.
- [#158](https://github.com/riscPrint/risc-v-workstation/issues/158) feat(sim): verify aia imsic behavior. M2. Disposition: keep open — remaining scope.
- [#159](https://github.com/riscPrint/risc-v-workstation/issues/159) feat(sim): verify supervisor timer extensions. M2. Disposition: keep open — remaining scope.
- [#164](https://github.com/riscPrint/risc-v-workstation/issues/164) feat(sim): verify svnapot page mappings. M2. Disposition: keep open — remaining scope.
- [#165](https://github.com/riscPrint/risc-v-workstation/issues/165) feat(sim): verify aia aplic behavior. M2. Disposition: keep open — remaining scope.
- [#166](https://github.com/riscPrint/risc-v-workstation/issues/166) feat(sim): verify nmi and recoverable error entry. M2. Disposition: keep open — remaining scope.
- [#170](https://github.com/riscPrint/risc-v-workstation/issues/170) feat(sim): verify compare-and-swap extensions. M2. Disposition: keep open — remaining scope.
- [#171](https://github.com/riscPrint/risc-v-workstation/issues/171) feat(sim): verify sv57 translation behavior. M2. Disposition: keep open — remaining scope.
- [#174](https://github.com/riscPrint/risc-v-workstation/issues/174) feat(sim): verify landing-pad control-flow integrity. M2. Disposition: keep open — remaining scope.
- [#175](https://github.com/riscPrint/risc-v-workstation/issues/175) feat(sim): verify shadow-stack control-flow integrity. M2. Disposition: keep open — remaining scope.
- [#176](https://github.com/riscPrint/risc-v-workstation/issues/176) feat(sim): verify state-enable access controls. M2. Disposition: keep open — remaining scope.
- [#177](https://github.com/riscPrint/risc-v-workstation/issues/177) feat(sim): verify environment configuration controls. M2. Disposition: keep open — remaining scope.
- [#178](https://github.com/riscPrint/risc-v-workstation/issues/178) feat(sim): support systemverilog uvm testbench adapters. M4. Disposition: keep open — remaining scope.
- [#179](https://github.com/riscPrint/risc-v-workstation/issues/179) feat(sim): verify pointer masking and address rules. M2. Disposition: keep open — remaining scope.
- [#181](https://github.com/riscPrint/risc-v-workstation/issues/181) feat(sim): verify architectural ras reporting. M2. Disposition: keep open — remaining scope.
- [#182](https://github.com/riscPrint/risc-v-workstation/issues/182) feat(sim): add memory-controller and noc stress agents. M4. Disposition: keep open — remaining scope.
- [#184](https://github.com/riscPrint/risc-v-workstation/issues/184) feat(sim): verify ztso memory-order behavior. M3. Disposition: keep open — remaining scope.
- [#186](https://github.com/riscPrint/risc-v-workstation/issues/186) feat(sim): verify clic and aclic configurations. M2. Disposition: keep open — remaining scope.
- [#187](https://github.com/riscPrint/risc-v-workstation/issues/187) feat(sim): add systemc and tlm co-simulation adapters. M4. Disposition: keep open — remaining scope.
- [#188](https://github.com/riscPrint/risc-v-workstation/issues/188) feat(sim): verify iommu translation and isolation. M2. Disposition: keep open — remaining scope.
- [#190](https://github.com/riscPrint/risc-v-workstation/issues/190) feat(sim): add apb verification agents. M2. Disposition: keep open — remaining scope.
- [#192](https://github.com/riscPrint/risc-v-workstation/issues/192) feat(sim): add axi-stream verification agents. M2. Disposition: keep open — remaining scope.
- [#197](https://github.com/riscPrint/risc-v-workstation/issues/197) feat(sim): verify dvfs and clock-switch behavior. M2. Disposition: keep open — remaining scope.
- [#199](https://github.com/riscPrint/risc-v-workstation/issues/199) feat(sim): add ahb verification agents. M2. Disposition: keep open — remaining scope.
- [#202](https://github.com/riscPrint/risc-v-workstation/issues/202) feat(sim): add uart verification agents. M2. Disposition: keep open — remaining scope.
- [#204](https://github.com/riscPrint/risc-v-workstation/issues/204) feat(sim): add spi verification agents. M2. Disposition: keep open — remaining scope.
- [#205](https://github.com/riscPrint/risc-v-workstation/issues/205) feat(sim): add i2c verification agents. M2. Disposition: keep open — remaining scope.
- [#209](https://github.com/riscPrint/risc-v-workstation/issues/209) feat(sim): add gpio verification agents. M2. Disposition: keep open — remaining scope.
- [#212](https://github.com/riscPrint/risc-v-workstation/issues/212) feat(sim): add optional chi verification backend. M2. Disposition: keep open — remaining scope.
- [#213](https://github.com/riscPrint/risc-v-workstation/issues/213) feat(sim): validate dram model integration contracts. M4. Disposition: keep open — remaining scope.
- [#214](https://github.com/riscPrint/risc-v-workstation/issues/214) feat(sim): add timing annotation capability contracts. M4. Disposition: keep open — remaining scope.
- [#215](https://github.com/riscPrint/risc-v-workstation/issues/215) feat(sim): add pcie transaction-model adapters. M2. Disposition: keep open — remaining scope.
- [#216](https://github.com/riscPrint/risc-v-workstation/issues/216) feat(sim): add ethernet packet-model adapters. M2. Disposition: keep open — remaining scope.
- [#217](https://github.com/riscPrint/risc-v-workstation/issues/217) feat(sim): define mixed-signal boundary model adapters. M4. Disposition: keep open — remaining scope.
- [#295](https://github.com/riscPrint/risc-v-workstation/issues/295) feat(sim): extend open simulation to match or beat VCS and Xcelium. M6. Disposition: keep open — remaining scope.
- [#378](https://github.com/riscPrint/risc-v-workstation/issues/378) docs(research): study CORE-V-VERIF for UVM and CPU verification practice. M4. Disposition: untouched.

## Unmapped; owner assignment

- [#335](https://github.com/riscPrint/risc-v-workstation/issues/335) feat(sim): version-aware core adapters so bisect and gates work across core history. M4. Disposition: keep open — remaining scope.
- [#344](https://github.com/riscPrint/risc-v-workstation/issues/344) perf(sim): capture PGO and hierarchy inputs for BOOM trials. M4. Disposition: keep open — remaining scope.
- [#345](https://github.com/riscPrint/risc-v-workstation/issues/345) feat(sim): evaluate native Arcilator with C1 and C2 contracts. M4. Disposition: keep open — remaining scope.
- [#346](https://github.com/riscPrint/risc-v-workstation/issues/346) feat(sim): save and restore native model and harness state. M4. Disposition: keep open — remaining scope.
- [#347](https://github.com/riscPrint/risc-v-workstation/issues/347) feat(sim): transfer Spike checkpoints into VexRiscv RTL. M4. Disposition: keep open — remaining scope.
- [#348](https://github.com/riscPrint/risc-v-workstation/issues/348) feat(arch): measure checkpoint warm-up bias against RTL. M4. Disposition: keep open — remaining scope.
- [#349](https://github.com/riscPrint/risc-v-workstation/issues/349) feat(cov): measure isa closure against random stimulus. M3. Disposition: keep open — remaining scope.
- [#350](https://github.com/riscPrint/risc-v-workstation/issues/350) feat(sim): extend checkpoint profiles for FP and system state. M4. Disposition: keep open — remaining scope.
- [#351](https://github.com/riscPrint/risc-v-workstation/issues/351) feat(component-sims): qualify TAGE-SC-L and BOOM-like project models. M3. Disposition: keep open — remaining scope.
- [#352](https://github.com/riscPrint/risc-v-workstation/issues/352) feat(cov): close sequence bins with bounded stimulus actions. M3. Disposition: keep open — remaining scope.
- [#353](https://github.com/riscPrint/risc-v-workstation/issues/353) feat(cov): guide stimulus with measured rtl event goals. M3. Disposition: keep open — remaining scope.
- [#354](https://github.com/riscPrint/risc-v-workstation/issues/354) feat(arch): check own core configuration and timing structures. M3. Disposition: keep open — remaining scope.
- [#355](https://github.com/riscPrint/risc-v-workstation/issues/355) feat(arch): calibrate own core model against held-out rtl events. M3. Disposition: keep open — remaining scope.
- [#356](https://github.com/riscPrint/risc-v-workstation/issues/356) feat(arch): qualify own core predictions and native speed. M3. Disposition: keep open — remaining scope.
- [#357](https://github.com/riscPrint/risc-v-workstation/issues/357) feat(arch): model multi-level BTB and FTQ-directed prefetching. M3. Disposition: keep open — remaining scope.
- [#358](https://github.com/riscPrint/risc-v-workstation/issues/358) feat(component-sims): compare predictor models with explicit RTL events. M3. Disposition: keep open — remaining scope.
- [#359](https://github.com/riscPrint/risc-v-workstation/issues/359) feat(arch): model a generic micro-op cache. M3. Disposition: keep open — remaining scope.
- [#360](https://github.com/riscPrint/risc-v-workstation/issues/360) feat(component-sims): add BTB and RAS trace models. M3. Disposition: keep open — remaining scope.
- [#361](https://github.com/riscPrint/risc-v-workstation/issues/361) feat(formal): extend coherence models with fair progress and directory profiles. M2. Disposition: keep open — remaining scope.
- [#362](https://github.com/riscPrint/risc-v-workstation/issues/362) feat(arch): validate wide rename and bound memory renaming. M3. Disposition: keep open — remaining scope.
- [#363](https://github.com/riscPrint/risc-v-workstation/issues/363) feat(sim): bind coherence model monitors to TileLink-C channel RTL. M2. Disposition: keep open — remaining scope.
- [#364](https://github.com/riscPrint/risc-v-workstation/issues/364) feat(agent-bench): qualify native Spinal and VexRiscv tasks. M3. Disposition: keep open — remaining scope.
- [#365](https://github.com/riscPrint/risc-v-workstation/issues/365) feat(component-sims): add prefetch and cache-replacement studies. M3. Disposition: keep open — remaining scope.
- [#366](https://github.com/riscPrint/risc-v-workstation/issues/366) feat(agent-bench): add bounded external agent trials. M3. Disposition: keep open — remaining scope.
- [#367](https://github.com/riscPrint/risc-v-workstation/issues/367) feat(arch): integrate generated scheduling models into native compilers. M3. Disposition: keep open — remaining scope.
- [#369](https://github.com/riscPrint/risc-v-workstation/issues/369) feat(arch): extend scheduling measurements with held-out kernels. M3. Disposition: keep open — remaining scope.
- [#370](https://github.com/riscPrint/risc-v-workstation/issues/370) feat(query): elaborate full SV cores with slang and captured includes. M1. Disposition: keep open — remaining scope.
- [#371](https://github.com/riscPrint/risc-v-workstation/issues/371) feat(query): add a GHDL front end for VHDL designs. M1. Disposition: keep open — remaining scope.
- [#372](https://github.com/riscPrint/risc-v-workstation/issues/372) feat(query): add a FIRRTL and CIRCT front end for Chisel. M1. Disposition: keep open — remaining scope.
- [#722](https://github.com/riscPrint/risc-v-workstation/issues/722) feat(integration): add a chipyard verilator c1 adapter. Milestone needs owner assignment. Disposition: owner decision.
- [#723](https://github.com/riscPrint/risc-v-workstation/issues/723) feat(integration): adapt chipyard retirement traces to c2. Milestone needs owner assignment. Disposition: owner decision.

## VER: co-simulation and test sources

- [#8](https://github.com/riscPrint/risc-v-workstation/issues/8) Generic gap: Spike platform fixes privilege modes and misaligned-access policy. M2. Disposition: keep open — remaining scope.
- [#10](https://github.com/riscPrint/risc-v-workstation/issues/10) Cosim: compare FP registers and `fflags`. M2. Disposition: untouched.
- [#11](https://github.com/riscPrint/risc-v-workstation/issues/11) Cosim: per-core settings for absent PMP CSRs and `mtval` on `ecall`. M2. Disposition: keep open — remaining scope.
- [#75](https://github.com/riscPrint/risc-v-workstation/issues/75) Verification: riscv-vector-tests. M2. Disposition: keep open — remaining scope.
- [#93](https://github.com/riscPrint/risc-v-workstation/issues/93) feat(cosim): define faulting memory access records. M2. Disposition: keep open — remaining scope.
- [#96](https://github.com/riscPrint/risc-v-workstation/issues/96) feat(cosim): check rvwmo litmus outcomes. M2. Disposition: keep open — remaining scope.
- [#114](https://github.com/riscPrint/risc-v-workstation/issues/114) feat(cosim): compare hypervisor architectural state. M2. Disposition: keep open — remaining scope.
- [#136](https://github.com/riscPrint/risc-v-workstation/issues/136) feat(cosim): compare debug entry and stepping state. M2. Disposition: keep open — remaining scope.
- [#143](https://github.com/riscPrint/risc-v-workstation/issues/143) feat(cosim): load custom reference extensions. M2. Disposition: keep open — remaining scope.
- [#189](https://github.com/riscPrint/risc-v-workstation/issues/189) feat(cosim): exchange standard risc-v observation streams. M2. Disposition: keep open — remaining scope.
- [#210](https://github.com/riscPrint/risc-v-workstation/issues/210) feat(cosim): assess cheri architectural comparison. M3. Disposition: keep open — remaining scope.
- [#376](https://github.com/riscPrint/risc-v-workstation/issues/376) feat(cov): integrate RISCV-DV random instruction streams with cosim. M2. Disposition: keep open — remaining scope.

```

## Closed-today review block

A GitHub closure is an event, not a scope check. Proposed text:

```markdown
## Closed issues with acceptance review pending

- [#379](https://github.com/riscPrint/risc-v-workstation/issues/379) docs(research): study Chipyard and find contributions we can make. Review reported execution against all acceptance points before removing this review item.
- [#296](https://github.com/riscPrint/risc-v-workstation/issues/296) feat(sim): build a full open UVM flow. Review reported execution against all acceptance points before removing this review item.
- [#206](https://github.com/riscPrint/risc-v-workstation/issues/206) feat(integration): import implementation feedback links. Review reported execution against all acceptance points before removing this review item.
- [#185](https://github.com/riscPrint/risc-v-workstation/issues/185) feat(lint): validate rtl timing-constraint intent. Review reported execution against all acceptance points before removing this review item.
- [#161](https://github.com/riscPrint/risc-v-workstation/issues/161) feat(debug): test openocd and gdb interoperability. Review reported execution against all acceptance points before removing this review item.
- [#156](https://github.com/riscPrint/risc-v-workstation/issues/156) feat(debug): verify debug system-bus access. Review reported execution against all acceptance points before removing this review item.
- [#153](https://github.com/riscPrint/risc-v-workstation/issues/153) feat(debug): verify abstract commands and program buffer. Review reported execution against all acceptance points before removing this review item.
- [#133](https://github.com/riscPrint/risc-v-workstation/issues/133) feat(debug): add native dmi and jtag simulation drivers. Review reported execution against all acceptance points before removing this review item.
- [#127](https://github.com/riscPrint/risc-v-workstation/issues/127) feat(debug): verify debug module lifecycle. Review reported execution against all acceptance points before removing this review item.
- [#118](https://github.com/riscPrint/risc-v-workstation/issues/118) feat(lint): analyze reset-domain crossings. Review reported execution against all acceptance points before removing this review item.
- [#106](https://github.com/riscPrint/risc-v-workstation/issues/106) feat(platform): test agents against misleading evidence. Review reported execution against all acceptance points before removing this review item.
- [#87](https://github.com/riscPrint/risc-v-workstation/issues/87) feat(cosim): check unread architectural csr effects. Review reported execution against all acceptance points before removing this review item.
- [#85](https://github.com/riscPrint/risc-v-workstation/issues/85) feat(checks): generate csr behavior verification. Review reported execution against all acceptance points before removing this review item.
- [#64](https://github.com/riscPrint/risc-v-workstation/issues/64) Formal: riscv-formal checks generated from Sail. Review reported execution against all acceptance points before removing this review item.
```

## PR #381 exact milestone issue lists

Replace each Issues paragraph with the matching block. Closed issues remain marked for review. Unmapped issues require an owner assignment.

### M1

```markdown
Issues (9): [#1](https://github.com/riscPrint/risc-v-workstation/issues/1), [#15](https://github.com/riscPrint/risc-v-workstation/issues/15), [#34](https://github.com/riscPrint/risc-v-workstation/issues/34), [#52](https://github.com/riscPrint/risc-v-workstation/issues/52), [#76](https://github.com/riscPrint/risc-v-workstation/issues/76), [#79](https://github.com/riscPrint/risc-v-workstation/issues/79), [#370](https://github.com/riscPrint/risc-v-workstation/issues/370), [#371](https://github.com/riscPrint/risc-v-workstation/issues/371), [#372](https://github.com/riscPrint/risc-v-workstation/issues/372).
```

### M2

```markdown
Issues (115): [#5](https://github.com/riscPrint/risc-v-workstation/issues/5), [#8](https://github.com/riscPrint/risc-v-workstation/issues/8), [#10](https://github.com/riscPrint/risc-v-workstation/issues/10), [#11](https://github.com/riscPrint/risc-v-workstation/issues/11), [#17](https://github.com/riscPrint/risc-v-workstation/issues/17), [#29](https://github.com/riscPrint/risc-v-workstation/issues/29), [#33](https://github.com/riscPrint/risc-v-workstation/issues/33), [#40](https://github.com/riscPrint/risc-v-workstation/issues/40), [#42](https://github.com/riscPrint/risc-v-workstation/issues/42), [#43](https://github.com/riscPrint/risc-v-workstation/issues/43), [#48](https://github.com/riscPrint/risc-v-workstation/issues/48), [#49](https://github.com/riscPrint/risc-v-workstation/issues/49), [#54](https://github.com/riscPrint/risc-v-workstation/issues/54), [#55](https://github.com/riscPrint/risc-v-workstation/issues/55), [#64](https://github.com/riscPrint/risc-v-workstation/issues/64) (closed; acceptance review pending), [#65](https://github.com/riscPrint/risc-v-workstation/issues/65), [#66](https://github.com/riscPrint/risc-v-workstation/issues/66), [#70](https://github.com/riscPrint/risc-v-workstation/issues/70), [#75](https://github.com/riscPrint/risc-v-workstation/issues/75), [#77](https://github.com/riscPrint/risc-v-workstation/issues/77), [#80](https://github.com/riscPrint/risc-v-workstation/issues/80), [#82](https://github.com/riscPrint/risc-v-workstation/issues/82), [#83](https://github.com/riscPrint/risc-v-workstation/issues/83), [#84](https://github.com/riscPrint/risc-v-workstation/issues/84), [#85](https://github.com/riscPrint/risc-v-workstation/issues/85) (closed; acceptance review pending), [#87](https://github.com/riscPrint/risc-v-workstation/issues/87) (closed; acceptance review pending), [#90](https://github.com/riscPrint/risc-v-workstation/issues/90), [#91](https://github.com/riscPrint/risc-v-workstation/issues/91), [#93](https://github.com/riscPrint/risc-v-workstation/issues/93), [#95](https://github.com/riscPrint/risc-v-workstation/issues/95), [#96](https://github.com/riscPrint/risc-v-workstation/issues/96), [#97](https://github.com/riscPrint/risc-v-workstation/issues/97), [#98](https://github.com/riscPrint/risc-v-workstation/issues/98), [#99](https://github.com/riscPrint/risc-v-workstation/issues/99), [#100](https://github.com/riscPrint/risc-v-workstation/issues/100), [#102](https://github.com/riscPrint/risc-v-workstation/issues/102), [#104](https://github.com/riscPrint/risc-v-workstation/issues/104), [#109](https://github.com/riscPrint/risc-v-workstation/issues/109), [#111](https://github.com/riscPrint/risc-v-workstation/issues/111), [#112](https://github.com/riscPrint/risc-v-workstation/issues/112), [#114](https://github.com/riscPrint/risc-v-workstation/issues/114), [#122](https://github.com/riscPrint/risc-v-workstation/issues/122), [#123](https://github.com/riscPrint/risc-v-workstation/issues/123), [#127](https://github.com/riscPrint/risc-v-workstation/issues/127) (closed; acceptance review pending), [#128](https://github.com/riscPrint/risc-v-workstation/issues/128), [#129](https://github.com/riscPrint/risc-v-workstation/issues/129), [#131](https://github.com/riscPrint/risc-v-workstation/issues/131), [#133](https://github.com/riscPrint/risc-v-workstation/issues/133) (closed; acceptance review pending), [#134](https://github.com/riscPrint/risc-v-workstation/issues/134), [#136](https://github.com/riscPrint/risc-v-workstation/issues/136), [#137](https://github.com/riscPrint/risc-v-workstation/issues/137), [#138](https://github.com/riscPrint/risc-v-workstation/issues/138), [#139](https://github.com/riscPrint/risc-v-workstation/issues/139), [#140](https://github.com/riscPrint/risc-v-workstation/issues/140), [#141](https://github.com/riscPrint/risc-v-workstation/issues/141), [#143](https://github.com/riscPrint/risc-v-workstation/issues/143), [#144](https://github.com/riscPrint/risc-v-workstation/issues/144), [#146](https://github.com/riscPrint/risc-v-workstation/issues/146), [#147](https://github.com/riscPrint/risc-v-workstation/issues/147), [#148](https://github.com/riscPrint/risc-v-workstation/issues/148), [#149](https://github.com/riscPrint/risc-v-workstation/issues/149), [#151](https://github.com/riscPrint/risc-v-workstation/issues/151), [#152](https://github.com/riscPrint/risc-v-workstation/issues/152), [#153](https://github.com/riscPrint/risc-v-workstation/issues/153) (closed; acceptance review pending), [#154](https://github.com/riscPrint/risc-v-workstation/issues/154), [#155](https://github.com/riscPrint/risc-v-workstation/issues/155), [#156](https://github.com/riscPrint/risc-v-workstation/issues/156) (closed; acceptance review pending), [#157](https://github.com/riscPrint/risc-v-workstation/issues/157), [#158](https://github.com/riscPrint/risc-v-workstation/issues/158), [#159](https://github.com/riscPrint/risc-v-workstation/issues/159), [#161](https://github.com/riscPrint/risc-v-workstation/issues/161) (closed; acceptance review pending), [#162](https://github.com/riscPrint/risc-v-workstation/issues/162), [#163](https://github.com/riscPrint/risc-v-workstation/issues/163), [#164](https://github.com/riscPrint/risc-v-workstation/issues/164), [#165](https://github.com/riscPrint/risc-v-workstation/issues/165), [#166](https://github.com/riscPrint/risc-v-workstation/issues/166), [#168](https://github.com/riscPrint/risc-v-workstation/issues/168), [#169](https://github.com/riscPrint/risc-v-workstation/issues/169), [#170](https://github.com/riscPrint/risc-v-workstation/issues/170), [#171](https://github.com/riscPrint/risc-v-workstation/issues/171), [#172](https://github.com/riscPrint/risc-v-workstation/issues/172), [#174](https://github.com/riscPrint/risc-v-workstation/issues/174), [#175](https://github.com/riscPrint/risc-v-workstation/issues/175), [#176](https://github.com/riscPrint/risc-v-workstation/issues/176), [#177](https://github.com/riscPrint/risc-v-workstation/issues/177), [#179](https://github.com/riscPrint/risc-v-workstation/issues/179), [#181](https://github.com/riscPrint/risc-v-workstation/issues/181), [#185](https://github.com/riscPrint/risc-v-workstation/issues/185) (closed; acceptance review pending), [#186](https://github.com/riscPrint/risc-v-workstation/issues/186), [#188](https://github.com/riscPrint/risc-v-workstation/issues/188), [#189](https://github.com/riscPrint/risc-v-workstation/issues/189), [#190](https://github.com/riscPrint/risc-v-workstation/issues/190), [#192](https://github.com/riscPrint/risc-v-workstation/issues/192), [#193](https://github.com/riscPrint/risc-v-workstation/issues/193), [#194](https://github.com/riscPrint/risc-v-workstation/issues/194), [#195](https://github.com/riscPrint/risc-v-workstation/issues/195), [#196](https://github.com/riscPrint/risc-v-workstation/issues/196), [#197](https://github.com/riscPrint/risc-v-workstation/issues/197), [#199](https://github.com/riscPrint/risc-v-workstation/issues/199), [#201](https://github.com/riscPrint/risc-v-workstation/issues/201), [#202](https://github.com/riscPrint/risc-v-workstation/issues/202), [#204](https://github.com/riscPrint/risc-v-workstation/issues/204), [#205](https://github.com/riscPrint/risc-v-workstation/issues/205), [#206](https://github.com/riscPrint/risc-v-workstation/issues/206) (closed; acceptance review pending), [#207](https://github.com/riscPrint/risc-v-workstation/issues/207), [#209](https://github.com/riscPrint/risc-v-workstation/issues/209), [#212](https://github.com/riscPrint/risc-v-workstation/issues/212), [#215](https://github.com/riscPrint/risc-v-workstation/issues/215), [#216](https://github.com/riscPrint/risc-v-workstation/issues/216), [#361](https://github.com/riscPrint/risc-v-workstation/issues/361), [#363](https://github.com/riscPrint/risc-v-workstation/issues/363), [#375](https://github.com/riscPrint/risc-v-workstation/issues/375), [#376](https://github.com/riscPrint/risc-v-workstation/issues/376), [#377](https://github.com/riscPrint/risc-v-workstation/issues/377), [#379](https://github.com/riscPrint/risc-v-workstation/issues/379) (closed; acceptance review pending).
```

### M3

```markdown
Issues (48): [#18](https://github.com/riscPrint/risc-v-workstation/issues/18), [#19](https://github.com/riscPrint/risc-v-workstation/issues/19), [#20](https://github.com/riscPrint/risc-v-workstation/issues/20), [#21](https://github.com/riscPrint/risc-v-workstation/issues/21), [#26](https://github.com/riscPrint/risc-v-workstation/issues/26), [#31](https://github.com/riscPrint/risc-v-workstation/issues/31), [#35](https://github.com/riscPrint/risc-v-workstation/issues/35), [#38](https://github.com/riscPrint/risc-v-workstation/issues/38), [#58](https://github.com/riscPrint/risc-v-workstation/issues/58), [#60](https://github.com/riscPrint/risc-v-workstation/issues/60), [#61](https://github.com/riscPrint/risc-v-workstation/issues/61), [#62](https://github.com/riscPrint/risc-v-workstation/issues/62), [#63](https://github.com/riscPrint/risc-v-workstation/issues/63), [#72](https://github.com/riscPrint/risc-v-workstation/issues/72), [#78](https://github.com/riscPrint/risc-v-workstation/issues/78), [#103](https://github.com/riscPrint/risc-v-workstation/issues/103), [#106](https://github.com/riscPrint/risc-v-workstation/issues/106) (closed; acceptance review pending), [#107](https://github.com/riscPrint/risc-v-workstation/issues/107), [#119](https://github.com/riscPrint/risc-v-workstation/issues/119), [#124](https://github.com/riscPrint/risc-v-workstation/issues/124), [#125](https://github.com/riscPrint/risc-v-workstation/issues/125), [#142](https://github.com/riscPrint/risc-v-workstation/issues/142), [#145](https://github.com/riscPrint/risc-v-workstation/issues/145), [#173](https://github.com/riscPrint/risc-v-workstation/issues/173), [#184](https://github.com/riscPrint/risc-v-workstation/issues/184), [#198](https://github.com/riscPrint/risc-v-workstation/issues/198), [#200](https://github.com/riscPrint/risc-v-workstation/issues/200), [#203](https://github.com/riscPrint/risc-v-workstation/issues/203), [#208](https://github.com/riscPrint/risc-v-workstation/issues/208), [#210](https://github.com/riscPrint/risc-v-workstation/issues/210), [#211](https://github.com/riscPrint/risc-v-workstation/issues/211), [#349](https://github.com/riscPrint/risc-v-workstation/issues/349), [#351](https://github.com/riscPrint/risc-v-workstation/issues/351), [#352](https://github.com/riscPrint/risc-v-workstation/issues/352), [#353](https://github.com/riscPrint/risc-v-workstation/issues/353), [#354](https://github.com/riscPrint/risc-v-workstation/issues/354), [#355](https://github.com/riscPrint/risc-v-workstation/issues/355), [#356](https://github.com/riscPrint/risc-v-workstation/issues/356), [#357](https://github.com/riscPrint/risc-v-workstation/issues/357), [#358](https://github.com/riscPrint/risc-v-workstation/issues/358), [#359](https://github.com/riscPrint/risc-v-workstation/issues/359), [#360](https://github.com/riscPrint/risc-v-workstation/issues/360), [#362](https://github.com/riscPrint/risc-v-workstation/issues/362), [#364](https://github.com/riscPrint/risc-v-workstation/issues/364), [#365](https://github.com/riscPrint/risc-v-workstation/issues/365), [#366](https://github.com/riscPrint/risc-v-workstation/issues/366), [#367](https://github.com/riscPrint/risc-v-workstation/issues/367), [#369](https://github.com/riscPrint/risc-v-workstation/issues/369).
```

### M4

```markdown
Issues (31): [#14](https://github.com/riscPrint/risc-v-workstation/issues/14), [#16](https://github.com/riscPrint/risc-v-workstation/issues/16), [#22](https://github.com/riscPrint/risc-v-workstation/issues/22), [#28](https://github.com/riscPrint/risc-v-workstation/issues/28), [#32](https://github.com/riscPrint/risc-v-workstation/issues/32), [#41](https://github.com/riscPrint/risc-v-workstation/issues/41), [#45](https://github.com/riscPrint/risc-v-workstation/issues/45), [#46](https://github.com/riscPrint/risc-v-workstation/issues/46), [#57](https://github.com/riscPrint/risc-v-workstation/issues/57), [#71](https://github.com/riscPrint/risc-v-workstation/issues/71), [#118](https://github.com/riscPrint/risc-v-workstation/issues/118) (closed; acceptance review pending), [#132](https://github.com/riscPrint/risc-v-workstation/issues/132), [#160](https://github.com/riscPrint/risc-v-workstation/issues/160), [#167](https://github.com/riscPrint/risc-v-workstation/issues/167), [#178](https://github.com/riscPrint/risc-v-workstation/issues/178), [#180](https://github.com/riscPrint/risc-v-workstation/issues/180), [#182](https://github.com/riscPrint/risc-v-workstation/issues/182), [#187](https://github.com/riscPrint/risc-v-workstation/issues/187), [#191](https://github.com/riscPrint/risc-v-workstation/issues/191), [#213](https://github.com/riscPrint/risc-v-workstation/issues/213), [#214](https://github.com/riscPrint/risc-v-workstation/issues/214), [#217](https://github.com/riscPrint/risc-v-workstation/issues/217), [#296](https://github.com/riscPrint/risc-v-workstation/issues/296) (closed; acceptance review pending), [#335](https://github.com/riscPrint/risc-v-workstation/issues/335), [#344](https://github.com/riscPrint/risc-v-workstation/issues/344), [#345](https://github.com/riscPrint/risc-v-workstation/issues/345), [#346](https://github.com/riscPrint/risc-v-workstation/issues/346), [#347](https://github.com/riscPrint/risc-v-workstation/issues/347), [#348](https://github.com/riscPrint/risc-v-workstation/issues/348), [#350](https://github.com/riscPrint/risc-v-workstation/issues/350), [#378](https://github.com/riscPrint/risc-v-workstation/issues/378).
```

### M5

```markdown
Issues (7): [#24](https://github.com/riscPrint/risc-v-workstation/issues/24), [#27](https://github.com/riscPrint/risc-v-workstation/issues/27), [#74](https://github.com/riscPrint/risc-v-workstation/issues/74), [#150](https://github.com/riscPrint/risc-v-workstation/issues/150), [#183](https://github.com/riscPrint/risc-v-workstation/issues/183), [#294](https://github.com/riscPrint/risc-v-workstation/issues/294), [#297](https://github.com/riscPrint/risc-v-workstation/issues/297).
```

### M6

```markdown
Issues (4): [#25](https://github.com/riscPrint/risc-v-workstation/issues/25), [#59](https://github.com/riscPrint/risc-v-workstation/issues/59), [#282](https://github.com/riscPrint/risc-v-workstation/issues/282), [#295](https://github.com/riscPrint/risc-v-workstation/issues/295).
```

### M7

```markdown
Issues (4): [#23](https://github.com/riscPrint/risc-v-workstation/issues/23), [#37](https://github.com/riscPrint/risc-v-workstation/issues/37), [#39](https://github.com/riscPrint/risc-v-workstation/issues/39), [#51](https://github.com/riscPrint/risc-v-workstation/issues/51).
```

### Unmapped

```markdown
Issues (2): [#722](https://github.com/riscPrint/risc-v-workstation/issues/722), [#723](https://github.com/riscPrint/risc-v-workstation/issues/723).
```
