# rvw doctor

Check the workstation and the selected core project:

```sh
rvw doctor --features sim,riscv-gcc,cosim --json
rvw doctor --features all --smoke-elf rvw/out/programs/smoke --json
rvw doctor --install sim,riscv-gcc --dry-run --json
rvw doctor --install sim,riscv-gcc
```

Default features are `sim,riscv-gcc`. `all` adds cosim, formal and gem5.
Sail is checked by the installer when `RVW_SAIL` is set.
Native checks call `scripts/install.sh --check`. The installer owns minimum
versions and warnings against `docs/TOOL_VERSIONS.md`. Doctor preserves its
output and parses version records. Version probes do not qualify a tool flow.
Unrequested backends remain visible as `skipped`. Optional GUI and IDE checks are described below.

`--install FEATURES` is the only installation path. It calls the same script.
The script asks before system packages. `--yes` approves those commands.
`--dry-run` needs `--install` and prints the installer plan without installation.
The diagnostic checks still run. Installation does not reload the parent shell.
Source `env.sh` and repeat doctor after installation.

The project check validates the project and regression tables. An optional
`project.rvw_version` is an exact pin to `rvw --version`. The shared project
loader enforces it for all project commands. Older files without a pin work.
Doctor checks C1 `info`, selected test files (ELF magic only), input declarations
and clean core/workstation commits. It does not claim a gate verdict.

`--smoke-elf` explicitly permits a native build and one run. It uses the default
config, seed 1 and 10000 cycles. It validates the written C1 result and requires
a pass without inconclusive evidence. The ELF hash, seed and cycle limit must
match the request. Synthesized and wall-clock-marked results cannot show readiness.
Temporary run files are removed; the
result stays in doctor JSON. Adapter build caches can change. The adapter owns
native build locks. Without this flag build/run conformance stays inconclusive.
The default smoke check does not test optional artifacts or replay completeness.
Use the explicit options below for bounded C2 and artifact checks.

The `adapter.info` check waits up to `core.startup_s` (at least 30 s) for
`info --json`: a mapped launcher compiles before it answers. A timeout is an error
that names `core.startup_s`.

## C1 option conformance

`--conformance` (with `--smoke-elf`) runs more C1 checks around the same ELF.
Each check is a `conformance.*` record:

| Check | Requirement |
|---|---|
| `build.CONFIG` | Every config in `info --json` builds. |
| `options.recorded` | Seed 7, `--mem-latency 0` and `--max-cycles 100000` are recorded; the run passes and has a replay command. |
| `determinism` | A second identical run has the same status, cycles, instret and `rtl_sha256`. |
| `max_cycles` | A limit below the run's cycle count ends as `timeout`. |
| `run_many` | A two-line manifest runs each line with its own seed and latency. |
| `replay` | The recorded replay command (run from `RVW_HOME`) reproduces status, cycles, instret, seed and identities. |
| `unknown_config` | An unknown config exits 2; a written result says `error`. |
| `bad_elf` | A file that is not an ELF gives `error` and exit 2. |
| `irq_schedule` | `--irq-schedule 1:0x0` passes and is recorded. |
| `no_completion` | A copy of the ELF whose entry instruction is `jal x0, 0` ends as `timeout` with exit 1, never `pass`. |
| `wall_timeout` | When `[core] wall_timeout` is declared: the looping copy with `--wall-timeout 3` ends as a wall-clock timeout. |

`adapter_conformance.requested_checks` reports these selected checks.
`full_c1` stays inconclusive. These checks cover one ELF and the default config's options. They do not check
coverage, Konata or SpinalTrace models, interrupt delivery or other programs.
On the PicoRV32 example all eleven checks are ready.

## Output and exits

`rvw.doctor/1` has `status`, `exit_code`, `checks`, `native`, `native_output`
and `backends`. Each check has a name, status, detail and fix. Native records
retain the evidence and version text. They report installation, version support,
and a match against the checked-in tested version table. A table match is not
a tested flow. Warnings outside the tested table do not
mean unsupported. Installer version refusals are errors. No complete native
combination is qualified by doctor. Skipped backends are outside the request.

Exit 0 means all requested checks are ready. Exit 1 means setup is not ready,
including a skipped build/run conformance check. Exit 2 means invalid options.
Malformed selected projects appear as failed checks with exit 1.
`rvw_doctor` exposes the same diagnostic JSON through MCP. It accepts `project`
and `features`. It cannot install tools or start a smoke build.

