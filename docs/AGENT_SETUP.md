# Agent setup for a new core

Use this playbook inside the user's core repository. Install the workstation
once in a separate directory. Keep the core adapters in the core repository.
Do not add a submodule. Read the core's agent rules before you change files.
Read [C1, C2 and C8](PLATFORM_CONTRACTS.md) before you claim support.
The [human guide](BRING_YOUR_OWN_CORE.md) gives the full interfaces.
Use [AGENT_ARCH.md](AGENT_ARCH.md) for gem5 and performance exploration.

Follow the numbered steps in order. A command error is a stop for that step.
Save its exit code and log. Fix its cause before you continue.
`rvw doctor` and `rvw init` are available. Use the commands below.
For mapped adapters and optional-tool input examples, use
[the integration recipes](INTEGRATION_GUIDE.md#project-input-recipes).

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
Read [C8](contracts/c8-capture.md).

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
A matching prefix without an end record is `inconclusive` (exit 3). It is not a complete passing execution.
For a core with completed misaligned RAM accesses, review the explicit
`misaligned` policy and `scalar_split_ram` opt-in in the
[integration recipes](INTEGRATION_GUIDE.md#project-input-recipes).

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

<!-- rvw agent guide: begin (generated by `rvw agent guide --markdown`; do not edit) -->

## Agent workflows

Machine-readable form: `rvw agent guide --json`, MCP tool `agent_guide`, MCP resource `rvw://agent/guide`.

- Placeholders: Angle-bracket values (<ELF>, <RUN>, <REV>) are inputs the agent supplies. Every other argument is literal.
- Exit codes: 0 earned result; 1 failure or mismatch; 2 usage or setup error; 3 inconclusive. Never treat 3 as a pass.
- Stop: A step ends a workflow with `stop` when its decision says so. Record the command, exit code and log before you stop.
- Locks: Heavy runs hold the project lock (core.lock). Do not start a second heavy run of the same core.
- Integration guide: Follow docs/INTEGRATION_GUIDE.md for install, project binding and evidence limits. A scaffold or tool list does not qualify a core. For mapped security, use rvw/sec/flow.S with the generated flow policy and a 110-second budget. Progress reports name preparation cost. For composed SoCs, use GENERATED/verify.json and supply runtime-classpath.txt, soc.db and apb.jsonl. Fabric proof rows do not close whole-SoC verification.
- Verdicts: Evidence producers own verification verdicts in their stated scope. The evidence index preserves reports. Plan summaries retain the weakest input verdict. Farm completion and guide steps do not grant verification or C4 acceptance.

### New core bring-up (`bring-up`)

A Spinal core repository has no rvw.toml yet, or `rvw doctor` is not ready.

Optional tool set: 22 tools. Load MCP profile `core` with `rvw_tools_load`. Read the tool names in `rvw agent guide --json`. Use `rvw_tools_describe` before a call.

1. **doctor**: Check the installation and the native tools. `rvw doctor --features sim,riscv-gcc,cosim --json` / MCP `rvw_doctor`
   - If exit 1 and a native tool is missing: go to `install`.
   - If project missing: go to `init-plan`.
   - If exit 0: go to `regress-list`.
2. **install**: Inspect the installer actions, then run them without --dry-run. `rvw doctor --install sim,riscv-gcc,cosim --dry-run --json`
   - If the plan is acceptable: go to `doctor`.
3. **init-plan**: Plan the project files. Read every planned file. `rvw init --isa <ISA> --wire-build --dry-run --json` / MCP `init_scaffold`
   - If exit 2: go to `stop`. Fix the reported input (ISA, sbt project, linker script).
   - If exit 0: go to `init`.
4. **init**: Write rvw.toml, rvw/run.sh and the core playbook. Mapped RV32 req/rsp init with RVFI also writes formal and security bindings. Export fresh RTL with rvw/export-rtl.sh before native consumers. `rvw init --isa <ISA> --wire-build --json` / MCP `init_scaffold`
   - If exit 0: go to `map-adapter`.
5. **map-adapter**: Use init_scaffold with spinal_top, reset_pc, buses and rvfi_prefix for a mapped adapter. Map clock, reset, accepted memory transactions, completion and committed RVFI fields in the core adapter. Follow docs/INTEGRATION_GUIDE.md sections 2 to 4. Review the ISA and memory map. Build a smoke ELF. (manual)
   - If the adapter compiles: go to `smoke`.
6. **smoke**: Build the model and run one ELF through C1. `rvw doctor --smoke-elf <ELF> --smoke-options rvfi --json` / MCP `doctor_smoke`
   - If smoke run fails: go to `test-fails`.
   - If smoke run passes: go to `regress-list`.
7. **regress-list**: List the suites and tests the project declares. `rvw regress list --json` / MCP `regress_list`
   - If no tests: go to `stop`. Build the test ELFs (AGENT_SETUP.md step 6).
   - If tests listed: go to `quick`.
8. **quick**: Run the quick tier with C2 traces. `rvw regress run --tier quick --rvfi-trace --out <RUN> --json` / MCP `regress_run`
   - If a test fails: go to `test-fails`.
   - If all pass: go to `cosim`.
9. **cosim**: Compare one passing C2 trace with Spike. `rvw cosim check --elf <ELF> --trace <RUN>/rvfi.jsonl --json` / MCP `cosim_check`
   - If mismatch: go to `test-fails`.
   - If match: go to `gate`.
10. **gate**: Commit the project files, then judge the committed revision. `rvw regress gate --tier quick --base-rev <REV> --json` / MCP `regress_gate`
   - If NOT ACCEPTED on a dirty tree: go to `gate`. Commit first. A dirty tree cannot earn accept.
   - If inconclusive (exit 3): go to `stop`. Missing evidence. Do not report acceptance.
   - If accept: go to `design-db`.
11. **design-db**: Build the design database for design questions. `rvw query build --json` / MCP `query_build_db`
   - If exit 0: go to `done`.

### A test fails (`test-fails`)

A C1 run or a regression test reports fail, assert, timeout or rvfi_error.

Optional tool set: 57 tools. Load MCP profile `debug` with `rvw_tools_load`. Read the tool names in `rvw agent guide --json`. Use `rvw_tools_describe` before a call.

1. **identity**: Check the source revision, RTL hash, ELF hash, config and seed of the failing run and each cited artifact. Reject stale waves, wrong ELFs and incomplete runs before cause analysis. (manual)
   - If identities match and the failure is reproduced: go to `bundle`.
   - If evidence is missing or inconsistent: go to `stop`. Record the missing evidence. Do not claim a cause or fix.
2. **bundle**: Write the failure report from the failed run directory. `rvw bundle <RUN> --json` / MCP `bundle_make`
   - If the bundle has a C2 trace: go to `cosim`.
   - If no C2 trace: go to `stop`. Rerun the test with --rvfi-trace.
3. **cosim**: Find the first instruction where the core and Spike differ. `rvw cosim check --elf <ELF> --trace <RUN>/rvfi.jsonl --json` / MCP `cosim_check`
   - If mismatch at a retirement: go to `known-bug`.
   - If match but the run failed: go to `wave`. The failure is not architectural: look at the end condition, hang or assertion.
4. **known-bug**: Compare the failure signature with stored bug patterns. `rvw bugmem match <BUNDLE>/report.json` / MCP `bugmem_match`
   - If a high score: go to `drivers`. Check the stored root cause first.
   - If no match: go to `drivers`.
5. **drivers**: Ask what drives the wrong register or signal. `rvw query drivers <SIGNAL> --json` / MCP `query_drivers`
   - If the driver logic is clear: go to `wave`.
6. **wave**: Explain the wrong value at the failing cycle. `rvw wave why <WAVE> <SIGNAL> --at <TIME> --json` / MCP `wave_why`
   - If the cause is a Scala statement: go to `fix`.
   - If no observed statement explains the value: go to `stop`. Keep the cause unknown. Static drivers alone do not prove a dynamic cause.
7. **fix**: Edit the core. Keep the change small. Do not edit the workstation. (manual)
   - If edited: go to `reproduce`.
8. **reproduce**: Rerun the failing test and the required passing tests with the repair. Use a new output directory. Keep all results. `rvw regress run --tier quick --rvfi-trace --out <REPAIRED_RUN> --json` / MCP `regress_run`
   - If the failing test passes and the required passing tests stay passing: go to `gate`.
   - If a test fails: go to `bundle`.
   - If coverage is incomplete: go to `stop`. Do not report a repair.
9. **gate**: Judge the fix on the committed revision. `rvw regress gate --tier quick --base-rev <REV> --json` / MCP `regress_gate`
   - If reject: go to `bundle`.
   - If inconclusive (exit 3): go to `stop`. Do not claim a fix.
   - If accept: go to `done`.
10. **reduce** (optional): Optional: shrink a long failing program before debugging. `rvw reduce <RUN> --json` / MCP `reduce_run`
   - If a smaller reproduction: go to `bundle`.
11. **bisect** (optional): Optional: find the commit that introduced a regression. `rvw bisect <RUN> --good <REV> --json` / MCP `bisect_run`
   - If a first bad commit: go to `drivers`.

### Add coverage (`add-coverage`)

Tests pass, and the next question is what they do not exercise.

Optional tool set: 81 tools. Load MCP profile `verification` with `rvw_tools_load`. Read the tool names in `rvw agent guide --json`. Use `rvw_tools_describe` before a call.

1. **run**: Run the suite with coverage collection. `rvw regress run --tier full --rvfi-trace --out <RUN> --json` / MCP `regress_run`
   - If runs complete: go to `functional`.
2. **functional**: Measure instruction and event coverage from the C2 traces. `rvw cov functional <RUN> --json --out <COV>` / MCP `cov_functional`
   - If holes listed: go to `merge`.
3. **merge**: Merge Verilator coverage into one database. `rvw cov merge <RUN>` / MCP `cov_merge`
   - If a database: go to `report`.
4. **report**: Report RTL holes against Scala source lines. `rvw cov report <COVDB>` / MCP `cov_report`
   - If holes: go to `rank`.
5. **rank**: Rank tests by unique contribution. `rvw cov rank <COVDB> --json` / MCP `cov_rank`
   - If holes remain: go to `closure`.
6. **closure**: Select generated candidates that close holes, then add them as tests. `rvw cov closure <COVDB> --candidates <CANDIDATES>` / MCP `cov_closure`
   - If new tests added: go to `run`.
   - If no candidate closes a hole: go to `done`.

### Prove a property (`prove-property`)

A rule must hold for all inputs within a bound, not only for the tests.

Optional tool set: 74 tools. Load MCP profile `formal` with `rvw_tools_load`. Read the tool names in `rvw agent guide --json`. Use `rvw_tools_describe` before a call.

1. **doctor**: Check the formal tools. `rvw formal doctor --out <OUT> --json` / MCP `formal_doctor`
   - If a solver is missing: go to `stop`. Install with scripts/install.sh --with-formal.
   - If ready: go to `bmc`.
2. **bmc**: Run bounded model checking on the generated or declared checks. `rvw formal bmc --out <OUT> --depth 20 --json` / MCP `formal_bmc`
   - If fail: go to `cex`.
   - If timeout or unknown (exit 3): go to `stop`. Bounded and inconclusive. Not a proof.
   - If pass: go to `riscv`.
3. **riscv** (optional): Optional: run the declared ISA kit. Mapped single-bus Spinal RV32 init supplies the wrapper. Run smoke with --rvfi-trace, then formal isa --trace RUN/rvfi.jsonl. Review latency_measurement, memory assumptions and per-check actions. Exact instruction cycles can need check_options.cycles. Timeouts and machine-state gaps remain inconclusive. `rvw formal isa --trace <TRACE> --out <OUT> --json` / MCP `formal_isa`
   - If fail: go to `cex`.
   - If pass: go to `done`. A bounded pass is not a full ISA proof.
4. **cex**: Explain the counterexample and replay it in simulation. `rvw formal cex --result <OUT> --out <CEX> --json` / MCP `formal_cex`
   - If a real design bug: go to `test-fails`.
   - If an environment assumption is missing: go to `bmc`. Add the assumption and say so in the result.

### Performance question (`performance-question`)

The question is cycles, IPC or where a pipeline stalls.

Optional tool set: 59 tools. Load MCP profile `arch` with `rvw_tools_load`. Read the tool names in `rvw agent guide --json`. Use `rvw_tools_describe` before a call.

1. **konata**: Run the workload with a Konata pipeline log (adapter option --konata). The mapped adapter collects declared probes and converts them. Compare retirement counts with C1 and C2. (manual)
   - If a Konata log: go to `report`.
2. **report**: Report IPC, stalls and the top stall causes. `rvw perf <LOG> --json` / MCP `perf_report`
   - If a change to compare: go to `compare`.
   - If a design-space question: go to `calibrate`.
3. **compare**: Compare two logs or reports from the same workload. `rvw perf compare <A> <B> --json` / MCP `perf_compare`
   - If a difference over tolerance: go to `done`.
4. **calibrate** (optional): Optional: fit the gem5 model to RTL results and explore trends. `rvw arch calibrate --out <OUT> --json` / MCP `arch_calibrate`
   - If a calibrated model: go to `done`. Model results show trends. RTL is the truth.

### SoC and execution infrastructure (`soc-integration`)

A project needs peripheral, lint, multi-run or simulation infrastructure checks.

Optional tool set: 42 tools. Load MCP profile `soc` with `rvw_tools_load`. Read the tool names in `rvw agent guide --json`. Use `rvw_tools_describe` before a call.

1. **review**: Review the project map, adapter and required evidence. Choose the tools listed for this workflow. (manual)
2. **discover**: Describe the selected tool. Load its profile. Keep transport completion separate from verification. MCP `rvw_tools_search`

### Agent evaluation (`agent-evaluation`)

Measure a bounded fixture or native repair task with independent checks.

Optional tool set: 5 tools. Load MCP profile `verification` with `rvw_tools_load`. Read the tool names in `rvw agent guide --json`. Use `rvw_tools_describe` before a call.

1. **select**: Select a task pack and its independent checks. Keep fixture scores separate from native repair evidence. (manual)
2. **inspect**: Describe the benchmark tool before a trial. Record budgets, partial attempts and evidence limits. MCP `rvw_tools_search`

<!-- rvw agent guide: end -->

## Limit ownership

Waiver policy: [#2](https://github.com/riscPrint/risc-v-workstation/issues/2). Integration choice: [#34](https://github.com/riscPrint/risc-v-workstation/issues/34). Backend capabilities: [#116](https://github.com/riscPrint/risc-v-workstation/issues/116).

Retained limit: Agents must preserve adapter refusals and require human review where stated. No invented RVFI, Konata or waiver support is permitted.
