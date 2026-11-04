# risc-v-workstation

IDE tools to make RISC-V development easier. SpinalHDL gets first-class treatment, however should be easy to extend to other HDLs. Many features do not rely on SpinalHDL.

The BOOM core these tools use is in the private repository
[riscPrint/spinal-boom](https://github.com/riscPrint/spinal-boom). Access is optional.
For a public core example, use [examples/vexriscv](examples/vexriscv/).

Start with [AGENTS.md](AGENTS.md) (layout, commands, rules), [ROADMAP.md](ROADMAP.md) (plan, and where each area stands against commercial EDA tools) and [TODO.md](TODO.md) (the open GitHub issues, by area).

## Quickstart

```sh
git clone https://github.com/riscPrint/risc-v-workstation.git
cd risc-v-workstation
scripts/install.sh --with-sim --with-riscv-gcc --with-cosim
source env.sh
scripts/install.sh --check --with-sim --with-riscv-gcc --with-cosim
```

Keep your core in a separate repository. Follow the
[agent setup playbook](docs/AGENT_SETUP.md) or the
[bring-your-own-core guide](docs/BRING_YOUR_OWN_CORE.md).
Use the [architecture playbook](docs/AGENT_ARCH.md) for gem5.
The installer asks before system package commands. Homebrew is required on macOS.
The full quickstart combination is not yet qualified on clean macOS and Linux
hosts ([#17](https://github.com/riscPrint/risc-v-workstation/issues/17),
[#40](https://github.com/riscPrint/risc-v-workstation/issues/40)). See [tool versions and install limits](docs/TOOL_VERSIONS.md).

Track work in the [v0.2 (near term) milestone](https://github.com/riscPrint/risc-v-workstation/milestone/1)
and the [Later phases milestone](https://github.com/riscPrint/risc-v-workstation/milestone/2).
The setup tasks are [integration model #34](https://github.com/riscPrint/risc-v-workstation/issues/34),
[`rvw doctor` #35](https://github.com/riscPrint/risc-v-workstation/issues/35),
[`rvw init` #36](https://github.com/riscPrint/risc-v-workstation/issues/36) and
[CI #16](https://github.com/riscPrint/risc-v-workstation/issues/16).

## Tools

| Tool | What it does |
|---|---|
| [SpinalWaves](SpinalWaves/) | SpinalHDL types and source locations in waveforms, viewed in Surfer. Port of Tywaves. |
| [SpinalTrace](SpinalTrace/) | Traces a signal value back to the SpinalHDL statements that caused it. CLI and GUI. Port of ChiselTrace. |
| [SpinalBlocks](SpinalBlocks/) | Block diagrams of SpinalHDL designs: extractor, embeddable viewer engine, web host. |
| [SpinalDB](SpinalDB/) | One extraction run (the design is elaborated twice, for source locations) that writes a design database (SQLite): hierarchy, signals, registers, memories, assignments with Scala lines, the dependency graph, and the SpinalTrace/SpinalBlocks/SpinalWaves outputs. |
| [RiscvSim](RiscvSim/) | Runs programs on a Spinal RISC-V core in Verilator through one command (the run contract): result JSON, RVFI trace, waves, Konata, coverage, replay. BOOM is the first adapter. The [VexRiscv example](examples/vexriscv/) adds an external RV32IM core. |
| [SpinalChecks](SpinalChecks/) | Assertions generated from the elaborated design (stream handshakes, index ranges, legal states, progress), and the formal flows behind `rvw formal`. |
| [SpinalKonata](SpinalKonata/) | Konata pipeline traces for any Spinal design that tags its pipeline events. |
| [Arch](Arch/) | Native gem5 O3 models, local bare-metal benchmarks, and C1 RTL calibration reports. |
| [Cosim](Cosim/) | The Spike library shim behind `rvw cosim`. |
| [rvw](rvw/) | The `rvw` command: one CLI (and one MCP server) for every tool below. |

`rvw` command groups (JSON support depends on the command). See the complete
[CLI and MCP reference](docs/COMMAND_REFERENCE.md) for every command and tool:

| Command | What it does |
|---|---|
| [`rvw regress`](rvw/src/rvw/regress/) | Test suites through a core's adapter, baseline comparison, accept/reject/inconclusive verdicts (`gate`), known failures, history. Accept requires committed core revisions. |
| [`rvw cosim`](Cosim/README.md) | Compares a core's RVFI trace with Spike (lockstep) or Sail, stops at the first architectural difference. |
| [`rvw bundle`](rvw/src/rvw/bundle/), `reduce`, `bisect` | Failure report for a failed run (last instructions, pipeline state, wave window, SpinalTrace causes, replay); shrinking a failure; finding the commit that caused it. |
| [`rvw wave`](rvw/src/rvw/wave/) | Command-line VCD/FST queries and window cuts. |
| [`rvw query`](rvw/src/rvw/query/) | Design questions over a SpinalDB database: drivers, loads, fan-in/out, paths, search, hierarchy, diff between two builds. |
| [`rvw cov`](rvw/src/rvw/cov/) | Code coverage merge and ranking, RVFI functional coverage, change-based test selection, proof exclusions, mutation testing. |
| [`rvw formal`](SpinalChecks/) | BMC from reset, BMC from a simulation state, X-propagation. |
| [`rvw workloads`](rvw/src/rvw/workloads/) | Build pinned open kernels and check outputs with Spike or QEMU; local licensed workload hook. |
| [`rvw arch`](Arch/) | Build and run native gem5 models. Compare the same ELFs with C1 RTL ROI counters. |
| [`rvw perf`](rvw/src/rvw/perf/) | Text performance reports from Konata logs. |
| [`rvw doctor`](rvw/src/rvw/doctor/) | Check native tools, project inputs and adapter readiness. |
| [`rvw init`](rvw/src/rvw/init/) | Create safe setup stubs for a Spinal/sbt core. CLI-only. |
| [`rvw farm`](rvw/src/rvw/farm/) | Run native SSH shards and write a static results dashboard. |
| [`rvw lint`](rvw/src/rvw/lint/) | Native lint diagnostics and structural CDC/RDC inventory. |
| [`rvw soc`](rvw/src/rvw/soc/) | Export project maps and check bounded database bindings. CLI-only. |
| [`rvw mcp`](rvw/src/rvw/mcp/) | One stdio MCP server exposing all of the above to agents, with background jobs. |

The shared file formats are in [docs/PLATFORM_CONTRACTS.md](docs/PLATFORM_CONTRACTS.md).

## Use your own core

Run `scripts/install.sh` in this checkout. Then run `source env.sh`.
Use `--with-sim`, `--with-riscv-gcc`, `--with-cosim`, `--with-formal`, `--with-gem5` or `--all`
for native tools. Use `--dry-run` to inspect actions. Use `--check` to inspect
installed tools. System package commands need approval unless you pass `--yes`.
The [installation guide](docs/BRING_YOUR_OWN_CORE.md#install-the-workstation)
also gives the manual `uv` steps.

Keep your core in a separate repository with a root `rvw.toml` and its own
adapters. Neither repository needs to contain the other.

From the core repository, use `rvw regress list` and `rvw regress run --tier quick`.
Use `rvw --project /path/to/core/rvw.toml ...` or `RVW_PROJECT` to select it from
another directory. Explicit `--core boom` keeps the bundled example.

See [Bring your own core](docs/BRING_YOUR_OWN_CORE.md) for installation, project
selection, C1/C2 adapters, C8 input declarations, gates, Scala libraries and MCP.
The external BOOM project passed its five-test gate and add-trace comparison.
The separate VexRiscv project passed 41 aligned RV32UI tests, a four-test committed
gate with equal RTL hashes, a 17-instruction Spike smoke comparison and database
queries. See the [VexRiscv limits](examples/vexriscv/README.md#design-and-limits).

See the [public release procedure](docs/RELEASING.md) for release gates.
Source setup support does not establish clean-host qualification.

## Status (P1+P2 integration branch, 2026-11-04)

Supported scope under contract C8:

- `rvw regress run` and `rvw regress gate` on committed revisions, without known-failure waivers.
- `rvw cosim` (Spike and Sail).
- `rvw formal bmc`, `from-sim` and `xprop` on single-clock designs with synchronous state.
- `rvw cov prove` (proof exclusions), `rvw cov merge/report/select`, `rvw cov functional`.
- `rvw query diff` and the navigation queries (drivers, loads, path, where).
- `rvw bundle`, `reduce`, `bisect`, `wave`, `perf`, and `rvw mcp`.
- Read-only `rvw doctor` checks and the minimal Spinal/sbt `rvw init` scaffold.
  Doctor needs an explicit smoke run for build/run readiness. Init writes safe stubs.
  Neither command qualifies a core or earns gate acceptance.

Experimental features need manual result checks before use:

- Native SSH farm execution, static dashboards, remote caches and job budgets.
  Farm completion is collection status. It is not a gate verdict. See
  [farm limits](rvw/src/rvw/farm/README.md), [cache limits](rvw/src/rvw/regress/README.md)
  and [budget limits](rvw/src/rvw/common/README.md#native-job-budgets).
- `rvw lint` structural CDC/RDC inventory and `rvw soc check` bindings.
  Neither establishes signoff or full bridge correctness. SoC exports use explicit project data.
- Extended formal flows (multi-clock, equivalence, protocol checks and counterexample replay),
  architecture fitting/sweeps and Linux reference boot. Their bounded scope and
  native qualification limits stay in [SpinalChecks](SpinalChecks/README.md) and [Arch](Arch/README.md).
- Native tool bundles. Pins and checksums are checked, but native builds and
  relocation on all three hosts remain unqualified. See [bundle limits](scripts/README.md).
- Saved VS Code result views and manual source/wave/trace navigation.
  They display producer data and do not issue verification verdicts.

- Known-failure waivers (`rvw regress known`) and failure-signature matching.
  The #2 review fixes more signature collisions. Wildcard scope and coarse failure identities
  still need review. See the [close rules](rvw/src/rvw/regress/README.md#review-status-and-close-rules).
- Gates on stored result folders (`--base`/`--cand` folders). The #4 identity checklist remains open.
- Performance metrics (`perf_metrics`). Reports state sample counts and no estimated confidence.
  Native repeated-seed experiments, semantic ROI checks and statistical rules remain open (#4).
- Mutation testing (`rvw cov mutate`) ([#3](https://github.com/riscPrint/risc-v-workstation/issues/3)).
- SpinalChecks generated checks (run reports, check selection). On BOOM, 24 stream checks fire;
  source-backed dispositions are recorded, but runtime triage remains open (see [#5](https://github.com/riscPrint/risc-v-workstation/issues/5)).

## VS Code extension

[vscode/](vscode/) is one extension for all the tools. Each tool adds a feature under `vscode/features/<tool>/` (SpinalBlocks is the first). See [vscode/README.md](vscode/README.md) to build it or add a feature.

Each tool has its own README with build and usage instructions. SpinalBlocks depends on SpinalWaves through a relative path, so keep them side by side. Read diagrams from SpinalDB with `rvw query export blocks blocks.json.gz`.
The separate `SpinalDB/boom` example needs a BOOM checkout.

## Decisions

- Gate accept requires committed core revisions. Missing or ambiguous evidence is inconclusive.
- Races, mid-run file or tool changes, cache tampering and hostile inputs are outside C8.
- Shared formats stay in `docs/PLATFORM_CONTRACTS.md`. Core details stay in adapters.
- Heavy jobs use the machine-wide lock. Timeout and cancellation stop the process group.
- [Cosim/README.md](Cosim/README.md) is the canonical co-simulation guide.
- Current gaps stay in [TODO.md](TODO.md). Review results belong in issues and pull requests.

## History

SpinalWaves and SpinalTrace started as separate ports. This checkout does not
retain their full import histories or past review reports. Upstream revisions
and local patches are listed in
[SpinalWaves Rust porting notes](SpinalWaves/docs/RUST_PORTING.md) and
[SpinalTrace porting notes](SpinalTrace/PORTING_NOTES.md).
