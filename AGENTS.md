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
- GitHub issues: the tasks. `TODO.md` lists them under the roadmap areas.
- `docs/PLATFORM_CONTRACTS.md`: the file formats and commands the tools share (C1–C9).
- [docs/BRING_YOUR_OWN_CORE.md](docs/BRING_YOUR_OWN_CORE.md): install once, then use a
  separate core repository with `rvw.toml`, core adapters and project selection.

Keep `ROADMAP.md` up to date when work starts or finishes. Track tasks as GitHub issues, and
keep the issue list in `TODO.md` in step with them.

## Layout

| Path | What |
|------|------|
| `rvw/src/rvw/init/` | Minimal Spinal/sbt core project scaffold. See its `README.md`. |
| `rvw/src/rvw/doctor/` | Setup diagnostics, explicit installer forwarding and `rvw_doctor` MCP. See its `README.md`. |
| `rvw/src/rvw/farm/` | Native SSH shards and a static C3/C4 history dashboard. |
| `rvw/src/rvw/soc/` | Project-owned SoC map validation, software exports and bounded design checks. See its `README.md`. |
| `rvw/` | The `rvw` command and `rvw mcp` server. One subpackage per tool under `rvw/src/rvw/<tool>/`; each registers its subcommand (`cli.py`) and its MCP tools (`mcp_tools.py`). Shared code in `rvw/src/rvw/common/` (process groups, the lock, the RISC-V decoder) and `rvw/src/rvw/results/` (C1/C3/C4 formats). |
| `RiscvSim/` | Runs ELFs on a Spinal RISC-V core in Verilator through the run contract (C1): result JSON, RVFI trace (C2), waves, Konata, coverage, replay. Generic library in `RiscvSim/src/`; BOOM's adapter in `RiscvSim/boom/` (`run.sh`). |
| `examples/vexriscv/` | External RV32IM VexRiscv adapter, regression config, Spike platform and SpinalDB entry. See its `README.md`. |
| `rvw/src/rvw/workloads/` | Pinned open workload builds and Spike/QEMU output checks; local Linux and licensed SPEC manifests. |
| `ComponentSims/` | Native trace-driven component models. Bimodal/gshare direction studies and a perfect-direction bound. See its `README.md`. |
| `Arch/` | Native gem5 O3 model and bare-metal benchmark runtime. `rvw arch` builds, runs, and compares it with C1 RTL results. Core parameters live in project data. |
| `Uvm/` | Pinned Accellera UVM conformance suite and bounded TileLink-UL/load observation example. See its `README.md`. |
| `Cosim/` | The C++ shim that lets `rvw cosim` drive Spike as a library. |
| `rvw/src/rvw/lint/` | Native lint adapters and structural CDC/RDC inventory. See its `README.md`. |
| `SpinalDB/` | Elaborates a Spinal design and writes a design database (SQLite, `rvw.designdb/20`). Queried with `rvw query`. |
| `SpinalChecks/` | Assertions generated from the elaborated design, and the formal flows behind `rvw formal`. BOOM settings and waivers in `SpinalChecks/boom/`. |
| `SpinalChecks/c2rtl/` | Native C truth-table reference against small combinational RTL units. See its `README.md`. |
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

Run the public fast Python set from the repository root:

```sh
cd rvw
uv venv
uv pip install -e '.[dev,mcp]'
cd ..
rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q -ra --durations=10
```

The `fast` marker uses the explicit module list in `rvw/tests/conftest.py`.
It covers result formats, RISC-V decoding, project selection, performance reports,
database queries from committed SQL fixtures, commit policy and release hygiene.
It needs Python 3.11 or later, Git and Bash. It needs no BOOM checkout, simulator,
solver, Spike shim or RISC-V compiler. Expected optional skips: none.
The target is less than five minutes for the Python test command, after dependency
installation. CI logs show timing, pass counts and skip counts on Linux and macOS.
The JUnit artifacts retain the Python results for seven days.

New modules default to `slow`. Review their dependencies and time before adding
one to `FAST_MODULES`. The marker selection deselects tests; deselection is not a skip.
Run the slow set with `-m slow`. Run both sets with no `-m` option:

```sh
scripts/with-lock.sh suite nice -n 10 rvw/.venv/bin/python -m pytest rvw/tests -q -ra
```

