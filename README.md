# RISC-V Workstation

Agent-native tooling for RISC-V cores written in SpinalHDL (and standard SystemVerilog/Verilog/VHDL/Chisel via `SpinalDB`), focused on four pillars: predictive microarchitecture exploration, fast simulation & lockstep co-simulation, design DB / waveform debug / structural lint, and compositional RTL-to-Lean 4 formal verification (`FV` v2).

No `spinal-boom` or private core checkout is required: every shipped workflow is self-contained with public examples including [examples/vexriscv](examples/vexriscv) and [examples/vexiiriscv](examples/vexiiriscv), while core-specific adapters (such as `examples/boom`) stay decoupled via [the platform contracts](docs/PLATFORM_CONTRACTS.md).

## Four Focus Pillars

| Pillar | What it includes | Primary entry points |
|---|---|---|
| **1. Predictive Microarchitecture & Performance** | Analytical/trace OoO modeling (`Arch/`, `rvw/ooo`), branch/prefetch/cache component models (`ComponentSims/`, `rvw/csim`), checkpoint sampling (`rvw/sample`), workloads (`rvw/workloads`), Konata pipeline & probe views (`SpinalKonata/`, `SpinalProbes/`, `rvw/perf`). Built to calibrate tightly against RTL and project Apple M4/M6 & Zen 5-class targets. | `rvw arch`, `rvw ooo`, `rvw csim`, `rvw perf`, `rvw sample`, `rvw workloads` |
| **2. Fast Simulation, Linux Boot & Co-Sim** | Fast Verilator runners (`RiscvSim/`), Spike/Sail/QEMU lockstep differential checking (`Cosim/`, `rvw/cosim`), committed regression gates (`rvw/regress`, `rvw/runs`), Linux boot & privilege/MMU suites. | `rvw sim`, `rvw regress`, `rvw cosim`, `rvw privilege` |
| **3. Design DB, Debug & Structural Hygiene** | `SpinalDB/` design SQLite database (`rvw query`), `SpinalTrace/`, `SpinalWaves/`, `SpinalBlocks/`, VS Code extension (`vscode/`), waveform slicing & cause attribution (`rvw wave`, `rvw bundle`, `rvw reduce`, `rvw bisect`), structural CDC/RDC/lint (`rvw lint`), and bounded SBY checks (`rvw formal bmc`, `from-sim`, `xprop`). | `rvw query`, `rvw wave`, `rvw bundle`, `rvw lint`, `rvw lsp`, `rvw formal` |
| **4. Agent-Native RTL -> Lean 4 (`FV` v2)** | Centerpiece deductive formal track: lower SpinalHDL-elaborated Verilog/RTLIL via Yosys JSON into hierarchical Lean 4 `BitVec` transition systems (`bv_decide` + induction), anchored on `sail-riscv` Lean 4 semantics. | [docs/LEAN_VERIFICATION_SPIKE.md](docs/LEAN_VERIFICATION_SPIKE.md) |

> **Scope Trim (Nov 2026):** Out-of-scope commercial-EDA parity subsystems were removed (`Uvm/`, `rvw/uvm`, `rvw/vip`, `rvw/cov`, `rvw/farm`, `rvw/plan`, `rvw/verification_plan`, `rvw/evidence`, `rvw/bugmem`, `rvw/agent_bench`, `docs/roadmap/`, and black-box BMC solver-race catalogs inside `rvw/formal/` and `SpinalChecks/`).

## Quickstart

```sh
scripts/install.sh --with-sim --with-riscv-gcc --with-cosim
source env.sh
rvw doctor --features sim,riscv-gcc,cosim --json
rvw mcp --list
```

See [docs/AGENT_SETUP.md](docs/AGENT_SETUP.md) for agent/MCP setup, [docs/INTEGRATION_GUIDE.md](docs/INTEGRATION_GUIDE.md) for core bring-up and contracts, and [docs/AGENT_ARCH.md](docs/AGENT_ARCH.md) for architecture exploration workflows.
