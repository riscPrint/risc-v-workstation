# TODO

Open tasks are GitHub issues in [riscPrint/risc-v-workstation](https://github.com/riscPrint/risc-v-workstation/issues).
This file lists them under the areas of [ROADMAP.md](ROADMAP.md). Add new tasks as issues, then add a
line here. Remove the line when the issue closes. Core bugs found by the tools are in the
[spinal-boom issue tracker](https://github.com/riscPrint/spinal-boom/issues).

## Release (v0.1 public)

- [#37](https://github.com/riscPrint/risc-v-workstation/issues/37) Choose a license
- [#38](https://github.com/riscPrint/risc-v-workstation/issues/38) Community files: CONTRIBUTING, SECURITY, issue and PR templates
- [#39](https://github.com/riscPrint/risc-v-workstation/issues/39) Ask GitHub Support to purge cached old commits
- [#40](https://github.com/riscPrint/risc-v-workstation/issues/40) Reproducible installs: Python lock file and tested tool versions
- [#41](https://github.com/riscPrint/risc-v-workstation/issues/41) Fast and slow test sets for CI

## Integration with cores

- [#1](https://github.com/riscPrint/risc-v-workstation/issues/1) Integrate risc-v-workstation with BOOM
- [#34](https://github.com/riscPrint/risc-v-workstation/issues/34) Integration model: how core projects install and use the workstation
- [#35](https://github.com/riscPrint/risc-v-workstation/issues/35) `rvw doctor`: check (and optionally install) the setup
- [#36](https://github.com/riscPrint/risc-v-workstation/issues/36) `rvw init`: scaffold a core project

## ARCH: architecture exploration

- [#12](https://github.com/riscPrint/risc-v-workstation/issues/12) gem5: generic fitting
- [#13](https://github.com/riscPrint/risc-v-workstation/issues/13) gem5: in-order and RV32 cores
- [#56](https://github.com/riscPrint/risc-v-workstation/issues/56) Linux boot flow: QEMU, OpenSBI and Buildroot
- [#72](https://github.com/riscPrint/risc-v-workstation/issues/72) gem5: model features for wide cores

## IDE: design entry and navigation

- [#69](https://github.com/riscPrint/risc-v-workstation/issues/69) SpinalTrace and SpinalWaves: read the design database
- [#70](https://github.com/riscPrint/risc-v-workstation/issues/70) SpinalBlocks and SpinalDB: check on more designs
- [#77](https://github.com/riscPrint/risc-v-workstation/issues/77) Decide what the IDE needs beyond VS Code and Metals

## SIM: simulation and regression

- [#6](https://github.com/riscPrint/risc-v-workstation/issues/6) Generic gap: RiscvSim's build loads BOOM's sbt project
- [#7](https://github.com/riscPrint/risc-v-workstation/issues/7) Generic gap: store helpers assume 8-byte bus lanes
- [#9](https://github.com/riscPrint/risc-v-workstation/issues/9) Generic gap: the driver does not check the ELF XLEN
- [#14](https://github.com/riscPrint/risc-v-workstation/issues/14) Speed: persistent simulation server
- [#48](https://github.com/riscPrint/risc-v-workstation/issues/48) More test sources through RiscvSim: ACT4, riscv-dv, TestRIG
- [#73](https://github.com/riscPrint/risc-v-workstation/issues/73) Regression: full-tier run and cold gate timing
- [#74](https://github.com/riscPrint/risc-v-workstation/issues/74) Simulation: measure and cut Verilator build and run times for large configs
- [#2](https://github.com/riscPrint/risc-v-workstation/issues/2) Review: known-failure waivers and failure signatures
- [#4](https://github.com/riscPrint/risc-v-workstation/issues/4) Review: performance metrics and stored-folder gates
- [#25](https://github.com/riscPrint/risc-v-workstation/issues/25) Regression farm and web dashboard
- [#59](https://github.com/riscPrint/risc-v-workstation/issues/59) Run jobs on Kubernetes for scale tests
- [#76](https://github.com/riscPrint/risc-v-workstation/issues/76) Cleanup: drop the generic input_commands fields

## VER: co-simulation and test sources

- [#8](https://github.com/riscPrint/risc-v-workstation/issues/8) Generic gap: Spike platform fixes privilege modes and misaligned-access policy
- [#10](https://github.com/riscPrint/risc-v-workstation/issues/10) Cosim: compare FP registers and `fflags`
- [#11](https://github.com/riscPrint/risc-v-workstation/issues/11) Cosim: per-core settings for absent PMP CSRs and `mtval` on `ecall`
- [#47](https://github.com/riscPrint/risc-v-workstation/issues/47) Cosim: interrupt stimulus
- [#50](https://github.com/riscPrint/risc-v-workstation/issues/50) Regenerate the saved BOOM cosim traces
- [#75](https://github.com/riscPrint/risc-v-workstation/issues/75) Verification: riscv-vector-tests

## FV: formal verification and generated checks

- [#5](https://github.com/riscPrint/risc-v-workstation/issues/5) Triage the 24 SpinalChecks firings on BOOM
- [#65](https://github.com/riscPrint/risc-v-workstation/issues/65) SpinalChecks: more check rules
- [#66](https://github.com/riscPrint/risc-v-workstation/issues/66) SpinalChecks: TileLink and AXI protocol checks
- [#46](https://github.com/riscPrint/risc-v-workstation/issues/46) Formal: multi-clock designs and asynchronous resets
- [#67](https://github.com/riscPrint/risc-v-workstation/issues/67) Formal: X-propagation tooling
- [#63](https://github.com/riscPrint/risc-v-workstation/issues/63) Formal: generic riscv-formal harness
- [#18](https://github.com/riscPrint/risc-v-workstation/issues/18) Formal: sequential equivalence
- [#19](https://github.com/riscPrint/risc-v-workstation/issues/19) Formal: datapath checking against a C model
- [#20](https://github.com/riscPrint/risc-v-workstation/issues/20) Formal: security and information flow
- [#21](https://github.com/riscPrint/risc-v-workstation/issues/21) Formal: deeper proofs
- [#60](https://github.com/riscPrint/risc-v-workstation/issues/60) Formal: counterexample debugging (FV 8)
- [#61](https://github.com/riscPrint/risc-v-workstation/issues/61) Formal: full SVA and a SymbiYosys regression runner (FV 9)
- [#62](https://github.com/riscPrint/risc-v-workstation/issues/62) Formal: proof-core and cone-of-influence reports (FV 6)
- [#64](https://github.com/riscPrint/risc-v-workstation/issues/64) Formal: riscv-formal checks generated from Sail
- [#3](https://github.com/riscPrint/risc-v-workstation/issues/3) Review: `rvw cov mutate` on a BOOM unit
- [#42](https://github.com/riscPrint/risc-v-workstation/issues/42) Coverage: FSM coverage and Scala line mapping

## LINT: lint and clock-domain crossing

- [#22](https://github.com/riscPrint/risc-v-workstation/issues/22) Lint and clock-domain crossing

## DBG: debug and waveforms

- [#24](https://github.com/riscPrint/risc-v-workstation/issues/24) Integrated debug GUI and VS Code panels
- [#43](https://github.com/riscPrint/risc-v-workstation/issues/43) SpinalWaves needs a forked Surfer
- [#44](https://github.com/riscPrint/risc-v-workstation/issues/44) SpinalBlocks: use the design database and remove the BOOM entry point
- [#45](https://github.com/riscPrint/risc-v-workstation/issues/45) Run `rvw bisect` on real core history
- [#49](https://github.com/riscPrint/risc-v-workstation/issues/49) Konata: stall causes and predicated-off commits
- [#68](https://github.com/riscPrint/risc-v-workstation/issues/68) RiscvSim: --spinaltrace model flag

## EMU: emulation and FPGA prototyping

- [#23](https://github.com/riscPrint/risc-v-workstation/issues/23) Emulation and FPGA prototyping

## PLAT: platform

- [#15](https://github.com/riscPrint/risc-v-workstation/issues/15) Owner decisions from the simplicity audit
- [#16](https://github.com/riscPrint/risc-v-workstation/issues/16) CI: GitHub Actions
- [#17](https://github.com/riscPrint/risc-v-workstation/issues/17) Installer: full Linux installs with --with-riscv-gcc, --with-cosim, --with-formal, --with-gem5 and --all
- [#26](https://github.com/riscPrint/risc-v-workstation/issues/26) Non-Spinal cores
- [#53](https://github.com/riscPrint/risc-v-workstation/issues/53) Remote result cache
- [#54](https://github.com/riscPrint/risc-v-workstation/issues/54) Remote MCP server with authentication
- [#55](https://github.com/riscPrint/risc-v-workstation/issues/55) SystemVerilog and Verilog cores: design queries
- [#57](https://github.com/riscPrint/risc-v-workstation/issues/57) Agent run budgets and cost reports
- [#58](https://github.com/riscPrint/risc-v-workstation/issues/58) Documentation site
- [#71](https://github.com/riscPrint/risc-v-workstation/issues/71) Native tool bundle: pinned binaries per OS

## Later areas

- [#51](https://github.com/riscPrint/risc-v-workstation/issues/51) PPA estimates: synthesis, timing, area and power
- [#52](https://github.com/riscPrint/risc-v-workstation/issues/52) Fault injection for functional safety

## Ideas

- [#27](https://github.com/riscPrint/risc-v-workstation/issues/27) Idea: agent bug-fix loop
- [#28](https://github.com/riscPrint/risc-v-workstation/issues/28) Idea: self-explaining design diff
- [#29](https://github.com/riscPrint/risc-v-workstation/issues/29) Idea: spec-to-test generation from Sail
- [#30](https://github.com/riscPrint/risc-v-workstation/issues/30) Idea: coverage-closing test generation
- [#31](https://github.com/riscPrint/risc-v-workstation/issues/31) Idea: continuous model calibration
- [#32](https://github.com/riscPrint/risc-v-workstation/issues/32) Idea: bug-pattern memory
- [#33](https://github.com/riscPrint/risc-v-workstation/issues/33) Idea: random instruction streams with cosim

## Architecture model scope

Core projects choose queue models, event counters and fitting targets.
`examples/boom/arch/` is a demonstration. It is not a tuned BOOM model.