The root [nightly workflow](.github/workflows/nightly.yml) runs both Python sets
on Ubuntu at 03:23 UTC each day. It also supports `workflow_dispatch`.
It needs no private core checkout. Missing native tools cause expected skips:
Spike shim and RISC-V GCC for native co-simulation, Sail, formal tools
(Yosys, SymbiYosys and solvers), Verilator, Icarus and GTKWave conversion tools.
Tests that need a second Z3 install or an OSS CAD Suite launcher can also skip.
The nightly job installs Clang, Verilator, GTKWave tools, Yosys, Icarus and
JDK 21/sbt for launcher and database extraction tests. It warms the Scala classpath before pytest. It does
not install the other optional tools. Use `-ra` to read the
actual skip reasons. A skipped test does not establish native-tool support.
For local native tests, source `env.sh` and build `Cosim/build.sh` as needed.

The root [push/PR workflow](.github/workflows/ci.yml) runs the fast Python set,
including `test_release_hygiene.py`, on `ubuntu-latest` and `macos-latest`.
It also runs these checks on both systems:

- Rust: `cd SpinalTrace && cargo test --locked -p spinaltrace-rs`.
- JavaScript: `cd vscode && npm ci && npm run typecheck && npm run build && npm test`.
- Scala: in `SpinalWaves/spinalwaves`, run `sbt -batch -J-XX:ActiveProcessorCount=2
  'testOnly spinalwaves.NamingSpec spinalwaves.EmitterSpec'` with JDK 21 and sbt.

These checks need Rust, Node.js 22 and JDK 21/sbt, but no core or native EDA tools.
The nightly Scala job runs the generic Konata tests with native Verilator. It
compiles the SpinalDB, SpinalTrace and SpinalChecks test sources. Compilation is
not a test pass. `RiscvSim` and `SpinalBlocks` sbt builds remain excluded because
they load BOOM's `ProjectRef` ([#6](https://github.com/riscPrint/risc-v-workstation/issues/6)).
The full SpinalWaves and SpinalTrace native suites are not part of this minimum
signal. BOOM gates remain separate and need a private core and native tools.
Clean-install CI belongs to [#17](https://github.com/riscPrint/risc-v-workstation/issues/17)
and [#40](https://github.com/riscPrint/risc-v-workstation/issues/40).
The fast/slow selection is tracked in [#41](https://github.com/riscPrint/risc-v-workstation/issues/41);
the root CI is tracked in [#16](https://github.com/riscPrint/risc-v-workstation/issues/16).

CI checks PR titles and each new non-merge commit with
`scripts/check-conventional.py`. It checks the syntax, summary length and issue
footer rules below. Reviewers check imperative wording and the required docs for
breaking changes. Generated merge commits are excluded. A new branch push checks
its tip; a PR checks all commits after its merge base. PR title edits rerun CI.

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
- Do not change the core from this repository. Report core bugs the tools find as
  issues in `riscPrint/spinal-boom`.
- New tool: add a row to the Components table in `ROADMAP.md`, a `README.md`, a row in the Layout
  table above, and its tasks as issues listed in `TODO.md`.
- Reuse open-source tools first (Verilator, Spike, Sail, Yosys, SymbiYosys, mcy, Surfer, ...); write
  only what they lack, and record in `ROADMAP.md` what each area builds on.

## Commits and pull requests

Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) for commit messages
and pull request titles: `type(scope): summary`.

- Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`, `revert`.
- Scope: the tool or area, for example `regress`, `cosim`, `arch`, `query`, `formal`, `install`.
- Summary: imperative, lower case, no full stop, at most 72 characters.
- Breaking changes: add `!` after the scope and a `BREAKING CHANGE:` footer. Update the docs in
  the same commit.
- Link issues in a footer: `Refs: #12` or `Closes: #12`.
- A pull request title follows the same format. Its body has `## Summary`, `## Testing` (commands
  and pass/skip counts) and `## Issues` sections.

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

See the complete [CLI and MCP reference](docs/COMMAND_REFERENCE.md) for command paths,
options and built-in tool arguments. The reference is checked against the code.

## Local CI

The CI, Conventional Commits and Nightly definitions target the repo-level runner with
labels `self-hosted`, `macOS`, `ARM64`, `rvw-local`. Use `scripts/ci-local.sh`
for the same fast checks as CI. The script creates a clean temporary workdir
and venv. It uses `scripts/with-lock.sh suite|sbt` and `nice -n 10`. Never point
CI at another contributor's checkout. Nightly runs at 03:23 UTC.

The per-user launchd agent is in `~/opt/actions-runner`. Run `./svc.sh status`,
`./svc.sh stop` or `./svc.sh start` there. It starts after login. Keep one
runner only. Keep Nightly disabled until its local definition reaches the default
branch. Keep Linux workflows and Native tool bundles disabled. See
[Local CI](CONTRIBUTING.md#local-ci) for prerequisites and Linux runner limits.
