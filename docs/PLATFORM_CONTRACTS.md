# Platform contracts

The file formats and commands the phase 1 and 2 tools share. Every tool reads and writes these, so
they can be built in parallel and swapped out later. Change a contract only by editing this file
in the same commit as the code that needs it.

Principles (from `ROADMAP.md`):

- Deterministic work is code with a command-line interface; every command has `--json` output.
  With `--json`, stdout is exactly one JSON document (on failure, the command's error document, as
  `rvw cov` and `rvw cosim` write, or nothing); progress and human messages go to stderr.
  The document is serialized in full before it is written; bundle, reduce, bisect, cov, regress,
  wave and perf also refuse NaN and Infinity (exit 2). `rvw/tests/test_json_stdout.py` runs every
  subcommand that has `--json` (error paths, and bundle/reduce/bisect on a fake-adapter failure).
  Agents reach the same commands through the MCP server (`rvw mcp`).
- Reuse open-source tools (Verilator, Spike, Sail, SymbiYosys, Yosys, mcy, SpinalTrace, Surfer) and
  write only what they lack.
- Generic first. Anything specific to one core (signal names, configs, test lists, paths) lives in
  an adapter or a config file, never in the generic code. BOOM is the first adapter.
- Every result records how to reproduce it: source revision, config, seed, ELF hash, tool versions,
  and a replay command.

Coverage proof exclusions use `rvw.coverage-exclusions/7`. The file records `config` and
`config_sha256`, `work_dir`, `timeout`, and an `elaboration` snapshot with `path` and `sha256`,
in addition to input resolution records and solver jobs. Apply binds every excluded point to
its reviewed plan mapping, generated property, SBY job and recomputed cone cover. It requires
a passing single-clock guard and synchronous state controls. Apply rechecks every module of the
saved raw netlist. Asynchronous reset/set/clear/load controls, latches and unsupported state
cells refuse exclusions. Memory asynchronous resets must be tied inactive. Older exclusion
schemas, including `/6`, require a proof rerun. `source_snapshot` records the path and hash of
one manifest captured before any front end runs. The manifest binds original source and include
resolution records, raw copies and frozen RTL with redirected literal includes. The guard and
every sanity, cover, proof and cone job read this snapshot. Each job and point records its
`snapshot_sha256`; each front end records `input_hashes`, including its actual RTL and harness
copies. Apply checks these copies against the snapshot and rebuilds generated job text from it.
Missing, changed or mixed snapshot evidence refuses exclusions. The files are local
evidence; they are not signed certificates. See `rvw/src/rvw/cov/README.md` for the proof limits.

Coverage test selection (`rvw.coverage-select/1`) keeps the requested range in `diff` and records
the full compared commit IDs in `base_revision` and `head_revision`. Each distinct ref is resolved
once. Both Git diffs use those IDs. Different refs are resolved in sequence; this does not claim
an atomic snapshot of all refs. Later branch moves do not change the recorded selection.

### C2 writer state for live native checkpoints

`rvw.rvfi-writer/1` is the `rvfi` component of a native checkpoint. It contains
header, base64 prefix, SHA-256, decimal byte position, decimal counters
`records`, `traps`, `gaps`, `next_order`, `last_cycle`, and `pending`.
`pending` is null or `[cycle, cause, intr]`, with decimal strings for integers.
The prefix is flushed before capture. Restore validates it before output opens.
The outer native checkpoint binds the writer to model and harness identity.
A writer snapshot alone does not restore a model or establish replay equality.

### Project native snapshot port control

`rvw.snapshot-adapter/1` supplies a trusted project Python `module`, optional
`options`, and ordered `identity_files` lists for the four native identities.
Hash each identity as concatenated 8-byte big-endian lengths and file contents.
The harness digest additionally binds the port source and exact manifest bytes.
The port implements native snapshot methods, `advance(unit, target)`,
`position(unit)`, `finish(out)` and `close()`. Advancement must stop at the
requested cycle or retired-instruction count. An inexact boundary is refused.
Restore uses a fresh port. `restored` is not an equivalence verdict. Exact C2
suffix comparison requires matching prefixes and complete end events.

### Project architectural injection

`rvw.arch-injection/1` and `rvw.arch-map/1` are project-port documents, not the
proposed qualified Spike interchange format. Their exact fields and port calls
are defined in `rvw/src/rvw/sim/INJECTION.md`. Both name the same profile. The
profile declares the complete CSR and RAM inventory. The implementation checks
widths, x0, unique bindings, exact CSR sets and non-overlapping memory images.
A successful `injected` result means all mapped registers and memory passed
readback before fetch release. It is not a C1 pass or C4 accept. Bare M mode
and no active devices, interrupts or hidden execution state are required.
Raw FPR bits are preserved. Native FP qualification remains required.

### Reverse execution through native checkpoints

`sim_reverse_step` and `rvw sim reverse-step` validate every supplied native
checkpoint against current identities. Each must have `counters.instructions`.
Select the greatest count at or before the target. Restore into a fresh port,
then call `replay_to_instruction(target, max_seconds=...)`. The port must cancel
native work on timeout. The reached count must equal the target before saving.
The result lists history, selected count, target and time budget. `saved` means
a stopped checkpoint exists. It does not mean native replay qualification or
ISA correctness. A target before available history is refused.

### Captured historical adapter selection

An optional captured `.rvw-adapters.json` uses `rvw.adapter-versions/1`.
Exact revision mappings take precedence over a captured version marker.
Only adapter API 1 is supported. Its command uses C1 options. Paths stay inside
the captured core tree. Selection pins the interpreter under C8 and adds
`adapter_selection` to source identity. It records API, version, revision,
manifest SHA-256 and executable SHA-256. Unsupported revisions produce no run
and remain skipped bisect evidence. See `rvw/src/rvw/runs/ADAPTERS.md` for the
manifest and the current debug-launch-only integration boundary.

### Native project device ABI

Shared libraries export `rvw_device_plugin_v1`, returning `DeviceApiV1` with
ABI number 1 and all callbacks. Calls are serialized at stopped cycle boundaries.
Create takes project JSON and a seed. MMIO uses device-relative byte addresses,
1 to 8 byte little-endian values and byte masks. Tick takes absolute cycles;
project data declares cycle period and interrupt routing. Nonzero status is an
error. Snapshot size zero declares non-restorable effects. Store versioned
payloads under native envelope devices and bind library/configuration hashes.
DPI-C wrappers never propagate C++ exceptions. Null handles and nonzero status
must stop the run. Device maps, Linux behavior and TLM timing are not inferred.
See `RiscvSim/src/main/cpp/DEVICES.md` for exact ABI and DPI declarations.

### Simulation cost report

`rvw.sim-profile/1` reports C1 file hashes, native identities, terminal status,
recorded elaboration/native-setup/model-compile/execution times, counters and
derived throughput. Missing measurements are null. It does not infer separate
Scala compile time or process-tree RSS. `status: reported` is not qualification.
`profile_applied: false` states that proposed flag profiles were not executed
and do not classify the recorded runs. Tool statuses reflect PATH lookup only.
Unimplemented hierarchy/PGO/Arcilator paths remain explicit unsupported entries.

### External gate-netlist and SDF replay interface

`rvw.timing-request/1` names a netlist, SDF, cell libraries, top, cell inventory,
delay constructs, timing checks, unknown behavior and min/typ/max corner.
`rvw.timing-capabilities/1` declares simulator/version, supported inventories,
unknown behavior and corners. `rvw.timing-handoff/1` reports captured input
hashes and declarations. `declared_compatible` means interface readiness only.
It does not establish annotation, complete cell coverage or physical signoff.
Unsupported requested cells, delays, checks, corners or unknown behavior fail.

An external native `TimingPort` consumes captured input bytes and must refuse
ignored annotation. It returns a native C1 outcome. A compile-only result is
not a run outcome. `physical_signoff` remains false. The simulation README
lists exact fields. No standard-cell library or native gate backend is bundled.

## Layout

| Path | What | Language |
|---|---|---|
| `rvw/` | The `rvw` command: one Python package, a subpackage per tool (`rvw/src/rvw/<tool>/`, with `cli.py` defining `register(subparsers)`). Run with `rvw/.venv/bin/rvw` after `cd rvw && uv venv && uv pip install -e '.[dev]'`. Python ≥ 3.11, standard library first. | Python |
| `RiscvSim/` | Generic Spinal simulation pieces for any RISC-V core with RVFI (trace writer, tohost, ELF loading, the run contract's command line), and `RiscvSim/boom/`, BOOM's adapter. | Scala |
| `SpinalChecks/` | Assertions Spinal generates while elaborating, and the simulation-to-formal flow. | Scala, shell |
| `SpinalKonata/` | Generic Konata pipeline-trace library for Spinal designs. | Scala |
| `SpinalDB/` | One extraction pass over an elaborated Spinal design: the design database. | Scala |
| `scripts/with-lock.sh` | Machine-wide lock for heavy jobs (see Resources); a wrapper around `rvw/src/rvw/common/lock.py`. | shell |

## Project configuration (`rvw.project/1`)

Install the workstation once. Keep each core project in its own repository. Neither
repository contains the other. See [BRING_YOUR_OWN_CORE.md](BRING_YOUR_OWN_CORE.md).

`rvw` finds the nearest `rvw.toml` by walking up from the current directory.
`--project PATH` selects a file or a directory containing `rvw.toml`. It works before
or after a subcommand. `RVW_PROJECT` has the same meaning. Selection order is an
explicit project, `RVW_PROJECT`, then discovery. A missing or invalid selected file
is an error. There is no fallback to an example after a selection error.

An explicit `--core NAME` or legacy TOML path selects the shipped core config instead
of project discovery. Do not combine it with `--project`. `--core boom` still selects
`rvw/configs/boom.toml`. `RVW_CORE` remains a regression fallback when no project is
selected. MCP tools for regress, cosim, query, formal and debug accept `project`; server
`RVW_PROJECT` and discovery also apply. Each call resolves its own selection without
changing the server environment. `rvw mcp --project PATH` binds the server default.
A per-call `project` or explicit legacy `core` overrides that default.

The project file reuses the existing regression `[core]`, `[suites]` and `[tiers]`
tables. `[core].name` and `[core].adapter` are required for regression. All paths are
relative to the project file directory, including paths in optional tool tables.
Strings accept `${VAR}` and `${VAR:-default}`. Command lists use the existing adapter
rule: prefix relative file arguments with `./` or `../`; a bare executable uses PATH.
`[project]` is optional. If present, its only fields are `schema = "rvw.project/1"`
and `root`, which defaults to the project file directory. Project history is
filtered by `core.name`. `core.source_repo` defaults
to that root. Gates judge commits in this source repository. The adapter must honor
`core.source_env` to select base and candidate source trees. Project adapters can stay
at a fixed path while the selected source revision changes.

Optional tables have these exact fields. Unknown fields and unsupported schemas are
errors. Tool input paths must exist when the command consumes them.

| Table | Fields | Meaning |
|---|---|---|
| `arch` | `description`, `sources`, `benchmarks` | Paths to the core description JSON, riscv-tests benchmark sources, and native ELF build directory. See C9. |
| `cosim` | `platform` | Platform JSON used unless `--platform` is explicit. A selected project with no platform is an error for cosim. |
| `debug` | `config` | Debug TOML for bundle, reduce and bisect. It must describe the recorded core. |
| `debug_module` | `profile` | Debug profile (`rvw.debug-profile/1`) for `rvw debug suite` and `rvw debug serve`. See "C1 debug transport". |
| `checks` | `settings`, `waivers` | Project adapter settings and waiver file paths. Their format belongs to the adapter. The launcher must consume them. |
| `query` | `build`, `db` | Build command list and output database path. `rvw query build` calls `build CONFIG OUT`; `--config` and `--out` override the core default and `db`. Query reads use `db` unless `--db` is explicit. |
| `riscv_formal` | `root`, `wrapper`, `verilog`, `isa`, `nret`, `checks`, `depth`, `solver`, `defines`, `ports`, `check_options`, `instruction_models` | Bounded native riscv-formal settings. See `rvw/src/rvw/formal/README.md`. NRET 1 only; unsupported settings are refused. |
| `formal` | `verilog`, `top`, `checks`, `clock`, `reset` | Defaults for existing formal arguments. `verilog` is a nonempty path list. Explicit arguments override these fields. No proof limits change. |

The project file and expanded environment are captured before parsing and execution.
Regression includes declared cosim, debug and checks files in its input capture and
cache keys. The adapter still declares all other result-changing files, tools and
environment through `cache_paths`, `input_tools`, `input_commands` and `input_env`.
A project file does not imply complete adapter dependencies. `input_complete=true`
is the same explicit completeness claim as C8. Missing declared inputs refuse reuse.
Project config files do not replace source commit identity or generated RTL identity.
Adding only project files can change source commits while leaving `rtl_sha256` equal.

Scala adapters can use sbt `ProjectRef` dependencies on workstation library projects
through an absolute `RVW_HOME`. Keep core adapter sources in the core repository.
Use offline sbt after toolchain dependencies are installed. Source-directory settings
in reusable builds must resolve from `baseDirectory.value`, not the caller's cwd.

### Coverage counter interchange

`rvw cov exchange` and `cov_exchange` implement the declared UCIS 1.0 counter
profile `rvw-counter-profile/1`. Every original counter is a singleton ordinal
coverpoint bin. `rvw.counter` preserves its native kind, original bin tuple,
source link and exclusion metadata. `rvw.context` binds sources and plan/native
context. Native UCIS metric tags and arbitrary vendor profiles are unsupported.
Import returns `rvw.coverage-exchange/1`: context, rows with id/kind/count/metadata,
status `reported`, and `proof_exclusions_verified=false`. Unknown XML structures
are errors. Compatible merges require identical context and bin semantics.
The optional input `rvw.assertion-counters/1` has a design hash and property
id/source/count dictionaries. Counters alone grant no proof or non-vacuity.
Native DAT exports retain exact point keys. LCOV uses `verilator_coverage`.
Each export includes a `.rvw.json` metadata sidecar. Reports use
`rvw.coverage-export/1`, with destination/metadata paths and hashes. Counter
transport never authorizes a proof exclusion or C4 accept.

### Encoded coverage field domains

Pinned ISA plans enumerate encoded register fields and aliases, vector register
fields, scalar rounding modes, atomic ordering bits and bounded vector control
fields using the captured argument widths. All raw rounding encodings remain
in the denominator. The bins do not classify runtime legality. Scalar integer
operand-value classes also cover A, Zba, Zbb, Zbc, Zbs and Zicond source files.
FP/vector data never use integer RVFI operand values. Explicit reviewed semantic
forms and cross catalogs retain their existing legality and availability rules.
Plan fingerprints change when the expected field domains change.

### Measured RTL recipe feedback

Stimulus-loop settings may bind `rtl_plan` and `recipes` together. Recipes use
`rvw.event-recipes/1`, the exact sampling `plan_id`, generated RTL `design` hash,
and a list of generator `goal` to RTL `targets` mappings. Generic code contains
no core signal paths. The UCB controller records new observed events separately
from ISA bins. It accepts only complete `rtl_samples` artifacts from unique
C1 ELF results that passed strict full Spike qualification. The C1 `rtl_sha256`
must match the recipe and sampling plan. C1 `details.rtl_samples` must contain
exactly `elf_sha256`, `rvfi_sha256`, `samples_sha256`, `plan_id` and `rtl_sha256`,
matching that run and its attached files. A missing or stale receipt earns none. Reused sample hashes cannot earn reward.
Missing hooks and stale, incomplete or incompatible samples are unsupported.
Guidance history and sample hashes persist in the checked resume state. This
bounded policy grants no reachability proof or measured performance improvement.

### Bounded sequence candidates

`rvw cov actions` and `cov_actions` emit `rvw.sequence-candidate/1` reports.
The report contains a goal, kind, distance, ordered action graph, preconditions,
exact instruction words, source hash and payload symbols. Memory requires an
explicit writable program-data declaration. Generation grants no measured hits.
The stimulus loop accepts optional `sequences` and `memory` settings. It retains
all declared pairs in the denominator. The full C1/Spike verifier checks payload
bytes and samples the existing retirement observer. Each action retires once.
Retirement pairs remain separate from pipeline hazard and stall evidence.

### Bounded candidate execution loop

`rvw cov campaign` and `cov_campaign` use `rvw.stimulus-loop/1` settings and
reports. Settings and limits are defined in `rvw/src/rvw/cov/CAMPAIGN.md`.
The controller selects remaining integer profile holes. Only conclusive C1 pass
and complete strict Spike comparison can earn observations. Payload symbols and
bytes bind sampling to the compiled ELF. Functional report configuration includes
`sampling_policy=payload-pc-v1`; each trace records its ELF-bound payload region.
These reports cannot merge with full-trace reports. Setup and termination earn
no coverage. Generated, unsupported, UNSAT, timeout, compile errors, missing
traces, mismatches, misses and measured hits remain separate attempt outcomes.
Reports retain full-plan and supported denominators, input and artifact hashes,
wall time, controller CPU and reaped-child CPU. Descendant completeness is not
qualified. Rate stays null. No paired random comparison or C4 acceptance follows.
State uses immutable C8 generations. Resume pins one generation and checks all
recorded attempt artifacts and declared input identities. Raw attempts remain
outside the state generation. Transitive dependency closure is not established.

### Bounded ISA candidate report

`rvw cov generate` and `cov_generate` return `rvw.stimulus-candidate/1`.
Inputs are a pinned ISA manifest, its opcode source root, a semantic goal ID,
three project-owned writable integer registers, a uint32 seed, a solver limit
in milliseconds and a new output directory. Goal IDs use the closure reader's
`group:JSON-array` syntax. The backend is `z3-solver==4.13.4.0`.

Statuses are `generated`, `unsupported`, `unsat`, `timeout` and `inconclusive`.
A generated result binds plan, SMT constraints and source hashes. It includes
the solved instruction and source values. The saved source has one payload
word and start/end symbols. The report records the full plan bin count and
the 170-bin supported profile separately. `measured_hits` is always empty.
Unsupported goals and missing backends do not create an output directory.
UNSAT applies only to the declared instruction template and register resources.
It cannot exclude a bin from coverage. A candidate report grants no C1 pass,
reference match, gate acceptance or measured closure result.


## C1. Run contract (core adapter)

RiscvSim supports the optional `--spinaltrace` model flag on `build`, `run`,
`run-many` and `identity`. Its model identity includes `spinaltrace` (default
false), and replay preserves it. A supported traced model emits a `pdg` artifact
from its RTL elaboration. `--wave` records the instrumented wave. A missing
requested trace model is an error; it must not yield computed-cause claims.

Each core provides one adapter command. BOOM's is `RiscvSim/boom/run.sh`.

```
<adapter> build --config NAME [--rvfi] [--wave] [--coverage] [--konata] [--json]
<adapter> run   --elf PATH --out DIR [--config NAME] [--seed N] [--max-cycles N] [--mem-latency N]
                [--rvfi-trace] [--wave [--wave-from CYCLE] [--wave-to CYCLE]] [--konata] [--coverage]
<adapter> run-many --manifest jobs.jsonl [--jobs N]   # one JVM, one compiled model, many ELFs
<adapter> identity                                     # optional: what results depend on (see below)
```

`run-many` takes one JSON object per line with the same keys as `run`'s options (`elf`, `out`,
`config`, `seed`, ...), written with underscores or dashes (`max_cycles` or `max-cycles`). A missing seed means "pick one and record it". `--mem-latency` absent means
randomized memory timing; present means fixed latency.

Optional `--irq-schedule '1:0x0,1000:0x80,12000:0x0'` (manifest
`irq_schedule`, a string) selects full input levels in `mip` bit positions.
Cycles must strictly increase, start at 1, and finish before `max_cycles`.
Adapters reject unsupported input bits. A selected schedule replaces software device
levels. Without a schedule, existing device behavior stays active. At sampled edge N,
the adapter drives the new levels for the next edge. C2 records the actual driven
levels at N. Interrupt acceptance at N is not evidence for the new levels.
C1 `irq_schedule` stores the normalized string, or null. Replay carries the same string.
The schedule is inline, so replay needs no separate stimulus file.

Optional, declared in the core config of `rvw regress` (`[core] identity = true`, `wall_timeout = true`):

- `identity` prints text that changes whenever anything besides the ELF and the run options can
  change a result (toolchain versions, adapter and core source keys). `rvw regress` adds its hash
  to the result cache and resume keys; if it fails, nothing is reused.
- `wall_timeout` (manifest key; `run --wall-timeout S`): a wall-clock limit in seconds per run.
  The adapter ends the run as `timeout` with `"wall_clock_timeout": true`, so a hung test does
  not hold the batch. It writes that result within max(2 s, 10%) of the limit (RiscvSim abandons
  a simulation that does not stop); `rvw regress` stops a batch only after `wall_timeout` + 10 s +
  20% without a new result.

`run` writes `DIR/result.json`:

```json
{
  "schema": "rvw.run/1",
  "core": "boom", "config": "small",
  "elf": "/abs/path/rv64ui-p-add", "elf_sha256": "…", "rtl_sha256": "…",
  "seed": 12345, "max_cycles": 200000, "mem_latency": null,
  "status": "pass | fail | timeout | assert | rvfi_error | error",
  "fail_code": null,
  "message": "assertion text, exception message, or null",
  "cycles": 1234, "instret": 456,
  "wall_s": 3.2,
  "source": {"core_repo": "/abs/path", "core_rev": "<short commit>", "core_dirty": false,
             "core_rev_full": "<full commit>",
             "tools_repo": "/abs/path", "tools_rev": "<full commit>", "tools_dirty": false},
  "tools": {"verilator": "5.049", "spinalhdl": "1.15.0"},
  "artifacts": {"log": "run.log", "rvfi_trace": "rvfi.jsonl", "wave": "wave.vcd",
                "konata": "konata.log", "coverage": "coverage.dat"},
  "replay": "RiscvSim/boom/run.sh run --elf … --seed 12345 --config small --out …"
}
```

`elf_sha256` identifies the bytes loaded by this run. RiscvSim reads the ELF once before
model compilation and passes the captured input as `RunContext.elf`. Adapters use that input
for loading, symbols and disassembly. They must not reopen the original `elf` path. That path
remains metadata and the input path for a later replay; a replay needs the same ELF bytes to
reproduce the run.

RiscvSim also records optional `tools.native_build`: the native cache namespace and SHA-256,
effective native environment values, an inherited environment digest and its ignored keys, tool paths,
executable hashes and full versions, and `cache_enabled` with `cache_disabled_reasons`.
The launcher records these values once before compilation. `identity` uses the same collector
as model compilation. An unknown native input disables caching and result reuse. Replay restores
the saved native environment and unsets absent values. It uses the current launcher's make wrapper.
Replay needs the same installed tools and input bytes.

Optional `"metrics"`: an object of named numbers measured by the run. Programs that store
region-of-interest counters to a `bench_stats` symbol (two 64-bit words: cycles, then instret, as
riscv-tests benchmarks do) report them as `metrics.roi_cycles` and `metrics.roi_instret`; `cycles`
and `instret` stay whole-program. `rvw regress` uses the ROI values for benchmark performance.

`result.json` appears atomically (written elsewhere and renamed). `"wall_clock_timeout": true`
marks a `timeout` of the wall clock, not of `max_cycles`: it says nothing about the core.
Optional `"inconclusive": "<reason>"` marks a result the adapter cannot vouch for, e.g. a failure
it could not attribute to this run (RiscvSim: an `assert` printed while other simulations ran,
pending or failing its serial rerun; RiscvSim's `details.serial_rerun.attributed: false` and a
`details.concurrent` `assert`/`rvfi_error` without `serial_rerun` are read the same way).
Debug reruns also require the returned `elf_sha256` to match the requested ELF bytes.
A missing or different hash makes the attempt inconclusive.
Debug reruns check each explicitly requested C1 seed, config, max_cycles and mem_latency
against the returned result. A missing or different value marks the attempt inconclusive.
It cannot reproduce or rule out the requested failure.
A C1 result is evidence about the core only when `rvw.results.inconclusive_cause` finds nothing:
not `inconclusive`, not status `error` (the harness could not run the test), not `synthesized`
(rvw wrote it), not a wall-clock timeout. Every reader uses that one rule (regress resume, cache
and compare; reduce, bisect and bundle): such a result neither reproduces nor rules out a failure.
The BOOM launcher records full source commit IDs and dirty flags at start. `rtl_sha256`
identifies its generated Verilog, including enabled probes and the RVFI monitor. The harness
identity is `source.tools_rev` plus `source.tools_dirty`. The native identity is
`tools.native_build.sha256`. Direct JVM launches lack the launcher's native binding and remain
inconclusive. The replay path is relative to the tools checkout.

Artifact paths are relative to `DIR`; absent artifacts are omitted. `status` meanings: `fail` the
program wrote an odd value other than 1 to `tohost` (`fail_code` is the value >> 1); `assert` an
HDL assertion or simulation exception; `rvfi_error` the riscv-formal monitor flagged an error;
`error` the harness itself failed (bad ELF, build failure).

C1 `run` and `run-many` exit 2 for `status: error`, including input errors before
model compilation. This takes priority over missing-evidence markers such as missing RTL.
Otherwise they exit 3 for an explicit `inconclusive` marker, 0 when all runs pass,
and 1 for other run failures. Error results remain unsuitable as core evidence.

Optional `run-many --persistent --jobs 1` uses the serial fresh-instance server.
Adapters must declare fresh native and harness state for each request. C1
`execution_mode` is `server`; `details.simulation_session` records session UUID,
model run number and reset policy. RTL and native hashes still identify the model.
An abandoned worker stops the batch before later requests and forces exit 2,
including when no result exists for those requests. This is model reuse, not
result reuse. Regression `[core] persistent = true` selects this mode and skips
the separate pre-build process. Each process has a serial timeout budget.
Regression can start several isolated processes.

Cosim reproduction metadata records `tools.spike_build.spike_identity` with the
installed reference's version, source revision when supplied, and origin. The same
label is bound into `build_inputs`. Source installs supply `share/rvw/spike-source.json`;
Homebrew builds capture their receipt and available SBOM. An unlabelled external
build has null version/revision. These labels are package provenance, not binary
attestation. The captured library and shim hashes identify the executed bytes.
C1 from an RTL-only run does not imply that Spike ran.

### Native checkpoint envelope (`rvw.native-checkpoint/1`)

This adapter API format is distinct from from-reset replay descriptors and
portable architectural checkpoints. No bundled adapter currently provides the
required live native port.

The JSON envelope contains `payload` and `sha256`. The digest covers UTF-8 JSON
of the payload with sorted keys, compact separators and no non-finite numbers.
The payload contains `schema`, `identity`, `state` and `native`. `native` is
nonempty strict base64. `identity` contains exactly four lowercase SHA-256
fields: `rtl`, `native_build`, `harness`, `stimulus`. All must equal the expected
restoring instance identities.

`state` contains exactly `scheduler`, `clock`, `memory`, `pending`, `rng`,
`devices`, `interrupts`, `monitors`, `rvfi`, `stimulus` and `counters`. Each adapter defines
and validates its component representations. All components must be present
and non-null. Empty inventories must be explicit. The native build and harness
identities bind these representations to their implementation.

Save and restore require a stopped quiescent instance and an empty external
effects inventory. Validate bytes, identity and adapter state before mutation.
Discard an instance after a failed restore. A restored snapshot is not an
equivalence verdict. Qualification needs a fresh-process native restore and
complete C2 suffix and terminal-counter comparison with uninterrupted execution.

## C2. RVFI trace (`rvfi.jsonl`)

First line is a header, then one object per retired instruction in `order`:

```json
{"schema": "rvw.rvfi/1", "xlen": 64, "isa": "rv64imafdc_zicsr_zifencei", "core": "boom", "config": "small", "elf": "…"}
{"order": 0, "cycle": 52, "pc": "0x80000000", "pc_next": "0x80000004", "insn": "0x00000297",
 "mode": 3, "trap": false, "intr": false, "halt": false,
 "rs1": 0, "rs1_rdata": "0x0", "rs2": 0, "rs2_rdata": "0x0", "rd": 5, "rd_wdata": "0x80000000",
 "mem_addr": "0x0", "mem_rmask": 0, "mem_wmask": 0, "mem_rdata": "0x0", "mem_wdata": "0x0",
 "mem_fault": false}
```

Field meanings follow riscv-formal's RVFI spec (`rd` 0 means no write; `insn` for compressed
instructions holds the 16-bit encoding). Values are `"0x…"` lowercase hex strings. Optional extra
records, distinguished by an `"event"` key:
`{"event": "trap", "cycle": N, "cause": "0x…", "tval": "0x…", "intr": bool}` and
`{"event": "end", "cycle": N, "status": "pass"}`.
A trap event's `cause` and `tval` are the values the core writes to `xcause`/`xtval` (BOOM
writes 0 for illegal instructions, as the spec allows; Spike writes the instruction bits). An
adapter reads them from the core, not from its own decoding (BOOM's adapter reads the CSR
file for ECALL/EBREAK). `cycle` never decreases from one line to the next, events included: a
trap event whose `tval` arrives late is written before the next cycle's records.
`{"event": "irq", "cycle": N, "levels": "0x…"}` (optional) gives the levels of the interrupt
inputs the harness drives, in their `mip` bit positions (MSIP 3, MTIP 7, SEIP 9, MEIP 11), from
cycle `N` on. An adapter that writes these events writes one with the first sampled cycle and one
at every change; records of cycle `N` may come before it. `rvw cosim` takes an interrupt bit of a
`mip`/`sip` read from the core only with such evidence (see `rvw/src/rvw/cosim/README.md`).
Tools that report C2 values (for example `rvw cosim` mismatch JSON) use the same hex strings.

### Cosim platform policy audit

Cosim platform JSON permits the optional schema `rvw.cosim-platform/1`.
Unknown top-level settings and other schema values are errors. The existing
schema-free platform format remains supported. `rvw.cosim/1` results include
`platform_policy` with the selected privilege, misaligned, endian, absent-PMP
and ECALL choices. `applied_masks` contains objects with `reason`, `csr` and
`mask`. The CSR and mask are hex strings. Each entry is the union of masks
actually used for that reason and CSR across the compared trace. This list
is independent of the bounded recent synchronization history.