## Decisions and limits

Use the existing installer policy. Keep installation explicit. Never infer
adapter conformance from file presence or `info`. Input declarations are claims
that need review; doctor does not prove their completeness. Gate readiness is a
preflight check. Full C1 option conformance and C2 mapping checks remain open.

## Optional backend and trace checks

`--features waves,ide` probes Surfer and VS Code. It records executable paths,
versions and capabilities in JSON. The IDE check also needs the installed
`riscprint.risc-v-workstation` extension and records its version. `all` includes
these backends. Missing requested tools are errors. GUI installation is manual;
`--install` accepts native features only. A version probe does not test a GUI
session. Native backend status reflects the aggregate installer check; individual
version records remain in `native`.

Use an explicit smoke request to check selected C1 artifacts:

```sh
rvw doctor --smoke-elf rvw/out/programs/smoke --smoke-options rvfi,wave,coverage,konata,spinaltrace --json
rvw doctor --smoke-elf rvw/out/programs/smoke --smoke-options rvfi --smoke-platform rvw/cosim.json --json
```

Each selected option reaches build and run. Its artifact must be nonempty and
inside the run directory. Doctor streams C2 through the shared validator. It
checks core, config, ISA and XLEN against adapter info and requires instructions
and a passing end event. Schema validation alone does not establish signal
mapping. Without `--smoke-platform`, mapping stays inconclusive. With that option,
the shared Spike checker must return a complete match with `end_status: pass`.
The platform JSON must describe the actual core and its memory map.

`adapter_conformance` lists the adapter checks and their bounded scope. Full C1
conformance stays inconclusive. This smoke request does not test every config,
run-many, option interactions, wall timeouts, replay or interrupt scheduling.
No native combination was qualified by the fixture tests for this increment.

## Shared tool inventory

`tools.json` is the optional tool inventory. It records pins, command areas,
environment variables, OS recipes and source discovery locations. Linux recipes
are untested. `rvw doctor` prints each tool area, presence and its exact installer
flag. Presence does not establish a working tool flow.

Use `scripts/install.sh --profile minimal|verification|formal|arch|all`.
`minimal` installs the Python CLI. `verification` adds simulation, GCC, Spike,
riscv-dv, cocotb, pyuvm and lint. `formal` adds the base formal tools, rIC3 and
EBMC. `arch` selects architecture tools. `all` selects the inventory except Sail
and the IDE, which need separate setup. Existing `--all` retains its old scope.
Use `--dry-run` before installation. Some flags print manual upstream recipes
and exit nonzero on installation; they do not claim an automated install.
Sail needs `--with-sail --from-bundle`. GUI sessions are not checked.

The inventory also defines presence probes. Managed CIRCT and riscv-dv prefixes,
typed-wave executables and the native OoO library need not be on `PATH`.
Explicit environment selectors are authoritative. Invalid selectors do not fall
back to another executable. Slang and GHDL need their plugin files; a
`yosys-config` executable alone does not establish plugin presence. File presence
still does not establish that a plugin can load into the selected Yosys ABI.

## Per-config C2 conformance

`--conformance --smoke-elf ELF` also requests RVFI for each advertised config.
Each run must pass and write a complete C2 stream with the selected core,
config, ISA and XLEN. Missing, invalid and truncated streams give a named error.
Use `--smoke-options rvfi --smoke-platform PLATFORM` for independent reference
checks. Without a platform, signal mapping stays inconclusive.

`adapter_conformance.requested_checks` reports the selected checks. `full_c1`
and `full_c2` stay inconclusive. One ELF cannot test all option interactions,
interrupt acceptance, memory faults or architectural trace fields. Replay must
also exit successfully; a result file alone cannot establish replay success.

Declare `hdl = "sv"` or `hdl = "vhdl"` in `[project]` for pure HDL projects.
The HDL scaffold writes this field. Doctor marks the JDK, javac and sbt checks
`not_applicable`. Applicable native checks still run. The raw installer output
is retained. An installed version does not prove that the adapter runs.

## MCP workflow calls

MCP `rvw_doctor` stays read-only. Use `doctor_smoke` for the native `rvw doctor --smoke-elf` job. Supply `elf`, the selected project and optional `options` or `platform`.
