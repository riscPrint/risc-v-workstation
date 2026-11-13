# rvw

One command for the RISC-V Workstation tools. Each subpackage of `src/rvw/` is a subcommand
(it registers itself from its `cli.py`) and may expose MCP tools (`mcp_tools.py`); see the
repository README for the list and [docs/PLATFORM_CONTRACTS.md](../docs/PLATFORM_CONTRACTS.md)
for the shared formats (C1–C8).

```sh
cd rvw && uv sync --locked --extra dev --extra mcp
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

## Tests and release checks

From the workstation root, run `scripts/install.sh` to create `env.sh`.
Install the development dependencies, then run tests from the workstation root:

```sh
source env.sh
uv sync --locked --extra dev --extra mcp --project rvw
scripts/with-lock.sh suite nice -n 10 rvw/.venv/bin/python -m pytest rvw/tests -q
```

Formal and co-simulation tests need optional native tools. Install them with
`--with-formal`, `--with-cosim` and `--with-riscv-gcc` as needed. Build the
Spike shim with `Cosim/build.sh` after setup. Missing optional tools can cause
skips. Report pass and skip counts. BOOM integration checks also need access to
the private BOOM checkout and its built test ELFs. Set `SPINAL_BOOM` for that
checkout. BOOM is optional for Python unit tests. For a public core integration,
use [examples/vexriscv](../examples/vexriscv/).

The full Python suite includes `tests/test_release_hygiene.py`. To run only the
release scan from the workstation root:

```sh
rvw/.venv/bin/python -m pytest rvw/tests/test_release_hygiene.py -q
rvw/.venv/bin/python rvw/tests/test_release_hygiene.py
```

The second command prints a JSON report for owner review. It lists commit
authors, committers and annotated-tag taggers separately. The test scans commit
messages and annotated tags for paths and credential patterns. Names and email
addresses alone do not fail the test. Before publication, the owner must decide
whether to publish their identity. Keep required upstream attribution.

The tracked-file scan reads working-tree bytes and symlink target strings. It
checks Unix and Windows home paths, common credential assignments, token forms,
URL credentials and private-key headers. It checks ASCII strings in binary and
non-UTF-8 files and decodes UTF-8, UTF-16 and UTF-32 text. Diagnostics omit matched
values. Review any finding before publication.

This is a bounded pattern scan. It does not unpack archives, decode arbitrary
encodings, prove that a value is a live secret, or prove that no secrets exist.
It omits untracked files and deleted working-tree files. Metadata covers commits
reachable from local refs and local annotated tags. It does not fetch refs or
inspect unreachable objects, remote caches, hosted pull-request refs or tag
names. A shallow clone gives a partial metadata report. Old remote-object cleanup
remains in [#39](https://github.com/riscPrint/risc-v-workstation/issues/39). A clean
scan does not close that task.

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

## Limit ownership

Release checklist: [#78](https://github.com/riscPrint/risc-v-workstation/issues/78). Publication scan: [#79](https://github.com/riscPrint/risc-v-workstation/issues/79). Remote MCP: [#54](https://github.com/riscPrint/risc-v-workstation/issues/54).

Retained limit: The documented release scan and local MCP boundaries remain unchanged. A scan does not prove absence of all secrets or qualify remote authentication.

Setup: use [`rvw doctor`](src/rvw/doctor/README.md) for tool, project and adapter checks. Installation requires `--install FEATURES`.

New Spinal/sbt core: use [`rvw init`](src/rvw/init/README.md) to create a valid project and safe adapter stubs.

See the complete [CLI and MCP reference](../docs/COMMAND_REFERENCE.md) for command paths,
options and built-in tool arguments. The reference is checked against the code.

## Sampled RTL IPC

`rvw sample STUDY.json --out RUN_ROOT --interval 10000 --max-k 8 --warmup 1000`
joins Spike BBVs, checkpoints, project bootstrap adapters and checked RTL intervals.
See [the sampled flow](src/rvw/sample/README.md). Native sampling error is unmeasured.

## Start-up cost

Measured on Python 3.13.5 with MCP SDK 2.3.0, 2026-11-13. Each row uses the median CPU sample from three fresh processes. Load is the 1/5/15-minute load average for that sample. CPU time excludes waiting on this heavily loaded host. Import counts include the standard library.

| Command | Before CPU s | Before imports | Before load | After CPU s | After imports | After load | Factor |
|---|---:|---:|---|---:|---:|---|---:|
| rvw --help | 0.3155 | 759 | 221.0, 246.1, 242.4 | 0.0523 | 227 | 200.7, 229.8, 236.5 | 6.03x |
| rvw query --help | 0.2926 | 759 | 221.0, 248.3, 243.1 | 0.0564 | 235 | 202.2, 231.1, 237.1 | 5.19x |
| rvw probes --help | 0.2859 | 759 | 220.9, 247.9, 242.9 | 0.0612 | 244 | 202.2, 231.1, 237.1 | 4.67x |
| rvw mcp --list | 0.6059 | 815 | 223.6, 246.3, 242.5 | 0.0930 | 384 | 201.1, 230.4, 236.8 | 6.51x |
| rvw mcp --list --profile core | 0.3107 | 815 | 220.9, 247.9, 242.9 | 0.0450 | 174 | 201.1, 230.4, 236.8 | 6.90x |
| MCP core, first tools/list response | 0.6850 | 1177 | 223.7, 245.9, 242.4 | 0.4121 | 635 | 200.7, 229.8, 236.5 | 1.66x |
| MCP all, first tools/list response | 0.9079 | 1177 | 224.7, 245.7, 242.4 | 0.4847 | 840 | 202.2, 231.1, 237.1 | 1.87x |

The MCP rows send real `initialize` and `tools/list` requests over stdio. The server records CPU after it flushes the first tool-list response. SDK imports account for much of the remaining server cost. The baseline uses revision `67423943`. The all-profile count grew from 338 to 343 tools during parallel development. These measurements do not use a frozen source tree across variants.

Keep these two rules:

1. Keep `cli` and `mcp_tools` declarations light. Import heavy implementations inside handlers. Update `cli_declarations.py` when a provider adds a top-level command. A drift test checks this metadata. The core workflow's cross-package declarations also have a drift test.
2. Read large data files on first use. Cache immutable catalogs after that read. Do not read JSON catalogs or schemas at module import time.

Repeat start-up measurements with `rvw/.venv/bin/python scripts/profile-startup.py > "$RUN_ROOT/startup.jsonl"`. Use `python -X importtime -m rvw mcp --list` for import elapsed-time attribution. Use `rvw/.venv/bin/python scripts/profile-startup.py --cpu-profile "$RUN_ROOT/startup.prof" mcp --list` for CPU attribution. Profile tests and fixtures with `rvw/.venv/bin/python scripts/profile-fast.py "$RUN_ROOT/fast.json"`. Add `--collect-only` to measure collection. Profile call overhead with `rvw/.venv/bin/python scripts/profile-mcp-calls.py`. Its `--control` flag restores the previous empty-argument and signature work. Keep reports outside the repository.
To estimate IPC of a long workload, first compare short full RTL runs with
sampled runs. Then measure a fixed interval at several warm-up lengths.
Attach the resulting validation report to the long run. See the
[integration recipe and evidence limits](../docs/INTEGRATION_GUIDE.md#estimate-ipc-of-a-long-workload).
The current native sampling error and cached warm-up bias remain unmeasured.
