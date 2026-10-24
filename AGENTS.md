# risc-v-workstation

Using the workstation on your own core? Read [docs/AGENT_SETUP.md](docs/AGENT_SETUP.md).
Use [docs/AGENT_ARCH.md](docs/AGENT_ARCH.md) for architecture models.
The rules below are for agents working on the workstation.

Open-source EDA tools for RISC-V cores written in SpinalHDL: simulation, regression, co-simulation,
debug, design queries, coverage, formal checks and performance reports, with one command line
(`rvw`) and one MCP server for agents. The first user is the BOOM port (`riscPrint/spinal-boom`).
The goal is to replace the commercial EDA stack for architecture, RTL design and verification by
reusing open-source tools and extending them where they fall short.

`CLAUDE.md` is a symlink to this file. Edit `AGENTS.md`.

- `ROADMAP.md`: the plan for every area, and where each area stands against commercial tools.
- `TODO.md`: the tasks, under the same areas.
- `docs/PLATFORM_CONTRACTS.md`: the file formats and commands the tools share (C1–C8).
- [docs/BRING_YOUR_OWN_CORE.md](docs/BRING_YOUR_OWN_CORE.md): install once, then use a
  separate core repository with `rvw.toml`, core adapters and project selection.

Keep `ROADMAP.md` and `TODO.md` up to date when work starts or finishes.

## Layout

| Path | What |
|------|------|
| `rvw/` | The `rvw` command and `rvw mcp` server. One subpackage per tool under `rvw/src/rvw/<tool>/`; each registers its subcommand (`cli.py`) and its MCP tools (`mcp_tools.py`). Shared code in `rvw/src/rvw/common/` (process groups, the lock, the RISC-V decoder) and `rvw/src/rvw/results/` (C1/C3/C4 formats). |
| `RiscvSim/` | Runs ELFs on a Spinal RISC-V core in Verilator through the run contract (C1): result JSON, RVFI trace (C2), waves, Konata, coverage, replay. Generic library in `RiscvSim/src/`; BOOM's adapter in `RiscvSim/boom/` (`run.sh`). |
| `examples/vexriscv/` | External RV32IM VexRiscv adapter, regression config, Spike platform and SpinalDB entry. See its `README.md`. |
| `Arch/` | Native gem5 O3 model and bare-metal benchmark runtime. `rvw arch` builds, runs, and compares it with C1 RTL results. Core parameters live in project data. |
| `Cosim/` | The C++ shim that lets `rvw cosim` drive Spike as a library. |
| `SpinalDB/` | Elaborates a Spinal design and writes a design database (SQLite, `rvw.designdb/20`). Queried with `rvw query`. |
| `SpinalChecks/` | Assertions generated from the elaborated design, and the formal flows behind `rvw formal`. BOOM settings and waivers in `SpinalChecks/boom/`. |
| `SpinalKonata/` | Konata pipeline traces for any Spinal design that tags its pipeline events. |
| `SpinalWaves/` | Spinal types and source locations in Surfer waveforms (port of Tywaves). |
| `SpinalTrace/` | Traces a signal value back to the Spinal statements that caused it (port of ChiselTrace). |
| `SpinalBlocks/` | Block diagrams of Spinal designs: extractor, viewer engine, web host. |
| `vscode/` | The RISC-V Workstation VS Code extension; each tool adds a feature under `vscode/features/<tool>/`. |
| `scripts/with-lock.sh` | Machine-wide lock for heavy jobs: `scripts/with-lock.sh boom <cmd>`. |
| `docs/` | Shared contracts and setup guides. |

Every tool has a `README.md` with build and usage instructions, a "Decisions" section and its known
limits.

## Environment

- Install with `scripts/install.sh` and the native-tool flags needed for the task.
  Source this checkout's `env.sh`. Use `scripts/install.sh --check` with the same flags
  to check tools. See [the installation guide](docs/BRING_YOUR_OWN_CORE.md#install-the-workstation).
- Set `JAVA_HOME` to a patched JDK 21. Put its `bin` directory on `PATH`.
  Put Verilator, Yosys, SymbiYosys and the solvers on `PATH` when needed.
- RISC-V GCC: add its `bin` directory to `PATH` (`riscv64-unknown-elf-*`).
- Spike needs matching headers and libraries. Set `SPIKE_PREFIX` for its install prefix.
  Set `RVW_SAIL` to the Sail executable when Sail checks are needed.
- Python ≥ 3.11 with `uv`: `cd rvw && uv venv && uv pip install -e '.[dev,mcp]'`.
- Installed tool use: set `RVW_HOME` to this checkout and add `rvw/.venv/bin` to
  `PATH`. Keep the core in its own repository. Do not nest repositories or add
  submodules to connect them. See the bring-your-own-core guide above.
- Spike shim: `Cosim/build.sh`.
- BOOM sources: `SPINAL_BOOM` (default `../spinal-boom-eda`, a private clone). Never build in the
  `spinal-boom` checkout that someone is editing.

## Common commands

In a core project, `rvw` finds `rvw.toml` by walking upward. Use `--project PATH`
anywhere on the CLI or set `RVW_PROJECT` for an explicit selection. Paths in the
project file are relative to its directory. Invalid selected projects must give
an error. They must not fall back to a bundled core. The `--core boom` commands
below select the legacy example explicitly.

| Job | Command |
|-----|---------|
| Run one program on BOOM | `RiscvSim/boom/run.sh run --elf ELF --out DIR [--rvfi-trace] [--wave] [--json]` |
| Test a change and judge acceptance | Edit, then `rvw regress gate --core boom --base-rev <base>`. A passing dirty tree prints TESTS PASS and NOT ACCEPTED. Commit and rerun to earn accept. |
| Run a suite | `rvw regress run --core boom --tier quick` |
| Compare with Spike, first difference | `rvw cosim check --trace DIR/rvfi.jsonl --elf ELF --core boom --json` |
| Failure report from a failed run | `rvw bundle DIR` |
| Smaller reproduction / guilty commit | `rvw reduce DIR`, `rvw bisect DIR --good REV` |
| Build a project's design database | `rvw query build --config NAME` (calls the project's `query.build` command with `CONFIG OUT`) |
| Design question | `rvw query drivers|loads|path|where|diff ...` (needs a SpinalDB database) |
| Coverage | `rvw cov merge|report|rank|select|functional|prove|mutate` |
| Formal | `rvw formal bmc|from-sim|xprop` |
| Performance from a Konata log | `rvw perf LOG` (`rvw perf compare A B`) |
| All of it for an agent | `rvw mcp` (stdio MCP server; `rvw mcp --list`) |