The cosim platform JSON declares `privilege_modes`, `misaligned` outcomes,
`endianness`, `absent_pmp_csrs` and `ecall_tval`. Missing keys retain the legacy
MSU, alignment-trap, little-endian, absent-PMP-trap and ECALL-zero defaults.
Unsupported policies must be refused. These settings do not permit arbitrary
trace values or broad CSR masks. See the exact settings and the
[C2/Spike/Sail comparison matrix](../Cosim/README.md#architectural-comparison-coverage).
### C2 version 2 (`rvw.rvfi/2`)

One schema supports `state`, `multihart`, `csr` and `fault` capabilities. A capability
can be used alone. `multihart` requires the `harts` header and the per-hart
records below. `state` requires the FP fields below on each retirement and
supports CSR snapshots and fault fields. The optional `csr` capability requires
C2/2 and a nonempty `csr_snapshot` set. It compares declared CSR state without
claiming FP observations. It retains all scalar instruction fields. It does
not permit FP fields unless `state` is also declared. Capabilities can combine.
For existing v2 producers, omitted capabilities mean `multihart` when `harts`
is present, and `state` otherwise. V1 keeps its existing scope. Missing state
in v1 or multi-hart-only traces is unavailable evidence, never a state match.
Single-hart Spike/Sail comparison refuses multi-hart traces before comparison.

#### State fields

The state capability retains version 1 instruction fields and adds:
`fd_valid` (boolean), `fd` (0..31), `fd_wdata` (64-bit hex), `fflags` (5-bit hex),
and `fcsr` (8-bit hex). `fd_valid` distinguishes no write from a write to f0.
`fd_wdata` contains the raw architectural FLEN=64 bits, including NaN boxing.
Do not canonicalize NaNs or change payload bits. When `fd_valid` is false,
`fd` and `fd_wdata` are not observations. `fflags` and `fcsr` are full state
immediately after this instruction, including synchronous trap entry.
The low five bits of `fcsr` must equal `fflags`. `fcsr` includes `frm`.
The checker compares these fields exactly. A backend without these observations
must refuse version 2 comparison. Version 1 keeps its integer-only scope.
Version 2 does not imply that a DUT adapter exports these fields.
FLEN above 64 remains unsupported. Multi-hart reference comparison is unsupported.

PMP platform settings: `pmp_granularity` is the minimum region size in bytes.
It defaults to 4 and must be a power of two. Spike applies it through
`cfg.pmpgranularity`. PMP entry priority follows the ISA: the lowest matching
entry wins. This priority is fixed and cannot be changed by a platform setting.
Sail refuses non-default grain until its configuration mapping is implemented.

The C2/2 `fault` capability allows scalar fault-access comparison without FP
fields. Missing FP state makes no FP claim.

Sail scalar fault observations use its independent instruction operands and
memory log. Within one virtual page, logged physical fragment offsets map to
attempted bytes. Completed masks and data include only logged fragments.
Overlapping fragments and split-page effects are refused. This does not add
partial-effect observation to Spike. A missing backend observation remains
an error. Synthetic fragments validate the adapter, not native partial faults.

C2 version 2 can declare `"csr_snapshot": ["0x300", "0x341"]` in its header.
Each instruction must then carry `"csr_state": {"0x300": "0x…", "0x341": "0x…"}`.
The key set must equal the declared set. Values are full XLEN state after the
instruction and synchronous trap entry, before the next reference step.
These snapshots check effects even if software never reads the CSR. They do
not assert that every changed CSR was captured. No CSR snapshot uses read
synchronization or a platform mask. Counters and external pending state can
differ with timing; include them only when the adapter can supply the same
architectural observation point. An unavailable backend CSR is an error.

Version 2 trap instructions can include `fault_access` with exactly these fields:
`addr` (XLEN hex virtual start address, access-relative), `rmask`, `wmask`,
`completed_rmask`, `completed_wmask` (integer byte masks), `rdata`, `wdata`.
Attempted masks describe bytes requested by the instruction, not successful
transfers. Completed masks must be subsets of the respective attempted masks.
Data is XLEN hex with valid bytes only in completed lanes. With no completed
lanes, data must be JSON null. Unknown data must never come from the reference.
Legacy `mem_*` fields still describe completed effects. A missing fault record
makes no claim about attempted accesses. This extension describes data accesses;
instruction fetch faults still use trap cause/tval.

Spike checks zero-completion scalar load/store attempts, compressed accesses
and LR/SC/AMOs. It computes address and width from its own instruction and
pre-step registers, then checks the synchronous cause. Reserved encodings,
partial effects on either side and Sail fault-attempt observations are refused. Such a refusal is not a match.
Partial records define validity but do not establish checker support.
The Spike shim refuses any trap with logged memory effects. It does not
discard those logs and infer zero completion. `state_coverage` includes
`csr_snapshot_steps` and `fault_access_steps`, the number of reference
observations checked. These counts include a mismatching observation.
A header declaration alone does not increase either count.


The cosim result's `state_coverage` gives the input `trace_schema`, whether FP
fields were compared (`fp`), and the declared `csr_snapshot` address list.
The optional live integration API uses the same C2 fields and synchronization
rules as offline checking. Its result adds `mode: online`,
`consumed_trace_prefix_sha256` and `consumed_trace_lines`. This digest covers
only consumed UTF-8 JSONL lines, including one-cycle lookahead. It is not a
full trace identity. Input/reference identities stay in `reproduction`.
An incomplete live stream returns `inconclusive`, with cause
`live_trace_incomplete`. The API stops the producer on a checked divergence.


### C1 debug transport (optional)

A core adapter can expose its simulated Debug Module in one of two ways.
The debug profile (`rvw.debug-profile/1`, see `rvw/src/rvw/debug/README.md`)
names the way in `[transport]`.

- `remote_bitbang`: the simulation contains a JTAG DTM and serves OpenOCD's
  remote_bitbang protocol on a TCP port. rvw drives TCK/TMS/TDI and reads TDO.
- `dmi_process`: the profile gives a command. rvw starts it and speaks a line
  protocol on its standard input and output. The adapter prints `ready ABITS`
  first. rvw then writes `r ADDR`, `w ADDR DATA`, `t CYCLES` or `q`. The adapter
  answers each `r` or `w` with `ok DATA`, `busy` or `fail`, and each `t` with
  `ok 0x0` after it advances the simulation by that many cycles. Values are
  hexadecimal with a `0x` prefix. `busy` means the request did not start; rvw
  sends it again. `fail` is a DMI failure (status 2). Diagnostics go to stderr.

`rvw debug serve` wraps a `dmi_process` bus in the reference JTAG DTM, so
OpenOCD can attach to a core that has only a DMI bus. A transport response is
not evidence that a debug operation worked. The campaigns check effects through
a separate path, for example memory read back by another access method.

The debug compliance suite writes C3 with `suite: "debug-compliance"`, `core`
set to the profile name and `config` set to `debug-<version>`. Each test entry
has `group`, `observations` and `dmi_accesses`. Against a non-model target it
also has `reference_status` and `reference_diff`, the result of the same check
on the reference model. A check the reference model cannot pass makes the entry
inconclusive. Different observations make it fail. Checks for options the
profile does not declare, or that the profile skips with a reason, are listed in
the top-level `unsupported` array and are not tests. An entry that could not
exercise its rule has status `error`, signature `inconclusive` and an
`inconclusive` reason. `rvw debug tap` writes the same layout with
`suite: "jtag-dtm"`. Exit codes: 0 all pass, 1 any fail, 3 inconclusive or no
checks.

### Optional multi-hart extension (C1 and C2)

C1 stays `rvw.run/1`. An adapter can opt in with `details.multihart`.
It lists `harts`: objects with unique non-negative `hart`, reset `epoch`, and
`status`. Each hart starts in reset. Each reset starts a new epoch and restarts
that hart's retirement order at zero. Shared memory survives a hart reset.
The adapter must drain or cancel that hart's outstanding transactions before reset.
Completion applies to one hart. A run can pass only after every declared hart
completes with pass. An unfinished hart at the cycle bound gives timeout.
Harness errors must stay errors. Record each hart's reset PC and input ELF hash
in project metadata. The current single-ELF CLI does not select multiple images.

Multi-hart traces use **`rvw.rvfi/2`**, never `rvw.rvfi/1`. The header adds
`harts: [0, 1]`. Each retirement adds `hart` and `epoch`; `order` is a decimal
string with full 64-bit precision. Order is contiguous within one hart and epoch.
Equal retirement orders on different harts are valid. Reset and completion are
`event: reset` and `event: hart_end` with `hart`, `epoch`, `cycle` and, for
completion, `status`. A missing reset or an order gap is an input error.
All records add `capture_seq`, a contiguous decimal string from zero, and share
one nondecreasing sampled `cycle` in 0..9007199254740991. These describe capture order only. They do
not impose a global retirement order or implement RVWMO.

Shared memory initialization is captured once before reset release. Project
inputs declare its address ranges, bytes, byte order, hashes, arbitration and
memory type. Capture accepted external transactions as `event: external` with
unique transaction `id`, `action` (read, write, atomic, irq or maintenance),
`source`, hex `address`, hex `data`, hex byte `mask`, cycle and capture sequence.
Retried requests keep their logical transaction ID. Capture interrupt targets,
DMA coherence mode, read-from/write serialization IDs and maintenance completion
in the payload when applicable. Request presentation is not acceptance. Record
all nondeterministic input and arbitration decisions required for replay.

A reference adapter must use per-hart architectural state and an explicitly
captured memory interleaving or a memory-model checker. It must not feed the
reference values read from DUT retirement. Ambiguous read-from relations or
missing external inputs give inconclusive. Current Spike/Sail single-hart
commands do not implement this extension. Do not split `/2` into `/1` files and
claim a shared-memory match. `MultiHartTrace` in RiscvSim supplies the writer and
completion aggregation. It does not supply a multi-hart reference backend.

A serialized project boundary can use `SerializedMemoryReference` for byte data
and read-from checks. The project assigns contiguous `serialization` IDs only
when memory actions are accepted. This order is separate from `capture_seq`
and each hart's `order`. An event names its `boundary`. Reads add `read_from`,
one write ID per observed byte; `initial` names the captured initial image.
External writes consume serialization IDs too. Initialize the reference from
captured input bytes. Derive expected writes from stimulus or independent
architectural state. Compare observed writes before updating the reference.
This stricter serialized model is valid only for a declared serialized boundary.
It must not reject legal weak-memory core behavior by imposing retirement order.
The native two-hart subset fixture uses this model. Production multi-image
loading and a full multi-hart architectural reference remain unavailable.


### C2 online launch

`rvw cosim live --elf ELF --core CORE --out DIR --simulator COMMAND ...`
launches a C1 adapter. DIR must be new. COMMAND must contain `{elf}` and `{out}`
placeholders. The command receives the captured ELF and writes C2 to
`DIR/rvfi.jsonl`. `RVW_RVFI_FLUSH=1` requests line flushes in RiscvSim.
The existing offline comparison and synchronization rules apply. The wall
timeout covers the whole launch, including builds and lock waits. A checked
mismatch stops the process group and returns exit 1. A timeout, incomplete
stream or nonzero exit cannot produce a match; it returns exit 3 when usable
trace evidence exists. A timeout before any C2 output is also inconclusive.
Other input and trace errors return exit 2. `simulator` records command,
returncode, timed_out and trace path. The consumed prefix digest is not a
complete file identity. Launch metadata captures the executable identity and
argument list; adapter build dependencies still require C1 provenance.


### Unspecified mscratch reset bits in C2 comparison

For a declared trace from reset, CSR synchronization can resolve the unknown
reset bits of `mscratch` (0x340) from its first read or C2 CSR snapshot.
`rvw.cosim/1.recent_synchronizations` records `reason: csr_reset_unknown`,
`csr`, `mask`, `reference`, `core`, `order` and `source` (`rd_wdata|csr_state`).
The reference takes only unknown bits. Full writes clear the unknown mask;
set/clear writes clear their written bits from that mask. Subsequent observations
remain strict. The rule is disabled by strict CSR synchronization or by
`trace_from_reset=false`. Unsupported reference synchronization is an error.
No other CSR reset state is inferred by this rule. C1/C2 formats do not change.

### Multi-image preparation and serialized byte checking

`rvw memory images` emits `rvw.hart-images/1` with a `harts` array.
Each entry has a unique non-negative integer `hart`, absolute `elf` path,
and `elf_sha256`. At least two harts are required. This is input preparation,
not adapter execution. The project still owns image placement, overlap policy,
reset PCs and shared-memory initialization.

`rvw memory check` consumes C2/2 plus `rvw.serialized-memory/1`. The latter
has `boundary`, `initial` regions with hex `address` and hex byte-string `bytes`,
and `writes` keyed by accepted transaction ID. Each expected write declares
hex `address`, `data` and byte `mask`. Read-from entries correspond to selected
byte lanes in increasing order. Capture order does not define memory order.
The report is `rvw.memory-check/1`, with `status`, `checks`, `scope` and
`exhaustive_proof:false`. Status is `consistent`, `mismatch` or `inconclusive`.
Consistency applies only to the sampled declared serialized boundary.


### C2 blocking co-simulation transport

`rvw cosim live --lockstep` supplies a localhost TCP port in `RVW_COSIM_PORT`.
The producer sends a C2 header and records as UTF-8 JSON lines. It waits for one
JSON reply after each line. `status: continue` permits the next observation.
Any other reply is the final `rvw.cosim/1` report. The producer must stop.
The end event receives the final report. Missing end evidence cannot earn match.
Events precede affected retirements, including events in the same cycle. This
transport does not reorder cycles or read ahead. Taken interrupt traps inject
only platform-declared interrupt inputs. Declared debug halt events also synchronize at that boundary.

### C2 observation exchange

`rvw cosim exchange` writes a new output only. C2 export to RVVI-TEXT 0.5
uses RET/TRAP, ORDER, MODE, X and NET elements. A vendor STATE string named
`rvw.c2` retains the complete C2 header and each original record. This includes
asynchronous events, extension snapshots and synchronization inputs. Imports
check retirement PC, instruction and register writes against the vendor state.
The format source is RVVI commit `04dc469012f718ffe104c1c1d0cd8cea66f96724`.
This is a bounded subset, not a complete RVVI implementation.

Spike commit-log export retains C2 in `# RVW-C2` comments. Trapping retirements
are refused. Plain logs without that extension produce `rvw.observations/1`
with explicit missing fields. Sparse imports cannot produce C2 or a match.
Unsupported Spike effects fail instead of being discarded. Conversion reports
`independent_check: false`; format conversion is not architectural validation.

### C2 custom Spike reference extensions

The cosim platform accepts `reference_extensions`, a list of objects with
`library` and `name` strings. Library paths are relative to the original platform
file. Inputs capture each library before execution and record its digest. Spike
loads captured libraries, then registers each named extension on the processor
before loading the ELF. Libraries must use the installed Spike extension ABI.
A missing library or registration failure is an error. Sail refuses this setting.
Custom CSR state uses the existing C2 `csr_snapshot` declaration. Reference trace
generation still refuses custom instructions with unknown operand layouts.

### C2 debug entry observations

C2/2 may declare `debug: true`. Every retirement then contains `debug` with
Boolean `mode` and `step`, XLEN hexadecimal `dpc`, and 32-bit hexadecimal `dcsr`.
`step` must equal `dcsr.step`. A separate `event: debug` record has a `cycle`,
`action` (`halt` or `observe`) and the same complete debug snapshot. A halt
injects a reference halt request before the next instruction. It does not inject
an ordinary exception or interrupt. All four snapshot fields compare exactly.
Spike processes a halt without executing a debug ROM instruction. Resume,
debug ROM execution, triggers and automatic single-step transitions are not yet
supported. Unsupported reference hooks fail; they cannot earn a match.

## C3. Suite results (`rvw.results/1`)

New regress run sets publish through C8 `current` and `generations/<id>`. The root workspace
files are progress copies. Readers resolve one generation, validate all artifacts and read
claim-bearing JSON through that generation. Nested suite paths resolve through the owner.
Resume creates a new generation. `--fresh` clears the workspace and retains published generations.
Legacy complete run sets use one captured JSON set while holding the writer ownership lock.
An active writer, orphan adapter, incomplete set or missing generation pointer refuses the read.
Legacy caches are misses. New generation-bound caches store conclusive passes, and
conclusive failures with complete RTL identity as specified in C8.


A suite run (riscv-tests, ACT4, VM tests, benchmarks, random-timing stress, elaboration) is a
directory with `results.json`:

```json
{
  "schema": "rvw.results/1",
  "run_id": "2026-10-20T21-03-11Z-small-riscv-tests",
  "suite": "riscv-tests", "core": "boom", "config": "small",
  "created": "2026-10-20T21:03:11Z",
  "source": {"core_rev": "…", "core_dirty": false, "tools_rev": "…"},
  "tests": [
    {"id": "rv64ui-p-add", "status": "pass", "seed": 1, "cycles": 1234, "instret": 456,
     "elf_sha256": "…", "options": {"max_cycles": 200000}, "kind": "elf-dir",
     "wall_s": 2.1, "run": "tests/rv64ui-p-add/result.json", "signature": null,
     "metrics": {"ipc": 0.37}}
  ]
}
```

Runner C3 files carry `run_set`, the relative path to their owning run directory. Every C3
directory load checks its nearest ancestor `run.json`, even when the caller names only a nested
suite or its JSON file. The owner must be complete and list that directory. Run id, suite,
config, test count, core and overlapping source fields must agree. Missing source fields are
inherited from the manifest. Manifest paths must stay inside the run directory. The owner must
record a non-empty source identity object. Missing or malformed source data is an error.
A recorded `run_set` with a missing or different owner is an error. Older standalone C3 files without
`run_set` or an ancestor manifest remain readable; their former ownership cannot be recovered.
Older suites in the runner layout with `.rvw-job.json` records also require an owner.
Runner source fields `tools_key` and `adapter` require an owner even in a detached legacy C3 file.
An alias cannot bypass the run manifest above the requested path. The boundary check applies
to both directories and `results.json` file links, even when another run has matching metadata.

Each runner test entry records `elf_sha256`, `seed`, stimulus `options` and `kind`. Build entries
have `kind: "build"`, no ELF hash, and a `build_options` array. Options include C1 `max_cycles`,
`mem_latency` and reported option defaults. Compare requires the recorded
program and stimulus inputs to agree for each shared test and seed. Missing identity, a changed
ELF or changed options makes that test inconclusive, even when the failure signature agrees.
RiscvSim entries also retain `rtl_sha256` and the per-model `adapter_identity` digest.
Pooling requires one pair of these identities for each suite and config. The RTL digest identifies the tested design; different
RTL digests are expected when a gate compares design revisions. Each result must match its
own adapter identity claims. Equal design decisions use the RTL digest.
Such a test cannot be classified as still failing, fixed or known, or used for performance
comparison. Older entries without input identity need a rerun. A baseline failure can cover
only the same seed. Count and random seed modes still detect insufficient sample counts, but
different seed sets are inconclusive; equal counts alone do not establish comparable inputs.

`signature` is a short normalized failure fingerprint (status + fail code or assertion location),
used to tell a known failure from a new one (`rvw.results.failure_signature`): e.g. `fail:3`,
`timeout` (max cycles), `timeout:wall-clock`, `assert:lsu.scala:1241`,
`assert:IllegalStateException@Mem.scala:42` (testbench exception), `rvfi_error:105`.
Assertions use the HDL file and line when there is no Scala location, for example `assert:core.sv:4`.
Without either location, `assert:sha256:<digest>` binds the full, unnormalized message.
Uncoded RVFI errors use `rvfi_error:sha256:<digest>` over the full message.
Runner C3 entries retain complete failure messages with `message_complete: true`.
Display limits must not truncate this evidence. Legacy 400-character messages without
this marker may be cut previews. Compare treats these entries as inconclusive and requires a rerun.
Compare derives assertion and RVFI signatures again from saved messages, including older C3 results.
C3 retains C1 `details.rvfi_errcode` when present. Compare uses this code before parsing
the message, as C1 signature generation does.
Old uncoded RVFI evidence without a saved message needs a rerun. Saved `fail_code` values
override saved fail signatures. An unchanged failure must also have the same status.
An assertion without a saved message or a complete location is inconclusive and needs a rerun.
Test entries and the top level may carry extra keys (e.g. `message`, `fail_code`, `cached`, `perf_metrics`);
readers ignore keys they do not know. An entry is *inconclusive* (`TestEntry.conclusive` is
false) when its status is `error`, it has `synthesized: true` (the runner wrote it because the
adapter did not), `wall_clock_timeout: true`, or `inconclusive` (the reason: `rvw regress` copies
`RunResult.why_inconclusive` of the C1 result, whatever its status, so every cause of the shared
rule reaches C3). Inconclusive results are not cached, not restored from the cache and not
resumed. `rvw regress` rechecks the core, `cache_paths`, adapter files, adapter identity and
ELF bytes after taking the execution lock, before reuse or execution, and again before result
publication under that lock. A detected input change makes every result in that suite
inconclusive in C1 and C3, clears cache keys, and prevents cache storage and resume. Later
suites in the invocation stay inconclusive. Explicit revision runs use a separate cached clone,
including for the current HEAD; live `WORKTREE` and `--source` runs use the checks above.
Job identities include `runner_identity_version: 5` so older unchecked cache and resume entries
are not reused.
Checks cannot detect an input changed and restored between checks, or an input not declared
in the identity. Each (`id`, `seed`) has its own run directory: `rvw regress` refuses a suite whose tests
would share one (same id after `strip_suffix`, ids that differ only in case, or one test's
directory inside another's). The top level may carry `seeds` (`{"mode":
"fixed" | "random", "base": 1}`) and `filter`. Shared code: `rvw/src/rvw/results/`. `rvw regress` also writes JUnit XML next to it.

A selected source checkout requires the core config's `source_env`; otherwise rvw refuses the
run before starting the adapter. C1 must name that source path and its Git revision when known.
`regress run` accepts at most one of `--source` and `--rev`. Shared validation refuses conflicting
selectors in CLI, Python and MCP calls before starting the adapter.
Recorded revision, dirty flag, fingerprint, link identity and identity coverage must agree with
the request. Conflicts make C1 and C3 inconclusive and prevent cache publication. Conflicting
cached or resumed results are discarded and rerun. A cached C1 may name a different checkout
only after rvw verifies that it has the same clean revision and link contents.

Suite `options` cannot replace runner fields: `config`, `elf`, `out`, `seed`, `max_cycles`,
`mem_latency`, `rvfi_trace` or `wall_timeout`, including dash spellings and a leading `--`.
C1 must agree with the
requested core, config, ELF SHA-256, seed and each requested stimulus option before C3 publication,
resume or cache reuse. Options may be reported as C1 fields or in a C1 `options` object. Missing
or conflicting evidence makes the result inconclusive and prevents cache publication. The runner's
wall timeout is a process budget, separate from the stimulus options checked in C1.
The observation flag `rvfi_trace` may instead be checked from one `--rvfi-trace` replay flag and
an existing C1 trace artifact inside that result directory. Both are required. An explicit
conflicting option field is never overridden by this evidence.

Source identity also checks raw tracked file bytes and executable bits, independent of index
flags, stat caching, `core.fileMode` and line-ending normalization. This applies to `cache_paths`
and cached revision checkouts. Private ignore files cannot hide untracked source files; use
repository `.gitignore` rules for build outputs. Sparse checkout, shallow history, replacement
refs, grafts, private attributes and active clean/smudge filters are refused.

## C4. Verdict (`rvw regress compare`)

Metric declarations use `name[:direction]`, where names match `[A-Za-z_][A-Za-z0-9_.-]*`.
The closed direction set is `min`, `lower`, `max`, `higher`. The default is `min`.
`lower` aliases `min`; `higher` aliases `max`. Unknown directions, malformed declarations and
duplicate metric names are usage errors in config loading and stored comparison. Cycle and
instruction selectors use non-empty dotted keys with `|` fallbacks. Empty fallback keys are errors.
The same finite, non-negative relative tolerance is applied separately to each metric.

Gate selectors `--base` and `--base-rev` are mutually exclusive. Selectors `--cand` and
`--cand-rev` are also mutually exclusive. Shared validation rejects conflicts before result
resolution or execution. CLI returns exit 2; MCP reports the same usage error.

C3 tests used for performance checks require `metric_origins`. Each metric maps to its actual
C1 dotted key, including the fallback selected by the runner. Derived IPC records
`{"operation": "instret/cycles", "instret": "<selected key>", "cycles": "<selected key>"}`.
All samples of a metric across both sides and seeds must have the same origin. Missing or
different origins make that metric inconclusive. Standard `cycles`, `instret` and `wall_s`
come from their canonical C3 fields; a custom metric cannot override them. A key must use the
same units on both sides. Unit conversion is not supported. Samples must be positive and finite
for relative comparison; zero and negative values are inconclusive. IPC is not rounded before
comparison. Old C3 performance evidence without origins requires a new run.
Performance means require the same seed sets on both sides. Extra candidate seeds cannot
change the comparison population. Unequal sets make performance inconclusive.

Stored gates require the requested suite's performance declarations to match C3 `perf_metrics`.
For performance suites, C3 `metric_keys: {"cycles": "<selector>", "instret": "<selector>"}`
must also match the requested selectors. The runner records both fields even for suites with
no performance metrics. Missing required metadata or changed declarations make an otherwise
accepted gate `inconclusive`, with cause `stored_plan_incomplete`. Run both sides again.

C4 records `generations: {"base": ["<id>"], "head": ["<id>"]}` for all published inputs.
Each list contains unique sorted IDs. An empty list names a legacy or in-memory input.
The optional `known_capture` binds the captured known-failures file. Gate pins stored result
inputs and the known-failures file before starting either simulation side.


Performance tolerances must be finite and non-negative. Regression timeouts must be finite
and positive, including computed batch and watchdog budgets. Counts and cycle limits must be
positive integers; memory latency may be zero. CLI, TOML and Python entry points validate these
limits. A non-finite performance metric makes the comparison inconclusive. Verdict JSON is
fully serialized with non-finite numbers refused before any output file is created or replaced.

`rvw regress compare BASE CANDIDATE [--known known-failures.toml] [--perf-tolerance 0.01]` prints
and writes `verdict.json`. BASE and CANDIDATE are C3 directories, run sets or trees of them; a run
set (`run.json`, `rvw.regress-run/1`) counts only the suites its `run.json` lists, and an
unfinished or inconsistent run set is an error (exit 2). Each side must have one consistent
source identity, including the core name, full revision when recorded, dirty fingerprint, link
contents, adapter and tool identities. Checkout paths may differ. Several result sets without a
recorded source identity cannot be combined. Duplicate `(suite, config, test id, seed)` entries
on either side are an error, including a `null` seed. Disjoint seed shards must agree on seed mode
and performance metric declarations. Each entry keeps its own C3 directory for reported run paths.
New C3 files record the full source fields of their run set. For older C3 files, the run-set loader
adds missing source fields from its manifest and refuses conflicting fields.

If either side has several C3 files and any records `source.identity_complete: false` or
`source.core_identity_covered: false`, compare and gate refuse to pool them and return
`inconclusive` (exit 3), including over MCP. Equal revisions or uncovered reasons do not prove
equal inputs. This also applies to several suites from one incomplete run set. A single C3
file per side can still show a new failure, but an explicitly incomplete identity never gives `accept`.

```json
{"schema": "rvw.verdict/2", "verdict": "accept | reject | inconclusive",
 "tests": "pass | fail | incomplete", "not_accepted_reason": null,
 "new_failures": [{"suite": "…", "id": "…", "signature": "…", "run": "…"}],
 "fixed": [...], "known_failures": [...],
 "missing": [{"suite": "…", "config": "…", "id": "…", "seed": 2, "base_status": "fail"}],
 "perf": [{"id": "qsort", "metric": "cycles", "base": 1000, "candidate": 1030, "change": 0.03}],
 "inconclusive": [{"suite": "…", "id": "…", "signature": "error:…", "why": "harness error"}],
 "reasons": ["2 new failures", "qsort cycles +3.0% > 1.0%"]}
```

C4 `/2` adds required `tests` and optional `not_accepted_reason`. `/1` verdicts must be
regenerated from their C3 evidence. They are refused by the C4 loader.

- `tests: "pass"`: the comparison has no rejecting or incomplete evidence. Unchanged failures
  (`still_failing`) and known failures do not reject. This does not assert that every test passed.
- `tests: "fail"`: the comparison found rejecting evidence. Rejection takes priority over
  incomplete evidence. A dirty source does not weaken a rejection.
- `tests: "incomplete"`: the comparison cannot judge all required evidence, including missing
  identities, incompatible inputs, no shared tests or incomplete stored plans.
- `verdict: "accept"` additionally needs full committed revisions and `core_dirty: false` on
  both sides. Dirty or absent committed identities keep an otherwise passing comparison
  `inconclusive` with `not_accepted_reason: "uncommitted"` and `uncommitted_sides` naming
  `base`, `candidate`, or both. An incomplete comparison can also record this source block.
  The compatibility cause `candidate_not_committed` applies to either side. It does not replace
  another `inconclusive_cause`. Rejected verdicts do not set `not_accepted_reason`.

Text output starts with `TESTS PASS` followed by `NOT ACCEPTED` for a passing comparison
blocked by uncommitted sources. Other verdicts start with `ACCEPT`, `REJECT` or `INCONCLUSIVE`.
The source revisions, reasons and result details follow. JSON and MCP use the same C4 fields.
Exit codes stay 0 accept, 1 reject, 3 inconclusive or not accepted, 2 input error.

`reject`: new failures, missing tests or seeds (unless allowed), or a performance regression.
Otherwise `inconclusive` when any candidate result is inconclusive (see C3: harness errors,
results the runner wrote itself, wall-clock timeouts, results the adapter marked `inconclusive`;
whatever their status they are never a pass, "still failing" or known, and a base failure is
"fixed" only by a conclusive pass of every failing seed), when a performance metric is missing
for a compared seed or is declared on one side only or with different directions (the union of
both sides' `perf_metrics` is compared, so a metric the candidate drops is still checked), or
when no test ran on both sides. Otherwise `accept` needs clean committed sources on both sides.
Exit code 0 accept, 1 reject, 3 inconclusive
(2 is a usage or config error). Seeds are compared before aggregation: with fixed seeds every
base (test, seed) must be in the candidate; with random seeds on either side the candidate must
run at least as many seeds per test (`--seed-policy auto | exact | count`). Different seed sets
remain inconclusive. Known failures are
matched on suite, test id and signature, each with a reason and the revision it was recorded at,
so a different failure of the same test is still new.
`known add --core X --from latest` resolves the latest indexed run for X. Every imported result
must match X, including explicit paths. Mixed-core result folders are refused before writing waivers.
Known-failure TOML accepts only the `known` array of tables. Each table accepts `suite`, `id`,
`signature`, `config`, `reason`, `recorded_at_rev` and `recorded_at`, all strings. The first three
are required and non-empty. An optional `config` must also be non-empty and match the result config.
Unknown fields or invalid types are usage errors with a file and line diagnostic.
Imports keep each result's config. `--config` filters imports and never relabels them.
Only conclusive failures are imported. Empty selections and `--from` with `--signature` are errors.
An all-config waiver requires a manual entry with no `config` field.
A matching all-config or wildcard-signature waiver makes comparison inconclusive.
Only an exact signature with an explicit config can waive a failure for acceptance.
An exact waiver covers its diagnostic class, including changed messages within that class.
It does not prove equal root causes. Without a waiver, unchanged failures also require
identical saved messages (including two absent messages for legacy diagnostic-only evidence).
Changed messages cannot be hidden by equal timeout, fail-code, monitor-code or source-line signatures.

### Regression performance evidence (C4)

Each `perf` item also records `samples: {base, candidate, paired}`,
`comparison_rule: "max_paired_relative_loss"` and `confidence: "not_estimated"`.
The counts refer to the seeds used in that workload's arithmetic means. The means use equal
seed sets. Means and `change` are descriptive. Acceptance checks every paired seed separately.
For a lower-is-better metric, loss is `(candidate - base) / base`.
For a higher-is-better metric, loss is `(base - candidate) / base`.
`max_paired_loss` records the greatest loss. `worst_seed` identifies its seed.
A loss greater than `perf_tolerance` on any seed rejects. Equality does not reject.
A faster seed cannot cancel a slower seed. Non-finite paired losses are inconclusive.
This is a bounded deterministic acceptance rule. It makes no population estimate.
No confidence interval, noise distribution or statistical significance is claimed. A declared performance workload without a
baseline or without passing results on every seed is inconclusive, even when its failure
is known or unchanged. A new correctness failure still rejects.

## C5. Failure bundle (`rvw bundle`)

`rvw bundle RUN_DIR [--out DIR]` turns a failed run (C1 result) into a directory:

```
summary.md       for a reader: what failed, where, last progress, suspected unit, next commands
summary.json     the same, structured (schema "rvw.bundle/1")
retired.txt      last N retired instructions, disassembled
wave-window.vcd  waveform cut to a window around the failure (when a wave exists or can be re-run)
dynpdg.json      SpinalTrace dependency trace of the failing signal (when available)
replay.sh        exact command to reproduce (when replay inputs were captured)
```

With `--no-rerun --no-spinaltrace`, the bundle reads saved artifacts and the verified ELF.
It does not require the replay source or adapter. Its summary sets `replay` to null, gives a note
that replay is unavailable and omits `files.replay`. Its published generation has no `replay.sh`.

Cycle labels in a bundle use the run's `details.wave_time_of_cycle_1` and `details.wave_time_per_cycle`
(cycle N at `time_of_cycle_1 + (N - 1) × period`) and `details.wave_window`. An adapter that writes waves
should record them; without `wave_time_of_cycle_1` the bundle does not trust a wave to reach the failure
and says that its cycle labels are assumed. Details: `rvw/src/rvw/bundle/README.md`.

Snapshot counts use `?/N` when any input is unknown or absent. A snapshot table can include
`unknown_entries`, a list of `{"#": index, "value": value}` keys whose live state is unknown.
An empty `rows` list with unknown entries does not prove that the table is empty.

### Reduction and bisect reports

`rvw.reduce/1` adds `streams`, keyed by `instructions:SYMBOL`, `irq`, or `stimulus`.
For `stimulus`, `kept` contains group names, and counts refer to groups.
The replay must include `--stimulus-file`; C1 must record its `stimulus_sha256`.
The `rvw.stimulus/1` event format and dependency rules are defined in
`rvw/src/rvw/bundle/README.md`. Minimality applies to admissible group removals.
Each entry has `original`, `remaining`, `kept` (zero-based input indices),
`completion`, `one_minimal`, and `global_minimum` (always false).
IRQ indices exclude the fixed initial event from the search, but still refer to
the full original schedule. Completion is `one_minimal`, `initial_not_reproduced`,
`inconclusive`, or `budget_exhausted`. `one_minimal` applies only to that search's
context. It proves no global minimum. Top-level `budget_exhausted` reports whether
the trial count reached the configured limit. The best replay includes the
captured candidate ELF and the reduced inline schedule. Every candidate uses the
shared conclusive reproduction rules. Integer data reduction stays in `symbols`.

`rvw.bisect/1` marks `result.inconclusive: true` when endpoint verification
stops on a skipped run. It cannot publish `first_bad` for that result.

## C6. Design database (`rvw query`)

One elaboration of a Spinal design, written by `SpinalDB` as a SQLite file with schema
`rvw.designdb/20` (`meta.schema`; `/2` added typed expression keys, memory init hashes and
write masks; `/3` keys compiler temporaries by their own assignments; `/4` adds clock-enable and
soft-reset polarity to clock domains and keys generated registers by content at their operand
position; `/5` does so at any depth (`$reg:<id>`, a canonical id of the register graph) and marks keys that
cannot be complete with `$incomplete:` (hashed parts `h!:`); `/6` adds the typed keys of each clock
domain's control signals and writes generated registers as `$reg:<hash>#<rank>`, so equal registers
stay distinct; `/7` applies the allow-list rule: anything the keys do not model, and a BlackBox
whose external body was not hashed, is `$incomplete:`, and memory ports, BlackBox generics,
`initial` values, assertions and tags are keyed; `/8` keys an enum by its element names in order
and each element's encoded value, and hashes every file a BlackBox body includes (a body whose
dependency set Yosys cannot list is `$incomplete:`); `/9` keys a `switch` default by every case key
(empty cases included) and a case by the earlier keys that can block it, writes the tags and
attributes of generated registers and temporaries into their keys, and adds `components.tags`;
`/10` flags a `when_`/`switch_` line name `generated` only when Spinal gave it (a user signal named
like one is a named signal), keys a Scala `object` tag by its fields, and adds `signals.port_index`,
each port's place in its module's emitted port list; `/11` writes every value in a key with one
canonical encoder (strings quoted and escaped, numbers and booleans typed, sets and maps in sorted
order, nested keys length-framed), labels enum-like Spinal values by name (never an identity
`toString`), keys an attribute subclass by its emitted languages, tag flags and fields, and keys
every field of a Scala `object` tag but the compiler's `MODULE$`, `serialVersionUID` and lazy-val
bitmaps; `/12` keeps tags and attributes in the order Spinal emits them (two `init` attributes in
either order differ), leaves out of a tag object only fields the Scala compiler provably added
(exact shape, and the name not declared in the Scala signature; a user's `var bitmap$0` is keyed;
unprovable: `$incomplete:`), and keys constant `final val`s, which have no field; `/13` reads a
case-class (any `Product`) tag payload by every field it holds, written `Class(name=value,...)`
sorted by field name, never through `productIterator` or another method the class can override,
and reads JDK big numbers, Scala library collections, `ClockDomain` and the Spinal tags written in
short forms only as their exact classes (a subclass is read by its fields or is `$incomplete:`);
`/14` adds `meta.emission_config` and applies the exact-class numeric allow-list to literal
values, poison masks, enum encodings, switch masks and memory init words. Rejected numeric
payloads stay `$incomplete:`, including outside memory init hashes. The emission key records every
config field except audited file placement, file splitting, comments, logs and source-location
collection. In `/14`, user phases, callbacks and nonempty scope properties were incomplete.
`/20` extends this rule with compiled-code keys, described below. Unknown values remain incomplete.
A report made outside `SpinalDB.elaborate` has an incomplete emission key. Diff compares this key
at the top level even with `--scope` or `--no-connections`. A changed setting is a difference;
a missing or equal incomplete key gives `identical: null` at `<emission_config>`.
Assignment targets use their union: a missing side has an empty driver list.
`/15` requires exact class identity, classloader and code source for library membership. A package name
alone cannot make an expression complete or remove a tag payload. Ignored bookkeeping tags use
exact classes. Older databases can hold forged complete keys despite the same table layout.
`/16` applies the identity check to signal declarations, expression references and generated keys:
they retain the signal-type allow-list. Unsupported signal classes remain incomplete, including unread
generated declarations. Container override and anonymous-Area forwarder checks are outside the C8
threat model. Compiler bookkeeping fields are omitted by exact name, modifiers and type. Constant
`final val` values are read from Scala signatures; missing constant metadata remains incomplete.
Yosys runs through the resolved launcher recorded by `Capture.tool`. Its path, hash and observed
version do not establish transitive tool dependency identity; `verify_tools` still checks recorded tools.
Unread unsupported generated declarations also mark their component incomplete. Conservative
BlackBox edges include clock-role input ports. An unknown diff scope is an error; a scope present
on one side still reports additions or removals.
`/17` hashes BlackBox dependencies from two independent Yosys contexts: implicit `SYNTHESIS`
and `-nosynthesis`. The fingerprint covers their union. Raw-source checks make unsupported
conditional defines, macro-built includes and context-changing directives `$incomplete:`. The scan
does not infer external defines or include directories. Both contexts must resolve under the
supplied generics. Timeouts and cancellation use `rvw.common.proc.run_group` through
`SpinalDB/scripts/hdl-deps.py`.
`/18` reads each inline Verilog body once before emission. The emitter and fingerprint use
that same value. One shared C8 capture supplies all external HDL roots, supplied sources, literal
includes and file-valued attributes before Yosys reads them. Both contexts use private copies.
`input_files(path, resolved, sha256, size, record)` and `meta.input_capture` bind file and tool
identities. Unsupported capture gives an incomplete key. A failed capture invalidates its batch.
`diff` requires a valid capture record with no capture problems; otherwise it is inconclusive.
Database publication closes a private sibling file, then uses one atomic rename. Query readers
capture that single file before opening SQLite; WAL inputs are refused. `where` checks private
RTL copies against `input_files` before reporting a line. Missing or changed RTL gives
`status: inconclusive` without a live Verilog line. Scala location files are captured and checked
against the same table. A missing or changed Scala file leaves only `stored_loc` and an
inconclusive status. These hashes do not prove compiler input bytes. Query results include the
database `input_capture`; `where` also includes `location_capture`. Artifact export uses an
atomic file replacement.
Default navigation roots are optional. The capture record lists each under
`optional_source_roots` with `state: present|absent`. Explicit roots are required.
Navigation bindings retain logical tree member paths and captured symlink provenance.
`where` matches stored lookup or resolved paths, including aliases proved by a captured tree
layout. An unrecorded alias has no binding, even when it resolves to the same live file.
`/19` keys every input, output and inout reference by its stable external path before
temporary expansion. Generated-name ports retain their identity in every operand position.
Each synchronous memory read output has a database-only `mem_read` state signal linked by
`mem_ports.output_id`. Memory, address and enable dependencies enter the state. Combined ports
also include write enable, data and mask dependencies. Consumers read that state. It has the
port's clock domain and no RTL or waveform name. `path` counts it as one register stage;
`--comb-only` and `--stop-at-regs` stop there. Asynchronous reads stay combinational.
Dependency graph queries refuse older databases with synchronous reads, because they lack these
boundaries.
`rvw query diff` requires `/20` and refuses `/19` and older files with an error to rebuild the
database with the current SpinalDB. Navigation queries still read older schemas. Diff
reports `identical: null` with the affected paths under `undetermined` when a current key is
incomplete). The tables are documented column by column in
`SpinalDB/README.md`; this section is what other tools may rely on.

