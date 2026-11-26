# Platform Contracts (Generic Tool Interfaces)

Every tool in `risc-v-workstation` separates generic platform logic (`rvw/`) from project-owned adapters and configurations (`examples/*/`).

## Core Contracts

| ID | Contract | Document |
|---|---|---|
| C1 | Adapter build & simulation run (`result.json`, exit codes) | [docs/contracts/c1-run.md](contracts/c1-run.md) |
| C2 | RVFI execution & architectural trace (`rvfi.jsonl`) | [docs/contracts/c2-rvfi-trace.md](contracts/c2-rvfi-trace.md) |
| C3 | Regression run-set manifests & layout | [docs/contracts/c3-results.md](contracts/c3-results.md) |
| C4 | Regression comparison & accept/reject verdict | [docs/contracts/c4-verdict.md](contracts/c4-verdict.md) |
| C5 | Failure debug bundle | [docs/contracts/c5-bundle.md](contracts/c5-bundle.md) |
| C6 | Design database (`SpinalDB` / HDL extraction) | [docs/contracts/c6-design-database.md](contracts/c6-design-database.md) |
| C7 | MCP server tools, profiles, jobs & envelopes | [docs/contracts/c7-mcp.md](contracts/c7-mcp.md) |
| C8 | Input identity & provenance capture | [docs/contracts/c8-capture.md](contracts/c8-capture.md) |
| C9 | Predictive architecture & component model schemas | [docs/contracts/c9-arch-models.md](contracts/c9-arch-models.md) |

## Feature Contracts (Active Domains)

- Setup, project & installer: [project.md](contracts/project.md), [setup.md](contracts/setup.md), [install.md](contracts/install.md), [resources.md](contracts/resources.md), [vexii.md](contracts/vexii.md)
- Simulation, regressions, cosim & memory: [sim.md](contracts/sim.md), [regress.md](contracts/regress.md), [cosim.md](contracts/cosim.md), [reduce-reference.md](contracts/reduce-reference.md), [act4.md](contracts/act4.md), [privilege.md](contracts/privilege.md), [mmu.md](contracts/mmu.md), [memory.md](contracts/memory.md), [custom-isa.md](contracts/custom-isa.md), [csr.md](contracts/csr.md)
- Architecture & performance: [arch.md](contracts/arch.md), [csim.md](contracts/csim.md), [sample.md](contracts/sample.md), [workloads.md](contracts/workloads.md), [perf.md](contracts/perf.md), [bench.md](contracts/bench.md), [probes.md](contracts/probes.md)
- Design DB, debug, lint & SoC: [query.md](contracts/query.md), [debug.md](contracts/debug.md), [wave.md](contracts/wave.md), [lint.md](contracts/lint.md), [formal.md](contracts/formal.md), [soc.md](contracts/soc.md), [soc-ip.md](contracts/soc-ip.md), [sec.md](contracts/sec.md)
