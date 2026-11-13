# Bring your own core

Install the workstation once. Keep your core in its own Git repository. Put the
core's configuration, adapters and test selection in that repository. The two
repositories do not need to be nested. Neither needs a submodule for the other.

This guide covers project selection and the adapter interfaces. The exact result
formats and evidence rules are in [PLATFORM_CONTRACTS.md](PLATFORM_CONTRACTS.md),
especially C1, C2 and C8. A project file does not establish that a core is correct.

For numbered agent steps, use [AGENT_SETUP.md](AGENT_SETUP.md).
For architecture work, use [AGENT_ARCH.md](AGENT_ARCH.md).

## Install the workstation

Run the installer from your workstation checkout on macOS, Debian, Ubuntu,
Fedora or RHEL. The default installs the Python CLI and MCP server in this
checkout. It needs Python 3.11 or later. It installs missing core tools through
Homebrew, apt or dnf. It asks before each system package command.

```sh
scripts/install.sh
source env.sh
rvw --help
```

To clone into another location, use `scripts/install.sh --prefix DIR`.
The script clones the workstation from GitHub. To clone a local checkout, use
`scripts/install.sh --source /path/to/workstation --prefix DIR`.
The default for a standalone copy of the script is
`$HOME/tools/risc-v-workstation`.

Select native tools with these flags:

| Flag | Tools |
|---|---|
| `--with-sim` | JDK 21, sbt, Verilator, make and a C++ compiler |
| `--with-riscv-gcc` | Bare-metal RISC-V GCC and binutils |
| `--with-cosim` | Spike with headers and libraries, then the Cosim shim |
| `--with-formal` | Yosys, SymbiYosys and Yices from OSS CAD Suite |
| `--with-gem5` | Native RISC-V gem5 v25.1.0.1. Reuse a build with `RVW_GEM5`. |
| `--with-typed-waves` | Pinned SpinalWaves checker and Surfer fork; requires Rust/Cargo |
| `--all` | All optional tools |

For private native workflow artifacts, use `--from-bundle --bundle-run RUN_ID`
with the selected native flags. Use `--bundle-dir DIR` for saved artifacts.
See the [native bundle guide](../scripts/README.md) for hosts and limits.

Use `scripts/install.sh --with-sim --dry-run` to inspect actions.
Use `scripts/install.sh --with-sim --check` to inspect installed tools and
versions. Check mode exits nonzero for a missing, old or unusable requested tool.
Both modes leave files and packages unchanged.
Use `--yes` to approve package commands without a prompt.

The script writes `env.sh` with `RVW_HOME`, `PATH`, `RVW_PYTHON` and
`RVW_LOCK_PYTHON`. Source it before using the tools. It prints the source line
for your shell startup file. It adds that line only with `--shell-rc FILE`.
Repeat the same command to check or repair the install. It does not update the
checkout or run a system-wide package upgrade. Local tool downloads use `.tools/`.
Downloaded native inputs use fixed revisions and archive checksums. See the
[tool version table](TOOL_VERSIONS.md) for selections, warnings and qualification
limits. Homebrew and OS repository packages can drift. Homebrew is a macOS
prerequisite. Full clean installs remain under issue #17, including Fedora and
macOS. A dry run does not establish a working install.

For a manual install, use Python 3.11 or later and `uv`. For example, install the
workstation under `$HOME/tools` and keep your core under `$HOME/projects`:

```sh
git clone https://github.com/riscPrint/risc-v-workstation.git "$HOME/tools/risc-v-workstation"
export RVW_HOME="$HOME/tools/risc-v-workstation"
cd "$RVW_HOME/rvw"
uv sync --locked --no-dev --extra mcp
export PATH="$RVW_HOME/rvw/.venv/bin:$PATH"
rvw --help
```

Save `RVW_HOME` and the `PATH` change in your shell setup. `RVW_HOME` points at the
workstation checkout. It lets your Scala builds find the workstation libraries.
The editable Python install uses this checkout, so keep it in place.