- **Build**: `SpinalDB/build-db.sh ENTRY CONFIG OUT.db` (a named entry `SpinalDB/ENTRY/` whose
  `entry.sh` sets its environment and lock; `boom` builds BOOM and holds the `boom` lock) or
  `SpinalDB/build-db.sh class TOP_CLASS OUT.db` (any component with a no-argument constructor);
  from Scala, `spinaldb.SpinalDB.generate(config, file)(new Top)`.
- **Find it**: tools take `--db PATH`; the default is `$RVW_DESIGNDB`, then `./design.db`.
- **Names**. Every signal has `path`: the instance path below the toplevel plus the Verilog name
  (`tile.core.rob_1.rob_head`), which is also the waveform path below the scopes in
  `meta.extra_scopes` (`TOP BoomSimTop`), and the SpinalTrace PDG symbol. `spinal_path` is the
  typed Spinal path through bundles, Vec indexes and Areas (`tile.core.rob_1.io.enq.valids.0`).
  Components have `path` (the same instance path, `""` for the toplevel) and `module` (the Verilog
  module name). `rvw query` resolves Verilog, waveform and Spinal spellings to these (see
  `rvw/src/rvw/query/db.py`); other tools should store `path` when they refer to a signal.
- **Facts**: components, Areas, bundles (Stream/Flow/Vec/...), signals (kind `reg|wire|mem|mem_read`,
  direction, type, width, clock domain, reset value, generated, pruned), memories and ports,
  assignments (source text, `when`/`switch` condition chain, enable, Scala `file:line`), and the
  signal dependency graph `edges(src, dst, kind)` with kinds `data`, `cond` (when/switch
  conditions), `sel` (mux selects, dynamic indexes, memory addresses), `init` (reset values),
  `blackbox`. These edges remain visible when either signal has a `clock_role`. Clock-domain
  relations are stored in `clock_domains`, not as clock edges in `/15`. The graph does not infer
  a data dependency from a domain relation. `--include-clock` has no additional relations to
  include in this schema; it never changes whether ordinary data edges are kept.
- **Artifacts** of the same elaboration (table `artifacts`, gzipped): `pdg.json` (SpinalTrace),
  `blocks.json` (SpinalBlocks), `hgldd/<top>.dd` (SpinalWaves). `rvw query export blocks|pdg|hgldd
  OUT` writes them out, so a viewer needs no elaboration of its own.
- **Queries**: `rvw query info|where|drivers|loads|fanin|fanout|path|search|hierarchy|component|regs|export|diff`,
  all with `--json`; the MCP tools `query_*` return the same JSON.

`/20` keys user phases and other user emission objects by exact class name, SHA-256 of the
captured class bytes, SHA-256 of the whole classpath entry, and the ordered captured classpath.
A directory entry covers all files, including helper classes and resources. A jar entry covers
its exact bytes. All hashes use private in-memory copies made before the user phases run.
The key omits source paths. It reads instance state, including inherited fields, by reflection.
Known collections preserve their element keys and order. Supported immutable values are strict
Scala library `List` (`::` and `Nil`), `Vector`, `Queue`, `ArraySeq`, `Range`, factory sets and maps,
`HashSet`, `ListSet`, `BitSet`, `HashMap`, `ListMap`, `VectorMap`, `TreeSet`, `TreeMap`, `Some`,
`None` and tuples of supported values. Their runtime classes need the library class, loader and
jar identity check. Keys retain the runtime class and iteration order. Sorted sets and maps also
key their ordering state. Range keys retain bounds and step. User collection subclasses, lazy
sequences, views, maps with defaults and unsupported values remain incomplete.
Unknown library values, cycles,
missing class bytes, missing code sources, nested classpath symlinks, unsupported lambda metadata and capture limits stay
`$incomplete:`. A size, mtime or file-set change invalidates the key. The capture limit is 512 MiB
and 100,000 entries per classpath directory. Whole-entry and whole-classpath changes can produce
conservative differences even if the changed code does not affect this design.
JVM hidden lambdas have no stable runtime class name or readable class resource. Their key uses
the exact compiled owner and implementation class, method name, descriptor, method kind,
functional interface and captured arguments. Only the JVM-generated metadata accessor on a
checked hidden synthetic nestmate is invoked. Ordinary user serialization hooks, formatters and
payload methods never decide a key. User phase lists are captured before the tools add phases.
Reports made outside `SpinalDB.elaborate` remain incomplete. Diff refuses `/19` and older schemas.
This records compiled code and instance state. Arbitrary generator reads of files, environment
variables or mutable global state are not a captured input contract.


### C6 native HDL navigation subset

`rvw query build-hdl --top MODULE --out DB FILE...` writes `rvw.designdb/20`
with `meta.frontend=yosys-verilog`. Root component path is empty. `spinal_path`
equals the HDL signal path. `meta.graph_semantics` declares conservative signal
and whole-cell dependencies. Query JSON repeats `frontend` and `graph_semantics`.
Named vectors can join disjoint bit slices. These are navigation paths, not
bit-exact functional cones. `data` edges represent value reads. `sel` edges
represent selects and enable/reset inputs. Flip-flop and latch outputs have
kind `reg`; clock inputs are excluded from value edges. Register stage counts
can include multiple aliases of the same state. Clock domains and reset
values are unknown. Empty memory and artifact tables do not imply completeness.

Sources and executable identity use C8 capture. Include directives, file input,
source remapping and token concatenation are refused. Source locations bind to
captured HDL files in `input_files`. Input errors do not publish a partial DB.
Semantic keys and emission configuration are `$incomplete:`. Diff must remain
inconclusive. This subset adds no C1 runtime or formal model claim.

### C6 debug metadata export

`SpinalDB/debug.sh` reads one C8 capture of a design database. It writes stored
`pdg.json` and `hgldd/*.dd` bytes without a new elaboration. `database.json` holds
`input_capture` (the C8 database record), `meta` (database metadata), and `artifacts`
(entries with `name`, uncompressed `bytes`, and uncompressed `sha256`). Surfer and
checker mode export HGLDD only. Trace, GUI and export mode require PDG and HGLDD.
The output directory must be empty. Native consumer exit codes pass through.
This export establishes artifact identity, not waveform or dynamic trace parity.

## C7. MCP tools (`rvw mcp`)

`rvw mcp` is one stdio MCP server for every rvw tool. Each subpackage plugs in without editing
the server:

- Add `rvw/src/rvw/<tool>/mcp_tools.py` with a function `mcp_tools()` returning a list of
  `rvw.mcp.ToolSpec`. Discovery imports `rvw.<pkg>.mcp_tools` for every subpackage, as `rvw`
  imports `rvw.<pkg>.cli`. A package whose import fails is skipped with a message on stderr.
  Modules outside rvw can be added with `RVW_MCP_PLUGINS=module[,module]`.
- `ToolSpec(name, description, input_schema, handler, long=False, annotations={}, isolate=False)`:
  - `name` is `<tool>_<verb>` (`query_drivers`, `regress_run`, `bundle_make`), unique;
  - `description` tells an agent when to use it;
  - `input_schema` is a JSON Schema object (`rvw.mcp.schema(properties, required)` helps);
  - `handler(**arguments)` returns a JSON-serialisable value, normally the same dict the CLI
    prints with `--json`, so CLI and MCP never disagree. Raise `rvw.mcp.ToolError(message, data)`
    for expected failures; the agent gets `{"error": message, **data}` with `isError`.
  - `annotations`: MCP tool annotations, e.g. `{"readOnlyHint": True}` for queries.
- `mcp_tools.py` must not import the MCP SDK (only `rvw.mcp.spec`), so declaring tools works
  without the optional dependency and `rvw mcp --list` works everywhere.
- **Long jobs**: anything that can take more than a few seconds (builds, simulations,
  regressions, bundles) sets `long=True`. The server runs it in a worker thread and returns
  `{"job_id": ...}` at once. If the handler has a `job` parameter it receives a
  `rvw.mcp.jobs.Job`: `job.log(line)`, `job.set_progress(text)`, `job.run(cmd, cwd, env)` (runs a
  subprocess, streams its output into the log, kills it on cancel), `job.check()` /
  `job.cancelled`. Built-in tools follow jobs: `job_status(job_id, wait_s)` (status, result when
  done; `wait_s` up to 60 blocks until it finishes), `job_log(job_id, tail)`,
  `job_cancel(job_id)`, `job_list()`. Heavy jobs still take the `boom` lock themselves
  (`rvw.mcp.worker.handler(..., lock="boom")` or the adapter's `with-lock.sh`).
- **Cancel**: `job_cancel` sends SIGTERM to the process group of every subprocess the job
  started with `job.run`, SIGKILL to what is left after 15 s (`Job.GRACE_S`, longer than the
  5 s `rvw.common.proc.GRACE_S` a worker gives its own adapter or solver groups), and reaps them.
  It returns `cancelled` once the job has ended, or `cancelling` while a handler that runs Python
  in the server has not reached `job.check()` yet. Processes that left the job's group (their
  own `start_new_session`) are stopped only by the handler's own cleanup (`rvw.common.proc`).
- **Job retention**: the server keeps the newest 100 finished jobs; `job_status` of an older one
  is an error that says it was evicted.
- **Isolated short tools**: `isolate=True` (or a name matching `RVW_MCP_ISOLATE`, default
  `wave_*`) runs a short tool's handler in a worker process. It answers inline if it ends within
  `RVW_MCP_SYNC_S` (20 s); otherwise the call returns `{"job_id": ...}` and continues as a
  cancellable job. The handler must be a module-level function.
- Results larger than 400 000 characters of JSON are shortened, not cut: the largest lists and
  strings are trimmed, the result keeps its shape (a non-object result is wrapped as
  `{"result": ...}`), and it gains `"truncated": true` and `"truncation": {note, original_chars,
  cuts: [{path, total, kept}]}`. It is always valid JSON. Give tools `limit`, `depth` or `scope`
  arguments instead of relying on that.
- Test a package's tools through `rvw.mcp.registry.Registry([...]).call_json(name, args)`, and
  end to end with an MCP client over stdio as `rvw/tests/test_mcp.py` does.

## C8. Input capture and result generations

### Threat model (2026-10-24)

The tools protect against honest mistakes in normal work. A result must never grant a pass,
match, accept or exclusion without enough evidence.

- Gate accept requires committed base and candidate revisions. A clean checkout at a commit
  counts as that commit. An otherwise passing dirty candidate gives `tests: "pass"`,
  `verdict: "inconclusive"` and `not_accepted_reason: "uncommitted"`, with compatibility
  cause `candidate_not_committed`. A rejecting dirty candidate stays `reject`.
  Commit the change, then run the gate again.
- Inputs, tools and caches stay stable during a command. Mid-run edits, edit-and-revert races,
  tool swaps, cache tampering and hostile inputs are outside this threat model.
- Normal mistakes remain in scope: stale files, wrong options, missing tools, interrupted
  builds, resume, cancellation, and concurrent runs with separate outputs.
- Unknown or incomplete evidence gives `inconclusive` with
  `input_not_captured:<name>`. It cannot earn passing-result reuse.

1. **Capture once.** Read each file input once. Save its bytes and compute SHA-256 from those
   bytes. Parse and run tools on the saved copy. Capture gzip and FST bytes before conversion.
2. **Bind claims.** Report paths, hashes, revisions and tool identities from the saved record.
   Do not replace captured claims with later reads of the source.
3. **Identify tools once.** Resolve each tool name and hash its executable at command start.
   Invoke the selected executable. Keep its invocation name when this changes its mode, as
   with `clang++`. Verify tools once before each publication. A cheap file stat check is
   sufficient under the stable-tool rule. A detected change refuses publication.
4. **Identify designs.** Use a commit plus a verified clean checkout, private captured sources,
   or the complete generated RTL input described below. Raw file bytes and the Git index
   determine cleanliness. `git status` alone does not detect `--assume-unchanged` edits.
   Missing dependencies or exceeded capture limits refuse the identity.
5. **Use complete keys.** Cache keys include all result-changing inputs, run options and saved
   environment values. Unknown dependencies disable reuse. `Capture.cache_key(options)`
   returns no key unless the caller sets `complete=True` and capture succeeds. Bump the key
   namespace when an identity contract changes. Old keys become misses.
6. **Publish generations.** Write a result set in a fresh directory. Publish it with one atomic
   pointer or rename. Never modify a published generation. Readers pin one generation and
   refuse missing members. Resume writes a new generation. C4 records its input generation IDs.

The Python APIs are `rvw.common.capture.Capture` and
`rvw.results.generation.publish` / `open_current`. See `rvw/src/rvw/common/README.md`.
`rvw.capture/1` records files, trees, Git refs, tools, environment and problems. File records
hold source and resolved paths, private copies, SHA-256, size, execute bits and symlink targets.
Tree records also hold directories and tracked deletions. Broken links and unreadable inputs
refuse capture. Private copy names do not enter keys. Keys use strict canonical JSON with
sorted string keys. `CaptureError` cannot be ignored to grant a verdict.

RiscvSim identifies a design with `rtl_sha256`, the SHA-256 of the exact generated Verilog
file used by Verilator. It includes RVFI monitor RTL in this file. External include and memory
data files are unsupported. The launcher holds the `boom` lock through sbt and JVM exit. It runs sbt offline for each
launch. It does not freeze
or identify the sbt classpath. Changes to sources, dependencies and elaboration tools that
change the design also change the emitted RTL.

The simulation identity also includes the RiscvSim repository commit and dirty flag, captured
ELF bytes, model and run options, native toolchain identity, and relevant environment values
such as `SPINAL_VERILATOR_FLAGS`. Dirty harness sources cannot earn passing-result caching.
Native cache keys use a new namespace and Spinal's RTL-based key. Native entries need a
verification receipt. An interrupted build cannot leave a reusable entry. Tools are identified
once at start and checked before each native receipt or C1 result publication.

### Regression input declarations

`input_complete=true` declares that the adapter inputs, stimulus files, environment and tools
cover the run. The default is false. Unknown dependencies give
`input_not_captured:adapter_dependencies`. Identity output alone does not prove completeness.

BOOM accept requires clean committed checkouts. Dirty candidates run in place and can reject.
Shared checkout execution is serialized.
Its adapter identity records generated RTL and native build digests. Every C1 result must
match those digests before it can count as evidence. Stored plans retain declared stimulus
file identities and reject changed file bytes, even when option path strings stay the same.
Base and candidate commit IDs identify report revisions. RTL digests identify equal designs.

Regression job identity version 10 can reuse conclusive results across core commits and dirty
flags when the complete `/2` adapter document claims all of: a 64-hex `rtl_sha256`, a full
committed `source.tools_rev`, `source.tools_dirty: false` and a 64-hex
`tools.native_build.sha256`. These claims must match each C1 result. Source-specific
`source.core_*` claims prevent this mode. All other adapter document fields, harness bytes,
ELF bytes, declared files, tools, environment and options still enter the key. The core source
fields and captured Git ref selectors are report metadata in this mode. They do not enter the
model key. Other adapters retain source-based keys. Dirty harness sources cannot cache results.
Reused C1 results keep their original source in `reused_from_source` and publish the selected
source in `source`. C3 names the selected source. Old job keys miss the cache.
With this complete RTL identity, conclusive failures can also enter the cache. Reuse retains
the original failure status, signature and source. It cannot turn a failure into a pass or
waive a new failure. Incomplete results are never cached. Source-based keys still cache only
passes. Use `--no-cache` to request fresh simulations.
RTL identity elaboration still runs. Reuse skips simulation for cached jobs.
The runner sets `RVW_CAPTURE_SOURCE_ENV` to the configured `source_env` name.
RiscvSim native identity namespace `native-inputs-v27` excludes that declared checkout selector
from native build environment keys. The RTL hash covers the selected design. Without this
selector declaration, environment values stay in the native key. Other build environment
values remain inputs. Source provenance retains the selected checkout path.

Regression executes the selected adapter and core checkout in place. `source_env` selects
the execution tree. `RVW_CAPTURE_SOURCE` supplies its C1 descriptor. Capture records retain
file and tool evidence. Declared stimulus paths keep their original values during execution.
`identity_capture=true` calls `identity --config NAME --options JSON` once per model.
The response uses `rvw.adapter-capture/2`: a complete source descriptor and nonempty
dotted C1 `result_claims`. Each result must carry the claimed values. RiscvSim claims its RTL,
harness and native digests. `/1` identities and old job keys require a rerun. The protocol does
not replace the completeness declaration. Computed paths, interpreter libraries and external
data need declared coverage. Missing or changed stored plans, source mismatches and incomplete
pooled results remain inconclusive.

### Mutation input declarations

`rvw cov mutate --run` captures the full MCY project. A project file named
`rvw-external-inputs` can declare all other inputs as a JSON list of file or directory paths.
Relative paths start at the project directory. An explicit `[]` declares no external inputs.
Use the captured resolved project directory as the base. Non-leading `..` components refuse
capture because they can cross a symlink. Directory captures retain their lookup layout.
The declaration itself and every listed input use the shared capture layer. Missing inputs,
invalid lists and overlapping input roots refuse capture. Execution uses a mirrored private
layout and redirects literal absolute paths in captured UTF-8 text to the corresponding copies.
Raw capture hashes and relocated execution hashes are recorded separately.

With a declaration, `rvw.mutation/2` records `dependency_complete: true` and
`dependency_declaration` with `claim: "declared complete by the user"`, the declared `paths`,
the captured manifest identity and external input identities. A successful fresh run can report
earned kills and equivalence. Inspection of its pinned generation retains this claim.
The literal-path scan refuses obvious undeclared absolute paths. Interpreter shebangs,
device streams and pinned tools are runtime exceptions. This check is not a sandbox or proof
of completeness. Computed paths and hidden tool dependencies remain the user's responsibility.

