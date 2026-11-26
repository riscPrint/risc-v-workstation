# risc-v-workstation

An agent-native hardware workstation and EDA platform built around SpinalHDL / RISC-V cores and four focused pillars:
1. **Predictive Microarchitecture & Performance (`Arch/`, `ComponentSims/`, `rvw perf`, `SpinalKonata/`, `SpinalProbes/`)**
2. **Fast Verilator Simulation, Linux Boot & Lockstep Co-Sim (`RiscvSim/`, `Cosim/`, `rvw sim/runs/regress/cosim`)**
3. **Design DB, Debug & Structural Hygiene (`SpinalDB/`, `rvw query`, `SpinalTrace/`, `SpinalWaves/`, `SpinalBlocks/`, `vscode/`, `rvw wave/bundle/reduce/bisect/lsp/lint`, `rvw formal bmc/from-sim/xprop`)**
4. **Agent-Native RTL -> Lean 4 Compositional Verification (`FV` v2)** — lowering SpinalHDL-elaborated Verilog/RTLIL to hierarchical Lean 4 transition systems (`bv_decide` + induction) anchored on Sail RISC-V (`docs/LEAN_VERIFICATION_SPIKE.md`).

Keep the workstation core-agnostic: core-specific signal names, presets, and test adapters live inside the core repo (`examples/*/`), not inside `rvw/src/rvw/` platform code.

## Contracts and docs

- Shared file/exit contracts: [docs/PLATFORM_CONTRACTS.md](docs/PLATFORM_CONTRACTS.md).
- Integration & agent setup: [docs/INTEGRATION_GUIDE.md](docs/INTEGRATION_GUIDE.md), [docs/AGENT_SETUP.md](docs/AGENT_SETUP.md), [docs/AGENT_ARCH.md](docs/AGENT_ARCH.md).
- Lean 4 formal verification spike plan: [docs/LEAN_VERIFICATION_SPIKE.md](docs/LEAN_VERIFICATION_SPIKE.md).
- Scope & task tracking: [ROADMAP.md](ROADMAP.md) and [TODO.md](TODO.md).

## Commands & tools

| Area | Entry points |
|---|---|
| Setup & health | `rvw doctor`, `rvw init` |
| Simulation & regression | `rvw regress run|compare|gate|cosim|list|history|known`, `rvw sim` |
| Co-simulation | `rvw cosim check|generate|exchange|adjudicate|doctor`, `Cosim/` |
| Microarchitecture & perf | `rvw arch`, `rvw ooo`, `rvw csim`, `rvw sample`, `rvw workloads`, `rvw perf`, `rvw probes` |
| Design DB & debug | `rvw query`, `rvw wave`, `rvw bundle`, `rvw reduce`, `rvw bisect`, `rvw debug`, `rvw lsp` |
| Checks, lint & bounded formal | `rvw checks`, `rvw lint`, `rvw soc`, `rvw sec`, `rvw fault`, `rvw memory`, `rvw formal bmc|from-sim|xprop|x-context|x-sweep` |
| MCP server | `rvw mcp --list`, `rvw agent guide` |

## Testing rules

- Run Python tests with `rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers`.
- Run hygiene & doc checks before finishing doc edits: `rvw/.venv/bin/python -m pytest rvw/tests/test_release_hygiene.py rvw/tests/test_doc_commands.py rvw/tests/test_docs_site.py`.
- Never embed personal filesystem paths in tracked files.
- Keep `rvw/pyproject.toml` and `rvw/uv.lock` synchronized if touching Python dependencies (`uv lock --check --project rvw`).
- Use `scripts/with-lock.sh` around heavy Verilator / sbt / gem5 runs.
