# Agent setup for a new core

Use this playbook inside the user's core repository. Install the workstation
once in a separate directory. Keep the core adapters in the core repository.
Do not add a submodule. Read the core's agent rules before you change files.
Read [C1, C2 and C8](PLATFORM_CONTRACTS.md) before you claim support.
The [human guide](BRING_YOUR_OWN_CORE.md) gives the full interfaces.
Use [AGENT_ARCH.md](AGENT_ARCH.md) for gem5 and performance exploration.

Follow the numbered steps in order. A command error is a stop for that step.
Save its exit code and log. Fix its cause before you continue.
`rvw doctor` and `rvw init` are planned in
[#35](https://github.com/riscPrint/risc-v-workstation/issues/35) and
[#36](https://github.com/riscPrint/risc-v-workstation/issues/36).
The commands below are the current setup path.

## Setup diagnostics

After the initial install, use `rvw doctor --features sim,riscv-gcc,cosim --json`
in the core project. It checks native versions through the installer and reports
project, adapter, ELF and gate actions. Exit 1 means setup is not ready.
Use `rvw doctor --install sim,riscv-gcc,cosim --dry-run --json` to inspect
installation. Remove `--dry-run` to run it. The installer asks before system
packages. Source `env.sh` afterward. MCP `rvw_doctor` is diagnostic-only.
Use `--smoke-elf PATH` to permit a build and one C1 run after the adapter works.
This does not prove RVFI mapping or earn a gate verdict.
See [doctor](../rvw/src/rvw/doctor/README.md) for exits and limits.

## 1. Select paths and check the installation

Set these paths to existing directories. Use absolute paths.

```sh
export RVW_HOME=/path/to/risc-v-workstation
export CORE_ROOT=/path/to/core
export RISCV_TESTS_SOURCE=/path/to/riscv-tests
cd "$CORE_ROOT"
unset RVW_PROJECT RVW_CORE
"$RVW_HOME/scripts/install.sh" --check --with-sim --with-riscv-gcc --with-cosim
```

Success: exit 0. Each requested tool prints `PRESENT`. This checks Python,
`rvw`, MCP, JDK 21, javac, sbt, Verilator, make, C++, RISC-V GCC, Spike,
its headers and libraries, and the Spike shim. Check mode changes no files.
Add `--with-formal` for formal tools. Add `--with-gem5` for architecture work.
Do not add flags for tools you will not use.

Failure: `MISSING env.sh` means setup has not finished in this installation.
A missing shim manifest needs the cosim install step below.
A missing command can mean that its directory is absent from `PATH`.
Set `JAVA_HOME` to the installed, patched JDK 21.
Add its `bin` directory to `PATH`. Do not use an old cached JDK.
Set `RISCV_PREFIX` to a different bare-metal compiler prefix when needed.
Set `SPIKE_PREFIX` if the Spike headers and library use another prefix.
Check mode returns nonzero for a missing, old or unusable tool.

## 2. Install missing tools

Inspect the actions first:

```sh
cd "$RVW_HOME"
scripts/install.sh --with-sim --with-riscv-gcc --with-cosim --dry-run
scripts/install.sh --with-sim --with-riscv-gcc --with-cosim
source "$RVW_HOME/env.sh"
scripts/install.sh --check --with-sim --with-riscv-gcc --with-cosim
rvw --help
cd "$CORE_ROOT"
```

**Human decision:** get approval before a system package command.
The installer asks before such commands. Do not pass `--yes` without that approval.
Local setup in the chosen workstation directory can proceed within task scope.

Success: the installer and check exit 0. `env.sh` exists. `rvw --help` lists
subcommands. The environment sets `RVW_PYTHON` and `RVW_LOCK_PYTHON`.

Failure: inspect the first failed tool in the log. Fix its path or install it.
For a stale shim, run `"$RVW_HOME/Cosim/build.sh"` with matching Spike headers
and libraries. Retry the check. See [installation details](BRING_YOUR_OWN_CORE.md#install-the-workstation).
The installer does not cache Scala dependencies. For an offline dependency
error, fetch the exact Scala, SpinalHDL and sbt dependencies in the adapter build
with network access if the local policy permits it. Then retry offline.
Do not change library versions only to use an available cache.

## 3. Create the project files

**Human decision:** agree on the ISA, reset PC, RAM map and supported presets.
Start with one preset and one small program. Record the intended scope.

For a new Spinal/sbt core, start with the minimal scaffold:

```sh
cd "$CORE_ROOT"
rvw init --isa rv32im --dry-run --json
rvw init --isa rv32im
rvw doctor --json
```

Replace `rv32im` with the specified ISA. The generated project file is valid.
Doctor should report `project: ready`. It returns exit 1 because adapter build/run,
ELFs and gate inputs are unfinished. Follow the generated `rvw/README.md`.
The launcher refuses build/run until signal mapping is complete. `--force`
replaces existing scaffold files, so preserve edited files first.
See [init limits](../rvw/src/rvw/init/README.md). It does not generate a cosim
memory map or SpinalDB entry. The steps below still apply.

For the shipped VexRiscv integration, run:

```sh
cd "$CORE_ROOT"
cp "$RVW_HOME/examples/vexriscv/rvw.toml" .
cp -R "$RVW_HOME/examples/vexriscv/rvw" .
unset VEXRISCV
```

For a BOOM project, copy only `examples/boom/rvw.toml` instead.
That example uses the installed BOOM launcher. It has no `rvw/` directory.
Set `SPINAL_BOOM` and each external test path for your checkout.
Copy its `arch/` directory only for architecture work.
Read the selected example's README before you run it.
For another core, use the closest example as source material.
Edit its launcher, Scala top, memory model and test files for that core.
The copied VexRiscv adapter is not a generic adapter for another core.

Set `core.name`, `configs`, `default_config`, `source_repo`, `source_env` and
`lock` in `rvw.toml`. Set `input_complete = false` during development.
The launcher must honor `source_env` for the selected revision checkout.
Keep build outputs ignored. The examples supply `rvw/.gitignore`.

```sh
rvw regress list
rvw regress run --tier quick --dry-run
```

Success: exit 0. The project names the intended core and preset.
Before ELF build, an empty selection can fail. Continue at step 6 to build it.
A dry run checks the plan. It does not test the adapter.

Failure: resolve every relative path from the directory of `rvw.toml`.
Remove stale `RVW_PROJECT` or use `rvw --project "$CORE_ROOT/rvw.toml" ...`.
Do not use `--core boom` to work around a project error.
For another core, replace all example source selectors and preset names.

## 4. Find the core signals

Start from the core sources. Do this before you use an existing adapter as an answer.

```sh
cd "$CORE_ROOT"
rg -n 'resetVector|resetAddress|resetPc|ClockDomain|resetKind' src
rg -n 'IBus|DBus|iBus|dBus|axi|wishbone|Stream|Flow' src
rg -n 'rvfi|FormalPlugin|retire|commit|tohost' src
```

Read the top-level generator and the selected plugin or bus classes.
Record signal paths, widths, directions, handshake rules and reset polarity.
Find the test linker script and the `tohost` ELF symbol.
`tohost` is normally a software address, not a core port.
Find a retirement event to confirm that the completion store retired.
Do not treat a speculative request as completion.

For VexRiscv, inspect `IBusSimplePlugin.scala`, `DBusSimplePlugin.scala`,
`FormalPlugin.scala` and `CsrPlugin.scala` under `src/main/scala/vexriscv/plugin/`.
The simple instruction bus has a command handshake and a response flow.
The data bus has a command handshake and a load response. Stores have no response.
`FormalPlugin` exports RVFI. Check trap CSRs separately.
Use the reset vector chosen by your top-level generator.

When a database launcher is available, run:

```sh
rvw query build --config rv32im
rvw query info --json
rvw query hierarchy --depth 2
rvw query search 'iBus*' --json
rvw query search 'rvfi*' --json
rvw query where rvfi_rd_wdata --json
rvw query drivers rvfi_rd_wdata --json
```

Replace the preset and signal names for another core.
For VexRiscv, the copied `rvw/build-db.sh` supplies the launcher.
For another core, create the optional launcher in step 10 first.
Source inspection can proceed without a database.

Success: source reads identify each interface. Database commands exit 0 and
return signals with source locations. Check that the database used the same
preset as simulation. Save the source locations in a core-owned setup note.

Failure: no search hit means try the elaborated name from `query search`.
An ambiguous signal needs its full hierarchy path. A missing database needs
`query build`. An inconclusive capture needs complete source roots and the
SpinalDB dependency runner. See step 10. Do not infer a missing signal value.

## 5. Write and build the C1 adapter

Implement `riscvsim.CoreAdapter` in core-owned Scala sources.
Read [RiscvSim](../RiscvSim/README.md) and
[Model.scala](../RiscvSim/src/main/scala/riscvsim/Model.scala).
Use the example launcher for identity capture, native tool binding and replay.
A bare sbt `runMain` call does not supply that evidence.

Implement `core`, `configs`, `isa`, `xlen` and `sourceDir`.
Implement `compile` and `elaborate` with the same generated RTL.
Implement `run` with the actual memory, reset and retirement interfaces.
Load memory and symbols from `ctx.elf`. Do not reopen `job.elf`.
Use the requested seed, limits and memory timing.
Return measured `RunOutcome` counters and status.
Accept `pass` only after the program's completion rule reports success.
For tohost tests, 1 means pass. Other odd values mean fail.
Connect C2 RVFI fields to actual retired effects. Preserve trap CSR values.
Reject unsupported flags. Do not fabricate an RVFI monitor or Konata support.

Keep Scala 2.13.14 and SpinalHDL 1.15.0 aligned with the workstation.
The current RiscvSim `ProjectRef` loads the bundled BOOM build.
For an independent core, compile `RiscvSim/src/main/scala` as unmanaged sources.
Use [the VexRiscv build](../examples/vexriscv/rvw/build.sbt) for that workaround.
It does not require a BOOM checkout. SpinalDB can use its `ProjectRef`.

For VexRiscv, run:

```sh
./rvw/run.sh info --json
nice -n 10 ./rvw/run.sh build --config rv32im --rvfi --json
```

Success: exit 0. `info` lists `rv32im`. Build reports the requested model.
The launcher holds `vex` through JVM exit. Scala compilation holds `sbt`.
Use the core's own lock for another integration.

Failure: read the first Scala or Verilator error in stderr.
Check the source selector, dependency versions and plugin configuration.
A native identity error needs the actual tool or input declared in step 8.
An unsupported flag must remain an error until the adapter implements it.
Do not alter core RTL to make this setup pass.

## 6. Build test ELFs

For VexRiscv, run:

```sh
export RISCV_TESTS_SOURCE=/path/to/riscv-tests
nice -n 10 ./rvw/build-tests.sh
rvw regress list --suite isa
```

For another core, replace the script with a core-owned test build.
Select the correct XLEN, ISA, ABI, link address and memory range.
Use `"${RISCV_PREFIX:-riscv64-unknown-elf-}readelf" -h ELF` to check an ELF.
Use `"${RISCV_PREFIX:-riscv64-unknown-elf-}nm" ELF` to find `tohost`.

Success: exit 0. VexRiscv writes ELFs in `rvw/out/isa` and `rvw/out/programs`.
The ISA list is nonempty. The quick tier in `rvw.toml` selects
`add`, `beq`, `lw` and `sw` in `rv32im`.

Failure: a missing compiler needs `PATH` or `RISCV_PREFIX` fixed.
Missing assembler includes need the full riscv-tests source tree.
An empty list needs built files and corrected suite patterns.
Do not change the test filters merely to hide a failing selected test.

## 7. Try the first regression

```sh
rvw regress run --tier quick --rvfi-trace --no-cache \
  --out rvw/out/first-run --no-index --json
```

With `input_complete = false`, expect exit 1 and
`input_not_captured:adapter_dependencies`. The runner refuses execution.
It writes synthesized error records. These records are not core failures.
Keep this refusal as evidence. Continue at step 8 to review the inputs.
For early adapter debugging, use the direct `run` command in step 10.
A direct program pass alone cannot earn acceptance.

After step 8, rerun this command with `--out rvw/out/first-complete-run`.
Success: exit 0 and four passing VexRiscv jobs.
Read the C3 run set and each C1 `result.json`.
Check that `inconclusive` is absent from each C1 result.

Failure: inspect the job's `run.log` and C1 message.
Check reset release, fetch address, loaded bytes and bus responses first.
A cycle timeout needs a wave or trace. A wall timeout is incomplete evidence.
A build error is a harness problem. Preserve actual core failures.
Fix the adapter or report the core defect. Use a fresh output path to rerun.

## 8. Declare inputs and review completeness

Inspect the actual launcher and build dependencies:

```sh
rg -n 'sys.env|sys.props|source|exec|python|sbt|make|verilator' rvw
rvw regress run --tier quick --dry-run
```

Declare core and adapter sources, build scripts and libraries in `cache_paths`.
Declare result-changing environment values in `input_env`.
Declare tool chains in `input_tools`, `input_commands` and
`input_verilator_toolchain` as needed.
Include external stimulus and generated inputs that the adapter reads.
Audit computed paths, wrappers and interpreter dependencies.
The example lists are starting points. They do not prove completeness.

Enable `identity = true` and `identity_capture = true` only with the supported
`identity --config NAME --options JSON` implementation.
It must emit `rvw.adapter-capture/2` with a complete source descriptor and
nonempty dotted C1 `result_claims`. Each C1 result must match those claims.
Read [C8](PLATFORM_CONTRACTS.md#c8-input-capture-and-result-generations).

**Human decision:** present the input list and its limits for review.
Set `input_complete = true` only when that claim is justified.
Keep known-failure waivers empty for the first gate.
A waiver needs a separate human decision. Waiver support remains experimental.

Success: the declared paths exist and every known result-changing input is covered.
Failure: keep `input_complete = false` for an unknown dependency.
Resolve `input_not_captured:*` causes. Do not suppress them to earn acceptance.
Rerun step 7 with a fresh output path after the review.
Keep sources, tools and caches stable throughout each command.

## 9. Run a dirty gate, then a committed gate

The workstation must be clean and committed before this step.
RiscvSim records the workstation revision and dirty flag.
Commit the new core project files as a usable baseline first.
Use a work branch. Follow the user's commit policy.

```sh
git add rvw.toml rvw
git commit -m 'Add workstation core integration'
export BASE_REV=$(git rev-parse HEAD)
printf '\n# Gate setup check\n' >> rvw.toml
RVW_RESULTS="$CORE_ROOT/rvw/out/gate-dirty" \
  rvw regress gate --tier quick --base-rev "$BASE_REV"
```

Success for this deliberate dirty check: exit 3, `TESTS PASS`, then
`NOT ACCEPTED`. Check the report for `candidate_not_committed`.
If the tests fail, the gate can reject instead. Do not expect a dirty pass.

```sh
git add rvw.toml
git commit -m 'Record gate setup check'
RVW_RESULTS="$CORE_ROOT/rvw/out/gate-committed" \
  rvw regress gate --tier quick --base-rev "$BASE_REV" --cand-rev HEAD --json
```

Success: exit 0 and `verdict: accept`. Check `tests`, causes and the selected
job count. Accept covers only these tests, presets and seeds.
The comment change should leave the RTL hashes equal.
The gate may reuse complete matching evidence. Use `--no-cache` for fresh runs.

Failure: exit 1 means reject. Exit 3 means inconclusive. Exit 2 means bad input.
Read the causes. Commit dirty core or harness sources before retrying.
Fix missing capture. Never map an inconclusive verdict to accept.
A gate can accept unchanged failures. Read `still_failing` before you claim
that all selected tests passed. See [the gate guide](../rvw/src/rvw/regress/README.md).

## 10. Check the Spike platform and optional design tools

Set `[cosim].platform` to a core-owned JSON file.
For VexRiscv, the example already selects `rvw/platform.json`.
Check `name`, `xlen`, `isa`, `reference_isa`, `reset_pc`, RAM, MMIO,
`pmp_regions`, `aligned_mem` and interrupt inputs against the core.
See [Cosim](../Cosim/README.md#platform-configuration) for the exact fields.
Do not copy a CSR mask or trace quirk without evidence and review.

```sh
./rvw/run.sh run --elf rvw/out/programs/smoke --out rvw/out/spike-smoke \
  --config rv32im --seed 1 --mem-latency 0 --rvfi-trace --json
rvw cosim check --elf rvw/out/programs/smoke \
  --trace rvw/out/spike-smoke/rvfi.jsonl --json
```

Success: both exit 0. Check `trace_complete: true` and `end_status: pass`.
Read the comparison's synchronization and quirk records.
A matching prefix can exit 0. It is not a complete passing execution.

Failure: exit 1 means an architectural mismatch. Inspect its first instruction.
Exit 2 means malformed or unsupported data. Exit 3 means incomplete evidence.
Rebuild a stale shim. Fix a wrong platform from source evidence.
VexRiscv differs from Spike on absent PMP CSR accesses and ECALL `mtval`.
Its local smoke program avoids these differences. Do not claim an ISA-suite match.

For optional SpinalDB, add `[query]` with `build` and `db`.
The launcher takes `CONFIG OUT` and must create the database at `OUT`.
Use a NUL-separated args file with `spinaldb.Main.expandArgsFile`.
Set `SPINALDB_PROCESS_RUNNER` to
`$RVW_HOME/SpinalDB/scripts/hdl-deps.py`.
Set `SPINALDB_PYTHON` to `$RVW_PYTHON`.
Capture both core and adapter source roots. Run the queries in step 4.
Success: exit 0 and a fresh database. A stale database is not a successful build.

For optional SpinalChecks, use `SpinalChecks.install` during elaboration.
Use `includeFormal` and assertion mode for formal RTL.
Make the launcher apply the configured settings and waivers.
Add `[formal]` with generated `verilog`, `top`, `checks`, `clock` and `reset`.
Use actual top-level port names. Select reset polarity from step 4.
The project `reset` field selects a port. It does not select polarity.
Set `CORE_RESET_ACTIVE=high` for active-high reset.
Set `CORE_RESET_ACTIVE=low` for active-low reset.
The CLI defaults to high, so pass this value explicitly. Then run:

```sh
rvw formal bmc --reset-active "$CORE_RESET_ACTIVE" \
  --depth 20 --out rvw/out/formal-first --json
```

Success: exit 0, `status: pass`, with assertions checked.
Failure: `no_checks` is not a pass. Review failed or unknown checks.
Multiple clocks, asynchronous state controls and latches are refused.
A bounded pass covers only its depth and assumptions.
VexRiscv's shipped example does not supply formal defaults or check reports.
Stop this optional path until you have written and reviewed them.

## 11. Connect the agent's MCP client

Check the server before you change a client config:

```sh
rvw mcp --list
```

Success: exit 0 and a list that includes `regress_list` and `cosim_check`.
Use absolute paths below. Merge the entry with the existing client config.
Start the client from a shell after `source "$RVW_HOME/env.sh"`.
The server needs the native tools on `PATH` and the selected JDK.

For Claude Code, put this entry in the core's `.mcp.json`:

```json
{
  "mcpServers": {
    "rvw": {
      "type": "stdio",
      "command": "/path/to/risc-v-workstation/rvw/.venv/bin/rvw",
      "args": ["mcp"],
      "env": {
        "RVW_HOME": "/path/to/risc-v-workstation",
        "RVW_PROJECT": "/path/to/core/rvw.toml",
        "RVW_PYTHON": "/path/to/risc-v-workstation/rvw/.venv/bin/python",
        "RVW_LOCK_PYTHON": "/path/to/risc-v-workstation/rvw/.venv/bin/python"
      }
    }
  }
}
```

For Codex, add this entry to `~/.codex/config.toml`:

```toml
[mcp_servers.rvw]
command = "/path/to/risc-v-workstation/rvw/.venv/bin/rvw"
args = ["mcp"]

[mcp_servers.rvw.env]
RVW_HOME = "/path/to/risc-v-workstation"
RVW_PROJECT = "/path/to/core/rvw.toml"
RVW_PYTHON = "/path/to/risc-v-workstation/rvw/.venv/bin/python"
RVW_LOCK_PYTHON = "/path/to/risc-v-workstation/rvw/.venv/bin/python"
```

Restart the client. Check `claude mcp list` or `codex mcp list`.
Call `regress_list` with `{"project":"/path/to/core/rvw.toml"}`.
Success: the client lists the server and returns the intended core's tests.
For a failed start, run the exact executable with `mcp --list` in the client
environment. Fix paths, missing MCP packages or native tool paths.
Client trust or approval prompts require the user's decision.
Do not change client permission settings to bypass them.
Long operations return job IDs. Use `job_status`, `job_log` and `job_cancel`.

Client syntax references: [Claude Code MCP](https://code.claude.com/docs/en/mcp)
and [official OpenAI MCP documentation](https://developers.openai.com/codex/mcp).

These steps were checked end to end on a fresh VexRiscv setup (2026-10-24).

## 12. Finish the setup record

```sh
git status --short
rvw regress list --suite isa
rvw mcp --list
```

Success: exit 0 and only intended files in the worktree.
If the tree is dirty, commit approved setup files before an acceptance claim.
Report each remaining error with its command and exit code.

- Record the core revision, workstation revision and exact selected presets.
- Record the reset, memory, completion and RVFI signal sources.
- Record the reviewed input declaration and human decisions.
- Record the regression count and C1 status counts.
- Record both gate verdicts and their causes.
- Record cosim completeness, end status, quirks and mismatches.
- Record query and formal outcomes separately.
- State which optional paths and configurations were not checked.

Do not claim hardware correctness from simulator results.

## Limit ownership

Waiver policy: [#2](https://github.com/riscPrint/risc-v-workstation/issues/2). Integration choice: [#34](https://github.com/riscPrint/risc-v-workstation/issues/34). Backend capabilities: [#116](https://github.com/riscPrint/risc-v-workstation/issues/116).

Retained limit: Agents must preserve adapter refusals and require human review where stated. No invented RVFI, Konata or waiver support is permitted.