Without a declaration, a fresh run writes `/1` observations and returns `inconclusive` with
`input_not_captured:mcy_dependencies` and a stderr note that explains how to declare.
Earned outcome counts are zero; `observed_counts` and `observed_state` retain observations.
A failed MCY run also remains inconclusive. Declarations do not enable cache keys or resume.
Existing and interrupted projects still require a fresh run directory.
Raw databases and all saved `rvw.mutation/1` results provide observations only. This includes
`/1` records with `dependency_complete: true`. A fresh `/2` writer must attach and validate
its declaration, capture and tool evidence before it classifies outcomes. Saved-result role,
failed-run and mutation-control checks still apply. All selected equivalence
checks must return PASS before a mutation can be equivalent. Missing checks
stay pending. Conflicting equivalence PASS and FAIL results are errors.

### Result generation layout

The generation store has this layout:

```text
OUT/current                       # rvw.generation-pointer/1: id, manifest_sha256
OUT/generations/<id>/generation.json  # rvw.generation/1: id, files, directories
OUT/generations/<id>/...           # sealed artifacts
```

IDs are unique 32-character lowercase hexadecimal strings. `current` is a regular JSON file
replaced atomically. It binds the generation ID to the manifest SHA-256. The manifest binds
all artifact paths, SHA-256 hashes, sizes, execute bits and directories. Artifact paths stay
inside the generation. Symlinks, hardlinks and special files refuse publication. Readers
validate the full manifest when opening. `Generation.read_bytes` checks the exact returned
bytes against that manifest. `Generation.path` pins and checks the directory identity; direct
filesystem reads still require content verification. Files and directories are read-only after
publication. These permissions do not sandbox another process with the same user ID.

The builder must stop all writers before it returns. An exception in the builder preserves the
previous pointer. A process stop after sealing can leave an unpublished directory. Concurrent
publishers can finish in either order; the last pointer switch wins. Old generations remain
available. Garbage collection and crash durability are outside this API. A reader never falls
back to a newer generation when its pinned evidence vanishes.

## Resources

The machine has 10 cores and 32 GB. Wrap every heavy job in `scripts/with-lock.sh boom …`:
Verilator builds of BOOM, sbt compiles that touch `../spinal-boom-eda`, and BOOM simulations
longer than a minute. Use at most `-j4` for Verilator inside the lock. Small designs and unit tests
need no lock.

The lock (`rvw/src/rvw/common/lock.py`, used by `with-lock.sh`, `rvw regress` and the MCP workers):

- It is an OS file lock (flock) on `$RVW_LOCK_DIR/<name>.flock` (default `~/.cache/rvw-locks`).
  `with-lock.sh NAME CMD` execs CMD with the lock descriptor open, so CMD is the
  `with-lock.sh` process: killing it ends the job, and the lock lasts while CMD or any child that
  inherited the descriptor runs. Python holds it with `rvw.common.lock.held(name)`; children
  started with `rvw.common.proc.run_group` inherit the descriptor.
- Waiters are served in arrival order and print who holds the lock (pid, command, start time)
  and how many wait ahead. `python3 rvw/src/rvw/common/lock.py --status boom` prints the same.
- Re-entry: a job that holds the lock does not wait for itself. `RVW_LOCKS_HELD` lists
  `<name>:<pid>:<fd>:<dev>:<ino>` entries; an entry counts only when this process has that
  descriptor open on the locked file. Being a descendant of the holder without the descriptor
  does not count: such a child waits. Starters pass descriptors and entries together
  (`run_group`, `Job.run`, exec). An adapter that takes the lock again under rvw keeps the
  inherited descriptor open for that child (bash does; Python needs `close_fds=False` or
  `pass_fds`). Threads of one process exclude each other, and a lock belongs to the thread that
  took it: a child started by another thread gets only the locks the process inherited.
- Transition: until every checkout runs this version, holders also take the old mkdir lock
  `<name>.lock/` (marked with a `flock` file), so old and new users exclude each other.
  New holders atomically install a symlink to a private directory with both ownership markers.
  Installation never replaces an existing owner. A stop before installation leaves no public lock.
  `RVW_LOCK_LEGACY=0` turns this off.

The BOOM sources come from `SPINAL_BOOM` (default `../spinal-boom-eda`, a private clone at
`0cb0b69`). Never build or write anything in `../spinal-boom`: another agent works there. Test
ELFs may be read from `../spinal-boom/tests/vm/build`, `../ref/riscv-tests/build/isa`,
`../ref/act4/work/boom-rv64gc/elfs`; benchmark ELFs come from `rvw arch build` (`examples/boom/out/arch/bench`).

## UVM register sequence diagnostics

The generated `rvw.soc/1` register model can use `rvw_ral_pkg` normalized
transfers. A transfer starts with `UVM_NOT_OK`. The project bus driver must
set completion status. An explicit predictor consumes bus observations;
auto-prediction must be disabled when that predictor is connected.
`UNSUPPORTED_RAL_BACKDOOR` refuses standard access tests without a configured
backdoor. The caller resets hardware before the standard reset sequence.
This register fixture evidence does not establish peripheral or CPU behavior.

## C9. Native architecture models

These reports measure model performance. They do not produce C4 gate verdicts
or claim C8 completeness. Every CLI action supports `--json`. A bad selection,
invalid input, failed run or comparison mismatch exits 2. Stdout then contains
one error object with `--json`. Success exits 0 and means a report was produced.

`[arch]` in `rvw.project/1` has three path fields: `description`, `sources`,
and `benchmarks`. Each path resolves against the project file. An absent or
invalid selected section is an error. No core preset is selected implicitly.

`rvw.arch-core/1` describes one hart. O3 uses RV64; Minor and TimingSimple use
RV32IM (see the RV32 in-order extension below). Required fields are `schema`,
`config` (C1 preset), `isa`, `kind`, `cpu`, `queues`, `predictor`, `icache`,
`dcache`, `itlb_entries`, `dtlb_entries`, `line_bytes`, `bus_bytes`, and
`memory_latency`. Unknown top-level fields are errors. `cpu` contains scalar
gem5 parameters for the selected CPU. The cache tables contain scalar Cache parameters.
Unknown gem5 parameters and object references are errors. Omitted scalar
parameters use gem5 defaults. Each queue has `entries` and `units`. Each unit
has `ops` (gem5 opclass names), `count`, `latency`, and `pipelined`.
`predictor` has `tage`, `loop`, `btb`, and `ras_entries`. TAGE has
`nHistoryTables`, `minHist`, `maxHist`, `tagTableTagWidths`, `logTagTableSizes`,
and `logUResetPeriod`. Loop has `logSizeLoopPred` and `logLoopTableAssoc`.
BTB has `numEntries` and `associativity`. Clock is 1 GHz. Memory defaults to 512 MiB
at 0x80000000. `memory_latency` is a positive whole number of cycles.

`rvw.arch-build/1` records config, ISA, source path, gem5 and compiler identity (path, SHA-256,
version), and benchmark IDs, paths and SHA-256 hashes. Builds use native
newlib GCC and the description's ISA. RV64GC with optional Zba/Zbb/Zbs
and RV32IM are supported. The source path points to riscv-tests.

`rvw.arch-run/1` records `engine` (`rtl` or `gem5`), core, config, memory
latency, project capture, description/model hashes and a nonempty `benchmarks`
list. `benchmark_build`, when present, records the captured build manifest
and compiler identity. A null value means the ELF build provenance is unknown.
A supplied manifest must bind each selected ELF hash. gem5 runs also record the native binary identity in `tool`. Each row
has `id`, `elf`, `elf_sha256`, `status="pass"`, positive ROI `cycles` and
`instret`, and `evidence` plus `evidence_sha256`. Paths are absolute.
`evidence` is a C1 result for RTL or gem5's `bare.json`. The latter requires
integer `tohost=1`, integer `exit_code=0`, `roi="setStats"` and positive
integer `bench_stats.cycles` and `bench_stats.instret`. A model run requires
exactly two setStats entries and four ELF symbols: tohost, tohost_exit,
setStats and bench_stats. A tick limit or incomplete exit fails the run.

Calibration captures each selected ELF once in a fresh output directory.
Both engines run those copied bytes. The C1 adapter gets fixed latency,
seed 1 and the description's preset through `run-many` with one worker.
A conclusive pass is required. ELF hash, core, preset, seed and latency must
match the requested job. ROI counters are mandatory. Whole-program counters
are never substituted. Raw C1 evidence includes the adapter's source identity.

`rvw.arch-compare/1` records base/candidate report paths and SHA-256 hashes,
core, config, latency, `status="reported"`, per-benchmark counters and
`geomean_ipc_ratio`. Comparison rechecks raw evidence and ELF hashes. Both
sets must be nonempty with unique identical IDs, identical ELF hashes and
equal ROI instruction counts. Core, config and memory latency must match.
`ipc_ratio` is candidate IPC/base IPC, or base cycles/candidate cycles when
instructions match. `cycle_gap_percent` is 100*(candidate cycles/base cycles-1).
Comparison requires an RTL base and a gem5 candidate, in that order.
The aggregate is the geometric mean of IPC ratios. No acceptance threshold
or parameter fit is applied. `calibrate` writes this JSON to calibration.json
and a short table to summary.txt. Reports depend on the recorded local paths.

The model uses upstream gem5 v25.1.0.1. Runtime and setup are native. gem5
runs serially under the machine-wide `gem5` lock. RTL uses the project's
shared lock and C1 adapter. C1 termination has a 20-second cleanup grace,
so the 15-second adapter supervisor can stop its child group. Architecture MCP
workers have at least 30 seconds. Server shutdown honors that job grace.
MCP exposes arch_build, arch_run, arch_calibrate
and arch_compare as cancellable jobs. See Arch/README.md for commands and
limits. gem5 shows trends; RTL is the truth.


## Formal X campaign result extension

`rvw.formal/1` X results can include `backend: "yosys-xprop"`, `inventory`, and `replay`.
Each inventory target retains its assertion, signal, label and valid condition. Its
`disposition` is `candidate`, `confirmed`, `inconclusive`, or `not_reported`.
Only native 4-state replay can set `confirmed`. A formal encoded failure alone cannot.
`replay.backend: "icarus"` names the source RTL backend. Replay observations preserve
X/Z binary strings. Existing formal status and exit codes do not change. `unencoded_cells` lists data
cell types that Yosys could not encode. A nonempty list prevents a pass.

`rvw.formal.x-sweep/1` records `top`, `wall_s` and a `modules` array. Each module has its
name, disposition, target inventory, and result path or reason for missing evidence.
Module dispositions are `bounded_clean`, `confirmed`, or `inconclusive`. Bounded clean
requires a formal pass with reachability evidence. It applies only to this module's
free boundary inputs and selected bound. Campaign `status` is always `inconclusive`
and exit is 1. The inventory does not establish distinct bugs or core reachability.

### Native parent X context

`rvw formal x-context` writes `rvw.formal.x-context/1`. It records `top`,
`backend: "icarus"`, `depth`, `reset_cycles`, explicit constant `ties`,
`restrictions`, input capture identities and an `inventory`.
Each inventory entry has `signal`, `disposition` and `observations`.
An observation has `step` and a four-state binary `bits` string.
`reachable-in-core` requires a complete native run with X/Z after reset.
It is an unconditional signal observation in the selected top, not a claim that
a transaction is valid or a core bug exists. All other entries are `inconclusive`;
absence of X is not an unreachability proof. Overall `status` is always
`inconclusive`, and exit is 1. Invalid inputs exit 2.
`xprop` and `x-sweep` accept `--first-failure` to limit formal witness
collection. Unreported targets retain their existing disposition.

## Limit ownership

