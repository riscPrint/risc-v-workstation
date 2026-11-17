# TODO

Open tasks are GitHub issues in [riscPrint/risc-v-workstation](https://github.com/riscPrint/risc-v-workstation/issues).
This file lists them under the areas of [ROADMAP.md](ROADMAP.md). Add new tasks as issues, then add a
line here. Remove the line when the issue closes. Core bugs found by the tools are in the
[spinal-boom issue tracker](https://github.com/riscPrint/spinal-boom/issues).

Milestones: `v0.1 public release`, `v0.2 (near term)` and `Later phases`. Ideas have no milestone.

## Release (v0.1 public)

- [#37](https://github.com/riscPrint/risc-v-workstation/issues/37) Choose a license
- [#38](https://github.com/riscPrint/risc-v-workstation/issues/38) Community files: CONTRIBUTING, SECURITY, issue and PR templates
- [#39](https://github.com/riscPrint/risc-v-workstation/issues/39) Ask GitHub Support to purge cached old commits
- [#40](https://github.com/riscPrint/risc-v-workstation/issues/40) Reproducible installs: Python lock file and tested tool versions
- [#41](https://github.com/riscPrint/risc-v-workstation/issues/41) Fast and slow test sets for CI
- [#78](https://github.com/riscPrint/risc-v-workstation/issues/78) chore(release): define the public release checklist
- [#79](https://github.com/riscPrint/risc-v-workstation/issues/79) test(release): scan credentials and publication metadata
- [#83](https://github.com/riscPrint/risc-v-workstation/issues/83) test(waves): validate interactive typed rendering

## Integration with cores

- [#1](https://github.com/riscPrint/risc-v-workstation/issues/1) Integrate risc-v-workstation with BOOM
- [#34](https://github.com/riscPrint/risc-v-workstation/issues/34) Integration model: how core projects install and use the workstation
- [#130](https://github.com/riscPrint/risc-v-workstation/issues/130) feat(integration): define soc memory maps and register data
- [#134](https://github.com/riscPrint/risc-v-workstation/issues/134) feat(integration): verify memory-map and bridge consistency
- [#193](https://github.com/riscPrint/risc-v-workstation/issues/193) feat(integration): export rtl implementation handoff data
- [#206](https://github.com/riscPrint/risc-v-workstation/issues/206) feat(integration): import implementation feedback links
- [#208](https://github.com/riscPrint/risc-v-workstation/issues/208) feat(integration): describe memory bist handoff requirements
- [#211](https://github.com/riscPrint/risc-v-workstation/issues/211) feat(integration): describe jtag and test access topology
- [#377](https://github.com/riscPrint/risc-v-workstation/issues/377) feat(integration): add VexiiRiscv as a test core
- [#379](https://github.com/riscPrint/risc-v-workstation/issues/379) docs(research): study Chipyard and find contributions we can make

## ARCH: architecture exploration

- [#12](https://github.com/riscPrint/risc-v-workstation/issues/12) gem5: generic fitting
- [#56](https://github.com/riscPrint/risc-v-workstation/issues/56) Linux boot flow: QEMU, OpenSBI and Buildroot
- [#72](https://github.com/riscPrint/risc-v-workstation/issues/72) gem5: model features for wide cores
- [#124](https://github.com/riscPrint/risc-v-workstation/issues/124) feat(arch): model soc cache and memory topology
- [#125](https://github.com/riscPrint/risc-v-workstation/issues/125) feat(perf): analyze memory and interconnect performance
- [#160](https://github.com/riscPrint/risc-v-workstation/issues/160) feat(arch): manage design-space exploration experiments
- [#183](https://github.com/riscPrint/risc-v-workstation/issues/183) feat(arch): support representative workload sampling
- [#196](https://github.com/riscPrint/risc-v-workstation/issues/196) feat(arch): explore custom instruction trade-offs
- [#201](https://github.com/riscPrint/risc-v-workstation/issues/201) feat(arch): model system power-state workloads
- [#282](https://github.com/riscPrint/risc-v-workstation/issues/282) chore(workloads): choose open alternatives to SPEC CPU2017

## IDE: design entry and navigation

- [#69](https://github.com/riscPrint/risc-v-workstation/issues/69) SpinalTrace and SpinalWaves: read the design database
- [#70](https://github.com/riscPrint/risc-v-workstation/issues/70) SpinalBlocks and SpinalDB: check on more designs
- [#77](https://github.com/riscPrint/risc-v-workstation/issues/77) Decide what the IDE needs beyond VS Code and Metals

## SIM: simulation

- [#6](https://github.com/riscPrint/risc-v-workstation/issues/6) Generic gap: RiscvSim's build loads BOOM's sbt project
- [#7](https://github.com/riscPrint/risc-v-workstation/issues/7) Generic gap: store helpers assume 8-byte bus lanes
- [#9](https://github.com/riscPrint/risc-v-workstation/issues/9) Generic gap: the driver does not check the ELF XLEN
- [#14](https://github.com/riscPrint/risc-v-workstation/issues/14) Speed: persistent simulation server
- [#48](https://github.com/riscPrint/risc-v-workstation/issues/48) More test sources through RiscvSim: ACT4, riscv-dv, TestRIG
- [#68](https://github.com/riscPrint/risc-v-workstation/issues/68) RiscvSim: --spinaltrace model flag
- [#74](https://github.com/riscPrint/risc-v-workstation/issues/74) Simulation: measure and cut Verilator build and run times for large configs
- [#84](https://github.com/riscPrint/risc-v-workstation/issues/84) feat(sim): verify sv39 translation behavior
- [#90](https://github.com/riscPrint/risc-v-workstation/issues/90) feat(sim): define multi-hart run and trace contracts
- [#91](https://github.com/riscPrint/risc-v-workstation/issues/91) feat(sim): verify lr/sc reservations and progress
- [#97](https://github.com/riscPrint/risc-v-workstation/issues/97) feat(sim): verify amo atomicity and ordering
- [#99](https://github.com/riscPrint/risc-v-workstation/issues/99) feat(sim): verify tlb invalidation and asid behavior
- [#102](https://github.com/riscPrint/risc-v-workstation/issues/102) feat(sim): verify memory fence ordering
- [#103](https://github.com/riscPrint/risc-v-workstation/issues/103) feat(sim): verify instruction visibility and fence.i
- [#108](https://github.com/riscPrint/risc-v-workstation/issues/108) feat(sim): verify cache coherence state transitions
- [#109](https://github.com/riscPrint/risc-v-workstation/issues/109) feat(sim): verify instruction and data cache behavior
- [#111](https://github.com/riscPrint/risc-v-workstation/issues/111) feat(sim): verify reset lifecycle and warm reset
- [#112](https://github.com/riscPrint/risc-v-workstation/issues/112) feat(sim): verify physical memory attributes
- [#116](https://github.com/riscPrint/risc-v-workstation/issues/116) feat(sim): declare backend semantic capabilities
- [#121](https://github.com/riscPrint/risc-v-workstation/issues/121) feat(sim): verify dma and cache coherence interactions
- [#128](https://github.com/riscPrint/risc-v-workstation/issues/128) feat(sim): verify coherence forward progress
- [#129](https://github.com/riscPrint/risc-v-workstation/issues/129) feat(sim): verify page access and dirty updates
- [#131](https://github.com/riscPrint/risc-v-workstation/issues/131) feat(sim): verify plic arbitration and delivery
- [#132](https://github.com/riscPrint/risc-v-workstation/issues/132) feat(sim): add deterministic checkpoints and replay
- [#135](https://github.com/riscPrint/risc-v-workstation/issues/135) feat(sim): verify clint and aclint devices
- [#137](https://github.com/riscPrint/risc-v-workstation/issues/137) feat(sim): verify cache-block operation extensions
- [#138](https://github.com/riscPrint/risc-v-workstation/issues/138) feat(sim): verify epmp security policy
- [#139](https://github.com/riscPrint/risc-v-workstation/issues/139) feat(sim): verify supervisor privilege controls
- [#140](https://github.com/riscPrint/risc-v-workstation/issues/140) feat(sim): verify two-stage guest translation
- [#145](https://github.com/riscPrint/risc-v-workstation/issues/145) feat(sim): verify shared tlb shootdown scenarios
- [#147](https://github.com/riscPrint/risc-v-workstation/issues/147) feat(sim): verify sv48 translation behavior
- [#148](https://github.com/riscPrint/risc-v-workstation/issues/148) feat(sim): verify svpbmt page attributes
- [#149](https://github.com/riscPrint/risc-v-workstation/issues/149) feat(sim): verify wfi sleep and wakeup behavior
- [#150](https://github.com/riscPrint/risc-v-workstation/issues/150) feat(sim): define portable resource-aware scenarios
- [#151](https://github.com/riscPrint/risc-v-workstation/issues/151) feat(sim): verify hart lifecycle and shared resources
- [#152](https://github.com/riscPrint/risc-v-workstation/issues/152) feat(sim): reduce instruction and concurrent stimulus failures
- [#154](https://github.com/riscPrint/risc-v-workstation/issues/154) feat(sim): verify sv32 translation behavior
- [#155](https://github.com/riscPrint/risc-v-workstation/issues/155) feat(sim): generate custom extension verification plans
- [#158](https://github.com/riscPrint/risc-v-workstation/issues/158) feat(sim): verify aia imsic behavior
- [#159](https://github.com/riscPrint/risc-v-workstation/issues/159) feat(sim): verify supervisor timer extensions
- [#164](https://github.com/riscPrint/risc-v-workstation/issues/164) feat(sim): verify svnapot page mappings
- [#165](https://github.com/riscPrint/risc-v-workstation/issues/165) feat(sim): verify aia aplic behavior
- [#166](https://github.com/riscPrint/risc-v-workstation/issues/166) feat(sim): verify nmi and recoverable error entry
- [#170](https://github.com/riscPrint/risc-v-workstation/issues/170) feat(sim): verify compare-and-swap extensions
- [#171](https://github.com/riscPrint/risc-v-workstation/issues/171) feat(sim): verify sv57 translation behavior
- [#174](https://github.com/riscPrint/risc-v-workstation/issues/174) feat(sim): verify landing-pad control-flow integrity
- [#175](https://github.com/riscPrint/risc-v-workstation/issues/175) feat(sim): verify shadow-stack control-flow integrity
- [#176](https://github.com/riscPrint/risc-v-workstation/issues/176) feat(sim): verify state-enable access controls
- [#177](https://github.com/riscPrint/risc-v-workstation/issues/177) feat(sim): verify environment configuration controls
- [#178](https://github.com/riscPrint/risc-v-workstation/issues/178) feat(sim): support systemverilog uvm testbench adapters
- [#179](https://github.com/riscPrint/risc-v-workstation/issues/179) feat(sim): verify pointer masking and address rules
- [#181](https://github.com/riscPrint/risc-v-workstation/issues/181) feat(sim): verify architectural ras reporting
- [#182](https://github.com/riscPrint/risc-v-workstation/issues/182) feat(sim): add memory-controller and noc stress agents
- [#184](https://github.com/riscPrint/risc-v-workstation/issues/184) feat(sim): verify ztso memory-order behavior
- [#186](https://github.com/riscPrint/risc-v-workstation/issues/186) feat(sim): verify clic and aclic configurations
- [#187](https://github.com/riscPrint/risc-v-workstation/issues/187) feat(sim): add systemc and tlm co-simulation adapters
- [#188](https://github.com/riscPrint/risc-v-workstation/issues/188) feat(sim): verify iommu translation and isolation
- [#190](https://github.com/riscPrint/risc-v-workstation/issues/190) feat(sim): add apb verification agents
- [#192](https://github.com/riscPrint/risc-v-workstation/issues/192) feat(sim): add axi-stream verification agents
- [#197](https://github.com/riscPrint/risc-v-workstation/issues/197) feat(sim): verify dvfs and clock-switch behavior
- [#199](https://github.com/riscPrint/risc-v-workstation/issues/199) feat(sim): add ahb verification agents
- [#202](https://github.com/riscPrint/risc-v-workstation/issues/202) feat(sim): add uart verification agents
- [#204](https://github.com/riscPrint/risc-v-workstation/issues/204) feat(sim): add spi verification agents
- [#205](https://github.com/riscPrint/risc-v-workstation/issues/205) feat(sim): add i2c verification agents
- [#209](https://github.com/riscPrint/risc-v-workstation/issues/209) feat(sim): add gpio verification agents
- [#212](https://github.com/riscPrint/risc-v-workstation/issues/212) feat(sim): add optional chi verification backend
- [#213](https://github.com/riscPrint/risc-v-workstation/issues/213) feat(sim): validate dram model integration contracts
- [#214](https://github.com/riscPrint/risc-v-workstation/issues/214) feat(sim): add timing annotation capability contracts
- [#215](https://github.com/riscPrint/risc-v-workstation/issues/215) feat(sim): add pcie transaction-model adapters
- [#216](https://github.com/riscPrint/risc-v-workstation/issues/216) feat(sim): add ethernet packet-model adapters
- [#217](https://github.com/riscPrint/risc-v-workstation/issues/217) feat(sim): define mixed-signal boundary model adapters
- [#295](https://github.com/riscPrint/risc-v-workstation/issues/295) feat(sim): extend open simulation to match or beat VCS and Xcelium
- [#296](https://github.com/riscPrint/risc-v-workstation/issues/296) feat(sim): build a full open UVM flow
- [#378](https://github.com/riscPrint/risc-v-workstation/issues/378) docs(research): study CORE-V-VERIF for UVM and CPU verification practice

## SIM: regression

- [#2](https://github.com/riscPrint/risc-v-workstation/issues/2) Review: known-failure waivers and failure signatures
- [#4](https://github.com/riscPrint/risc-v-workstation/issues/4) Review: performance metrics and stored-folder gates
- [#25](https://github.com/riscPrint/risc-v-workstation/issues/25) Regression farm and web dashboard
- [#59](https://github.com/riscPrint/risc-v-workstation/issues/59) Run jobs on Kubernetes for scale tests
- [#73](https://github.com/riscPrint/risc-v-workstation/issues/73) Regression: full-tier run and cold gate timing
- [#76](https://github.com/riscPrint/risc-v-workstation/issues/76) Cleanup: drop the generic input_commands fields

## Coverage

- [#42](https://github.com/riscPrint/risc-v-workstation/issues/42) Coverage: FSM coverage and Scala line mapping
- [#62](https://github.com/riscPrint/risc-v-workstation/issues/62) Formal: proof-core and cone-of-influence reports (FV 6)
- [#82](https://github.com/riscPrint/risc-v-workstation/issues/82) feat(cov): generate expected isa coverage bins
- [#167](https://github.com/riscPrint/risc-v-workstation/issues/167) feat(cov): track reusable block verification evidence
- [#180](https://github.com/riscPrint/risc-v-workstation/issues/180) feat(cov): exchange coverage through ucis

## VER: co-simulation and test sources

- [#8](https://github.com/riscPrint/risc-v-workstation/issues/8) Generic gap: Spike platform fixes privilege modes and misaligned-access policy
- [#10](https://github.com/riscPrint/risc-v-workstation/issues/10) Cosim: compare FP registers and `fflags`
- [#11](https://github.com/riscPrint/risc-v-workstation/issues/11) Cosim: per-core settings for absent PMP CSRs and `mtval` on `ecall`
- [#47](https://github.com/riscPrint/risc-v-workstation/issues/47) Cosim: interrupt stimulus
- [#75](https://github.com/riscPrint/risc-v-workstation/issues/75) Verification: riscv-vector-tests
- [#87](https://github.com/riscPrint/risc-v-workstation/issues/87) feat(cosim): check unread architectural csr effects
- [#93](https://github.com/riscPrint/risc-v-workstation/issues/93) feat(cosim): define faulting memory access records
- [#96](https://github.com/riscPrint/risc-v-workstation/issues/96) feat(cosim): check rvwmo litmus outcomes
- [#110](https://github.com/riscPrint/risc-v-workstation/issues/110) feat(cosim): check retirement during simulation
- [#114](https://github.com/riscPrint/risc-v-workstation/issues/114) feat(cosim): compare hypervisor architectural state
- [#136](https://github.com/riscPrint/risc-v-workstation/issues/136) feat(cosim): compare debug entry and stepping state
- [#143](https://github.com/riscPrint/risc-v-workstation/issues/143) feat(cosim): load custom reference extensions
- [#189](https://github.com/riscPrint/risc-v-workstation/issues/189) feat(cosim): exchange standard risc-v observation streams
- [#210](https://github.com/riscPrint/risc-v-workstation/issues/210) feat(cosim): assess cheri architectural comparison
- [#376](https://github.com/riscPrint/risc-v-workstation/issues/376) feat(cov): integrate RISCV-DV random instruction streams with cosim

## FV: generated checks

- [#5](https://github.com/riscPrint/risc-v-workstation/issues/5) Triage the 24 SpinalChecks firings on BOOM
- [#65](https://github.com/riscPrint/risc-v-workstation/issues/65) SpinalChecks: more check rules
- [#66](https://github.com/riscPrint/risc-v-workstation/issues/66) SpinalChecks: TileLink and AXI protocol checks
- [#85](https://github.com/riscPrint/risc-v-workstation/issues/85) feat(checks): generate csr behavior verification. RV32 scratch selections added for NaxRiscv and ooo-mini; RTL binding and native runs remain open.
- [#98](https://github.com/riscPrint/risc-v-workstation/issues/98) feat(checks): verify zihpm counter behavior
- [#142](https://github.com/riscPrint/risc-v-workstation/issues/142) feat(checks): verify register-map side-effect transactions
- [#146](https://github.com/riscPrint/risc-v-workstation/issues/146) feat(checks): verify clock-gating controls
- [#157](https://github.com/riscPrint/risc-v-workstation/issues/157) feat(checks): verify isolation and power-off behavior
- [#163](https://github.com/riscPrint/risc-v-workstation/issues/163) feat(checks): verify retention and power sequencing
- [#198](https://github.com/riscPrint/risc-v-workstation/issues/198) feat(checks): verify test-mode functional isolation
- [#200](https://github.com/riscPrint/risc-v-workstation/issues/200) feat(checks): report rtl dft access constraints

## FV: formal verification

- [#18](https://github.com/riscPrint/risc-v-workstation/issues/18) Formal: sequential equivalence
- [#19](https://github.com/riscPrint/risc-v-workstation/issues/19) Formal: datapath checking against a C model
- [#20](https://github.com/riscPrint/risc-v-workstation/issues/20) Formal: security and information flow. Paired model identity checks added; native campaign qualification remains open.
- [#21](https://github.com/riscPrint/risc-v-workstation/issues/21) Formal: deeper proofs
- [#46](https://github.com/riscPrint/risc-v-workstation/issues/46) Formal: multi-clock designs and asynchronous resets
- [#60](https://github.com/riscPrint/risc-v-workstation/issues/60) Formal: counterexample debugging (FV 8)
- [#61](https://github.com/riscPrint/risc-v-workstation/issues/61) Formal: full SVA and a SymbiYosys regression runner (FV 9)
- [#63](https://github.com/riscPrint/risc-v-workstation/issues/63) Formal: generic riscv-formal harness
- [#64](https://github.com/riscPrint/risc-v-workstation/issues/64) Formal: riscv-formal checks generated from Sail
- [#67](https://github.com/riscPrint/risc-v-workstation/issues/67) Formal: X-propagation tooling
- [#107](https://github.com/riscPrint/risc-v-workstation/issues/107) feat(formal): prove declared connectivity
- [#294](https://github.com/riscPrint/risc-v-workstation/issues/294) feat(formal): extend open formal engines to match or beat JasperGold and VC Formal

## LINT: lint and clock-domain crossing

- [#22](https://github.com/riscPrint/risc-v-workstation/issues/22) Lint and clock-domain crossing
- [#118](https://github.com/riscPrint/risc-v-workstation/issues/118) feat(lint): analyze reset-domain crossings
- [#185](https://github.com/riscPrint/risc-v-workstation/issues/185) feat(lint): validate rtl timing-constraint intent

## DBG: debug and waveforms

- [#24](https://github.com/riscPrint/risc-v-workstation/issues/24) Integrated debug GUI and VS Code panels
- [#43](https://github.com/riscPrint/risc-v-workstation/issues/43) SpinalWaves needs a forked Surfer
- [#44](https://github.com/riscPrint/risc-v-workstation/issues/44) SpinalBlocks: use the design database and remove the BOOM entry point
- [#45](https://github.com/riscPrint/risc-v-workstation/issues/45) Run `rvw bisect` on real core history
- [#49](https://github.com/riscPrint/risc-v-workstation/issues/49) Konata: stall causes and predicated-off commits
- [#120](https://github.com/riscPrint/risc-v-workstation/issues/120) chore(waves): triage vendored typed-viewer limits
- [#127](https://github.com/riscPrint/risc-v-workstation/issues/127) feat(debug): verify debug module lifecycle
- [#133](https://github.com/riscPrint/risc-v-workstation/issues/133) feat(debug): add native dmi and jtag simulation drivers. Python suite progress callback added with target-only final results and profile skips; callback tests use fixtures and the reference model.
- [#144](https://github.com/riscPrint/risc-v-workstation/issues/144) feat(debug): verify trigger modules
- [#153](https://github.com/riscPrint/risc-v-workstation/issues/153) feat(debug): verify abstract commands and program buffer
- [#156](https://github.com/riscPrint/risc-v-workstation/issues/156) feat(debug): verify debug system-bus access
- [#161](https://github.com/riscPrint/risc-v-workstation/issues/161) feat(debug): test openocd and gdb interoperability
- [#168](https://github.com/riscPrint/risc-v-workstation/issues/168) feat(debug): verify e-trace encoder streams
- [#172](https://github.com/riscPrint/risc-v-workstation/issues/172) feat(debug): verify trace loss and resynchronization
- [#173](https://github.com/riscPrint/risc-v-workstation/issues/173) feat(debug): query large waveforms through indexed storage
- [#191](https://github.com/riscPrint/risc-v-workstation/issues/191) feat(debug): add reverse-step through checkpoint replay
- [#194](https://github.com/riscPrint/risc-v-workstation/issues/194) feat(debug): verify n-trace encoder streams
- [#195](https://github.com/riscPrint/risc-v-workstation/issues/195) feat(debug): verify trace control and security filters
- [#207](https://github.com/riscPrint/risc-v-workstation/issues/207) feat(debug): verify vendor trace format adapters
- [#297](https://github.com/riscPrint/risc-v-workstation/issues/297) feat(debug): extend open debug tools to match or beat Verdi
- [#375](https://github.com/riscPrint/risc-v-workstation/issues/375) Owner review: upstream SpinalTrace work (ccromjongh/SpinalHDL, SigTrail)

## EMU: emulation and FPGA prototyping

- [#23](https://github.com/riscPrint/risc-v-workstation/issues/23) Emulation and FPGA prototyping

## PPA estimates

- [#51](https://github.com/riscPrint/risc-v-workstation/issues/51) PPA estimates: synthesis, timing, area and power

## Functional safety

- [#52](https://github.com/riscPrint/risc-v-workstation/issues/52) Fault injection for functional safety

## PLAT: platform

- [#15](https://github.com/riscPrint/risc-v-workstation/issues/15) Owner decisions from the simplicity audit
- [#16](https://github.com/riscPrint/risc-v-workstation/issues/16) CI: GitHub Actions
- [#17](https://github.com/riscPrint/risc-v-workstation/issues/17) Installer: full Linux installs with --with-riscv-gcc, --with-cosim, --with-formal, --with-gem5 and --all
- [#26](https://github.com/riscPrint/risc-v-workstation/issues/26) Non-Spinal cores
- [#35](https://github.com/riscPrint/risc-v-workstation/issues/35) `rvw doctor`: check (and optionally install) the setup
- [#36](https://github.com/riscPrint/risc-v-workstation/issues/36) `rvw init`: scaffold a core project
- [#54](https://github.com/riscPrint/risc-v-workstation/issues/54) Remote MCP server with authentication
- [#55](https://github.com/riscPrint/risc-v-workstation/issues/55) SystemVerilog and Verilog cores: design queries
- [#57](https://github.com/riscPrint/risc-v-workstation/issues/57) Agent run budgets and cost reports
- [#71](https://github.com/riscPrint/risc-v-workstation/issues/71) Native tool bundle: pinned binaries per OS
- [#80](https://github.com/riscPrint/risc-v-workstation/issues/80) feat(platform): track implemented isa versions and options
- [#104](https://github.com/riscPrint/risc-v-workstation/issues/104) feat(platform): track rva23 and rvb23 profile obligations
- [#122](https://github.com/riscPrint/risc-v-workstation/issues/122) feat(platform): define custom instruction semantics
- [#141](https://github.com/riscPrint/risc-v-workstation/issues/141) feat(platform): track risc-v specification changes
- [#162](https://github.com/riscPrint/risc-v-workstation/issues/162) feat(platform): define explicit low-power intent
- [#169](https://github.com/riscPrint/risc-v-workstation/issues/169) feat(platform): generate custom instruction software hooks
- [#203](https://github.com/riscPrint/risc-v-workstation/issues/203) feat(platform): track cryptographic entropy interfaces

## Documentation

- [#58](https://github.com/riscPrint/risc-v-workstation/issues/58) Documentation site
- [#101](https://github.com/riscPrint/risc-v-workstation/issues/101) chore(trackers): reconcile documented limit ownership

## Ideas

- [#27](https://github.com/riscPrint/risc-v-workstation/issues/27) Idea: agent bug-fix loop
- [#28](https://github.com/riscPrint/risc-v-workstation/issues/28) Idea: self-explaining design diff
- [#29](https://github.com/riscPrint/risc-v-workstation/issues/29) Idea: spec-to-test generation from Sail
- [#30](https://github.com/riscPrint/risc-v-workstation/issues/30) Idea: coverage-closing test generation
- [#31](https://github.com/riscPrint/risc-v-workstation/issues/31) Idea: continuous model calibration
- [#32](https://github.com/riscPrint/risc-v-workstation/issues/32) Idea: bug-pattern memory
- [#33](https://github.com/riscPrint/risc-v-workstation/issues/33) Idea: random instruction streams with cosim
- [#95](https://github.com/riscPrint/risc-v-workstation/issues/95) feat(platform): query verdict evidence across all tools
- [#100](https://github.com/riscPrint/risc-v-workstation/issues/100) feat(platform): adjudicate independent reference disagreements
- [#106](https://github.com/riscPrint/risc-v-workstation/issues/106) feat(platform): test agents against misleading evidence
- [#119](https://github.com/riscPrint/risc-v-workstation/issues/119) feat(platform): benchmark agent and human engineering tasks
- [#123](https://github.com/riscPrint/risc-v-workstation/issues/123) feat(platform): expose agent workflow plans and completion events