Install the tools needed by your adapter. A Spinal simulation normally needs
JDK 21, sbt, Verilator, a C++ compiler and make. Test builds need a RISC-V toolchain.
Fresh `--with-cosim` installs build the same qualified Spike source revision on
macOS and Linux. Existing headers and libraries are reused, including those under
`SPIKE_PREFIX`. The cosim build manifest records their identity. See
[the reference choice](../Cosim/README.md#build-and-run) before selecting a newer Spike.

Spike co-simulation needs Spike with its headers and library, plus
`"$RVW_HOME/Cosim/build.sh"`. Formal flows need Yosys, SymbiYosys and a supported
solver. See the [co-simulation guide](../Cosim/README.md) and
[SpinalChecks guide](../SpinalChecks/README.md) for those tools.

The Python install does not install native tools or cache Scala dependencies.
Offline sbt builds need their dependencies already in the cache. The VexRiscv
launcher uses `-Dsbt.offline=true`. With an empty cache, first fetch its Scala,
SpinalHDL and sbt dependencies online from `examples/vexriscv/rvw/`. Empty-cache
startup remains unverified. SpinalWaves, SpinalTrace GUI, the VS Code extension
and Sail need separate setup steps. See [tool versions](TOOL_VERSIONS.md).

Use a patched JDK 21. Fetch Scala dependencies only when the local network
policy permits it. Then use offline sbt for repeat builds.
No adjacent core checkout is needed to set up the workstation.

## Put the project files in your core repository

A SystemVerilog, VHDL or Chisel core starts with `rvw init --hdl sv|vhdl|chisel
--top TOP --isa ISA`. It writes the project file, a design-database build
through slang, GHDL or firtool, and a Verilator C1 launcher scaffold. See
[`rvw init`](../rvw/src/rvw/init/README.md#non-spinal-cores---hdl).

A useful layout is:

```text
my-core/
  rvw.toml
  src/
  tests/elf/
  rvw/
    run.sh
    build-db.sh
    cosim.json
    debug.toml
    checks.toml
    waivers.txt
    scala/
    out/
```

The scripts and Scala sources are core adapters. Commit them with `rvw.toml`.
Keep generated files under `rvw/out/` out of Git. Only add the optional files
that your project uses.

Start with this `rvw.toml`. Replace `my-core`, the configuration name and the test
selection with values that your adapter supports:

```toml
[project]
schema = "rvw.project/1"
root = "."

[core]
name = "my-core"
adapter = ["./rvw/run.sh"]
configs = ["small"]
default_config = "small"
source_env = "MY_CORE"
lock = "my-core"
jobs = 1
input_complete = false

[suites.smoke]
dir = "tests/elf"
glob = "*.elf"
max_cycles = 200000
timeout_s = 300

[tiers.quick]
runs = [{ suite = "smoke", configs = ["small"] }]
```

`[core]`, `[suites]` and `[tiers]` reuse the regression config format. The
`[project]` table is optional in `rvw.toml`. If you set `project.schema`, its value
must be `rvw.project/1`. `project.root` defaults to `.`. `core.source_repo` defaults
to the project root. You can set it when the source repository has another path.
Unknown top-level tables and unknown fields in project sections are errors.

All configuration paths are relative to the directory that contains `rvw.toml`.
Changing the shell's current directory does not change those paths. This includes
the paths in optional sections below. Shell command arguments that you type on
the CLI still use that command's normal path rules.

`source_env` names the environment variable that the adapter reads to find the
selected core checkout. In this example, `run.sh` must use `MY_CORE`. Revision
runs and gates use this variable to select the source tree. Do not hard-code the
original checkout path in the adapter. The shipped BOOM adapter uses
`SPINAL_BOOM`; your adapter can use its own name.

## Select the project

From your core repository or a directory below it:

```sh
cd "$HOME/projects/my-core"
rvw regress list
rvw regress run --tier quick --dry-run
```

`rvw` walks upward from the current directory to find `rvw.toml`. To select a
project from another directory, use one of these forms:

```sh
rvw --project "$HOME/projects/my-core/rvw.toml" regress list
rvw regress list --project "$HOME/projects/my-core/rvw.toml"
export RVW_PROJECT="$HOME/projects/my-core/rvw.toml"
rvw regress list
```

`--project PATH` is a global option and can appear anywhere in the command. It
takes priority over `RVW_PROJECT`, which takes priority over upward discovery.
Project selection takes priority over the legacy `RVW_CORE` default.
An invalid selected project is an error. It must not select a bundled core or a
different project as a fallback.

An explicit `--core boom` keeps the existing bundled BOOM configuration. An
explicit `--core /path/to/core.toml` keeps the old regression config interface.
An explicit `--core` bypasses project discovery and `RVW_PROJECT`.
Use these forms for legacy workflows. Omit `--core` when you want the project to
select the core. Do not pass both `--project` and `--core`.

## Write the run adapter

The adapter is an executable command. It can use SpinalHDL and RiscvSim, another
simulator, or another HDL. The generic regression runner uses the C1 interface:

```text
./rvw/run.sh build --config NAME [--rvfi] [--wave] [--coverage] [--konata] [--json]
./rvw/run.sh run --elf PATH --out DIR --config NAME --seed N --max-cycles N
./rvw/run.sh run-many --manifest jobs.jsonl --jobs N
```

Implement the options your suites request, including trace and memory timing
options when used. Reject unsupported options. `run-many` reads one JSON object
per line with the run options. It must write a separate C1 result for each job.
See [C1](contracts/c1-run.md) for the full command
and manifest interface, including optional wall-clock timeout support.

For each run, the adapter must:

1. Load the captured ELF bytes and record their SHA-256.
2. Run the requested core configuration, seed and cycle limit.
3. Measure the program result and counters from the simulation.
4. Write `DIR/result.json` atomically using schema `rvw.run/1`.
5. Record the actual core source, tool identity and run options.
6. List only artifacts that it wrote, with paths relative to `DIR`.

Use `pass` only when the program's completion protocol reports success. For a
`tohost` test, value 1 means pass. An odd value other than 1 means failure.
Use `error` for a harness or build error. A wall-clock timeout is not evidence of
a core failure. Preserve `inconclusive` causes even when a program reports pass.
Do not copy a successful result from an example adapter.

When a run requests `--rvfi-trace`, write C2 `rvfi.jsonl` and list it as
`artifacts.rvfi_trace` in the C1 result. Start with a `rvw.rvfi/1` header. Write
retired instructions in `order`. Record PCs, instruction bits, privilege mode,
register values, memory accesses and trap information from the actual run.
Keep cycles nondecreasing across instructions and events. Use the core's trap
CSR values. See [C2](contracts/c2-rvfi-trace.md) for exact
fields and interrupt events.

For a Spinal adapter, [RiscvSim](../RiscvSim/README.md) supplies the driver,
ELF loading, result writer and trace support. Implement its `CoreAdapter` for
your top level and memory interface. Use `RunContext.elf` for loading and symbols.
Keep signal names and completion rules in your adapter.

## Declare enough inputs for a gate

The unwired skeleton config sets `input_complete = false` on purpose. It lets you develop
the adapter without claiming that all dependencies are covered. Such evidence
cannot earn gate acceptance or passing-result reuse.

Before you set `input_complete = true`, account for all inputs that can change
the result. This includes the core, adapter sources, stimulus files, build
scripts, environment values and tools. Use the existing regression fields:
`cache_paths`, `input_env`, `input_tools`, `input_commands` and, when needed,
`input_verilator_toolchain`. See the
[regression config guide](../rvw/src/rvw/regress/README.md).

The declaration is a claim by the adapter author. A project file or an
`identity` command does not prove that the list is complete. Do not copy BOOM's
declaration without checking your own build and run dependencies.

For model identity capture, set `identity = true` and `identity_capture = true`
only when your adapter implements
`identity --config NAME --options JSON`. It must return
`rvw.adapter-capture/2` with a complete source descriptor and nonempty dotted
C1 `result_claims`. Each result must carry those values. Identify the actual RTL
and native model used by the simulation. Unknown dependencies give
`input_not_captured:<name>` and prevent acceptance. The exact requirements are in
[C8](contracts/c8-capture.md).

Build the selected test ELFs before a regression. Test discovery does not compile
them. Keep generated ELFs and build outputs under a repository `.gitignore` rule.
An empty test selection is an error.

Commit the installed workstation changes as well as both core revisions before
a gate. RiscvSim records the workstation revision and dirty flag as its harness
identity. A dirty workstation cannot earn gate acceptance.

Commit both the base and candidate core revisions before a gate. A dirty
candidate gives `candidate_not_committed`, not accept. Keep inputs, installed
tools and caches stable during a command. C8 covers normal mistakes such as stale
files, missing tools and interrupted builds. It does not cover hostile inputs,
mid-run edits or cache tampering.

## Run the first gate

First check that the selected tests exist and that the adapter works:

```sh
rvw regress list --suite smoke
rvw regress run --tier quick --out rvw/out/smoke
```

After you have implemented the C8 identity and completeness requirements, choose
a committed base revision. Test your working tree before you commit:

```sh
rvw regress gate --tier quick --base-rev BASE_COMMIT
```

A comparison that passes on dirty sources prints `TESTS PASS`, then `NOT ACCEPTED`.
Commit your change on a scratch branch or your work branch. Run the same command again
to earn `ACCEPT`. Accept needs clean committed sources on both sides. To select a
specific candidate, add `--cand-rev CANDIDATE_COMMIT`.
A dirty candidate with a new failure still prints `REJECT`. Other incomplete evidence
prints `INCONCLUSIVE` with its causes. C4 records `tests` separately from `verdict`.
A `tests: pass` comparison can include unchanged or known failures.

Complete RTL identities allow the second run to reuse conclusive results when the RTL,
harness, ELF, tools, environment and options stay equal. This includes unchanged failures.
Their failure status and signature stay unchanged. Incomplete results never enter the cache.
Identity elaboration still runs. Use `--no-cache` for fresh simulations.
Without complete RTL identity, only passes are cached and committing can invalidate the cache.

The gate judges the repository selected by `core.source_repo`, not the
workstation repository. Keep unchanged failures visible. A gate can report them
as `still_failing`; a gate accept does not mean that every test passed.
Known-failure waivers and signature matching remain experimental.

Gate exit codes are 0 for accept, 1 for reject, 3 for inconclusive, and 2 for an
input error. Check the verdict and its causes. Never treat inconclusive as accept.
A smoke gate only covers the selected tests, configurations and seeds. It is not
full ISA validation or a proof of hardware correctness.

## Add co-simulation, debug, queries and formal defaults

Add these sections when their files and adapters are ready:

```toml
[cosim]
platform = "rvw/cosim.json"

[debug]
config = "rvw/debug.toml"

[checks]
settings = "rvw/checks.toml"
waivers = "rvw/waivers.txt"

[query]
build = ["./rvw/build-db.sh"]
db = "rvw/out/design.db"

[formal]
verilog = ["rvw/out/rtl/MyTop.v"]
top = "MyTop"
clock = "clk"
reset = "reset"
checks = "rvw/out/rtl/MyTop.checks.json"
```

The `[formal]` section is optional. Its `checks`, `clock` and `reset` fields are
also optional. Set clock and reset names to match the generated top level.
Generate the RTL and checks report before running formal. Project selection does
not generate them. `[checks]` references are recorded as project inputs. The
project-owned launcher must read and apply the settings and waivers. A reference
alone does not install checks.

Match the co-simulation platform JSON to your core's ISA, reset state, memory map
and device behavior. Use your debug config for your signal paths. The bundled
BOOM files show the formats, but their platform and signals are core specific.

```sh
rvw cosim check --trace RUN_DIR/rvfi.jsonl --elf tests/elf/add.elf --json
rvw bundle FAILED_RUN_DIR --core-config rvw/debug.toml
rvw query build --config small
rvw query info --json
rvw query hierarchy --depth 2
rvw formal bmc --depth 20 --out rvw/out/formal --json
```

`rvw query build [--config NAME] [--out PATH]` runs the project's `query.build`
command and appends `CONFIG OUT` as two arguments. Write `build-db.sh` to accept
those arguments and produce the database at `OUT`. A build replaces an existing
output database. A failed build cannot return an older database. The command runs in the
project root. Resolve `OUT` before changing directories in the launcher. Do not
put `OUT` directly into an sbt `runMain` string. Use a NUL-separated arguments
file and `spinaldb.Main.expandArgsFile` to preserve spaces and punctuation.
The default database path comes from `query.db`. An explicit
`--out` lets you build another database. Explicit query `--db` and formal
`--verilog`, `--top` and `--checks` options let you select other inputs.

The formal flows currently support one rising-edge clock and synchronous state.
Other clocks, asynchronous state controls and latches are refused. A bounded
pass covers its depth and assumptions. `no_checks` is not a pass. Database
navigation and database diff have separate evidence rules; a successful database
build does not establish design equivalence.

## Link Scala adapters to workstation libraries

Keep the Scala adapters in your core repository. Use sbt `ProjectRef` to consume
the installed workstation libraries. For example, in `rvw/scala/build.sbt`:

```scala
ThisBuild / scalaVersion := "2.13.14"
val workstation = file(sys.env("RVW_HOME")).getCanonicalFile
val coreRoot = file("../..").getCanonicalFile

lazy val simulation = ProjectRef(workstation / "RiscvSim", "riscvsim")
lazy val database = ProjectRef(workstation / "SpinalDB" / "spinaldb", "spinaldb")
lazy val checks = ProjectRef(workstation / "SpinalChecks", "spinalchecks")
lazy val core = ProjectRef(coreRoot, "root")

lazy val adapters = (project in file("."))
  .dependsOn(simulation, database, checks, core)
  .settings(
    libraryDependencies += compilerPlugin(
      "com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % "1.15.0"),
    fork := true
  )
```

Use the actual sbt project ID of your core in place of `root`. Depend only on the
libraries that your adapter uses. Add a `compile->test` mapping only if it needs
the core's test sources. Match Scala, SpinalHDL and compiler-plugin versions.
The current workstation builds use Scala 2.13.14 and SpinalHDL 1.15.0.

The `RiscvSim` build loads only the generic library. It needs no core checkout.
The bundled BOOM adapter has a separate build under `RiscvSim/boom`.
Use the library `ProjectRef` above for external adapters.

Run builds offline from the adapter build directory. Use the machine lock for
shared sbt outputs:

```sh
cd "$HOME/projects/my-core/rvw/scala"
"$RVW_HOME/scripts/with-lock.sh" sbt nice sbt -batch -offline compile
```

For an external SpinalDB build, set these variables in `build-db.sh` before
starting sbt. The dependency runner binds generated RTL and source locations.
Without it, database queries can be inconclusive even when extraction finishes.

```sh
export SPINALDB_PROCESS_RUNNER="$RVW_HOME/SpinalDB/scripts/hdl-deps.py"
export SPINALDB_PYTHON="${RVW_PYTHON:-$RVW_HOME/rvw/.venv/bin/python}"
```

The wrapper scripts must pass their arguments safely to the JVM. SpinalDB's
`--args-file` interface avoids putting file paths through sbt's command parser.
See [SpinalDB](../SpinalDB/README.md) for `SpinalDB.generate` and the build entry
interface. See [SpinalChecks](../SpinalChecks/README.md) for installing checks.
The shipped BOOM launchers also handle identity, native tool binding and replay.
Replacing them with a bare `runMain` command does not provide those guarantees.

## Instrument your core

Many tools read events that only the core can give: predictor outcomes, pipeline stages,
stall causes, cache and TLB events, event counters. Add them once with
[SpinalProbes](../SpinalProbes/README.md). The probes are simulation-only and off by default.
`RiscvSim` (a `ProjectRef` of it, as above) brings the library with it.

1. In the RTL or in a plugin, call `spinalprobes.Probe.*` with existing signals. Calls add no
   hardware unless the elaboration runs under `Probe.enabled(true)`.
2. In the run adapter, set `override def supportsProbes = true`. Elaborate with
   `Probe.enabled(key.probes) { ... }`. In the run loop, open
   `ProbeCollector.open(Probe.of(dut), job, ctx.rvfiHeader)`, call `sample(ctl.cycle)` in
   `onSamplings`, `close(cycles)` after a finished run and `abandon()` in `finally`.
3. Run with `--probes`. The run writes `probe-events.jsonl` beside `rvfi.jsonl`.
4. Run `rvw probes list --events RUN/probe-events.jsonl`. It shows which tools your probes
   enable and what is still missing. With a database built from a probe elaboration,
   `rvw probes list --db DB` shows the same before any run.
5. Convert for each tool with `rvw probes convert RUN/probe-events.jsonl --to TARGET`.

Minimal probe set per tool:

| Tool | Probes | Convert |
|------|--------|---------|
| `rvw csim compare-rtl` | `branch` at the commit point with `predictedTaken` (and `semantics`) | `--to bp-events --c2 RUN/rvfi.jsonl` |
| `rvw perf` pipeline view | `stage` per stage with a unique instruction ID, `retire`, `flush` | `--to kanata` |
| `rvw perf` stall causes | the above plus `stall(scope, cause, valid)` | `--to kanata` |
| `rvw arch ooo-calibrate` | `counter` per RTL event in the plan (rename stalls, ROB full, IQ occupancy as an amount, mispredicts, misses) | `--to counts --c1 RUN/result.json --c2 RUN/rvfi.jsonl` |
| HPM monitors | `counter(name, inc, hpm = Some(selector))` | `--to hpm` |
| RiscvSim `CacheEventObserver` | `cacheAccess` with `data` (and `mask` for stores) | `--to cache` |
| `rvw regress mmu report --protocol-config` | `tlb` fill/hit/invalidate with va, pa, asid, entry, size, PTE | `--to mmu` |
| MMU walk capture | `pageWalk` request/response | `--to mmu` |
| `rvw debug etrace` | `traceIngress` from the encoder port | `--to etrace-ingress` |
| `rvw cosim` interrupt evidence | `interruptTaken` | `--to interrupts --c2 RUN/rvfi.jsonl` |

Per-slot CSR state for `rvw cosim` still uses `RvfiProbe csrSlots` (see RiscvSim). Fault
injection uses the design database and an adapter that implements C1 `--fault`.
The [VexRiscv example](../examples/vexriscv/README.md#probes) taps existing signals from
a plugin, without core source changes.

## Configure MCP

Use the installed `rvw` executable as a stdio MCP server. For clients that use a
`mcpServers` config, substitute your absolute paths:

```json
{
  "mcpServers": {
    "rvw": {
      "command": "/path/to/risc-v-workstation/rvw/.venv/bin/rvw",
      "args": ["mcp"],
      "env": {
        "RVW_HOME": "/path/to/risc-v-workstation",
        "RVW_PROJECT": "/path/to/my-core/rvw.toml"
      }
    }
  }
}
```

The server inherits native-tool paths from its environment. Check them when the
client starts outside your shell. `rvw mcp --list` lists the exposed tools.
Regression, co-simulation, query build/navigation, formal and debug MCP tools accept a
`project` path. `query_diff` takes two explicit database paths.
`rvw mcp --project PATH` binds the server default without changing its environment.
An explicit `project` selects that file for the call. Otherwise `RVW_PROJECT`
provides the server default. For example, call `regress_list` with
`{"project": "/path/to/my-core/rvw.toml"}`.

Long operations return a job ID. Use `job_status` and `job_log` to read the result.
Use `job_cancel` to stop a job. The same evidence and verdict rules apply to CLI
and MCP calls.

## Current limits

Project mode does not create a run adapter, a memory system, RVFI signals or a
test suite for a new core. Each integration must supply them and validate its
input declaration. The workstation still ships BOOM examples at their existing
paths for explicit `--core boom` use.

External BOOM and second-core integration checks are tracked in
[#1](https://github.com/riscPrint/risc-v-workstation/issues/1) and [#34](https://github.com/riscPrint/risc-v-workstation/issues/34). Do not read these setup steps
as a claim that those checks passed. Record measured run counts, gate verdicts,
query outputs and formal outcomes before claiming support for another core.

## Checked VexRiscv project

The [VexRiscv example](../examples/vexriscv/README.md) supplies a complete project
copy, test build script and commands for a separate core repository. Copy its
`rvw.toml` and `rvw/` directory into the core checkout. Run its commands from the
core root. The launchers use `RVW_HOME` for installed libraries and `VEXRISCV`
for revision selection. Leave `VEXRISCV` unset for normal use.

## Checked VexiiRiscv project

The [VexiiRiscv example](../examples/vexiiriscv/README.md) is a core with no RVFI
port and git submodules. Its adapter maps the upstream commit probe to C2. Its
build compiles the core's pinned SpinalHDL source instead of the release.
Gate checkouts include the submodules that the core repository has initialized.
`VEXIIRISCV` selects the revision. Leave it unset for normal use.

## Architecture exploration

Add `[arch]` with `description`, `sources`, and `benchmarks` paths. The
description maps the project preset to gem5 O3 parameters. The sources are
riscv-tests benchmarks. `benchmarks` is the native ELF build directory.
Run `rvw arch build` to locate gem5 and build the benchmarks. Run
`rvw arch calibrate --out rvw/out/calibration-1` to run both engines and
write JSON and text reports. See [the architecture guide](../Arch/README.md).

## Limit ownership

Installer qualification: [#17](https://github.com/riscPrint/risc-v-workstation/issues/17) and [#40](https://github.com/riscPrint/risc-v-workstation/issues/40). Native bundle: [#71](https://github.com/riscPrint/risc-v-workstation/issues/71). Waivers: [#2](https://github.com/riscPrint/risc-v-workstation/issues/2). Stored-folder/performance gates: [#4](https://github.com/riscPrint/risc-v-workstation/issues/4). Owner integration choice: [#34](https://github.com/riscPrint/risc-v-workstation/issues/34).

Retained limit: Adapters must reject unsupported options. Example validation does not qualify every host, backend or core preset. Owner decisions remain open.

Native syntax and style lint: run `scripts/install.sh --with-lint` and source
`env.sh`. This installs Verible v0.0-4298-g085eef05 under `.tools/verible`.
The installer checks the release archive SHA256 before extraction. Linux x86_64,
Linux arm64 and macOS are supported. The macOS release uses the upstream binary;
Apple Silicon can need Rosetta. Run `scripts/install.sh --with-lint --check` to
check the pinned version. `rvw lint` finds it through `PATH`.

### Inspect co-simulation capture first

After the adapter writes its first C2 trace, run this in the core project:

```sh
rvw cosim doctor --trace OUT/rvfi.jsonl --json
rvw cosim doctor --trace OUT/rvfi.jsonl --strict --json
```

Set `[cosim].platform` in `rvw.toml`. The report lists captured capabilities,
configured comparisons and absent state. It also lists conditional masks with
reasons and exact platform choices. Inspect these before a reference run.
For example, CSR-only capture must not claim FP state. A scalar trace cannot
establish vector correctness. Add the missing capture to the core adapter.

`inspected` means that C2 validation finished. No model ran. The report cannot
claim a match. Next run `rvw cosim check --elf ELF --trace OUT/rvfi.jsonl --json`.
Read its actual state coverage and applied masks. Use the `cosim_doctor` MCP
tool for the same inspection from an agent.


## Development path vs gate path

Use direct adapter runs to develop the signal, reset, memory and RVFI mapping.
Then use `rvw regress run --rvfi-trace` for the intended ELF inventory. Filter
out `.dump` files. Compare traces with `rvw cosim check`. Test passes on a dirty
core do not earn gate acceptance. Gate runs also require reviewed input capture,
clean commits and matching identities.

Wired Spinal init projects declare standard launcher inputs and both RTL hooks:
`elaborate` and `generatedVerilog(model)`. Review custom sources, external data,
environment and tools before regression. Keep mismatch refusal enabled.
The generated launcher compiles once, saves `rvw/target/rvw-classpath.json`,
and reuses Java while sources, build settings and runtime files match.
It uses `sbt-<project-name>` for private build trees. Use the shared `sbt` lock
only when the build writes shared outputs.

Use one project-owned `Elaboration.top()` and `Elaboration.config` for simulation
and SpinalDB. The generated database entry uses them. Formal and lint consume
the database's RTL. Rebuild that database after configuration changes.
Constant-value ASYNC reset FFs need the event BMC selection
`--event-model --async-reset` in formal BMC, apps or autocheck. Other unsupported
state stops early with a fix hint. IFT currently requires public rising-edge
SYNC state. If the project selects SYNC, change the shared entry and rebuild
all flows. IFT models X/Z constants as Boolean uncertainty with taint set.
It does not model electrical high impedance.

Architecture Minor/Timing and scheduling descriptions accept `rv32i` and
`rv64i` without M. RV64 O3 also accepts `rv64i`. Model selection does not prove
that the instruction behavior matches RTL. Gem5 remains an optional backend.

For a simple CPU memory interface, use `SimpleCpuBus` and `SimpleCoreWrapper`
from [SpinalSoc](../SpinalSoc/README.md). `core.bus = "simple"` inserts the APB3
bridge with byte strobes. The CPU must hold requests through completion.
A project wrapper must map reset, interrupts and memory waits. AXI4-Lite
wrappers retain the existing ingress. Run software on the composed core before
claiming CPU integration.

Use `rvw uvm new --adapter adapter.json` for a custom typed bus. Its
`rvw.uvm-adapter/1` file names a database bus, an agent profile, explicit pin
bindings and a project scenario. The generated bench requires positive checks.
`rvw vip list`, `vip buses` and `vip bench` expose the agent inventory and
bench skeletons. Their MCP names are `vip_list`, `vip_buses` and `vip_bench`.
Generation is not native qualification.

The init probe stub shows fetch/decode flushes and measured fetch/data stalls.
Bind actual pipeline slot IDs. After a `--probes` run, use `rvw probes check`
with `--require flush/fetch --require flush/decode --require stall` and an
`--events` file. The command names missing declarations. Presence does not
prove activation or complete pipeline accounting.