Backend semantics: [#116](https://github.com/riscPrint/risc-v-workstation/issues/116). Multi-hart: [#90](https://github.com/riscPrint/risc-v-workstation/issues/90). Faulting memory effects: [#93](https://github.com/riscPrint/risc-v-workstation/issues/93). Database consumers: [#69](https://github.com/riscPrint/risc-v-workstation/issues/69).

Retained limit: All documented unsupported capture structures, size bounds and synchronous-state restrictions remain in force. C1 cannot report success without captured model evidence. C9 does not claim complete C8 capture, immutable generations or a gate verdict. No dedicated issue owns broader C9 capture.

## Setup diagnostics and project version pin

`[project].rvw_version` is an optional exact pin to `rvw --version`. The project
loader rejects a mismatch. Existing projects without this key remain valid.
`rvw doctor --json` and MCP `rvw_doctor` return `rvw.doctor/1`. See the
[doctor contract](../rvw/src/rvw/doctor/README.md#output-and-exits) for fields
and exits. Diagnostic readiness does not imply a gate accept or native flow qualification.

## Explained design diff (`rvw.diff-explain/1`)

`rvw query explain OLD NEW [--coverage COV] [--effect CMP]` and MCP `query_explain` return
`schema`, `old`, `new`, `summary` (as `rvw query diff`), `items`, `count`, `selection` and
`effect`. Each item has `kind`, `change` (`added`, `removed`, `changed`), `path`, `detail`,
`locations` (`file`, `line`), `tests` (`status` one of `covered`, `unhit`, `unmapped`,
`uncovered`, `unknown`; `tests`, `mapped_points`, `cause` when present) and `effect`
(`status: unknown`). `selection` has `mode` (`covering` or `all`), `tests`, `covering_tests`,
`uncertain_items` and `basis`. `effect.status` is `not_measured` or `measured` (whole change).
A covering selection is a coverage claim on the base revision, not a gate verdict.

## Wave index (`rvw.wave-index/1`)

`rvw wave index INPUT -o SNAPSHOT.rvwi` publishes an explicit SQLite snapshot.
It does not change C1 artifacts. The `metadata` table has one JSON `value` row
with `schema`, captured input `sha256`, `size`, original `source` path, `records`
`tools` (captured converter paths and SHA-256 hashes), and `header` (lines,
timescale, vars). Each var keeps code, name, width, kind and
range. The `events` table stores `seq` (integer primary key, file order), `t`
(signed 64-bit time), `code`, and unmodified `raw` VCD value. Timestamp records
have null code and raw. Indexes cover `(t, seq)` and `(code, t, seq)`.

The source hash identifies the captured input bytes, including compression.
The index is a saved snapshot, not a cache lookup against a live source. Queries
open a read-only SQLite transaction without a full source scan or capture-copy.
Publishers must not edit an index in place. Querying a snapshot establishes no
new simulator result or verdict. Unknown values retain their VCD meaning.

Optional metadata fields (older indexes lack them): `source_stat` (`size` and
`mtime_ns` of the source when indexing started; the build fails if they change
before publication) and `reader` (`vcd` or `wellen`). The `wellen` reader reads
FST natively through pywellen; its `tools.pywellen.version` records the library.
It writes change rows with `seq` at or above 2^40 in signal order, then one
timestamp row per distinct time with a smaller `seq`. Readers order by
`(t, seq)`; the order of different signals at one time is not significant for FST.

The cached form (`--indexed`, MCP `indexed`) keeps one index per absolute source
path under `RVW_WAVE_INDEX_DIR` (default `~/.cache/rvw/wave-index`). An entry
whose `source_stat` differs from the source is stale and is rebuilt before the
query. `rvw wave verify INDEX [--source WAVE]` compares full SHA-256 and returns
`fresh` true only on an exact match (exit 1 when stale).

## Pipeline cause event extension

Kanata 0004 traces can carry version 1 `#rvw` comment records. Fields use literal
tabs. Records use the current cycle cursor. Standard viewers can ignore the
comments. Ordinary stage, dependency and terminal records remain valid.

```text
#rvw<TAB>1<TAB>stall<TAB>scope<TAB>cause<TAB>evidence
#rvw<TAB>1<TAB>replay<TAB>instruction_id<TAB>cause<TAB>evidence
#rvw<TAB>1<TAB>commit<TAB>instruction_id<TAB>kind
```

`scope` and `cause` are nonempty strings without tabs or newlines. Scope names
are project-defined. Common generic causes are `operand_wait`, `structural`,
`load_miss`, `rob_full` and `lsq_full`. `evidence` is `measured` or `inferred`.
A measured cause comes from an explicit sampled reason signal. Inferred adapter
estimates must use `inferred`. Stage residence and dependency `W` edges do not
establish a measured cause.

A stall record covers `[cursor, cursor + 1)`. Emit one sample per blocked cycle.
Several scopes or causes can overlap. Duplicate scope/cause/evidence samples in
one cycle count once. A replay record is one explicit event for a live instruction.
The optional standard `W` record supplies consumer/producer dependency edges.

Commit `kind` is `architectural` or `predicated_off`. Both denote physical commit.
The producer must know the predication flag. The annotation must precede exactly
one R type 0 for that instruction in the same cycle. It must not annotate a flush
or an open instruction at EOF. R type 0 without an annotation has unknown commit
kind. The extension does not change event IPC or C1 counter checks.

`rvw perf/1` adds `stall_causes`, `replays` and `commit_kinds` objects. Counts by
cause can overlap. Measured samples and inferred samples stay separate. Unknown
zero-retirement intervals have no measured sample, including idle cycles. Unit
stalls do not prove that global retirement was blocked. Commit-bubble head states
remain inferred. Readers refuse malformed `#rvw` records, unknown versions and
unknown event kinds. Other comments retain their existing behavior.

### Native job cost reports (first increment, #57)

`rvw.cost/1` records limits, local logical CPU capacity, elapsed wall seconds,
measured child CPU seconds, conservative charged CPU seconds, launched job units,
exit code, status and stop reason. A unit is one launch through `run_group`.
Native descendants within an adapter batch are not separate count units.
A locked command-owned counter covers nested launches. CPU reservation is host
capacity times wall time. Cleanup has a separate grace and remains in the report.
Missing or exhausted budgets cannot grant a gate accept. Reports are external
artifacts. See `rvw/src/rvw/common/README.md` for enforcement limits.

### Native shared result cache (first increment, #53)

`RVW_REMOTE_CACHE=HOST:/absolute/path` adds SSH/rsync transfer to the existing
regression cache. The directory key is the full existing C8 job key. Each new
cache generation contains `.rvw-cache-key` with that exact key. A fetched entry
must have a valid generation inventory, all artifact hashes and an equal stored
key. A missing or partial object is a miss. The existing runner still checks job
parameters and C1 provenance before reuse. Transfer adds no new admission rule.
Uploads send generations before `current`. Downloads use persistent private,
locked staging keyed by remote location and full C8 key. rsync checks checksums
on resume. Only fully verified generations can be published locally. Upload
ownership metadata (`rvw.cache-owner/1`) in `owners/<generation-id>.json` records host, user, key, generation and
upload time. It is not evidence. Explicit native maintenance verifies managed
entries and removes invalid entries, expired entries, then oldest publications
to meet an owner-supplied byte limit. Transfers must be idle during maintenance.
Unmarked directories are not deleted. Evicted or partial entries are misses.

### Native farm collection (first increment, #25)

`rvw.farm/1` records the explicit run-many plan, campaign-local cell IDs, options,
ELF hashes, hosts, per-shard completion, C1 outcomes and missing IDs. `complete`
means collection is complete. It does not mean tests pass or a gate accepts.
`rvw.farm-notifications/1` exports deterministic event IDs, campaign ID, event
kind, subject and details. DUT failures and infrastructure faults are distinct.
Collection-complete events do not claim pass. Delivery is `not_attempted`.
The export is read-only; external consumers own delivery and deduplication.
Host reservation stores are per OS user, not a cross-user admission service.
The static dashboard has no authentication layer.
New reports also carry `campaign_id` and the captured adapter `identity`.
`rvw.farm-classification/1` groups recorded executions by tool identity, ELF
hash and complete options. Every attempt retains its original outcome, source
report path and SHA-256, campaign ID and cell ID. An observed DUT failure keeps
the group failed even after a pass; that combination marks it unstable.
Infrastructure faults and missing outcomes stay separate. Different seeds and
builds cannot establish instability of one fixed execution identity. This is
recorded-outcome classification, not automatic retry or failure waiver.
The controller writes `plan.json` before dispatch and atomically replaces
`progress-N.json` after each validated cell and finished shard. `farm recover`
reads these checkpoints without mutation. Missing `farm.json` always gives an
inconclusive recovered campaign. Missing cells remain explicit. Recovery does
not infer a C1 outcome from unvalidated artifact files or confirm host cleanup.
A shard with a lost connection, wrong identity, missing C1 or invalid artifact
is inconclusive. Results retain their original failure outcomes. C1 config, seed,
ELF hash and every declared identity claim must match. Worker identity documents
must equal the supplied complete `/2` document. SHA-256 binds transferred files.

The first native SSH endpoint buffers transfers and uses a bounded run-many
process group. Separate SSH cancellation uses campaign control tokens. A host
acknowledges only after group cleanup and a host process-table check. Missing
acknowledgement is inconclusive. Host reservations share CPU slots, declared
memory bytes and named locks across workers. They report queue time and release
on handled exit. A persistent FIFO queue prevents newer requests from bypassing
older requests. Dead waiting tickets can be removed; active reservations cannot.
Reservations are cooperative, not OS CPU/RSS limits. Optional host `limits`
apply native hard CPU-seconds, file-byte and open-file limits before exec.
Linux also supports address-space-byte limits. Children inherit limits per
process. Unsupported requested limits fail closed. These are not aggregate
campaign CPU or RSS limits. The shard records its requested limit values. SIGKILL can leave
stale reservations; owner cleanup is required. Scalable streaming, crash recovery
and C3 gate import remain open. The static dashboard reads existing C3/C4/history. Recorded
C3 `ipc` and `coverage` metric samples are plotted by core, suite and config.
Pass rate divides conclusive passes by all recorded C3 tests. Run time sums all
recorded test `wall_s` values only when every value is present and valid. History
charts retain missing runs as gaps. These metrics do not prove plan completeness.
It does not establish bin compatibility or verification closure.
Dashboard filters select exact core, suite, config and gate values, plus a run-ID
substring. Counts and metrics use selected C3 suites. Missing evidence stays
visible when suite/config membership is unknown. Active filters are in the HTML.

## Lint and crossing inventory extension

`rvw lint` reads `rvw.lint-settings/1` from `--settings` or the project
`[lint] settings` path. Paths resolve against the settings file. See the
[lint guide](../rvw/src/rvw/lint/README.md) for fields and scope.
`rvw.lint/1` records settings and RTL hashes, native output, backend states,
structural inventory, exact waivers and match counts. Each finding has a SHA-256
`id` of its diagnostic data, backend, top and configuration. Waivers require
this value as `finding_id`, plus exact rule, endpoint, configuration and reason.
Structural diagnostic data includes `source_domain` and `destination_domain`
(the full domain records), `source_width` and `destination_width`. Changed clock
or reset records and changed widths invalidate the waiver.
A different source or message cannot reuse the waiver. Waived findings remain in
place. Missing backends remain `not_run`. Exit 0 means completed checks without
findings; 1 means active findings; 2 means input error; 3 means inconclusive.
Structural analysis cannot produce signoff. Its unrun rule inventory is mandatory.
No C4 gate acceptance is implied.
Structural reports also retain `reset_trees` (control cones with unknown-control
states) and `reset_crossings` (source and destination domain IDs). Different
reset signatures are candidates even when clock identity matches. Reset release
and reconvergence remain in the unrun rule inventory.
The structural backend also has `rdc`: `status` (`findings`, `protected`,
`inconclusive`, `no_crossings_found`; never `clean`), `domains` (reset
signatures with source, kind, clocks, register count and `release`) and
`crossings` (`source`, `destination`, reset domain IDs, `class`, `status`, and
`protected_by`/`reason` for declared protection). Settings `intent.isolation`
rows declare qualifiers with reasons. `waiver_findings` holds a
`lint.stale_waiver` error for each waiver that matched nothing in a backend that
ran; each waiver records `stale` (`true`, `false`, or `null` when its backend
did not run).
The structural backend also has `cdc`: `clocks` (per clock domain `kind`
`primary|divided|gated|generated|unknown`, `source`, `master`, `divide_by`,
`enables`), `obligations`, `memories`, `clock_groups` and `hierarchy`
(findings per component path). `crossings[]` rows gain `kind`,
`relationship` (`related`, `asynchronous`, `declared_*`, `unknown`), `stages`,
`library` and `width`. Settings `intent.clocks` rows declare clock groups with
reasons. `rvw lint --emit DIR` writes `rvw.cdc-obligations/1`
(`cdc_obligations.json`: `obligations` with `kind` `gray_code|data_stable`,
`bind` or `unbound_reason`; `checks`; `checked_rtl`; `unbound`), plus
`cdc_checks.sv` and `checked/` RTL copies. Emitted obligations are not results.
Lint settings may also have `rules` (rule severities and parameters) and
select backend `rules`, whose `findings` use `lint.*` rule IDs and whose `fsm`
list records `checked` or `inconclusive` state registers. `rvw lint --sarif PATH`
writes the same findings as SARIF 2.1.0 with fingerprint `rvw/finding-id`.
Backend `sdc` (settings `sdc`: `clocks`, `generated`, `multicycle`, `check`,
`register_pattern`, `output_pin`) returns `sdc` (generated text), `clocks`,
`spinal_synchronous`, `excepted`, `unsafe`, `check` and `sdc.*` findings.
`--emit` also writes `constraints.sdc`. SpinalDB adds table
`clock_frequencies(clock_domain_id, hz)` without a schema bump; a missing table
means unknown frequencies.

## Native backend semantic profiles

`rvw regress backends --json` maps backend names to semantic profiles. Fields
are `values`, `scheduling`, `x_handling`, `languages`, `assertions`, `foreign`,
`coverage` and `features`. `features` is the closed set of guarantees that a
component test can require. Unknown backends or requirements are errors.
Profiles describe the adapter invocation. They do not certify every installed
simulator version. Two-state runs cannot satisfy four-state or X/Z requirements.

## Cocotb component runs

`rvw regress cocotb MANIFEST --out NEW_DIRECTORY --seed N --timeout SECONDS`
accepts a JSON `rvw.cocotb/1` manifest. Required fields are `schema`, `name`,
`backend`, `top`, nonempty `sources` and `test_module`. Optional fields are
`python_paths`, `requires`, `clock` and `reset`. Paths resolve from the manifest.
`clock` has `signal` and positive `period_ns`. `reset` needs a clock and has
`signal`, `active` (0/1), and positive `cycles`. Testbenches call the optional
`rvw.sim.bench.start` helper for clock/reset setup. The native runner receives
the recorded seed. Requirements must be in the backend profile's feature set.

The adapter writes standalone C3 with `kind: "cocotb"` entries, seed, semantic
profile, declared source/Python input hashes, timeout, log/XML/request artifacts,
and replay arguments. It does not produce C1, C8 completeness or C4 acceptance.
The output must be new. Missing/empty/invalid XML, skips, timeouts and runner
errors cannot pass. Exits are 0 for all pass, 1 for test failure, 2 for errors.
See `rvw/src/rvw/sim/README.md` for exact limits and artifact paths.

## SoC project data

`rvw.soc/1` is an explicit input to `rvw soc generate MAP --out DIR`.
It does not change `rvw.project/1` selection. See the [SoC map contract](../rvw/src/rvw/soc/README.md)
for all fields and export limits. `rvw.sim-map/1` contains `address_bits`,
`regions` and `interrupts` from the validated map. The `schema` identifies the
consumer format. It does not imply that an adapter loaded the data.
Generation returns exit 0 with `status=generated`, or exit 2 with `status=error`.
No generation result is a design consistency verdict.

`rvw.soc-bindings/1` selects exact signal paths and decoder assignment keys from
SpinalDB `/20`, plus translation expectations for paired transaction samples.
`rvw soc check MAP --bindings FILE --db DB [--transactions JSONL] --json` writes
`rvw.soc-check/1`: `status`, `checks`, `gaps` and `transactions` (sample count).
Checks have `name`, `actual`, `expected`, and `status` (`consistent`, `mismatch`,
`unavailable`). Overall `mismatch` exits 1, `inconclusive` exits 3, and malformed
input exits 2 with `status=error`. No check result can grant C8 acceptance.
The [SoC tool README](../rvw/src/rvw/soc/README.md) defines the bounded evidence.

### C9 offline event fitting

`rvw arch fit PLAN --json` and MCP `arch_fit` consume `rvw.arch-fit-plan/1`.
The exact fields are `schema`, `rtl`, `candidates` (name to gem5 report path),
`train`, `held_out`, `events`, `scope`, `uncertainty`, and `unsupported`.
Paths resolve against PLAN. Each event has `name`, `rtl_metric`, `gem5_stat`,
`unit`, and `semantics`, plus optional `role` (`fit` or `consistency`). Events map raw C1 `metrics` to the first ROI stats
block in gem5 `stats.txt` beside `bare.json`. Event semantics are a project
assertion. All mapped values must be finite and nonnegative. Missing values
are errors. Existing C9 comparison evidence checks apply to every candidate.
Train and held-out IDs must be distinct, nonempty and cover all report IDs.
Their ELF hash sets must also be disjoint. Renamed ELF copies cannot be held out.

`rvw.arch-fit/1` records status `reported` or `inconclusive`, the selected candidate, training
scores, the winner's held-out score, winner event errors, split IDs, mappings,
scope, uncertainty, unsupported structures, plan/RTL/candidate report hashes,
and raw stats paths and hashes. Error is `abs(model-RTL)/max(1,RTL)`.
Instruction units, retired totals, instruction-class totals and commitStats
are consistency checks, even with role `fit`. They do not enter the objective.
Other events default to `fit`; role `consistency` excludes a project-owned fixed event.
The objective averages relative cycle error and eligible event errors per
workload, then averages workloads. `selected_errors` includes each event's
resolved role. `headline` includes `metric=cycle_relative_error`, per-workload
comparison rows (cycle gap and IPC ratio), and mean absolute cycle error per split.
Fewer than three training workloads, constant training cycle or eligible event targets, or equal
scores across multiple candidates give status `inconclusive` with a reason.
`event_fit` lists eligible events and constant targets. No eligible events or
insufficient target variation gives event-fit status `inconclusive`. Only training scores
select the winner. Lexical candidate names break ties. No acceptance or
confidence claim follows from this report. The caller must keep held-out
workloads separate when creating candidates. This offline command runs no parameter search.
Use the search extension below to generate parameter candidates.

### C9 static compatibility preflight

`rvw arch inspect --elf ELF --isa ISA --kind KIND --json` checks static ELF
layout independently of performance calibration. MCP exposes `arch_inspect`.
`rvw.arch-compatibility/1` records status, ELF path/hash, ISA, XLEN, CPU kind,
RAM base/bytes, required symbol addresses/sizes, blockers and limits.
Supported input labels are `rv32im`, `rv64gc`, `rv64gc_zba_zbb_zbs` and CPU
kinds `o3`, `minor`, `timing`. ELF class must match XLEN. Required runtime
symbols and the fixed RAM layout are checked in ELF32 and ELF64.
RV64 O3 and RV32IM Minor/TimingSimple return `compatible` (CLI exit 0).
Other known combinations return `unsupported` (CLI exit 2) with a CPU/ISA blocker. Unknown
labels or invalid files give the normal error object and exit 2.
Compatibility does not establish instruction behavior, ISA extensions,
ROI counter validity or model fidelity.
MCP returns the same status in the result of its background job.

### C9 SoC description extension

`rvw.arch-core/1` accepts optional `soc` as documented in `Arch/README.md`.
Its exact keys are `levels`, `interconnect`, and `memory`. Levels are an ordered
array of zero to two scalar Cache parameter objects (L2, LLC). Interconnect
requires width and the four crossbar latency parameters. Memory selects
`simple` (latency, bandwidth) or `dram` (model, controller, interface).
DRAM models are DDR3_1600_8x8 and DDR4_2400_8x8. One classic memory path and
one controller are supported. The address window does not change.
SoC runs are model-only. C1 fixed-latency calibration refuses this extension.

### C9 memory interval reports

`rvw.memory-observations/1` and `rvw.memory-report/1` use the fields and units
in Arch/README.md, Memory observations. Reports preserve all input counters,
observation identities and evidence hashes. Missing metrics are null and listed
as unobserved. Status reported means arithmetic completed. It does not validate
the producer's mapping or establish the cause of contention.

### C9 bounded experiment extension

`rvw.arch-sweep/1` declares parameters (dotted paths to value arrays), max_points
and timeout_s. `rvw arch sweep` and MCP arch_sweep implement the limits and
identity rules in Arch/README.md, Small design-space sweeps. Unknown fields
are errors. `rvw.arch-dse/1` records the input hash, model-only point records,
objective and speed-only Pareto list. Its status is reported only when all
points produced reports; otherwise it is inconclusive (CLI exit 3).
SQLite points retain completed and incomplete trials. Null area and power
and unquantified uncertainty must not be interpreted as zero cost or confidence.

### Linux reference reports

`rvw arch linux firmware|build|prebuilt|prepare|boot` writes `rvw.linux/1` to
`OUT/manifest.json`. `OUT` must be new. The JSON stdout uses the same object on
success. Errors return exit 2; an initialized output keeps an inconclusive
manifest and command log. These reports do not produce a C4 verdict or claim
C8 completeness. `rtl_boot` is `not_run`; `equivalence` is `not_checked`.

`built` means files were constructed. `prepared_reference` means images and
QEMU tables were captured and the selected properties matched project data.
`reference_userspace_observed` additionally requires a clean QEMU exit, the
fixed userspace marker and power-down message, with no kernel panic.
Artifacts use absolute paths and SHA-256. The build report binds the source and
configuration. Reference runs bind kernel, initramfs, firmware, DTB, platform,
QEMU, command line and console. Selected table checks record expected and
actual values separately. They are not device-state or timing checks.

The `prebuilt` action takes `--source` (`rvw.linux-prebuilt/1`) and `--images`
(the native firmware directory). The source declares HTTPS URLs and SHA-256
for `Image` and `rootfs.cpio.gz`. `initramfs_selection` declares directories,
source-to-target regular files and symbolic links. The action selects these
bytes from the checked newc archive and adds `/rvw-init`. The report records
upstream hashes, source-lock hash, init-script hash and transformed artifacts.
It does not verify an upstream package signature. Device compositions and
bounded startup reports in `examples/qemu-linux` are project data. They do not
extend C1 or certify a connected RTL device bus.

The explicit `--platform` JSON uses `rvw.linux-platform/1`: `machine=virt`,
`harts=1`, `memory_mib=128`, `command_line`, and nonempty `dt_checks`. Each
check has `node`, `property`, `type` (fdtget format) and `expected` (exact text).
It is independent of the project's C1 selection. Network, storage devices and
console input are disabled. RTL loading and device replay remain unsupported.
See `Arch/README.md` for pinned sources, host limits and the close condition.

### Core-owned ISA declarations (optional)

`rvw.isa/1` JSON declares an expanded `isa` string, `extensions` keyed by
extension name with `version` (string or null) and optional `requires` list,
`options` object, and optional `consumers` mapping tool names to ISA strings.
Null means not verified. `rvw cov isa-check` validates these declarations.
This optional file does not change the project selection contract.

For generated functional bins, the ISA manifest can include `source` with
`url`, a full commit `revision`, and `files` (relative opcode paths to SHA-256).
`arg_lut.csv` defines the encoded operand fields. `unavailable` lists excluded
coverage scope. Optional `specifications` stores other spec pin declarations.
The functional report embeds the generated plan in `config.isa_plan`. Its
fingerprint includes all pins and generated bins. `sequences.distances` in a
functional plan enables retirement-order pair bins. These additions do not
change the C2 trace format. `rvw.isa-diff/1` reports proposal changes and an
explicit `adoption_required` flag. It does not adopt specifications.

### Proof dependency report: `rvw.proof-cones/1`

`rvw cov prove` writes `proof-cones.json` beside `exclusions.json`. The latter also
embeds this report in `proof_cones`. This is informational evidence. Applying
exclusions does not validate this report as a certificate. It changes no coverage
counts and supplies no mutation results.

| Field | Meaning |
|---|---|
| `schema` | `rvw.proof-cones/1` |
| `source_snapshot` | The parent proof's frozen source snapshot reference |
| `top` | Flattened Yosys top module |
| `logic[]` | Cell `id`, elaborated `name`, Yosys `type`, optional `source` |
| `properties[]` | One row per reviewed plan point, in plan order |
| `outside_proven_cones[]` | Logic cell IDs outside all resolved, proven structural cones |
| `untested_assumptions[]` | Assumption cell ID, name, source and `status: not_tested` |
| `limits` | Explicit evidence limits |

Each property row has `property_id`, `point_id`, `requirement_ids`, `expression`,
`proof_status`, `proof_job`, `activation`, `proof_core` and `cone`.
`property_id` defaults to the stable plan `point_id`. Optional `requirement_ids`
are nonempty strings. Duplicate property IDs refuse the plan. Requirement IDs and
property IDs are join keys for external requirement obligations and activation
records. This report does not assert that an obligation is complete.

`proof_status` is `proven_conditional` only for an unbounded proof job with PASS,
exit 0 and no reported free wires. Otherwise it is `not_proven`. `proof_job`
retains the parent's local job paths and hashes, or is null. All proof assumptions
and all parent exclusion guards still apply. Activation is `{"status":"not_measured"}`
unless a separate declared activation cover runs, as specified below.
The solver does not export a proof core in this flow. `proof_core` has
`status: unavailable`, `cells: null` and a reason. Null is not an empty proof core.

`cone` has `status`, `cells` and `problems`. A resolved cone has status
`structural_overapproximation`. Missing names, netlists or unsupported cells give
`inconclusive`; such a cone contributes no reached logic to the union.
Fan-in traverses every input of each driver cell, including sequential feedback,
clock and reset. Whole buses are traced even for a selected bit. Constants end a
path. Constraints from assumption cells are not added to the cone.
Cell IDs are SHA-256 of snapshot hash, NUL, top, NUL and elaborated cell name.
They join rows within a frozen snapshot. They do not promise stability across
changed elaborations. Formal cells are excluded from the logic universe.

Logic outside these cones remains unverified by these expressions. It is not
proven irrelevant. The assumption list does not measure assumption activation,
necessity or adequacy. A cone is not a minimal solver proof core. Its size is not
functional coverage. Keep this evidence separate from MCY killed/survived results.

### Coverage mapping denominator fields

`rvw.coverage-report/1` adds `scala_mapping` with `mapped`, `denominator`
and `unit`. Each instrumented point counts once in that denominator.
`instance_scope` maps recorded hierarchy strings to `scope`,
`instrumented_points` and `exact_instance_denominator`. A wildcard gives
`scope: aggregate` and a null exact denominator. Missing hierarchy gives
`scope: unknown` and null. Literal hierarchy gives `scope: instance`.
No report expands aggregate counts into inferred physical instances.


### Typed RTL sampling coverage

`rvw.rtl-plan/1`, `rvw.rtl-samples/1` and `rvw.rtl-coverage/1` are the
project-defined RTL event sampling contract. See the coverage README for all
fields and refusal rules. Plan identity is SHA-256 over sorted compact JSON.
Every trace binds that identity and the design identity. Only unsigned integer
values sampled before a rising edge with disable-clear reset are supported.
Exact instance paths and an explicit bin universe define the denominator.
Incomplete traces give inconclusive results. Unobserved is not unreachable.
C2 retirement events and speculative RTL events remain separate domains.


The RTL plan can also declare bounded first-match `sequences`. Every later
step gives an inclusive sample-delay range. Reports separate activation,
completion, expiry, reset cancellation and trace-end pending attempts. Reset
clears all attempts. Each input starts fresh temporal history. Unsupported
clocks, reset rules or delay semantics refuse the calculation. See the
coverage README for the full sequence contract and native example.

## Experimental C reference datapath result

`SpinalChecks/c2rtl/check.py` writes `rvw.c2rtl/1`. It is a standalone experiment,
not C1 run evidence or a C4 gate verdict. `status` is `proved`, `counterexample`
or `inconclusive` (exit 0, 1 or 3). `width`, `signed`, `latency_cycles`,
`handshake`, `depth` and `input_pairs` state the comparison contract and bound.
The supported domain has two unsigned inputs and one unsigned output, each
1 to 4 bits, no state, no handshake, no assumptions and depth 1.
`proved` means all enumerated input pairs match the compiled C truth table.
`counterexample` requires SBY FAIL and a witness testbench. Missing, timed out,
unsupported or ambiguous evidence is inconclusive. It never grants gate accept.
`inputs`, `tool_files`, `tools`, `environment`, `commands` and `artifacts` record
source identities and reproduction data. `traces` names witness artifacts;
`reason` explains inconclusive results. A new output directory is required.
See [the C reference flow](../SpinalChecks/c2rtl/README.md) for the C-model
review requirement, native runtime trust and FP limits.

### Counterexample replay observations

`rvw formal cex` and MCP `formal_cex` write `rvw.formal.cex/1` to a separate
output directory. This is an observation format, not `rvw.formal/1` proof evidence.
`status` is always `inconclusive` (CLI exit 1). `disposition` is `reproduced`,
`failure_not_observed`, or `inconclusive`. The first two require an original replay
that observes a property named in the formal failure report. Reproduction also
requires that same property in the edited replay. Assumption violations and tool
failures remain inconclusive. Absence of an observed failure is not a pass.

`original_result`, `input_capture`, `restrictions` and `edits` retain the declared
inputs and environment. `baseline` and `edited` contain the Yosys sim summaries.
`wave` and `fst` name the edited replay artifacts. Optional `navigation` records
type-check, cause-trace and viewer launch outcomes. A viewer launch does not
establish successful source navigation. See the formal command README for limits.

### Formal bounded depth-search termination

`rvw.formal-depth-search/1` records `stop_reason`: `max_depth_reached`,
`budget_exhausted`, or `attempt_<status>`. `support` records the doubling
schedule, initial and maximum depths, total budget, per-attempt timeout and
engine selection. Engine portfolios and depth search are separate choices.
Every attempt uses at most the remaining budget as its timeout. Frontend and
capture overhead can exceed this budget. No new attempt starts after expiry.
A bounded pass at the maximum depth remains `inconclusive`. Only a concrete
failed attempt gives aggregate `fail`. Search never claims an unbounded proof.


### Formal simulation-state swarm

`rvw.formal-swarm/1` has aggregate `status: inconclusive` and exit 1. `selection`
records the uniform cycle interval selection. `attempts` retains each cycle,
status, relative result path, restrictions and loaded-state coverage. A refused
state has `status: error` and a reason. `missing_cycles` lists tasks not started.
`bounded_passes` and `conditional_failures` count observations only. They cannot
earn reset reachability, gate acceptance or unbounded proof. Sources, includes,
checks and waveform are copied once in the parent `input_snapshot`. Child
results retain their own full tool/input captures and solver evidence.


### Formal exact proof reuse

`rvw.formal/1` results can include `proof_cache` with `key`, `hit` and the checked
`rule`. The optional `bmc`/`prove` cache stores complete successful SBY evidence
under a SHA-256 input key. `rvw.formal-proof-key/1` binds complete prepared input
artifacts, script, captured files, tool payloads/versions, captured environment,
Python identity and formal/common runner code. Only the owned output prefix is
normalized. Whole-model identity is required; no inferred cone independence is
accepted. Entry manifests hash all retained evidence and provenance. Fresh input
capture, frontend checks, tool verification and bounded reachability remain
mandatory on hits. An invalid entry is a miss. Only successful results with
assertions and reachable guards enter this cache. Mounted directory sharing
requires C8 trust; no remote authentication or gate acceptance is supplied.


### Formal memory encoding

`rvw.formal/1` BMC/prove results record `memory_model.requested` (`auto`, `array`,
`map`), `retained_memory_cells` (prepared `$mem_v2` count, or null without a
model), and `semantics`. Explicit array mode requires an SMTBMC-only portfolio.
Map mode uses Yosys `memory_map -formal`. Both model the supplied RTL memory.
Neither adds a RAM/blackbox refinement contract or resolves undefined RTL
behavior by choosing a value. The retained-cell count is not a refinement proof.

### CDC sequential reconvergence depth

Lint intent accepts `reconvergence_depth` (integer 1..64, default 1). It bounds
register boundaries between synchronizer outputs and each sink. Findings retain
each synchronized endpoint and its minimum register depth in `reconvergence`.
Combinational edges do not consume this bound. Cycles are bounded. Memory and
blackbox internals remain outside scope. This is structural evidence only.

Lint settings can select optional backend `yosys`. Native `check` warnings use
`yosys.combinational_feedback`, `yosys.conflicting_drivers`, `yosys.undriven`,
or fallback `yosys.warning`. Findings retain elaborated bit IDs and available
source attributes. Backend output includes `elaborated_modules` and `script`.
Blackbox modules cannot earn a completed connectivity check.

### Selected CDC protocol and simulation results

`rvw lint --protocol MANIFEST --out NEW_DIRECTORY` accepts
`rvw.cdc-protocol/1` with exactly `schema`, `kind`, `top` and `verilog`.
The selected kinds, fixed port interfaces and digital sampling abstraction are
specified in the lint guide. Sources are frozen before native elaboration.
`rvw.cdc-protocol-result/1` records `status`, `proof_kind`, `kind`, source hashes,
the native child `result`, model, limits and `activation: not_measured`.
A pass only applies to the selected monitor and environment. It is not a
structural waiver or whole-design CDC verdict. No C4 acceptance is emitted.
`--simulate SAMPLES --seed SEED` instead emits `rvw.cdc-simulation/1` with
status, kind, seed, requested sample count, input hashes and limits. Missing
tools and incomplete execution are inconclusive. A simulation pass needs the
completion marker and no failed monitor assertion. It is not a proof.

Selected CDC protocol kinds also include `pulse_capture` (single injected pulse,
four destination-event response bound) and `coherent_bus` (equal-coded two-bit
output). The lint guide defines their exact interfaces and assumptions.
`rvw lint --benchmark MANIFEST --out NEW_DIRECTORY` accepts `rvw.cdc-bench/1`.
Cases pin source hashes and independent expected results. Optional commercial
adapters receive the same frozen spec and monitor, but not the expected verdict.
`rvw.cdc-adapter-response/1` must bind the exact request hash, mode, tool version
and verdict. BMC passes must reach the requested depth. All observations and
per-tool qualifications stay in `rvw.cdc-bench-result/1`. Missing commercial
adapters are `not_run`. Suite agreement is not signoff or commercial parity.

## Hardware leakage campaign result

`rvw formal security contract` writes `rvw.leakage/1` in `result.json`.
`verdict` is `violation`, sampled `no_violation`, or `inconclusive`.
Exit codes are 1, 0, and 3 respectively. This is separate from a C4 accept or
formal proof. `cases`, `compared_pairs`, `zkt_add_comparisons`, `zkt_verdict`,
`violations` and `errors` preserve the tested scope. A case with missing evidence
or architectural differences cannot contribute a clean comparison. No comparable
pair is inconclusive. A witness can coexist with incomplete cases.

The sequential Spike contract exposes retired PCs and memory addresses. RTL
adapters return `complete`, reference-comparable `effects`, strictly increasing
retirement `cycles`, and integer `observations` for exactly the declared channels.
The runner compares only equal public contexts and equal contract traces.
It records source inputs and adapter responses. Adapters must bind their native
tools and all external dependencies. See `rvw/src/rvw/formal/security/README.md`.
The hardware threat model and unmodeled channels do not expand C8.

### Formal campaign observations in C3 and C4

`rvw formal sby-regress` writes standalone C3 suites named `formal-sby`.
Each row names one single-assertion SBY job. Extra fields retain `formal_status`,
`requirements`, `assumptions`, `configuration` and `job_sha256`.
`formal_status` is `bounded_pass`, `unbounded_engine_pass`, `counterexample`,
`timeout`, `unknown` or `error`. C3 maps engine passes to `pass`, counterexamples
to `fail`, timeouts to `timeout`, and other states to `error`.
Every row carries an `inconclusive` reason: input closure, property attribution
and vacuity are not checked. A raw engine pass cannot earn acceptance.
C4 records `verdict: inconclusive` and `tests: incomplete`.
Retained standalone C3 directories form the history store. Each sample keeps
configuration and assumptions. Samples cannot be pooled into one proof.

Formal results add `proof_kind: bounded | unbounded`.
Only `formal prove` selects unbounded mode. Depth-search summaries use
`rvw.formal-depth-search/1`, retain attempt paths and statuses, and report
`max_bounded_pass`. Their status is `fail` or `inconclusive`; never proof.
Cut-point records name the signal, width and `unconstrained_anyseq` semantics.
An abstract counterexample records `status: unknown`, not a concrete failure.

### Bounded riscv-formal results

`rvw formal riscv` writes standalone C3 `results.json` and C4 `verdict.json`.
Each requested task is a C3 entry. PASS requires exit 0 and SBY PASS. Missing
status, unreachable retirement cover, tool errors and wall timeouts are
inconclusive. Without retirement cover, assertion PASS entries carry an
`inconclusive` reason. `source.formal_inputs` records input hashes;
`identity_complete` is false. The suite records the maximum selected check depth as `bounded_depth` and the settings.
C4 rejects assertion failures. Other outcomes remain inconclusive, including
complete bounded tests. These files cannot establish committed gate acceptance.
C1 is not emitted because these jobs do not execute an ELF.

`check_options.<exact check name>` can set `cycles`, `engine` and `defines`.
Cycles are `[check]` for instruction checks, `[start, check]` for consistency
and cover checks, and `[start, trigger, check]` for liveness and unique.
Each C3 entry retains these values in `formal_settings`. Engines are
`abc bmc3`, `btor btormc` or `smtbmc` with a supported solver. Cover needs SMTBMC.
ABC jobs omit the unsupported SBY `skip` option. The checker cycle still
controls when each assertion fires. `instruction_models` maps instruction
names to model files. The runner copies these over the private checker tree
and hashes them. It does not modify the upstream models.

## Formal event model extension

BMC can explicitly select a sampled event model with `--event-model` and repeatable
`--event-clock PORT`. Extra clocks must be rising-edge top inputs.
`--async-reset` separately enables constant-value reset FFs (`$adff`, `$adffe`).
SBY `multiclock on` applies Yosys `clk2fflogic`. Each step is a global input
sample, with arbitrary clock rates, phases, simultaneous edges and stalls.
Optional periodic schedules constrain sampled clock ratios and phases, as specified
below. Unscheduled clocks have no ratio constraints. No fairness is inferred.
Async reset pulses visible for a sample are represented without a clock edge.
Pulses wholly between samples and analog timing are outside the model.

`rvw.formal/1` BMC results in this mode add `event_model`:
`backend`, `step`, `clocks`, `relationships` and boolean `async_reset`.
Failure `step` counts global samples; `cycle` is null.
The reset harness counts primary-clock edges, not global samples.
Other domains need not see an edge during that reset interval.
`from-sim` and X flows retain their single-clock refusals.

Inserted `rvw.checks/1` check entries add nullable `clock_domain`:
`clock`, `edge`, `reset`, `reset_kind`, `reset_active` and `clock_enable`.
Signal names are relative to the design top. Unavailable signal names are null.
This field records the check's Spinal domain, not a relationship constraint.
Older reports without this field remain readable.

### Sequential equivalence result (`rvw.formal.equiv/1`)

`rvw formal equiv` compares two captured RTL file sets. It writes `result.json`.
`status` is `equivalent`, `not_equivalent`, or `inconclusive`. Exit 0 requires a
successful eqy run, at least one partition, PASS for every output partition, and
complete register matching by default. `--unmatched-state prove` instead checks
closed output cones without name pairing, as specified below. A timeout or unknown
partition cannot earn equivalence. Exit 1 covers the other two statuses. A busy or invalid
output directory exits 2. `not_equivalent` requires a failed output partition and
a VCD counterexample in `traces`. There are no internal state equality assumptions.
`state_mapping` records automatic or manual pairs and their widths. `unmatched`
lists unpaired registers on each side. `partitions` records each partition status.
`inputs` contains each side's capture and snapshot records. `restrictions` records
the single-clock, two-state model, reset alignment, unchecked startup clocks and
the declared fixed output latency difference. Blackbox obligations are refused. Optional `dsec` evidence
is advisory; `scorr; pdr` partition evidence sets the verdict. See the formal README
for the supported subset and initialization limits. This contract is separate from
bounded assertion results in `rvw.formal/1`; equivalence is an unbounded proof under
the recorded restrictions. A wall-time budget does not bound the cycles proved.

#### Register relocation matching

`state_mapping.method=unique_leaf` records an unmatched register pair with the
same leaf name and width. Each leaf must occur once on each unmatched side.
Manual and exact-name pairs have priority. This mapping adds no assumptions.
Ambiguous leaves and width changes remain unmatched.

### Directed MMU regression inputs

`rvw regress mmu` extends the existing ELF suite flow. It does not change C1–C4.
Its tool-local formats are `rvw.mmu/1` (scenario description),
`rvw.mmu-pma/1` (core-owned PMA declarations), `rvw.mmu-build/1` (ELF/hash manifest),
`rvw.mmu-reference/1` (Spike self-check results) and `rvw.mmu-check/1`
(C1 completion plus strict C2 oracle comparison). Field rules and limits are in
`rvw/src/rvw/regress/README.md`. Scenario bins are architectural-effect coverage.
A declaration or generated program alone gives no coverage. PMA declarations
are recorded inputs and do not imply PMA device observations.

### C1 persistent simulation session extension

`serve` requires `CoreAdapter.freshInstancePerRun = true`. The adapter declares
fresh DUT and harness state for each run. Other adapters cannot use `serve` and
record `reset: "adapter-defined"` in ordinary run metadata.
`serve` accepts JSONL run-option objects on stdin. Each response uses
`schema: "rvw.sim-server/1"` and contains `result` (C1) or `error` (a string).
`{"op":"shutdown"}` returns `shutdown: true` and ends the server. EOF also ends
it. Cancellation ends the whole process group. An abandoned worker ends the
server with exit 2 after its timeout response. Other run failures do not end it.
C1 `execution_mode` is `server` for server requests and `process` for ordinary
runs. Error and abandoned results also retain this field.
C1 `details.simulation_session` has `id` (process UUID), `model_run` (one-based
completed-run number per model), `rtl_sha256` (the generated Verilog hash,
null when unavailable), `reset: "new-native-instance"` and
`verilator_cached` (native cache hit at model compilation). These fields are
metadata. They do not prove reset equivalence. `details.execution_s` measures
adapter execution after model readiness. Existing RTL, native and source
identity fields still apply. Source edits require a server restart.
C1 `details.model_timing`, when present, records `elaboration_s` and
`native_and_setup_s`. The latter includes native cache lookup, workspace setup
and loading. Scala compilation and lock waits are outside these measurements.

Native identity namespace `native-inputs-v27` also accepts numeric Verilator
`--threads`, `--output-split` and `--output-split-cfuncs` options. Threads must be
positive. Values contain at most nine decimal digits. Unknown options and file
inputs still refuse capture. All exact option bytes remain identity inputs.

### C1 regression persistent worker pool

Regression defaults to persistent runs for `core.backend = "riscvsim-verilator"`.
An explicit `core.persistent = false` disables this default. Other adapters stay
opt-in. Each worker receives `run-many --persistent --jobs 1` and owns a separate
process group. `core.jobs` or regression `--jobs` selects the pool size. Each
process reuses its compiled models and requires the fresh-instance declaration.
Crash or timeout results do not grant a pass. Regression retries missing results
in a new process. Generated RTL identity remains required for result reuse.
The direct RiscvSim `run-many --persistent` command remains serial.

### From-reset replay descriptor

`rvw.replay-checkpoint/1` has `mode: "from-reset"`, a selected cycle, original
C1 path and SHA-256, C2 SHA-256, input identity, trace suffix and descriptor `id`.
The ID hashes the sorted compact JSON object without `id`. Verification rereads
original evidence. `rvw.replay-equivalence/1` with `status: "equivalent"` means
only that input identity, terminal result and suffix events match. It is not a
live snapshot or an architectural correctness verdict. External effects are
unsupported. Missing identity, changed evidence or differences exit 2.

### Source-revision equivalence export

`rvw formal equiv --gold-rev REV --gate-rev REV --top MODULE` selects
committed revisions from the selected project's `core.source_repo`. It requires
`core.source_env`, `query.build` and `formal.export_dependencies` (a nonempty
list of generator repository paths). Each generator repository must be clean.
The export records its commit. The build runs on a `git archive` source copy,
with `core.source_env` set to that copy, under the project's lock.
`query.build CONFIG DB --rtl DIR --no-pdg --no-blocks --no-hgldd` must generate
Verilog in DIR. Yosys selects MODULE and its child modules with `hierarchy -check`.
Missing modules or build failures cannot earn an equivalence verdict.

The result's `exports` records source commits, generator commits, configuration,
commands and RTL hashes. Each side retains source, generated RTL, selected module,
logs and `export.json`. Export directories must be new. This supports declared
sbt dependencies. It does not capture arbitrary external generator file reads,
network services or environment effects. Project authors must declare all generator
repositories. Submodule source content is not exported by `git archive`.

Directed MMU extensions retain the existing C1-C4 verdict rules. Control rows,
data corner fields, the optional adapter `rvw.mmu-observations/1` capture and
`rvw.mmu-coverage/1` inventory follow the regress README. `mmu check` additionally
binds `manifest_sha256` and each row's `c1_sha256`. A coverage report verifies
these hashes before using architectural bins. Observation counts are separate
from coverage. `recorded` is not a correctness pass.

Native farm collection also checks explicitly requested `max_cycles` and `mem_latency`
against C1 results. Missing or different values make collection inconclusive.

### C1 firmware payload extension

RiscvSim accepts `--elf-load-bias BYTES` (nonnegative decimal, default zero).
It applies only to self-relocating ET_DYN firmware. `elf_load_bias` records it
as a decimal string in C1. The ELF hash still identifies the original bytes.
ET_REL and PT_INTERP are unsupported. The loader does not apply dynamic
relocations. The adapter controls initial PC, privilege and GPRs.

`--boot-payloads PATH` selects a `rvw.boot-payloads/1` JSON object with `ram`
(`base`, `size`) and `payloads` (`file`, `address`) arrays. Addresses and sizes
are strings, in decimal or `0x` notation. Resolve files relative to the manifest.
Capture bytes before compilation. Reject overflow, overlap (including BSS),
empty payloads and ranges outside the declared RAM before the first write.
An adapter must declare support and load through `RunContext.loadMemory`.
Unsupported adapters must refuse this option. C1 `details.boot_payloads`
contains `path` and `sha256` for each input. `details.boot_loads` lists each
segment's `address` (hex string) and `size` (decimal string), in load order.
The replay command retains both loader options. These fields describe memory
placement only. They make no device, reset, Linux boot or timing claim.

### C9 RV32 in-order extension

Descriptions accept `kind="minor"` or `kind="timing"` only with `isa="rv32im"`.
O3 keeps its RV64 ISA choices. The CPU classes are RiscvMinorCPU and
RiscvTimingSimpleCPU. In-order descriptions require `queues=[]` and
`predictor=null`; CPU defaults apply. `cpu={}` selects all defaults.
Both caches can be null to bypass them. In-order SoC extensions are refused.
Optional `ram_bytes` selects page-aligned RAM capacity up to 512 MiB at the
existing base. The default remains 512 MiB. ELF segments must fit that range.
RV32 builds use ilp32 and stable high/low/high reads of 64-bit mcycle/minstret.
The guest still exports two 64-bit bench_stats words.
Static compatibility does not certify native execution or cycle fidelity.

C1 adapters can publish project-defined live ROI event numbers in `metrics`.
The project owns event names, observation points and mappings to gem5 stats.
They must not be inferred from model statistics. The VexRiscv example observes
RVFI retirement, excludes the first retired setStats entry and includes the
second. It publishes roi_retired, roi_loads, roi_stores and roi_branches only
with two markers and complete bench_stats stores. The CSR delta window stays
separate. Missing events remain missing; fitting refuses them. See the example
architecture README for opcodes, limitations and the saved-candidate fit plan.

### Generated SoC runtime input

C1 jobs can set `soc_map` / `--soc-map` to generated `rvw.sim-map/1`.
The parser captures the map bytes. C1 records `soc_map_sha256` and lists the
saved `sim-map.json` and `soc-transactions.jsonl` in `artifacts`.
`rvw.soc-capture/1` starts with `map_sha256`, `identity` (source and RTL hash), and
`observation` (`harness_decoder` or `map_monitor`). A map monitor classifies
accepted requests. It does not observe an actual RTL decoder select.
Request lines have `cycle` (integer string), `bus`, `address` (hex string),
`size` (byte count string), `write` (boolean) and `selected` (region name or null).
`{"event":"end"}` ends capture. These are harness request/endpoint observations.
They are not software-to-bus pairs. An incomplete stream cannot establish coverage.
`rvw soc capture-check` gives mismatch (1), inconclusive (3), or input error (2).
It has no pass verdict. `--platform` in cosim can also read `rvw.soc/1` directly.

SoC capture request identity: `rvw.soc-capture/1` headers carry a nonempty
`identity.run_id`. It is a fresh UUID for each simulation request. C1 records the
same value in `details.simulation_session.run_id`. `soc capture-check` requires
both values to match. A session UUID, ELF hash and seed alone do not identify one
request in a persistent session. Captures without a request ID are refused.

Request and process UUIDs belong to `RunContext.captureIdentity`. They do not
appear in the C2 header (`RunContext.rvfiHeader`). Equal simulation inputs keep
stable trace header bytes across fresh and persistent runs.

### Coverage semantic plans and closure suggestions

`rvw.isa/1` may include `semantics` with `version: 1`, `privilege_modes` and
an `exceptions` map from pinned instruction names to expected synchronous cause
numbers. These declarations participate in functional plan identity. They are
coverage targets, not reference outcomes or reachability proofs. Semantic operand
classes use C2 operand values. A per-instruction exception hit requires adjacent,
same-cycle trapped-instruction and synchronous trap records. Incomplete cause
correlation earns no hit. Sequence plans may select `kinds` as well as `distances`.

`rvw.coverage-candidates/1` has a `tests` array. Each item has `id`, `targets`
(nonempty glob patterns over bin IDs), integer `priority`, and `reason`.
`rvw.coverage-closure/1` hashes the report and candidates. It lists `unhit` bins
with separate `observation`, `reachability`, and `excluded` fields. Each bin has
ranked `candidate_tests`. Candidate rank is declared priority, not a measured
probability. No candidate changes a hit count or a reachability result.

RiscvSim exports native Spinal event tags as the existing `rvw.rtl-plan/1`.
IDs include physical instance paths. The complete plan hash supplies merge
identity. The exporter rejects pruned signals and conflicting source/type links.
Code coverage collection uses native `--coverage-per-instance` on checked
Verilator 5.052 or newer. Older or unknown tools keep collapsed coverage. Existing wildcard
hierarchies retain unknown exact instance denominators. Optional SpinalDB
attribution verifies the captured RTL hash and maps covered assignment targets
to Scala declarations. This attribution does not prove Scala statement coverage.
Schema `/20` memory-key `MemSymbolesTag` names can supply exact emitted memory
aliases for declaration attribution. Unknown or conflicting aliases are not guessed.
Coverage source links record comment, declaration, or mixed attribution methods.
Branch-operand declaration links are navigation evidence, not Scala statement hits.
Instance scope records include mapped and unmapped point counts.
Uncompleted RTL sequence goals can appear in `unhit` with `kind: sequence` and
`pending`. Pending activations do not establish unreachability.

The optional lint settings `intent` object contains `protocols` and `reset_order`.
The lint guide defines their exact fields. Structural `depth` records matched or
invalid protocol declarations, direct two-stage structures and declared reset
ordering. Protocol declarations and reset-order pairs are assumptions. They do
not earn protocol or release proof. New rule IDs are `cdc.handshake_candidate`,
`cdc.handshake_invalid`, `cdc.async_fifo_candidate`, `cdc.async_fifo_invalid`,
`cdc.reconvergence`, `rdc.reconvergence` and `rdc.release_order_unproved`.
Functional reconvergence and async FIFO rules retain `not_run` status as
`cdc.reconvergence_protocol`, `rdc.reconvergence_protocol` and
`cdc.async_fifo_protocol`. Structural findings retain the domain-bound waiver
identity. Protocol findings also bind their exact declaration in the message.
FIFO candidates require exact unconditional typed Gray encoder expressions.
`protocol_evidence` retains these keys and the selected memory/port records in
the finding, so they contribute to its waiver ID. This establishes an encoder
shape only. Pointer transitions and transfer behavior remain unproved.

## Formal capacity reports

`rvw formal contracts` writes `rvw.formal-contracts/1` in a fresh output directory.
Fields are `status`, `plan_sha256`, `obligations`, `restrictions` and `input_capture`.
Each obligation has an `id`, `status`, and either a child `result` with `proof_kind`
or a reason that it was not run. Run obligations also list assumption cells and
their source locations. `conditional_proved` requires fresh unbounded
passes for every component and the closed composition. Other outcomes give
`inconclusive`. The command returns 0 only for `conditional_proved`. Input errors
return 2. This report is not a C4 acceptance gate or a reusable proof certificate.
The copied plan and child input captures bind the report to its inputs.

`rvw formal strengthen` writes `rvw.formal-strengthen/1`. It records `status`,
`candidates`, `certified`, `obligations` and `semantics`. Only fresh unbounded passes
can add a candidate to `certified`. The final target proof supplies `status`.
Certified candidates remain assertions in the final target. Source assumptions
remain environment restrictions. Neither observations nor bounded passes can
certify an invariant. Missing evidence gives an inconclusive result.

BMC/prove abstraction entries extend `cut_points` with `kind` and `plan_sha256`.
The semantics remain `unconstrained_anyseq`. No abstraction assumption is implicit.
See the [formal capacity interface](../rvw/src/rvw/formal/README.md#capacity-templates-and-contracts).

## Formal app and benchmark reports

`rvw formal apps` reads `rvw.formal-apps/1` and writes
`rvw.formal-app-results/1`. Each row retains `property_id`, `requirement_ids`,
app kind, native status, proof kind and child result path. Status is `pass`
only when every child passes. Any failure gives `fail`; other cases give
`inconclusive`. Exit codes are 0 for pass and 1 for a written nonpass report.
Each child retains the existing `rvw.formal/1` evidence. A bounded app pass
cannot authorize an UNR coverage exclusion. The existing `cov prove` contract
still controls exclusion export. Activation and solver cores are not inferred.

`rvw formal bench` reads `rvw.formal-bench/1` and writes
`rvw.formal-bench-results/1`. Rows retain the case, engine, mode, requested
depth, explicitly observed depth or null, elapsed wall seconds, native peak
RSS bytes or null, native status, tool identity and result path. Absent engines
use `not_installed`; incompatible modes use `unsupported_mode`. Agreement is
`agree`, `disagree` or `inconclusive`. Exit 0 requires agreement for every case;
exit 1 means at least one disagreement or incomplete comparison. Agreement
is not a correctness or gate verdict. Pair comparisons require decisive,
matching verdicts on every case. Time ratios describe only the supplied suite.

Licensed adapters use `rvw.formal-adapter-request/1` and
`rvw.formal-adapter-response/1`. A response must bind to the SHA-256 of its
exact request bytes, retain the mode and engine version, and report finite
nonnegative measurements. A BMC pass requires an integer `reached_depth` at
least `depth - 1` (zero-based assertion step). Adapter verdicts are trusted observations. Invalid,
missing or timed-out responses stay inconclusive. See the formal README for
input fields and limits. Neither command emits gate acceptance.

### SVA frontend selection

`rvw.formal/1` results can add `frontend`, with value `verilog` or `slang`.
Absent means the default Verilog frontend. `slang` selects the restricted native
SVA subset for single-clock BMC. It preserves the existing bounded status and
reachability rules. It does not establish an unbounded proof or gate acceptance.
The plugin bytes appear in `input_capture.files`. The frontend's RTL dependency
report must stay within the copied inputs. See
[the supported subset](../rvw/src/rvw/formal/README.md#imported-sva-through-slang).

### Passive bus observations

An adapter can name `memory-bus.jsonl` in C1 `details.bus_observations`.
The JSONL header uses `rvw.bus-observations/1`. It gives C2 `identity`,
`bus_bytes`, `boundary: accepted-external-tilelink` and `independent: true`.
Each row records an accepted handshake with `channel`, decimal-string `cycle`
and `sequence`. A rows give `source`, `address`, `opcode`, `size_log2`, `mask`
and `data`. D rows give `source`, `opcode`, `size_log2`, `denied` and `data`.
Hex values use strings. Opcode and size use JSON integers. Same-cycle rows keep
capture order; this order does not imply an order between hardware effects.
An end row gives `kind: end`, `cycle` and the terminal C1 `status`.
Missing end rows mean incomplete capture. A terminal pass does not prove ordering.
The boundary excludes cache hits, buffered stores and device-side completion.
Adapters must not infer those events from retirement or from these handshakes.

The optional `rvw.mmu-observations/1` stream can also contain BOOM cache-stage
rows. `icache_response` gives hex `physical_address`, hex raw `data` and integer
`bytes`. `icache_invalidate` gives Boolean `refill_pending`.
`icache_refill_request` gives hex `address`. These share the stream's cycle clock.
They include speculative responses. They are not consumed-instruction evidence.

`fetch_consumed` rows in the optional observation stream give hex `pc` and
`instruction` from each accepted decode slot. These original instruction bits
come from the fetch buffer, independently of retirement. Wrong-path entries can
still occur. The project must map publication epochs and fence redirects before
using them as synchronized-byte checks.

Bus capture can include B, C and E rows. B gives `source`, `address`, `opcode`,
`param` and `size_log2`. C adds `data`. E gives `sink`. A and D rows also give
`param`; D gives `sink`. These accepted-channel observations do not identify
internal hits or replacement ways. Do not infer cache residency from capture
alone: clean evictions can be silent.

## TestRIG socket transport (`rvw.dii/1`)

`rvw cosim dii serve` and `replay` use RVFI-DII v1, separate from C1/C2.
See [the hook contract](TESTRIG.md) for wire pins, reset, timing and memory.
The server accepts at most 65,536 tokens per stream and a finite stream count.
Socket operations share a per-stream deadline. Replay accepts exactly one
nonempty stream terminated by EndOfTrace. It records the token SHA-256 and
both endpoints. These labels do not verify the remote model or its ISA config.
The caller must supply an independent Sail model. Each endpoint returns ordered
88-byte retirement packets and a halt delimiter. Empty, short, truncated,
unsupported or timed-out streams cannot earn a match. Exit codes: match or
served 0, mismatch 1, error 2, inconclusive 3. `served` is not equivalence.
The result has `schema`, `protocol` and `status`. Mismatch adds `index` and
`differences`; match adds `instructions` and `trace_complete`. Short streams add
`cause`, `core_retired` and `sail_retired`. Errors add `message`. All results
print one JSON document. This CLI mode has no MCP endpoint yet.


### Observed prediction outcome extension

Kanata comments can contain one measured outcome per live instruction, predictor
and kind. Emit it before terminal R. Fields are tab separated:

```text
#rvw  1  prediction  ID  PREDICTOR  KIND  PREDICTED  ACTUAL  RECOVERY  WORK  WARMUP  ALIAS  CONTEXT
```

`KIND` is `direction`, `target` or `return`. Direction values are `taken` or
`not_taken`. Target and return values are nonnegative decimal or `0x` addresses.
`RECOVERY` counts cycles from resolution to resumed correct-path fetch.
`WORK` counts admitted wrong-path instructions attributed to this resolution.
Both are nonnegative integers, or `?` for unknown. The producer must observe
these quantities. R type 1 and stage residence cannot supply them.
`WARMUP` and `ALIAS` are observed `true`, `false` or `?`. `CONTEXT` is a project
context token, or `?`. Tokens cannot contain tabs or newlines. A predictor name
is required. Duplicate outcomes, ended IDs and malformed known records fail.

Reports separate predictor, kind, warmup, alias and context groups. Unknown
costs stay unknown. Shared recovery costs can occur in multiple kinds. Do not
sum these groups as global lost cycles. Context differences and alias flags
do not establish causal effects. Project probes own the event bindings; the
generic reader does not simulate a predictor or infer missing observations.
`rvw.perf/1` adds `predictions.effects` (additive): per predictor and kind,
`overall`, `steady_state` (warmup=false and alias=false only) and `by_warmup`,
`by_alias`, `by_context` maps. Each holds `outcomes`, `correct`, `incorrect`,
`accuracy` (null when empty) and mispredict-only `mispredict_recovery_cycles`
and `mispredict_wrong_path_instructions` with `samples`, `unknown`, `sum`, `max`
and, when observed, `mean`, `p50`, `p95`.

### Property activation and requirement links

A `cov prove` point can declare an `activation` SystemVerilog expression. The
runner creates a separate cover job with the same captured inputs and assumptions.
The expression must be one statement-free expression. A successful cover needs
exit 0, PASS, no free wires and the existing sanity guard. Only then does
`proof_cones.properties[].activation.status` become `reached`. Other evidence is
`inconclusive`; an absent predicate is `not_measured`. This is a user-declared
activation predicate. It does not establish full property non-vacuity.

The additive `rvw.proof-cones/1` `requirements` array joins each declared
`requirement_id` to sorted `property_ids`. Property records join activation,
structural cones and the unavailable solver core through `property_id`. Every
requirement status stays `inconclusive`. A list of linked properties is not a
complete set of functional obligations. A structural cone is not a solver core.
These fields do not change exclusion or gate verdicts.


### Related clocks as periodic sampled schedules

Event BMC accepts repeated `--clock-schedule PORT=BITS` options. Declare every
clock, including `--clock`, or declare none. `clk=01` and `other=0011` describe
a 2:1 rate ratio. Rotate the bit strings to declare a phase. The leftmost bit is
sample zero. Each pattern repeats forever. Each must contain both levels and
2..256 samples. The joint period must not exceed 4096 samples. These are explicit
proof restrictions, not measured hardware clock relationships.

One solver step advances one global sample. The wrapper constrains clock levels
at that sample. The event backend samples property data before its triggering
edge; data that changes with a clock uses its previous sample at that edge.
Clock schedules do not add analog timing, delta cycles, jitter or events between
samples. When no schedule is given, the independent arbitrary-rate event model applies.
The existing reset harness still counts primary-clock edges. Async reset state
requires the separate `--async-reset` option. Unsupported state controls and raw
async-triggered properties remain refused. Replay and X flows remain unchanged.
`event_model.schedules` records the exact patterns; `relationships` states whether
the run used periodic schedules or unrelated clocks. Native phase tests require
both a passing same-phase reference and a failing opposite-phase reference.


### Sequential equivalence latency restrictions

The additive `rvw.formal.equiv/1` `restrictions.latency` is the nonnegative
candidate lag in clocks (0..64). The reference wrapper delays all output ports by
that amount. Both wrappers mask outputs until reset cycles plus settle cycles
plus latency cycles have elapsed. There is no input shift or protocol adapter.
`restrictions.unmatched_state` is `refuse` by default. With `prove`, unmatched
register names remain in the inventory but do not block a complete closed-output
proof. State equality is never assumed. Every partition must still have no
internal crossbits. Missing partitions, unknown results and tool failures remain
inconclusive. No named state relation or blackbox obligation is inferred.


### Imported single-sample implication

The slang import subset also accepts one top-level `Boolean |-> Boolean` in an
inline clocked assert or assume property. The pinned frontend patch evaluates
both operands at the same pre-update sample and checks `!antecedent || consequent`.
The existing `disable iff` condition gates the check. There are no pending threads.
`|=>`, delays, repetition, chained and nested implication remain refused before
a proof job. Qualified engines remain SMTBMC/Yices and ABC BMC3. The captured
plugin bytes identify the applied lowering. This is not full temporal SVA support.

### Init platform review marker

An optional `rvw init --linker-script` platform template carries
`review_required: true`. The cosim platform loader refuses it. The owner must
check the RAM, reset PC, MMIO, PMP, interrupt, privilege and fault policies
against the core specification before removing the marker. A linker map alone
does not establish these policies.
### C1 simulation throughput extension

Optional C1 `metrics.sim_khz` is `cycles / details.execution_s / 1000`.
`metrics.sim_instructions_per_s` is `instret / details.execution_s`.
The denominator includes adapter execution and artifact handling after model
readiness. It excludes model compilation and elaboration. The rates are absent
if seconds are missing, non-finite or non-positive, or counters are invalid.
These are throughput measurements, not architectural IPC or correctness claims.
C3 keeps the metrics. The history dashboard groups them by core, suite and preset.
Short workloads and concurrent jobs can give noisy samples. Use repeated long
workloads with fixed stimulus and equivalent complete C2 traces for comparisons.

`rvw.sim-speed/1` is a diagnostic report from `rvw regress speed-compare`.
It records `core`, `config`, `pairs`, geometric mean `speedup`, bootstrap
`speedup_ci95`, `resamples`, `bootstrap_seed` and `retain`. Each pair records
baseline/candidate C1 paths and hashes, native build hashes, complete C2 hashes,
execution run IDs, seconds and derived rates. A sample cannot be used twice.
At least five pairs of conclusive serial passing runs are required. Complete
validated C2 events, terminal counters, ELF, seed, preset and run inputs must
match. Each side must keep one native build identity. Default minimum sample
time is one second. Missing evidence or a difference gives exit 3.
`status: equivalent` is trace/result equivalence only. It is not ISA correctness,
C8 capture completeness or C4 acceptance. `retain` is a diagnostic timing filter:
the 95% interval lower bound must exceed one and all complete C2 files must
have the same raw SHA-256. `trace_bit_identical` reports this byte check.
Parsed equality alone can still report `equivalent`, but cannot retain an option.
`sim_khz.baseline` and `sim_khz.candidate` each record `geomean` and `ci95`.
These marginal percentile bootstrap intervals use the same pair resamples.
They include adapter and trace cost. They exclude model compilation.
The report does not change any options.

`rvw.sim-speed-sweep/1` records an explicit adapter, ELF hash, preset, host,
logical CPU count, seed, repeat count, thread counts, minimum sample seconds,
launch timeout, actual `order` of commands and completed `comparisons`.
Warmups are excluded from comparisons. Baseline/candidate order alternates
between pairs. Each process holds the selected core lock and uses `nice`.
The launch timeout includes the lock wait and is at most 1800 seconds.
Status stays `inconclusive` until all requested comparisons are equivalent.
A failed run stops the sweep. Cancellation stops the active process group.
Build costs, peak RSS, PGO and checkpoints are outside this report.


### UVM component results in C3

`rvw regress uvm` writes standalone `rvw.results/1` for the pinned
Accellera library and the bounded component suite in `Uvm/README.md`.
Entries use `kind: "uvm"` and the runtime seed. Normal passes require
successful exit, all expected test markers, one completion marker and no
UVM errors or fatals. The fault-detection entry requires the specific
RVFI mismatch and a failed simulation. A timeout, missing evidence or a
build failure is inconclusive with status `error`. These files have no
C1 ELF or complete C8 identity. They cannot establish C4 gate acceptance.


## Local integrated debug session

`python -m rvw.query.session --db DESIGN --wave SNAPSHOT.rvwi` holds one C6
database capture until exit. Stdio carries one JSON object per line. Requests
have integer `id` and `op`: `open`, `select`, `source` or `trace`. Responses echo
`id`. Success includes `result`, `database` (the capture record) and
`elapsed_ms` (backend time). Failure includes `error` and `status: inconclusive`.
`select` uses `signal`, decimal string `time` and optional decimal string `end`.
It returns the preceding value and at most 500 changes, with a truncation flag.
Change times are decimal strings. `source` uses `file` and integer `line` and
returns all candidates, without choosing among ambiguous mappings. `trace` uses
`signal` and `time`. It exports database PDG/HGLDD, checks the original VCD hash
and invokes SpinalTrace. Static drivers remain distinct from dynamic evidence.
The selected database and wave identities do not establish a shared C1 run.
The loopback web host exposes the same requests at `POST /api`. These are local
UI transport operations. They issue no simulation or acceptance verdict.



## Standalone HDL semantic tests

`rvw regress hdl` reads `rvw.hdl/1` and writes `rvw.hdl-result/1`.
This standalone format is not C1, C3 or C4 acceptance evidence.
The manifest fields are `schema`, `backend`, `top`, `sources`, optional
`requires`, and optional `vhdl_sources` plus `vhdl_top` for mixed synthesis.
A per-run `--backend` override must meet every declared requirement.
The [simulation guide](../rvw/src/rvw/sim/README.md#native-hdl-testbenches)
defines supported profiles and testbench completion rules.

The result records `status` (`pass` or `error`), `reason`, the selected `backend`,
`capabilities`, source-file SHA-256 `inputs`, resolved `tools`, `versions`,
`jobs`, `wall_s`, `timeout_s` and `replay`. Each job records its argument vector,
exit code, timeout flag, and paths to stdout/stderr logs. Exit zero plus exactly
one testbench `RVW_PASS` line and no native error diagnostic earns a pass.
A failed compile, failed run, timeout or missing completion marker gives error.
Requirements and missing-tool errors occur before output creation (CLI exit 2).
This format does not capture transitive file inputs or establish C8 reuse.

## Open workload recipe capture

`workloads list|build --recipe` selects a pinned open recipe. The same
selection is available through the `workloads_list` and `workloads_build`
MCP jobs. `workloads_verify` performs the existing reference checks.
`rvw.workloads/1` accepts optional `dependencies` (source-relative Git paths
to revisions) and `runtime_files` (workstation-relative runtime paths).
Dependency archives join the source capture. Runtime copies join the assets
capture. Both participate in existing hashes. CoreMark-derived smoke checks
report no CoreMark score. zstd uses an exact round-trip self-check. These
recipes issue no RTL accuracy or performance verdict.

## Workload reference flow

`rvw workloads list|build|verify` uses `rvw.workloads/1` manifests.
See [the workload README](../rvw/src/rvw/workloads/README.md) for fields.
`rvw.workload-build/1` records the manifest, captured source/runtime hashes,
compiler identity and per-workload commands, ELF hashes and sizes.
It means build completion, not output correctness.
`rvw.workload-verify/1` binds the build report SHA-256, oracle identity,
executed commands, ELF hashes, exits, timeout flags and stdout/stderr hashes.
`pass` requires a nonempty set, exit 0, no timeout and exact expected stdout
for every row. A timeout, nonzero exit or mismatch is `fail` (exit 2).
Invalid input or missing tools give an error (exit 2). No C4 verdict is issued.
The flow requires stable tools and inputs. Local external scripts and compiler
sysroots are not a complete C8 capture. Reports must not grant gate acceptance.
With `verify --trace`, successful Spike rows also contain `profile` with
whole-program instruction category counts and observed conditional-branch
transitions. Compressed instructions are decoded as RV64. FP and memory
categories overlap. Cache misses and branch mispredictions stay null.
The retained stderr file is the hashed instruction-log evidence.


### C9 search, repeats and prediction ledger

`arch search PLAN --out DIR` and MCP `arch_search` consume
`rvw.arch-search/1`. Exact fields: `schema`, `fit`, `parameters`, `budget`,
`repeats`, `timeout_s`. `fit` is `rvw.arch-fit-plan/1` with empty `candidates`.
RTL paths resolve against PLAN. Parameter rules follow `rvw.arch-sweep/1`.
The space is at most 32 points. Budget is 1..32. Repeats are 2..10.
At most 256 model processes run, serially under the gem5 lock.
Latency changes and SoC fitting are refused. Training mean cycle and eligible event errors drive
an RBF Gaussian process with expected improvement. Held-out workloads run only
after selection. `rvw.arch-search-result/1` stores method, plan hash, trials
with descriptions, report paths and training statistics, selected point,
held-out statistics and checked fit reports. Partial progress is inconclusive.
Search adds `headline`, `objective` and `reason`. A flat search objective or
inconclusive selected fit gives status `inconclusive` (CLI exit 3).
No search result is a fidelity verdict.

`arch measure --out DIR [--repeats N]` and MCP `arch_measure` repeat calibration
(default 3, range 2..10). `rvw.arch-measure/1` stores individual comparison
reports and per-workload statistics for RTL cycles, model cycles, IPC ratio
and cycle gap. The tool checks stable core, preset, latency, ELF, instruction
counts, description, model and gem5 binary across repeats. Intervals in these
reports use a 95% percentile bootstrap mean, 4000 resamples, seed 0. They
measure observed repeat variation only. Fixed seed 1 and deterministic runs
can give zero width. Constant repeats have interval status `inconclusive`
and a reason; the numerical interval remains visible. They do not quantify model bias or generalization error.

`rvw.arch-fit/1` adds `event_correlations`, keyed by `train` and `held_out`, then
event name. Values have `n`, `pearson_r`, `status` and `reason`. Less than three
workloads or a constant counter gives null and `inconclusive`. Otherwise the
coefficient describes the checked event pairs. No semantic match is implied.

`arch predict CANDIDATE --out FILE` / MCP `arch_predict` exclusively create
`rvw.arch-prediction/1`: UTC `created_at`, candidate path/hash, full checked
model report and status `predicted`. `arch score-prediction PREDICTION RTL
--out FILE` / MCP `arch_score_prediction` exclusively create
`rvw.arch-prediction-score/1`: UTC `scored_at`, prediction path/hash, checked
C9 comparison and status `reported`. Model report and raw evidence are rechecked.
Every RTL evidence mtime must follow the prediction time. This is a local
ordering check, not trusted chronology. The ledger requires original local
paths and stable evidence. No file races or hostile timestamp claims are covered.


## SpinalChecks normalized register map (version 1)

`SpinalChecks/scripts/import-map.py` writes Java properties. `version=1` is
required. `registers` lists unique comma-separated register names. Each name has
`address`, `width`, `reset`, `writeMask`, `w1cMask` and `readClearMask` properties.
Values are nonnegative decimal integers. Addresses use bytes. Masks and reset
must fit width. Ordinary-write and W1C masks must be disjoint. Register byte spans
must not overlap. Missing required fields fail loading. This format declares
register intent. It does not provide independent bus observations or a verdict.

### C1 native semantic requirements


## Agent benchmark fixture formats

`rvw.agent-tasks/1` has a nonempty `tasks` array with unique IDs. Each task has
`public` requirements, width, statements, expression choices, source text and
artifact identity claims. Its evaluator-only `private` object has the cause
statement ID, injected artifact defects and `[a, b, expected]` vectors. These
fixtures are not C1 runs, C2 traces or C6 database IDs.

`rvw.agent-bench/1` records `track: "fixture"`, agent name, pack SHA-256, per-task
scores, final candidates and ordered tool transcripts. Elapsed times use a
monotonic clock. Missing root causes have null times and a censor flag. Summary
rates retain counts and denominators; empty conditional rates are null.
`native_validation: "NOT RUN"` is mandatory for this track. Scores cannot earn
C4 acceptance. The dedicated stdio server exposes only fixture tools and rvw job
status tools, not the normal rvw tool registry or plugins. See
[the benchmark guide](../rvw/src/rvw/agent_bench/README.md).

### C2/2 V and H observations

An ISA declaring V requires a `vector: {"vlen": 128, "elen": 64}` header.
An ISA declaring H requires a `hypervisor: true` header. V1 traces for these
ISAs are refused. Each retirement carries the declared extension state.
Vector state has XLEN hex `vstart`, `vl`, `vtype`, 3-bit hex `vcsr`, 2-bit hex
`vs`, and `regs`: all 32 VLEN-bit hex register values after the step.
The complete snapshot checks register writes and mask v0, including unchanged
lanes. It does not identify writes that store an unchanged value. VLEN must
be a power of two from 128 to 65536. ELEN must be a power of two from 8 to 64.
The reference must have exactly the declared dimensions. No agnostic-bit
relaxation is implied.

Hypervisor state has boolean `virtual` (before), `virtual_after`, integer
`mode_after` (0, 1 or 3), `csrs`, and `translations`. Together with `mode`,
these distinguish M, HS, U, VS and VU entry and exit. `csrs` holds XLEN hex
values for 0x100, 0x105, 0x141, 0x142, 0x143, 0x300, 0x302, 0x303,
0x341, 0x342, 0x343, 0x600, 0x602, 0x603, 0x643, 0x64a, 0x680, 0x200, 0x205, 0x241,
0x242, 0x243, 0x280, 0x34a and 0x34b after the step. Translation records
have XLEN hex `va`, `gpa`, `pa` and `access` (fetch, load or store), in access
order. Missing intermediate translations are unavailable evidence. A backend
without translation observations must refuse nonempty records. An empty list
checks no translation. State comparison alone does not prove page walks.

The Spike walker checks successful RV64 guest fetch and scalar load mappings
with Bare/Sv39/Sv39x4. It refuses stores, faults and unsupported PTEs. HS
CSR addresses above always mean nonvirtual host state, including while in VS.

`state_coverage.two_stage_translations` counts matched translation records.
A zero count makes no translation comparison claim.

A regression config can set `[core] backend = "riscvsim-verilator"`.
Each suite can set `requires = ["two_state", "clock", "immediate_assertions"]`.
The shared native profile checker refuses unsupported or malformed requirements
before input capture and adapter launch. A nonempty requirement list without a
known profile is an error. Existing configs with no requirements stay valid.
The direct RiscvSim shell launch checks `RISCVSIM_REQUIRES`, a comma-separated
feature list, before it creates temporary launch state. This profile describes
the Spinal native interface, not the cocotb Verilator invocation. Coverage flags
retain their existing version checks and do not imply a coverage guarantee.

### Sampled reset checks

Optional project bindings can emit `rdc.assertion`, `rdc.release`,
`rdc.unknown_control`, `rdc.release_order`, `rdc.isolation` and
`rdc.reconvergence_protocol` monitor findings. Each binding uses an independent
observation clock and normalized control levels. These findings do not discharge
the structural lint report's unrun release or reconvergence proofs. Missing
bindings provide no reset protocol evidence. Between-sample pulses and physical
timing are outside this sampled contract.

### Optional HPM control checks

`hpm.selector`, `hpm.overflow_pending` and `hpm.counter_interrupt` identify
optional project monitor rules. The selector policy is a declared WARL mask.
The interrupt policy is sticky modular overflow with clear priority and a
separate interrupt enable. Counts and event multiplicity come from independent
observations. These rules do not establish architectural CSR access compliance,
selector event meaning, or real-core coverage without explicit project bindings.

### Independent device bus checks

Optional `register.bus_decode`, `register.bus_data`, `register.bus_order` and
`register.bus_latency` rules check accepted bus request/response observations
against project register addresses and version-1 register models. One request
can be outstanding. Read data precedes the request's side effects. An unmapped
address must receive an error. A zero-cycle response is allowed. A delayed
response must arrive within the declared positive cycle bound. These rules
provide no real-device or CSR compliance claim without a concrete binding.

MMU observation inventories can add `walk_check` with `status` of `consistent`,
`mismatch` or `inconclusive`. This bounded check compares immutable PTE read
addresses and values with scenario data and observes the physical target range.
It does not change architectural bins or C1-C4 verdicts. See the regress README.

Optional MMU `device_state` events retain sampled harness register state and an
IRQ schedule override flag. `pma_check` uses declared PMA data plus these events
and accepted bus requests. Its `consistent` result has the same bounded scope
as `walk_check`; neither changes architectural coverage or gate verdicts.

### Architecture Pareto intervals

`rvw.arch-pareto-plan/1` has `points` with unique `id` and `report` paths.
Optional `objectives` defaults to `["cycles"]`. Optional point `costs` paths
select user input files. Paths are relative to the plan. Reports are checked
`rvw.arch-run/1` gem5 runs with identical ELF hashes and ROI instruction counts.
Without costs, cycles use summed ROI cycles for all three interval bounds.
`rvw.arch-costs/1` has `report_sha256`, nonempty source/method text in `method`,
and `cycles`. Optional `area_mm2` and `power_w` are user-supplied inputs only.
The workstation does not estimate or validate area or power. PPA estimation
and hardware gain claims are out of scope.

Intervals are null or positive ordered `[lower, nominal, upper]` values.
Nominal cycles equal summed ROI cycles. Bounds are user declarations.
`rvw.arch-pareto/1` records selected `objectives`, plan/report/cost hashes,
`cost_origin` (`user-supplied` or `absent`), intervals, `eligible`,
`evidence_class: model-only`, `nominal_frontier` and `conservative_frontier`.
Conservative dominance compares only selected objectives. It requires all
upper bounds no greater than the other point's lower bounds and one strict gain.
Missing selected objectives exclude a point and make status inconclusive
(CLI exit 3). Unselected missing inputs do not affect eligibility.
No point is RTL-confirmed by this command.

### Architecture topology channels and agents

The optional `rvw.arch-core/1` `soc.memory.kind: multi` uses `interleave_bytes`
and 2, 4 or 8 `controllers` (simple or DRAM memory objects). Channels stripe
across RAM at a power-of-two byte size of at least 64. Optional `soc.agents`
contains up to eight read-only linear generators. Fields are `start`, `size`,
`block_bytes`, `period_ticks`, `duration_ticks`, `max_outstanding` and `attach`
(`memory` or an existing cache level). Addresses and blocks must align and fit
RAM. Time units are 1 ps ticks. Agents start at instantiation and idle after
the duration. They are not CPU harts. Fixed-latency C1 calibration still refuses
SoC topologies. Native model execution alone is not RTL correlation.

### Native memory mappings

`rvw.memory-mapping/1` has `inputs` (`stats`, `config`, `bare`, each with path
and SHA-256) and `observations`. Each observation has `point`, `region`, `hart`,
`workload` and `counters`. Counter keys use `rvw.memory-observations/1`; each
value has distinct `stats` names and positive `scale`. Names must start with
the native config object's point plus a dot. The first complete stats block
must have simFreq=1e12, simTicks equal to the difference of the two bare ROI
markers, and finalTick equal to the exit marker. Bare execution must pass.
`arch memory-extract` returns `rvw.memory-report/1` with `mapping_sha256` and
`native_inputs` hashes. It checks names and interval identity. The project
owns semantic mappings. Unmapped metrics and contention causes stay unobserved.
## Reviewed specification obligation catalogs

The optional `rvw.isa/1` `specifications` entries can bind a document and a
reviewed `rvw.spec-obligations/1` catalog. Each entry has `kind`
(`isa|profile|debug|platform`), `revision`, `path`, `sha256` and
`obligations` (`path`, `sha256`). Paths use the corresponding opcode source
root. Catalog rows in `obligations` have unique `id`, exact document excerpt
`text`, `checkers` and `tests` arrays. Diff verifies both hashes and document
excerpt membership. `rvw.isa-diff/1.obligations` reports added, removed and
changed rows, affected checkers, missing tests and present test hashes.
It reports metadata-only pins as unchecked. A changed catalog requires adoption.
Catalog completeness needs review. Test presence does not establish execution.

`rvw.isa/1.probes` can configure `compiler|dut|reference|act|coverage` probes.
Kinds are `gcc` (native target macros), `command` (native JSON capability
output), and `json|toml` (captured settings file with optional `key` path).
Command probes return `rvw.isa-consumer/1` with `xlen`, `extensions` (versions
or null), and `options`. File probes select the same fields. Paths use the
manifest directory. `rvw.isa-check/1` includes observed `probes` and
`unchecked_consumers`. `consistent` requires all five inputs with known,
matching versions and options. Missing evidence gives `inconclusive`.
Contradictions are errors. These statuses describe configuration consistency.
They do not certify ISA implementation or compliance.

`rvw.isa/1.semantics` can include `forms` and `crosses`. Forms map instruction
names to fields with `bits` (`[hi,lo,destination_lo]` slices), `width`, `bins`
(explicit values or `boundaries`), optional `signed`, `offset` and register
`bank`. Crosses declare `id`, `instruction`, `fields`, and exhaustive
`combinations` (`bin`, `status`, `reason`) within those finite field domains.
Statuses are `legal|illegal|unavailable`. Functional plans retain the catalog.
Cross reports retain every bin in the denominator and add `classifications`
with observed `count`. No catalog declaration is a proof exclusion.

`rvw.coverage-report/1.scala_mapping.methods` counts source mapping methods.
The `covered-span-assignment-links` method navigates to a unique local full
SpinalDB data assignment for an exact covered RTL target. Multiple, partial,
init/reset and nonlocal assignments refuse that inference. Mixed links have a
separate method. These links do not prove individual Scala statement hits;
`scala_mapping.statement_hit_status` remains `undetermined`.


### Cooperative farm capacity extensions (#57)

Host capacity and request resources support `disk_bytes` and `jobs` in addition
to CPU slots, memory bytes and named locks. A host can set `projects` with
per-project limits for those four dimensions. Requests then require a configured
`project`. All active requests for that project share its quota. Host aliases
share the same host state. An oversized request is refused; a capacity conflict
waits within the request timeout. Disk admission also checks current free space.
Reports include effective `limits`, `queued_s`, `held_s`, `released` and `outcome`.
Handled cancellation releases all reservations. These fields describe reservations,
not actual consumption. OS resource limits and cumulative project accounting are
not provided. See `rvw/src/rvw/farm/README.md` for defaults and remaining limits.

### Paired SoC bridge observations (#134)

The optional extended `soc check --transactions` JSONL record includes `write`,
`data`, `error`, `beats`, and optional `register`, in addition to the original
address fields. Bindings can declare `byteorder` and `software_byteorder`.
Beat masks index lanes by ascending address. The format and bounded comparison
rules are defined in `rvw/src/rvw/soc/README.md`. Matching samples never produce
a pass. Endpoint pairing and observation provenance remain the capture
producer's responsibility. The bundled captures do not emit extended records.

### riscv-formal input provenance (#63)

C3 `source.formal_inputs.settings_sha256` binds the selected formal settings.
`source.formal_inputs.committed_inputs.files` lists copied input hashes and their
comparison with repository HEAD bytes. Rows report `committed`, `modified`,
`untracked_or_unavailable`, or `unavailable`. The nonempty list has
`all_committed=true` only when every row matches a commit. This is file provenance,
not a generator-origin or adapter-conformance claim. `source.identity_complete`
remains false. C4 remains bounded and cannot accept. No C1 ELF run is fabricated.


## Native branch component reports

`ComponentSims/` defines `rvw.branch-trace/1`. The first line is schema plus
positive total instruction count. Each following `B ORDINAL PC TAKEN` row gives
a conditional branch, its one-based all-instruction ordinal, hexadecimal PC and
0/1 outcome. Ordinals strictly increase and cannot exceed the total. A final
`END` line is mandatory. No lines follow it. Nonbranches are represented by gaps.

The native engine emits `rvw.branch-sim/1` with `status=reported`, `model`,
`entries`, `history_bits`, `pc_shift`, `warmup_instructions`, `instructions`,
`branches`, `direction_misses`, `mpki`, `oracle_mpki=0`,
`training=sequential-actual-path`, and `rtl_comparison=inconclusive`.
`instructions` excludes warmup. `mpki` is 1000 times measured direction misses
divided by measured instructions. No C1 pass or C4 verdict is issued. Exit 0
means report completion; exit 2 means error without a stdout report.

The standalone Spike adapter selects one successful traced row from
`rvw.workload-verify/1`. It checks the retained stderr hash and instruction count.
It rejects multi-hart logs, exceptions and ambiguous branch successors.
Its `rvw.branch-sim/1` report adds `workload`, `elf_sha256`, `scope`, `oracle`,
`verify`, `source`, `trace`, `engine`, and `adapter_sha256`. The four file objects
contain absolute `path` and `sha256`. Scope includes startup and checker code.
A supplied verification report remains local trusted evidence, not an immutable
C8 generation. The adapter does not independently rerun workload correctness.
### Component study formats (`rvw csim`)

`rvw.csim-trace/1` is the native component trace. The first line is the schema.
Lines that start with `#` are comments. Rows use hexadecimal PCs, addresses and
values and decimal one-based instruction ordinals. Ordinals do not decrease;
two `B` rows cannot share one ordinal. The last line is `END INSTRUCTIONS`,
the total count of instructions, with no data after it.

```text
B ORD PC KIND TAKEN TARGET [LEN]   KIND cond|jump|ijump|call|icall|ret; TARGET is the next PC when taken
L ORD PC ADDR SIZE                 load, SIZE bytes (1..64)
S ORD PC ADDR SIZE                 store
W ORD PC RD VALUE FLAGS            register write; FLAGS '-' or letters l (load), m (move), z (zero idiom)
X ORD CONTEXT                      context (privilege mode or address space) from this ordinal on
```

Converters write an `X` row at the first instruction and at each change of the
C2 `mode` or the Spike privilege digit.

Unconditional kinds must be taken. `LEN` is 2 or 4 for RISC-V; 0 means unknown.
`rvw csim convert c2` writes it from one-hart C2 traces without order gaps. A
trapped instruction counts as an instruction but gets no branch row.
`rvw csim convert spike` reads one-hart Spike `-l --log-commits` logs: each
commit line is one instruction; a branch followed by an exception line gets no
row, and access sizes come from the decoded mnemonic.

`rvw.csim-study/1` is a JSON object with the sections `branch`, `btb`, `ras`,
`indirect`, `wrong_path`, `frontend`, `memory`, `mdp`, `vp`, `report`, the
integers `warmup_instructions` and `simulation_instructions`, and the metadata
`name`, `description` and `source`. `source.fidelity` is `approximate` or
`unqualified`. The engine refuses unknown keys. `rvw csim models` lists the keys.

The engine writes `rvw.csim-report/1` per trace with `status=reported`, `trace`
(format, instructions, warmup, measured instructions), one object per component,
`storage` (bits per table, `total_kib`, `metadata_kib`, `cache_data_kib`),
`training=sequential-actual-path`, `rtl_comparison=inconclusive` and `limits`.
MPKI is 1000 times events over measured instructions. `rvw csim run` wraps the
reports in `rvw.csim-study-report/1` with the study hash, input hashes, engine
identity and an aggregate that names its weighting. `rvw csim sweep` writes
`rvw.csim-sweep/1`; `rvw csim budget` writes `rvw.csim-budget/1`. No report
gives a C1 pass or a C4 verdict. Exit 0 means a report; exit 2 an error.

`rvw.bp-events/1` is JSONL from a project probe binding. The header has
`schema`, `elf_sha256`, `hart`, `counter_semantics` (`first-prediction` or
`final-prediction`) and an optional `roi` (`start_order`, `end_order`). Each row
has the C2 `order` of a retired branch, `pc`, `kind`, `taken`, and optionally
`predicted_taken`, `target` and `predicted_target`. Events for squashed
instructions have no order and are refused. `rvw csim compare-rtl` writes
`rvw.csim-rtl-compare/1` with status `compared` or `inconclusive`, `reasons`,
observed direction and target counts, per-branch rows and, for Kanata input, a
separate `inferred` section.

`rvw csim qualify` writes `rvw.csim-qualify/1`: `status=reported`, the
reference name, URL, pinned `reference_sha256` and `reference_patch`, the study
hash, the tolerance and, per trace, input hash, conditional branch count,
reference and model misses and MPKI, `prediction_agreement`,
`within_tolerance` and the largest per-branch differences. It is a measured gap
on the given traces, not a fidelity verdict.

The comparison status is `inconclusive` when the ELF identity,
hart, counter semantics or an event for a conditional branch in the ROI is
missing, or when an event does not align with the trace. It never reports a match.

## C9 compiler scheduling extension

`rvw arch sched-generate` reads `rvw.sched-core/1`. Required fields are `name`,
`config`, `isa` (rv32im or rv64im), `entry`, `issue_width`, `buffer_size`,
`resources` (identifier to instance count), `classes` and `mca_cpu`.
Each class requires `name`, `resource`, `latency`, `occupancy`, `llvm_opcodes`,
`gcc_type`, `mnemonic` and `encoding` (base RISC-V instruction word).
Cycles and counts are integers. Unknown fields, duplicate class/type/opcode
mappings and unsupported instructions fail. Occupancy is per unit instance.
The command writes partial `model.td` and `model.md` target fragments.

`rvw arch sched-measure` selects an existing project and C1 config. It builds
paired unrolled ELFs per class and mode. It requires passing C1 evidence with
matching ELF hash, core, config, seed 1 and fixed memory latency 0. C2 must end
with pass and contain every expected instruction at the exact PC and encoding.
Traps, order gaps and decreasing cycles are errors. Measurement output is
`rvw.sched-measure/1`, with `status=reported`, `model_kind=builtin-baseline`,
`generated_model_accuracy=inconclusive`, tool identities, raw evidence hashes,
per-size cycles and per-class signed slope errors. Missing evidence exits 2.
The report is local timing evidence, not a C4 verdict or complete C8 capture.
Stock llvm-mca cannot load generated TableGen. The built-in baseline does not
validate a generated model. See `Arch/SCHED_MODELS.md` for limits.
### Own-core memory-dependence replay

`memory_policy=speculate` enables a bounded load/store PC-pair predictor.
`dependence_entries` is its capacity. `replay_penalty` is its recovery delay.
Both are positive integer configuration fields. A violating issued load
causes younger ROB work to execute again without changing retirement order.
Events count speculative loads, violations, store-triggered recoveries and
replayed instructions. `issued` includes reexecution. This policy is not
memory renaming. Translation precedes component service in cycle order.
Completed or pending component requests are not cancelled by replay.
Accuracy remains inconclusive. See `rvw/ooo/README.md` for limits.

### Own-core rename policies

The optional `rename` configuration object enables bounded move elimination,
zero elimination and adjacent immediate execution fusion. All flags default
to false. Eliminated operations retain ROB entries and architectural commit
slots. Events `move_eliminated`, `zero_eliminated`, and `fused_immediates`
count these operations. `issued` counts execution requests. Full free-list
alias reclamation, macro-op decode fusion, faults and memory renaming remain
unsupported. These policies run in Python. See `rvw/ooo/README.md`.

### Own-core model search

`rvw.ooo-search-plan/1` selects a project model, complete C2 traces, numeric
parameter choices, grid or Bayesian search, a point budget and a cycle budget.
Optional area and power objects are project analytic cost estimates with a
named source. `rvw.ooo-search/1` records model-only points, trace timings,
frontier IDs, objective names, missing cost dimensions and unmeasured
uncertainty. `results.sqlite` retains one row per completed point. Reports
remain inconclusive for accuracy. They are not C1 runs or hardware evidence.

### Own-core native scheduler selection

`rvw.ooo-run/1` adds `backend` (`python` or `native`). The optional native
integer scheduler preserves the reference schedule. Unsupported streams use
Python. The report engine hash includes the native source and wrapper, and
also the selected library bytes when native execution occurs. This is model
identity, not a hardware accuracy claim. See `rvw/ooo/README.md` for support.

### Own-core decoupled pipeline timing

The optional `rvw.ooo-run/1` configuration objects `frontend`, `execution`,
and `translation` select decoupled fetch/decode, shared execution port binding,
per-class issue capacity and fixed page-walk timing. Fields and units are in
`rvw/ooo/README.md`. Omission preserves the original schedule.

The additional `topdown` object gives `unit=commit_slots`, `total_slots`,
`slots`, `fractions`, and `method`. Categories are `retiring`, `frontend_bound`,
`bad_speculation`, and `backend_bound`. Total slots equal cycles times commit
width. This is a model partition, not a hardware top-down measurement.
Events include uop-cache block hits/misses, FTQ stalls, predictor delay cycles,
shared-port stalls, per-port issued counts, TLB hits/misses, page walks and
walker-capacity stalls. Translation events count admitted translation attempts, including replay;
walker-full counts failed admission attempts. Wrong-path fetch slots are a
penalty-based estimate. No wrong-path instructions execute. Accuracy remains
inconclusive. Native speed and RTL correlation are not established.

### Own-core timing configuration snapshots

`rvw.ooo-run/1` accepts optional timing policies for per-class issue counts,
integer physical-register capacity, committed-path branch recovery and traced
address disambiguation. These remain fixed-latency experiments. They do not
supply RTL accuracy evidence or model wrong-path resource use.

An optional `rvw.ooo-effective/1` snapshot contains `source_revision`, `config`,
`parameters`, `extraction_keys` and `required_structures`. `parameters` must
match every normalized model setting. Each setting needs an extraction key.
Unsupported required structures are errors. `configuration_status` becomes
`snapshot_checked` only after this comparison. `configuration_evidence` holds
the snapshot SHA-256, revision, selected config and extraction keys. Exporter
correctness and current RTL agreement remain unverified. `accuracy_status`
remains `inconclusive`. Without a snapshot the configuration stays `unchecked`.

### Saved own-core model calibration

`rvw.ooo-calibration-plan/1` selects one fixed configuration, an event map and
training/heldout samples. Paths resolve beside the plan. Each sample binds
saved C1, complete C2, ELF bytes and event counts. ELF and trace hash overlap
across splits is an error. Regions cover the whole program only.
`rvw.ooo-calibration/1` records captures, individual errors, event correlations
and declared budget comparisons. Missing events and zero denominators remain
explicit. Accuracy stays inconclusive. Event predicate equivalence is not
verified automatically. No fitting or RTL execution occurs.

`rvw.ooo-prediction/1` records the frozen calibration hash, held-out trace,
config, engine, identity and local creation time. `rvw.ooo-prediction-score/1`
binds its hash and the later conclusive C1 hash in a separate exclusive file.
Scoring rechecks captures and exact identities. Local timestamp checks are
not trusted chronology. No native speed qualification is established.
### Saved checkpoint warmup observations

`rvw.arch-warmup-plan/1` declares captured ELF bytes, a fixed `[start,start+length)`
instruction ROI, an error target, a from-reset baseline and warmup samples.
Each sample binds saved C1/C2 and W. C1 metrics declare ROI start, instruction
count and measured cycles. Samples use start order W; baseline uses start.
`rvw.arch-warmup-bias/1` records input captures, cycles, CPI, IPC and signed and
absolute CPI bias. Architectural suffix records must match after excluding
order and cycle. Seeds, memory timing, ELF and core identities must match.
Missing evidence causes an error. Budget comparisons are observations only.
Accuracy remains inconclusive. No checkpoint or RTL job is launched.

### C2 BBV sampling plans

`rvw.arch-sampling/1` binds a complete single-hart C2 trace hash to fixed
instruction intervals, BBV counts, deterministic clusters and selected actual
intervals. Each sample gives `[start,end)`, capture order, actual planned
warmup, represented instruction count and its instruction fraction `weight`.
The final short interval uses its actual length. Weights sum to one.
`accuracy_status` remains inconclusive. Phase selection is not checkpoint
restore or timing qualification. The CPI helper checks each measured sample's
instruction count and weights CPI by represented instructions.

### Experimental trace-driven OoO timing reports

`rvw ooo CONFIG TRACE --max-cycles N --json` is a separate native timing
experiment. It does not use gem5 or emit `rvw.arch-run/1`.
CONFIG is explicit JSON with positive integer `fetch_width`, `fetch_entries`,
`rename_width`, `rob_entries`, `issue_width`, `issue_entries`, `load_entries`,
`store_entries`, `commit_width`, and a nonempty `latencies` map. Map keys are
`alu`, `multiply`, `divide`, `load`, `store`, `branch` and `jump`; values are positive integer
cycles. Unknown or missing fields are errors. Only configured classes can run.

The input is complete single-hart C2. Traps, interrupts, external events,
atomics, fences, privileged, FP and vector operations are
unsupported. End status must be `pass`. C2 cycles do not enter prediction.
The entire instruction stream defines the region. There is no ROI slicing.

`rvw.ooo-run/1` contains `config`, SHA-256 fields `config_sha256`,
`trace_sha256`, `engine_sha256`, `cycles`, `instret`, `ipc`, `wall_s`,
`events`, `max_occupancy`, `cycle_order`, `limits`,
`accuracy_status="inconclusive"` and `configuration_status="unchecked"`.
Engine identity hashes the kernel, decoder and C2 parser. It does not claim
complete C8 identity. Wall time includes file capture, parsing and simulation.
Cycle order is commit, issue, rename, fetch. Cycles include fill and drain.
Events count issued instructions and phase-sampled dependency/queue stalls.
Absent event keys mean zero. See `rvw/ooo/README.md` for exact predicates.
This is not a C1 run, a C4 verdict, a configuration check or an accuracy result.
Success exits 0 for a produced report. Bad input or exhausted cycle budget
exits 2 with a JSON error. No 50x speedup is established by this schema.
### C9 decoupled RISC-V O3 settings

The existing `cpu` scalar fields can enable gem5's BAC and FTQ.
`decoupledFrontEnd` must be a boolean. When true, the model requires O3,
`minInstSize=2`, positive FTQ capacity and prediction rates, and
`fetchTargetWidth >= fetchBufferSize`. Omitted numeric settings use the
pinned gem5 defaults. The default target width (32) is smaller than the
default fetch buffer (64), so set compatible values explicitly. Invalid
settings fail before native execution. C9 evidence and verdict rules do not
change. See `Arch/patches/README.md` for the optional mixed-width BAC fix.


### UVM CPU capture replay in C3

`rvw regress uvm-cpu` consumes a completed C1 run and its C2 artifact. It
can also launch a selected adapter with `run --rvfi-trace` before replay.
It checks the C1 ELF SHA-256, status and retirement count before replay. It
requires complete, passing, contiguous scalar C2 version 1 evidence. A
UVM analysis subscriber checks each retirement with a native Spike DPI bridge.
The standalone C3 report marks `mode=offline-c1-replay` and records the
profile, captured reference inputs, source hashes, commands and logs. It
does not modify C1 or establish C4 acceptance. Unsupported profiles and
incomplete observations are errors. Source identity remains incomplete.

### Named SMT core reports

`rvw.smt-bindings/1` binds one SMT query to `property_id`, optional
`requirement_ids`, and a `constraints` object indexed by every named assertion.
Each constraint can list design `signals`. Bindings are caller-supplied metadata.
`rvw.solver-core/1` retains the query SHA-256, solver calls, core labels and their
bindings, optional SpinalDB locations, and the input capture. `status=pass` means
only that this SMT query is UNSAT. `minimal=true` means deletion minimality was
checked with SAT on each single-constraint removal. Unknown removal results set
`minimal=false`. This report is not a coverage exclusion or an RTL proof result.
### Project CSR generation

`rvw.csr/1` describes CSR addresses, project reset values, privilege, presence,
field ranges, per-privilege access, legal values, legalization tables and bounded
side effects. See `SpinalChecks/csr/README.md` for the exact transaction binding.
`rvw formal csr` and `formal_csr` emit `rvw.csr-generation/1` with status
`generated`. This status records artifact generation only. It is not C7 proof
or C1 execution evidence. `coverage.json` uses existing functional group data.
### Seeded random campaign report

`rvw regress random` and `regress_random` write `rvw.random-campaign/1` to
`campaign.json`. Settings are project-owned TOML, separate from `rvw.toml`.
Paths resolve from the settings file. The report records the settings hash,
upstream revision, selected core/configuration and ordered seed attempts.
Each attempt retains generator and compiler arguments, source and ELF hashes,
C1 result artifacts and the public `rvw.cosim/1` comparison where available.

Attempt statuses are `generator_error`, `compile_error`, `adapter_error`,
`trace_error`, `cosim_error`, `core_failure`, `mismatch`, or `pass`.
Errors never count as a pass. The aggregate status is `fail` for a core failure
or mismatch, `pass` only when every attempt passes, otherwise `inconclusive`.
CLI exit codes are 0, 1 and 3 for those statuses. Invalid requests exit 2.
Coverage is present only after a complete, nonempty Spike match with passing
termination and a C1 retired count equal to the comparison count. Coverage uses
the existing functional report and its input capture. It includes the complete
trace, including setup and termination. It does not establish payload closure.
Existing output directories are refused. The run has no resume or cache reuse.
Each C1 run retains the runner's source/native identity and ELF replay records.

The project schema accepts `[stimulus] random_settings = "random.toml"`.
This path resolves from `rvw.toml`. An explicit `--settings` overrides it.

### Project-selected MMU matrices

`rvw.mmu/1` descriptions may contain `schema` and `matrix` instead of `schema`
and `scenarios`. `matrix` contains a nonempty unique `modes` list. Supported
modes are `sv32`, `sv39`, `sv48` and `sv57`. Expansion produces the same explicit
scenario records used by `rvw.mmu-build/1`. Scenarios may set `mode`; its default
is `sv39`. Levels range from zero to the selected mode's walk depth minus one.
Sv32 uses 32-bit PTEs, RV32 programs and nine ASID bits. Other modes use 64-bit
PTEs and sixteen ASID bits. Explicit non-canonical addresses require a
page-fault expectation. Existing schemas and default Sv39 behavior are retained.
Coverage groups are the scenario `bins`. Reference groups describe Spike only.
C1 coverage still requires the existing bound strict-check evidence.

Explicit MMU scenarios can select `napot` (RV64 boolean) and `napot_ppn`
(four low PPN bits, default 8). NAPOT cases use 16 equal level-zero PTEs.
`pbmt` selects a two-bit RV64 leaf encoding. `pbmte` selects menvcfg.PBMTE
(default true when pbmt is present). These scenarios check architectural
access or fault effects, not cacheability, ordering or device side effects.
`mode_switch` selects a translated/Bare/translated load check at the fixed
RAM payload. These options are opt-in and do not change old descriptions.

A scenario with `guest = true` selects an RV64 HLV.D test with Sv39 VS-stage
and Sv39x4 G-stage tables. `guest_flags` declares the G-stage payload leaf
permissions. `guest_fault` requires a load guest-page fault with checked
mtval2. `vmid` selects a 14-bit VMID. These cases require the H extension.
A scenario with `shootdown = true` selects a two-hart mailbox protocol for a
level-zero RV64 mapping. The Spike reference uses `-p2`. The C1 project must
select an adapter configuration with two harts. Request, acknowledgement and
completion use RAM mailboxes and explicit memory fences. No IPI is implied.
Neither option supports the independent immutable-walk checker yet.
### Random MMU programs and functional groups

`rvw.mmu/1` may contain `random` with selected `modes`, integer `seeds`, `pages`
and `accesses`. Pages are bounded to 1..64. Accesses are bounded to 1..128.
Each seed creates one program with multiple random mappings and load/store
accesses. PTEs select read/write, read-only, invalid or reserved level-zero
entries. Programs check each load, each exact trap cause/tval/PC and all final
physical data values. A/D bits are preset. Every access restores MPP before
MPRV so a prior trap cannot change the effective privilege. These are bounded
random programs, not exhaustive VM verification. The same ELF-dir C1 adapter
suites run them. `random_program` in expanded scenarios records seed and bounds.

MMU builds also write `functional-groups.json` for `rvw cov functional`.
Groups cross paging mode/access/result, levels/faults, PTE permissions,
translation protocols, harts, VS/G modes, pointer controls and IOMMU contexts,
stages and queues. C2 retirements may carry `mmu_protocol` and `iommu` lists
of captured dictionaries. Protocol records use `kind` and optional `hart`.
IOMMU records use `device`, `process`, `result`, `stage`, `access`, `queue`
and `operation` as applicable. Missing fields do not hit the affected group.
The coverage engine also consumes `mmu_walks`, hypervisor translations and
pointer CSR snapshots. C2/2 multi-hart traces keep separate dependency and
sequence histories for each hart and reset epoch. Coverage hits are capture
observations. They do not prove correctness or fill MMU architectural bins.
Missing captures remain holes. Hardware support and reachability are not
inferred from the declared domains.

### Decoded IOMMU scenarios

`rvw regress mmu iommu --generate --seed N --mode MODE` emits
`rvw.iommu-scenarios/1` data. `contexts` maps device IDs to decoded contexts.
A context can have `valid`, `first`, `second`, `processes` and `msi` fields.
First/second stages give `mode` (bare/sv39/sv48/sv57) and `root`. First stages
can set `privilege`. Process IDs map to first-stage contexts. Second stages use
x4 geometry. VS PTE reads also pass through second-stage translation.
`memory` gives physical PTE values. MSI `mask`/`pattern` selects page addresses;
`pages` maps selected page numbers to host page bases. These are decoded model
inputs, not raw architectural DDT/PDT/MSI structures.

`steps` contains `request`, `command`, `process_command`, `pte_write` and
`fault_pop` records. A request gives `device`, optional `process`, `address`,
`access` (load/store/fetch) and optional `size` (1/2/4/8). It must fit one page.
Decoded commands are `iotinval`, `iodir` and `iofence`, with optional device,
process and address scope. The model retains cached translations until an
invalidation. Queues have power-of-two `queue_size` with one slot reserved.
Full fault queues set `fault_overflow`. Faults have descriptive stage/cause
fields; these are not the architectural binary fault record encoding.

`rvw regress mmu iommu DESCRIPTION --observations FILE --result C1` compares
independent device-agent records. `rvw.iommu-observations/1` has `records`, C1
`identity` and `c1_sha256`. The C1 details must bind `iommu_description_sha256`.
All identity fields must match. Missing or unbound evidence stays inconclusive.
Mismatches remain mismatches. Reports use `rvw.iommu-check/1`. MCP exposes
`regress_mmu_iommu_generate` and `regress_mmu_iommu`. The Python device agent
calls a project-owned exchange callback with the same requests as the model.

The report records the pinned upstream reference-model revision. That pin is
source metadata. It does not mean that the C reference ran. Raw directory and
register conformance, ATS, PRI, atomic A/D, MSI wire formats and DUT transport
integration remain unsupported by this decoded model.

### Pointer-masking privilege matrices

`rvw.mmu/1` may contain `pointer_matrix` with `modes`, `extensions` and
`controllers`. Supported modes are sv39, sv48 and sv57. Extensions are smnpm,
ssnpm, smmpm, sspm and supm. Sspm/Supm require explicit controller declarations
in the project: `sspm = "smnpm"` and `supm = "ssnpm"` for this backend.
These capability names do not define separate CSRs. Scenarios may declare
`pointer_extension` and `pointer_controller`. Ssnpm selects senvcfg.PMM with
MPRV effective U privilege. Smmpm selects mseccfg.PMM for Bare M-mode data.
Smnpm selects menvcfg.PMM with effective S privilege. Tagged instruction fetch
under Ssnpm/Smnpm must fault even when data masking is enabled. The programs
check PMM readback, exact trap cause/tval/PC and successful data values.
Guest/debug interactions and nonstandard execution-environment controls remain
unsupported. The backend refuses inconsistent controller declarations.

### Hypervisor MMU matrices

`rvw.mmu/1` may contain `guest_matrix = {"modes": [...]}` instead of scenarios.
Supported modes are sv39, sv48 and sv57. The generator crosses the selected
VS and x4 G geometries. Guest scenarios may give `guest_mode`, `guest_op`
(hlv.d, hlvx.wu, hsv.d, vs-satp, vs-sfence, vs-sret), `guest_trap` (m or hs),
and boolean `guest_switch`. VS controls require `expect = "virtual-instruction"`.
`ad_mode` and `ad_expect` select VS-stage A/D behavior and check the full PTE.
G roots have 16 KiB alignment and widened top-level indices. hgatp and vsatp
readback must preserve the selected modes. G faults check mtval2 or htval and
mtinst or htinst. Trap-instruction values may be zero or the specified
transformed instruction. `guest_switch` uses two G roots with different payloads
under the same VMID. It fences each switch, including reuse. It requires a
successful M-mode HLV.D test. Independent `mmu_nested.translate` checks G walks
for every VS PTE read as well as for the final payload. Its Python results do
not imply DUT capture or nested-walk comparison. Hardware A/D and extension
PTE walk models remain outside its scope.

### Translation protocol probes

`rvw regress mmu report --protocol-config FILE` reads `rvw.mmu-probes/1`.
The project declares `harts`, a `probes` object that maps event kinds to probe
paths, and optional `pbmt_types` mapping PBMT numbers as strings to memory-type
names. The example paths and memory-type names require project replacement.
Events remain in the identity-bound `rvw.mmu-observations/1` sidecar.
Each has an ordered `cycle` and `kind`. Translation events give `hart`.

`pte_write` gives physical `address` and `data`. `ad_atomic` gives `address`,
`old`, `new` and `set_bits` (64 or 192). The old value must equal the current
observed PTE. The new value must preserve all bits except the set A/D bits.
`tlb_fill` gives `entry`, aligned `va`/`pa` bases, power-of-two byte `size`,
`asid`, optional `global`, `pte_address` and `pte`. A fill must use the current
observed PTE. `tlb_hit` gives `entry`, `va`, `pa` and `asid`. It must match a
retained entry. `tlb_invalidate` is a completion with `va` and `asid`, each
nullable for all addresses or all ASIDs. An address invalidates the containing
range. ASID-specific invalidations preserve global entries.

`shootdown_request` gives unique `request`, target hart list `targets`, and
optional `va`/`asid` scope. `shootdown_ack` gives `request` and `hart`.
It requires a prior matching local invalidation completion. A
`shootdown_complete` requires every target acknowledgement. `memory_type`
gives `pbmt` and `memory_type`; it requires the explicit project policy.
Missing initial PTEs, unfinished requests and absent probes are inconclusive.
Protocol results remain separate from architectural coverage. This checker
does not infer missing events, bus ordering or cache coherence.

MMU `atomic_ad = true` selects a two-hart RV64 store with hardware A/D and a
software AMO update to RSW. The final full PTE must contain both updates.
It does not establish that DUT updates overlap. A `shootdown` scenario can
provide `ipi` with project-owned `msip` base and per-hart `stride`. It delivers
an actual M software interrupt before local SFENCE and acknowledgement.

### Ordered MMU walk observations

C2 retirements may contain `mmu_walks`, a list of completed walk records.
Each record has `kind = "mmu_walk"`, sequential integer `access_id`, `mode`
(Sv32/39/48/57 in lower case), `access` (load/store/fetch), `va`, `root`,
`status` (success/page-fault/access-fault), and ordered `reads`. Successful
records also give `pa`. Addresses and PTE data use integers or integer strings.
Each read gives integer `level`, physical `address`, boolean `fault`, and
`data` when the read succeeds. PMP-denied reads have `fault = true`.
The adapter captures these from project-declared probes. It must not synthesize
walk records from retirement results. `access_id` follows the scenario's tested
accesses, excluding harness accesses. A project must capture all tested walks
for a complete comparison. A TLB hit that has no walk leaves this comparison
inconclusive. No TLB hit coverage is implied.

`rvw regress mmu report` checks bounded data scenarios against an independent
Python walker. Reference PTE snapshots come from the scenario generator, never
from DUT returned PTE data. Fenced leaf remaps use separate memory snapshots.
The checker compares every level, PTE address, PTE value and final result.
C2 must have a passing end and its core/config/ELF/RTL/source/seed identity must
match C1. Missing records remain inconclusive. Incorrect or extra records are
mismatches. These results do not fill architectural bins. Hardware A/D writes,
extension PTEs, root switches and unfenced alternatives are unsupported here.

MMU scenarios may set `pte_fault_level` or `walk_deny_level`. The named level
must exist in the selected page table. The first option invalidates its PTE.
The second denies PMP reads of only that table page. Programs check the exact
page/access fault, tval and PC. These fields require the matching fault
expectation and exclude remapping and blanket walk denial.

### Automatic formal checks

`rvw.autocheck/1` extends the reviewed formal app port manifest with optional
`dead_code` rows (`id`, `expression`) and `fsms` rows (`signal`, integer `states`,
`transitions` as integer pairs). Generated app plans use `rvw.formal-apps/1`.
The added kinds are `stuck_at` (`signal`, `bit`, `value`), `dead_code` (`target`),
`fsm_state` (`signal`, `value`) and `fsm_transition` (`signal`, `source_value`,
`value`). Report rows add `observation` without changing their raw native status.
A failing negated reachability target means `reached`. A passing bounded target
means `not_observed_bounded`. Unbounded passing targets mean
`unreachable_conditional`. Constant checks distinguish `not_constant`,
`holds_bounded` and `constant_conditional`. Existing safety contracts use
`violated`, `holds_bounded` or `holds_conditional`. Unknown results are
`inconclusive`.
Plans with reachability targets have aggregate status `inconclusive` because
reached targets are observations. No exclusion is authorized. Optional `xprop`
records the status and path of a separate bounded output X-propagation result.

### Paired register hardware updates

Paired SoC register observations accept optional full-width expanded bit masks:
`write_mask`, `hw_clear`, and `hw_set`. Their defaults are all write bits, zero,
and zero. Hardware clear follows software effects; hardware set has final
priority. Failed bus accesses suppress software effects, but not hardware events.
These fields describe independently observed events over the transaction interval.

### Standard CSR catalog selection

`rvw.csr-catalog/1` stores pinned UDB definitions, source paths, source hashes
and notices. IDL expressions and extension conditions remain data.
`rvw.csr-selection/1` selects named CSRs and fields with project reset, access,
legalization and side-effect overrides. It resolves field positions to
`rvw.csr/1` before the existing generator runs. Unsupported alias, hypervisor
and debug execution models are errors. Selection is not compliance evidence.

### Counterexample reduction

The optional `reduction` field in `rvw.formal.cex/1` has schema
`rvw.cex-reduction/1`. It records each exact-property replay check, removed input
events, the retained end time, and whether all earlier prefixes were tested.
`status=reproduced` is a simulation observation under the retained assumptions.
It is not a proof. Initial values remain. Reduction can stop at `max_checks`.
The optional `testbench` field records generated model and stimulus paths. Its
`status=generated` does not imply compilation or failure reproduction. The
optional `why` field contains SpinalDB drivers, fan-in and staleness diagnostics.
MMU scenarios may select `pointer_mask` as 0, 7 or 16. These bounded RV64
Smnpm cases tag bit 63 of the tested data pointer. They set and read back
menvcfg.PMM. They use MPRV with effective S privilege. Unmasked tags must
fault. Enabled masking must recover the declared canonical address and value.
The reference selects Smnpm explicitly. These cases do not check debug,
instruction-fetch or guest pointer-masking interactions. Their independent
walk and PMA checks remain inconclusive.

### Privilege campaign artifacts

Kinds `imsic`, `aplic`, `aclint` and `smnip` select versioned controller
programs. `spec_version` pins the implemented version; `spec_revision` records
an optional immutable source revision. `reference_backend = "python"` selects
small executable reference models. The reference report adds `evidence =
"model-based"` and `model_sha256`, mapping model source files to hashes.
Its scenario outcomes are model observations, not native Spike or DUT results.
The normal C1 plus complete strict-reference gate remains unchanged.

Kinds `pmp`, `epmp` and `pma` generate separate protection matrices. PMA
scenarios require a `privilege_bus` C1 artifact: `complete` is Boolean,
`transfers` hold address/width/write and `device_state` holds independent
project state. The configured counts, transfer shapes and state must agree.
Missing state or an incomplete capture remains inconclusive. Reports bind the
artifact hash. These observations do not replace the strict architectural check.

`compiler_isa` optionally selects compiler instruction parsing. `isa` still
selects the reference model architecture. Numeric encodings can therefore be
compiled with a base assembler without claiming extension model support.

Kinds `plic`, `reset` and `nmi` emit `rvw.stimulus/1` device events. Each
payload has a positive `step`, request/ack ELF symbols and project event data.
The adapter applies events in order and acknowledges each step after driving
it. Optional `when_pc` requires the resolved architectural PC. Build manifests
bind the stimulus hash; C1 must record `stimulus_sha256`. Reset campaigns also
require a `privilege_reset` artifact containing one list of ResetSample objects
per requested pulse. Samples use `cycle`, `asserted`, `state` and `valid`.
The report binds the observation hash and requires the existing independent
reset contract check. Missing evidence remains inconclusive.

`kind = "scheduled-wfi"` emits per-program suites with C1 `irq_schedule`.
`wake` declares assertion/clear cycles and optional retained-state masks in
`clock_state`. The optional C1 artifact `privilege_clock` holds a JSON sample
list: `tick` is the reference edge, `clock_running` is a Boolean, `state` maps
names to integers, `retired` is cumulative retirement and `pending` is Boolean.
Unknown values can be null. The checker requires a complete observed pause
and restart, stable masked state and a pending event during the pause. It binds
the artifact hash. A missing artifact is inconclusive. The artifact reports
project harness observations; Spike CLI cannot supply clock-stop evidence.

The optional `kind = "disabled"` selects FS-Off or absent-supervisor matrices.
`priv = "mu"` selects absent supervisor operations. Otherwise FS-Off requires
F in `isa`. The reference forwards `priv` to Spike. These cases use the same
build, reference and check schemas.

`rvw regress privilege build` reads `rvw.privilege/1`: `modes` selects distinct
M/S/U modes and `isa` selects an RV64 compiler and Spike ISA string. The current
control matrix requires `priv = "msu"` when given. It writes self-checking ELFs,
sources, a linker script, a suite fragment and `rvw.privilege-build/1` manifest.
The manifest records the description hash, specification URL, configuration,
scenario IDs, ELF/source hashes and functional group names in `bins`.

`reference` writes `rvw.privilege-reference/1` JSON to stdout. It records command,
return code, model hash and per-scenario self-check status. It is reference-only.
`check` writes `rvw.privilege-check/1`: it binds the build manifest and each C1
result by SHA-256. A group passes only if every member has a passing C1 result
and a complete strict Spike match with a passing end event, positive instruction
count and zero synchronizations. Missing or duplicate evidence is inconclusive.
These artifacts do not change C1, C2 or C3 and do not grant C4 acceptance.

The privilege description also accepts `kind = "wfi"` and a `timer` object with
integer `mtime`, `mtimecmp`, `msip` and `delta`. The generator programs the
project-owned timer/software device and crosses the two sources with MIE
clear/set. The delta is in timer ticks. C1 execution bounds the wait. It makes
no minimum sleep or physical clock-gating claim. Builds include
`functional-groups.json` for C2 observation coverage. Observation hits do not
grant the architectural pass groups from `privilege check`.




### Finite temporal SVA and parallel SBY observations

`rvw formal sva-lower SOURCE --out FILE` lowers finite clocked SVA to native
Yosys statements. It reports `rvw.sva-lowering/1` on stdout, with per-property
`id`, `kind`, `clock`, `disable_iff` and `horizon`. Unsupported syntax raises a
named `unsupported:CONSTRUCT` error before any output write. BMC accepts
`--frontend temporal`; its sealed source record contains the generated bytes.
Its `temporal_properties` array records each lowering horizon. Sampling, finite
bounds and asynchronous cancellation limits are in the formal README.

`rvw formal regress [MANIFEST] --jobs N --timeout SECONDS --out DIR` selects
one task per `[[property]]` row. `[formal] regress` in project data supplies the
manifest if omitted. A row has `id`, `sby`, `top`, optional `task`, `requirements`,
`assumptions`, and `config`. Paths are relative to the manifest. The new optional
project key is a path. Each resolved job has one assertion and one engine.
Workers are capped by N and CPU count. Listed inputs and tools are frozen first.

C3 `formal-regress` rows add `formal_status`, `mode`, requested `depth`, `traces`,
`task`, `requirements`, `assumptions`, `configuration`, `job_sha256`, `activation`
and an `inconclusive` reason. Unsupported rows carry `diagnostic`. Status values
are `proven`, `bounded-pass`, `failed`, `unknown`, `timeout`, `unsupported`,
`vacuous`, `error`. `proven` means an unbounded engine observation only. PREUNSAT
is vacuous. All other activation remains unmeasured. Input closure, full
attribution and non-vacuity are not certified. These rows cannot grant acceptance.
C3 and JUnit retain that restriction. `rvw.formal-regress/1` in `result.json`
has `status: unknown`, `suite`, `junit`, `workers`, and `properties`. Exit is 1
for these conditional observations. MCP `formal_regress` returns this summary.

### SVA intent generation

`rvw formal properties SPEC.json [--channels CHECKS.json] --out FILE` writes
module-body SVA snippets. MCP `formal_properties` returns the output path.
Without `--channels`, the spec has a nonempty `properties` array with unique
IDs. Supported `kind` values are `handshake`, `fifo`, `one-hot`,
`arbiter-fairness`, `request-response`, `flow`. Each row declares exact RTL
identifiers, an optional `clock` and optional active-high `reset`. The formal
README defines each finite contract and its fields. No environment assumption
is generated. Output generation is not a proof result.

With `--channels`, CHECKS uses the existing `rvw.checks/1` channel list. SPEC
maps each exact `path.object` to `id`, `clock`, optional `reset`, `width`, and
`ports`. `ports` maps reported qualified signal names to local RTL identifiers.
Flow also requires `max_value`. Missing clock/port bindings and composite
payloads are unsupported. This explicit mapping preserves independent channel
clocks without guessing domain semantics absent from the report.

The finite temporal frontend also accepts finite `throughout`, `within`, and
`intersect`. Endpoints remain part of the path semantics. Single-argument
sampled-value functions use the property clock, with unconstrained history
before the first event. `$rose` and `$fell` use bit zero; `$stable` and `$changed`
compare full vectors. Explicit depths and nested sampled calls remain refused.
These are sampled formal observations, not simulator-region qualification.
### Verification obligation plans

`rvw.verification-obligations/1` declares explicit `specifications` versions and
`obligations`. Extension obligations expand operand bins, exception scenarios
and dependency scenarios. Environment-control obligations expand project legal
writes, contexts, transitions and enabled/disabled expectations for menvcfg,
senvcfg or henvcfg. Each obligation includes attributed independent reference
vectors and attributed mutants that differ from a named vector.
`rvw.verification-plan/1` output has `status: generated` and `not_run` cases.
No RTL execution is implied. `rvw verification-plan check` compares supplied
observations only for reference cases and writes C3 with incomplete source
identity. Missing observations are errors; differing observations are failures.
Other case kinds remain unexecuted. C3 vector passes do not establish plan
closure, mutation coverage, architectural correctness or C4 acceptance.

### Symbolic datapath result

`rvw.datapath/1` records the `yosys-boolean-cbmc` backend, source and tool hashes,
width, rounding, case split and fixed transaction latency. `proved` exits 0 only
when CBMC exits 0 and every property succeeds, including the result assertion.
`counterexample` exits 1 only for result, flags or completion violations.
C safety failures, unwinding failures, missing tools and timeouts are
`inconclusive`, exit 3. This is not a C4 acceptance result. The `properties`
array retains CBMC property descriptions, statuses and available traces.
The reference model and dependencies are trusted specification inputs.

#### Bounded datapath completion

`rvw.datapath/1.max_latency` is null for the existing fixed-latency contract.
A positive value selects a first-done completion bound in 1..256 clocks after
start. Result bits and flags are checked at that first completion. Missing done
is a completion failure. Operands stay stable. `inputs.binding.json` captures the
optional project top and canonical-to-project port map by SHA-256. A binding
changes names only. It does not remove ports, change widths or add assumptions.

### Generic multi-hart harness inputs

C1 adapters can declare `hartIds(config)` and accept `--hart-images PATH`.
The file uses `rvw.hart-images/1` from `rvw memory images`. Each row must match
one declared hart and its captured ELF hash. Relative ELF paths resolve beside
the manifest. The driver captures all images before compilation. Shared
segments must have identical address, file bytes and memory size. All other
segments must be disjoint, including BSS. `--boot-payloads` is incompatible.
The primary `--elf` remains the legacy C1 identity. `details.hart_images` holds
all captured identities and entries. Replay includes the manifest path.
`MultiHartSession` writes one C2/2 trace with per-hart retirement orders,
reset epochs and completion. It does not infer a memory order from capture.


The temporal frontend can combine captured source files for module-target
checker bindings. Original source records remain in the input snapshot. The
combined `inputs/temporal.sv` is a sealed generated proof artifact. Module-local
argument-free named properties resolve before monitor generation. Recursive or
unused named properties are refused. Only explicit ANSI input checker ports and
named-port module-target bindings are supported. Instance-target bindings and
checker scheduling extensions remain unsupported.




### Captured-model solver cores

`rvw.solver-core/1` can contain `bounded_model` with `top`, `depth` and `scope`.
These cores refer to an aggregate bounded assertion query exported from frozen
SBY RTLIL. Labels identify sample constraint groups. They are not cell coverage,
per-property proofs, or coverage exclusions. Generated SMT and bindings are retained.
The optional `environment_core` lists constraint labels when the environment
feasibility query is UNSAT. Such a run is inconclusive. `bounded_model.feasibility`
records this separate check. `--property` selects one top-module assertion cell;
the generated property ID is `TOP:CELL_NAME`, bound to the captured model.

### Formal testplan evidence joins

`rvw.formal-testplan/1` lists property IDs, modules, origins, optional source
locations, requirement IDs, mutation IDs and external evidence paths.
`rvw.formal-testplan-report/1` retains each property result, depth, proof kind,
activation, core labels and explicit mutation outcomes. It groups counts by
module and source line. Missing evidence remains explicit. Requirements and the
aggregate report remain inconclusive. `cell_coverage=unavailable` prevents SMT
constraint labels from becoming cell coverage. `exclusion=not_authorized` grants
no new waivers. The input capture binds the plan and every evidence file.
Solver-core reports can include `assumptions`, with captured cell names, labels
and `in_core`. An UNSAT environment gets a reduced `environment_core` and an
`environment_minimal` flag. This is deletion minimality over constraint groups,
not minimum cardinality or full assumption adequacy.
### Deep formal experiment reports

`rvw.formal-portfolio/1` records pinned self-contained RTL hashes, source
assumptions, engine rows, the first conclusive winner and observed cross-checks.
Its `pass` requires an unbounded engine answer. Bounded success is
`bounded_pass` on the engine row and cannot earn portfolio `pass`. Disagreement
makes the report `inconclusive`. Unavailable backends are `not_installed`.
No checks or failed preparation makes the report inconclusive without a winner.
The raw experiment adds no environment or activation guards.

`rvw.formal-engine-bench/1` records one row per case/engine pair. Its `pass`
means verdict agreement on each case, including agreement on a fault. It is not
a proof verdict for the benchmark design. Wall time includes engine preparation.
A requested depth does not claim a measured reached depth.

`rvw.formal-model-grid/1` records the canonical explicit-model SHA-256 and one
row per property. `pass` requires every row to prove its safety property.
`fail` requires a concrete graph counterexample. A spurious projected trace is
inconclusive until replay and refinement. Helper invariants require initiation
and consecution. The graph, including all memory choices, is a supplied input.
No RTL-to-graph correspondence or whole-core result is implied.

A distributed explicit-model grid adds `shards`, expected property names and
adapter source identities. The existing farm worker transports JSON model bytes
and formal result artifacts. It adds no C1 simulation claims. Transfer, identity
or coverage failure leaves that shard inconclusive. Real SSH execution requires
compatible installed adapters and trusted hosts.

`rvw.formal-rtl-refine/1` records frozen source hashes, automatically selected
state/RAM cuts and each refinement round. Abstract counterexamples remain
inconclusive. Only a cut-free failure reports `fail`. An unbounded proof of an
overapproximation can report `pass`. Budget expiry and engine errors remain
inconclusive. This flow preserves the existing guarded proof runner.

Raw engine portfolios with source assumptions remain inconclusive until a
separate activation check exists. Engine rows retain the observed conditional
answer. AIGER imports record original input bytes and the translated Verilog
and importer SHA-256 identities. Justice/fairness inputs are unsupported.
Relational strengthening uses `rvw.formal-strengthen/1` with independently
certified relational candidates in addition to unsigned bounds.

`rvw.formal-rtl-grid/1` reports one result per independently exported RTL
property case. It uses pinned source bundles and the same farm artifact adapter
as explicit-model grids. `pass` requires every case to earn a portfolio proof.
A concrete case failure reports `fail`. Missing remote properties are
inconclusive. The full exported property set must be supplied by the caller.

### Native formal engine diagnostics and benchmark totals

`rvw.formal-doctor/1` records installed dependencies, executable paths, supported
modes, and enabled adapter features. `qualification` is `not_measured`.
`status: pass` means the diagnostic completed. It does not mean a proof passed.
The `formal_doctor` MCP tool returns the same report.

`rvw.formal-engine-bench/1` adds `total_wall_s` per row, including preparation,
and `summary` per engine with solved, bounded passes, cases, and total wall time.
Only `pass` and `fail` count as solved. Missing tools and unsupported modes do
not count. SBY `UNKNOWN` with exit 4 is inconclusive. Inconsistent status and
exit code pairs are errors.


### Eventual-response liveness jobs

`rvw.formal-live/1` records `status`, `observation`, property ids, clock names,
`live` or `fair` cell wires, input capture and restrictions. The frontend accepts
single-clock Boolean eventual response and emits SBY `mode live` with
`aiger suprove`. It never substitutes a bounded response. Generated jobs report
`not_run`. Missing tools report `missing_tool`. Engine PASS remains unknown;
engine FAIL is a failure. The result does not certify activation or non-vacuity.
CLI `formal liveness` and MCP `formal_liveness` share this result.
### Coverage-directed replay selection and finite-graph fairness

`rvw.formal-swarm/1` can select cycles from a state plan. The plan declares
`trace_sha256`, unique `holes`, and `states` with unique positive `cycle` and
`targets` from those hole IDs. The runner checks the captured trace hash. It
selects the state with most remaining targets first, then the lowest cycle.
Targets are priorities, not proof evidence. `selection` records the plan hash,
trace hash and unrepresented targets. `engine_pool` rotates across attempts.
Every attempt records its engine. The campaign remains inconclusive.

`rvw.formal-model-live/1` checks `GF progress` on an explicit transition graph.
`progress` lists states. Each entry in `fairness` is a state set that must recur
infinitely. The checker searches reachable nonprogress strongly connected
components that contain a cycle and meet every fairness set. Such a component
is a counterexample. No feasible fair infinite execution is inconclusive.
Deadlocks are listed separately. A pass proves the supplied graph only under
its declared justice assumptions. It does not certify an RTL translation.
`model_sha256` identifies the exact captured model. CLI `model-live` and MCP
`formal_model_live` return the same report. MCP `formal_swarm` runs replay.
### Scalar axiomatic memory annotations

C2/2 can declare `memory_dependencies: complete` and add `memory_model` to
retirement records. This object identifies the event by string `id`, integer
`hart` and integer per-hart `order`. It carries `kind` R/W/LR/SC/AMO/FENCE and
complete dependency source ID arrays `addr`, `data`, `ctrl`. Scalar memory
events carry integer byte `address`, `size` and integer `read` and/or `write`.
A successful SC names its paired LR ID in `rmw`. Fences and aq/rl attributes
are decoded from RVFI instructions. The checker validates annotated bytes
against RVFI. Dependency completeness is a project observation contract.

`rvw.axiomatic-initial/1` has `locations` with string hex `address`, integer
byte `size` and string hex `value`. `rvw.axiomatic/1` reports allowed, forbidden
or inconclusive, the model, candidate count and an optional witness. Results
apply to one finite scalar execution under declared dependencies. Limits and
unsupported profiles cannot produce allowed or forbidden. No full-core proof
is implied. `rvw.concurrent-programs/1` contains seeded per-hart RV64 assembly
fragments and project requirements. `executed:false` is mandatory at generation.


### Timed finite-SVA simulation

`rvw.formal-events/1` contains `timescale`, `clocks` and `events`. Each event has
`time` and an `inputs` map of exact-width four-state binary strings. Time starts
at zero with every input declared. Later times strictly increase. Clock changes
and data/reset changes have distinct timestamps. No periodic clock is inferred.

`formal simulate` and MCP `formal_simulate` write C1 `rvw.run/1`. Additional
fields include `assertions` with per-property pass/fail/cover/miss counts,
`observations`, `unknowns`, `backend`, `x_semantics`, `scope` and captured inputs.
Assumption failures and absent checks are inconclusive errors. Assertion faults
use C1 `assert`; requested X observations use `fail`. Verilator results cannot
claim four-state X evidence. The coverage artifact contains sampled monitor
points in Verilator point-record format, attributed to generated simulation RTL.
It is consumable by `rvw cov`, and is not native RTL code coverage. Source hashes
keep different generated models separate. Pending future obligations and full
simulator scheduling-region conformance remain outside a finite replay pass.
### Bounded bug-hunting campaigns

`rvw.formal-bug-hunt/1` captures pinned source bytes once. Its manifest has the
same `top` and `sources` fields as engine-race, plus increasing positive
`depths`, bounded `engines`, and unique unsigned 64-bit `seeds`. Seeds apply to
rIC3 only. Every other engine runs once per depth. `attempts` records depth,
engine, seed, native rows and retained result path. `unstarted` records work
left after the budget expires or a counterexample stops the campaign. A complete
bounded schedule remains inconclusive. Only a concrete failure earns `fail`.
CLI `bug-hunt` and MCP `formal_bug_hunt` expose a budget and per-stage timeout.

Portfolio manifests can set `ric3_seed`. BMC probes the rIC3 help interface.
When it has `--end`, a recorded wrapper translates SBY's older bounded flags.
The wrapper clears inherited Python launcher variables and preserves native
output and exit status. `compatibility_sha256` identifies its captured bytes.


Composite SVA intents use `payloads` with per-field signal and width for Stream,
or per-field maximum value for Flow. Single-payload intent inputs remain valid.
Optional database binding emits `rvw.channel-bindings/1` beside the generated
SVA. It contains `bindings`, `input_capture` and `db_warnings`. Domain anchors,
clock/reset ports and widths resolve from SpinalDB. Ambiguous or mixed domains
are refused. A database warning is not a current-RTL match or timing result.