Exit codes and JSON formats are in `docs/PLATFORM_CONTRACTS.md`. A gate verdict of `inconclusive`
(exit 3) means the evidence is not enough to accept or reject; never treat it as accept.

## Tests

- Python: source `env.sh`, then build the shim with `Cosim/build.sh` if needed.
  Run targeted tests with `nice -n 10 rvw/.venv/bin/python -m pytest rvw/tests/TEST_FILE.py -q`.
  Run the full suite with `scripts/with-lock.sh suite nice -n 10 rvw/.venv/bin/python -m pytest rvw/tests -q`.
  Missing optional native tools can cause skips. Report the pass and skip counts.
- Scala: hold the `sbt` lock with `scripts/with-lock.sh sbt nice -n 10 sbt ...`.
  Use `sbt test` in `SpinalWaves/spinalwaves`, `SpinalTrace/spinaltrace`, `SpinalDB/spinaldb`,
  `SpinalChecks`, `SpinalKonata`; `sbt spinalblocks/test` in `SpinalBlocks/spinalblocks`;
  `sbt riscvsim/test` in `RiscvSim`.
- Rust: `cargo test -p spinaltrace-rs` in `SpinalTrace`.
- VS Code extension: `npm run typecheck && npm run build && npm test` in `vscode/`.

## Working rules

- Generic first. Code under `rvw/src/`, `RiscvSim/src/` and the Spinal libraries must not name a
  core's signals, configs or test lists. New integrations keep these in the core's
  repository, beside `rvw.toml`. The existing bundled BOOM examples stay in
  `RiscvSim/boom/`, `rvw/configs/boom.toml`, `rvw/src/rvw/cosim/configs/boom.json`,
  `SpinalChecks/boom/` and `SpinalDB/boom/` for compatibility.
- Change a shared format only by editing `docs/PLATFORM_CONTRACTS.md` in the same commit.
- A tool must never report a pass, a match or an accept that it has not earned. When evidence is
  missing or ambiguous, report `inconclusive`, `no_checks` or an error. Every fix gets a test that
  fails before the fix.
- Heavy jobs (BOOM Verilator builds, sbt compiles against BOOM, long BOOM simulations, long formal
  runs) go through `scripts/with-lock.sh boom ...`. Use the `vex` lock for
  VexRiscv jobs. Hold the `sbt` lock for shared sbt outputs.
  Hold the `suite` lock for the full Python suite. Use `nice` for heavy jobs. Subprocesses with a timeout or a cancel use
  `rvw.common.proc.run_group`, so the whole process tree stops.
- Threat model: see "Threat model" in C8 (`docs/PLATFORM_CONTRACTS.md`). Verdicts that let work go
  ahead (`gate` accept) come only from committed revisions; races and hostile inputs are out of scope.
- Do not change the core from this repository. Report core bugs the tools find in `TODO.md`.
- New tool: add a row to the Components table in `ROADMAP.md`, a `README.md`, a row in the Layout
  table above, and its tasks in `TODO.md`.
- Reuse open-source tools first (Verilator, Spike, Sail, Yosys, SymbiYosys, mcy, Surfer, ...); write
  only what they lack, and record in `ROADMAP.md` what each area builds on.

## Architecture models

Install native gem5 with `scripts/install.sh --with-gem5`. Use `RVW_GEM5` to
select an existing RISC-V gem5 v25.1.0.1 binary. Add `[arch]` paths to the
project file. See [Arch/README.md](Arch/README.md),
[docs/AGENT_ARCH.md](docs/AGENT_ARCH.md) and `examples/boom/rvw.toml`.

```sh
rvw arch build --bench median,vvadd,memcpy --json
rvw arch calibrate --bench median,vvadd,memcpy --out rvw/out/calibration-1
rvw arch compare rvw/out/calibration-1/rtl.json rvw/out/calibration-1/gem5.json --json
```

The IPC ratio is model IPC divided by RTL IPC. It is a measured model gap.
It is not a correctness or gate verdict. gem5 shows trends; RTL is the truth.
Use the project's lock for RTL. gem5 runs under the `gem5` lock, one process
at a time. Core presets and calibration targets belong in project data.
