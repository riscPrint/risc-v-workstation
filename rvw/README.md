# rvw

One command for the RISC-V Workstation tools. Each subpackage of `src/rvw/` is a subcommand
(it registers itself from its `cli.py`) and may expose MCP tools (`mcp_tools.py`); see the
repository README for the list and [docs/PLATFORM_CONTRACTS.md](../docs/PLATFORM_CONTRACTS.md)
for the shared formats (C1–C8).

```sh
cd rvw && uv venv && uv pip install -e '.[dev,mcp]'
.venv/bin/rvw --help
.venv/bin/rvw mcp --list          # every MCP tool
.venv/bin/rvw mcp                 # stdio MCP server
```

## Core projects

Install `rvw` in the workstation once. Set `RVW_HOME` to the workstation checkout
and add `$RVW_HOME/rvw/.venv/bin` to `PATH`. Keep your core in a separate Git
repository. Follow [Bring your own core](../docs/BRING_YOUR_OWN_CORE.md) for the
full setup and adapter requirements.

```sh
cd /path/to/my-core
rvw regress list
rvw regress run --tier quick
rvw --project /path/to/my-core/rvw.toml regress list
rvw regress list --project /path/to/my-core/rvw.toml
```

Selection order is `--project PATH`, `RVW_PROJECT`, then the nearest `rvw.toml`
found by walking upward. The global `--project` option can appear anywhere on
the CLI. An invalid selected file gives an error. It must not select another
project or a bundled core. Explicit `--core boom` or `--core path/to/core.toml`
keeps the legacy config interface and bypasses project discovery and
`RVW_PROJECT`. Project selection takes priority over `RVW_CORE`. Do not pass
both `--project` and `--core`.

The root project file reuses the regression `[core]`, `[suites]` and `[tiers]`
tables. `[project]` is optional for `rvw.toml`. If you set `project.schema`, it
must be `rvw.project/1`. `project.root` defaults to `.` and `core.source_repo`
defaults to the project root. All config paths resolve against the directory
that contains the project file.
Unknown top-level tables and unknown fields in project sections are errors.

Optional sections select per-project inputs:

| Section | Fields |
|---|---|
| `[arch]` | `description = "rvw/arch/large.json"`, `sources = "../riscv-tests/benchmarks"`, `benchmarks = "rvw/out/arch/bench"` |
| `[cosim]` | `platform = "rvw/cosim.json"` |
| `[debug]` | `config = "rvw/debug.toml"` |
| `[checks]` | `settings = "rvw/checks.toml"`, `waivers = "rvw/waivers.txt"` |
| `[query]` | `build = ["./rvw/build-db.sh"]`, `db = "rvw/out/design.db"` |
| `[formal]` | `verilog = ["rvw/out/rtl/MyTop.v"]`, `top = "MyTop"`, optional `checks`, `clock` and `reset` |

`rvw query build [--config NAME] [--out PATH]` executes `query.build` in the
project root and appends `CONFIG OUT` as two arguments. The adapter must create
the database at `OUT`. Other query commands use `query.db` when no `--db` is
given. Formal uses the project inputs unless the CLI supplies them explicitly.
Generate the RTL and reports first. Checks references are recorded as project
inputs. The project-owned launcher must apply the settings and waivers; file
references alone do not install checks.

Regression, co-simulation, query build/navigation, formal and debug MCP tools accept
`project` as a path. `query_diff` takes two explicit database paths.
Set `RVW_PROJECT` in the server environment to use one project by default:

```sh
RVW_PROJECT=/path/to/my-core/rvw.toml rvw mcp
rvw mcp --project /path/to/my-core/rvw.toml
```

The adapter must implement C1 and C2 as needed. Set `input_complete = true` only
after all result-changing inputs are covered. Gate accept requires committed
base and candidate core sources and complete C8 evidence. An incomplete identity
or dirty candidate cannot earn accept. Project mode keeps these rules.

Tests: `source ../../spinal-boom/env.sh && ../Cosim/build.sh && .venv/bin/python -m pytest tests -q`
(the formal and cosim tests need oss-cad-suite, Spike and the RISC-V GCC; they skip without them).

## Decisions

- The `rvw` CLI turns SIGTERM and SIGHUP into cancellation exceptions. Commands
  can stop their child process groups and release locks before exit. Commands
  that use the CLI handler return `128 + signal number`: 143 for SIGTERM and
  129 for SIGHUP.

## Architecture exploration

`rvw arch build`, `run`, `calibrate`, and `compare` use native gem5 v25.1.0.1.
Add `[arch]` paths to the project. See [Arch/README.md](../Arch/README.md) for
setup, the description fields, exact commands, and report limits. The MCP tools
are `arch_build`, `arch_run`, `arch_calibrate`, and `arch_compare`.
