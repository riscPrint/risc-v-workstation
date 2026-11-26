# RISC-V Workstation Roadmap

`risc-v-workstation` is organized around **four high-leverage engineering pillars** rather than commercial-EDA checklist parity. Out-of-scope subsystems cut in November 2026 are listed at the bottom.

## Focus Pillars & Components

| Component | Path | Purpose | Generic? | Status | Next Step |
|---|---|---|---|---|---|
| **Architecture & Predictive Uarch** | `Arch/`, `ComponentSims/`, `rvw/src/rvw/{arch,ooo,csim,sample,workloads}/` | gem5 exploration, calibrated analytical OoO/component models, workload sampling | Yes | Active | Improve predictive accuracy to project Apple M4/M6 & Zen 5-class targets on `giga` |
| **Pipeline Perf & Probes** | `SpinalKonata/`, `SpinalProbes/`, `rvw/src/rvw/{perf,probes}/` | Konata cycle traces, pipeline stall attribution, hardware probes | Yes | Active | Feed stall/wrong-path deltas directly back into OoO calibration |
| **Simulation Runner & Gates** | `RiscvSim/`, `rvw/src/rvw/{sim,runs,regress}/` | Fast C1 Verilator simulation, ACT4/ISA/privilege/MMU runners, C3/C4 gates | Generic core interface + `examples/*` | Active | Linux boot + wide RV64GC/vector `giga` regression loops |
| **Lockstep Co-Sim** | `Cosim/`, `rvw/src/rvw/{cosim,csr}/` | Spike/Sail/QEMU RVFI lockstep checking, FP/vector/H/debug comparisons | Yes | Active | Complete wider CSR/fault/privilege differential checks |
| **Design DB & Queries** | `SpinalDB/`, `rvw/src/rvw/query/` | Elaborated design SQLite extraction (Spinal, SV via slang, VHDL via GHDL, FIRRTL) | Yes | Active | Export module hierarchy, widths, and source spans for RTL -> Lean decomposition |
| **Wave & Debug Loop** | `SpinalTrace/`, `SpinalWaves/`, `rvw/src/rvw/{wave,bundle,reduce,bisect,debug}/` | Dynamic PDG signal tracing, Surfer typed waves, C5 failure bundles, delta reduce, git bisect | Yes | Active | Tighten counterexample-to-Scala cause localization |
| **Block Diagrams & IDE** | `SpinalBlocks/`, `vscode/`, `rvw/src/rvw/lsp/` | Sigasi-style hierarchical diagrams, LSP navigation, VS Code integration | Yes | Active | Keep diagrams/LSP in sync with pruned CLI/JSON contracts |
| **Structural Lint & Bounded Formal** | `SpinalChecks/`, `rvw/src/rvw/{lint,checks,soc,sec,fault,memory}/`, `rvw/src/rvw/formal/` (`bmc`, `from-sim`, `xprop`, `x-context`, `x-sweep`) | CDC/RDC structural lint, SoC decode/connectivity checks, IFT security checks, X-prop & bounded SBY | Yes | Active | Keep focused on fast structural bugs & X-propagation; no BMC solver-race expansion |
| **Agent-Native RTL -> Lean 4 (`FV` v2)** | [docs/LEAN_VERIFICATION_SPIKE.md](docs/LEAN_VERIFICATION_SPIKE.md) | Hierarchical Verilog/Yosys JSON -> Lean 4 `BitVec` FSM (`bv_decide` + induction) anchored on `sail-riscv` | Yes | **Spike planned** | Execute 14-day vertical spike on BOOM rename/issue/MSHR targets |

## Intentional Scope Cuts (November 2026)

Instead of competing head-on with commercial simulation/formal/planner tools, the following areas were removed:
- **Accellera UVM & VIP parity:** `Uvm/`, `rvw/uvm`, `rvw/vip`, `rvw/sim/{uvm*,ral}`, UVM/VIP bench scaffolding in `rvw/soc`.
- **Verification management, cluster farm, bug memory & agent evals:** `rvw/{farm,plan,verification_plan,evidence,bugmem,agent_bench}`, `examples/{agent-bench,regression-scale}`.
- **Coverage closure & mutation campaigns:** `rvw/cov`, `rvw/regress/{commands/mutation.py,random_stream.py}`, `rvw/wave/mutations.py`, `rvw/examples/coverage/`.
- **Commercial 357-cell matrices & black-box BMC sprawl:** `docs/roadmap/`, `examples/formal/`, `SpinalChecks/{generated,c2rtl,upf,power,equiv}/`, and unused BMC engine-portfolio/race/catalog modules inside `rvw/formal/` (reduced to `bmc`, `from-sim`, `xprop`, `x-context`, `x-sweep`).
