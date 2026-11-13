# Project configuration (`rvw.project/1`)

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
| `riscv_formal` | `root`, `wrapper`, `verilog`, `isa`, `nret`, `checks`, `depth`, `solver`, `defines`, `ports`, `check_options`, `instruction_models` | Bounded native riscv-formal settings. See `rvw/src/rvw/formal/README.md`. NRET 1..16; unsupported settings are refused. |
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

### Project-owned verification plans

`rvw plan status` and `plan_status` read `rvw.vplan/1`: requirement descriptions
and features that map requirement IDs to coverage groups, C1/C3 tests, named
formal app properties and C4/block checks. Evidence references have relative
paths and optional exact SHA-256 pins. `rvw.plan-status/1` reports feature
status, coverage totals, holes, evidence hashes and unassigned requirements.
Missing/inconclusive evidence, zero denominators and unmeasured groups stay open.
Bounded formal evidence cannot meet an unbounded obligation. Features can select
block or integration scope. Block-only evidence cannot close integration scope.
Block reuse does
not cover new wiring. Source/execution contexts constrain coverage trends.
Same-plan snapshots can report hole/hit deltas; incompatible coverage contexts
have no numeric trend. `reported_closed` is a recorded evidence rollup under
project-declared mappings. It grants no requirement completeness, unconditional
proof, runtime assumption enforcement, whole-core closure or C4 acceptance.

### Reusable block evidence

`rvw cov block-check` and `cov_block_check` compare `rvw.block-evidence/1` with
`rvw.block-integration/1`. Both bind the same declared logical source set.
Evidence lists source path/hash pairs and exact tested configurations with
parameters, assumptions and hash-bound C1 records. Integration lists current
source paths, parameters and environment facts. Matching C1 records must have
an exact `details.block_evidence` receipt with source_id/parameters/assumptions.
Source ID hashes the compact sorted logical-name-to-source-hash JSON map.
`rvw.block-reuse/1` reports eligible_for_reuse, incompatible or inconclusive,
with holes and matched run records. Missing evidence cannot authorize reuse.
new_wiring_covered is always false. Assumption checks are static declarations.
Transitive dependency closure, runtime enforcement, formal evidence and new
integration wiring remain outside the first interface.

### Directed tests linked to pinned Sail rules

`rvw regress sail-tests` and `regress_sail_tests` emit
`rvw.sail-directed-tests/1`. The bounded domain is the existing pinned RV32
add/sub/addi arithmetic slice. Each case records its exact rule/obligation,
seeded inputs encoded as DII words, token/source hashes, complete reference
packets, expected result and instruction/register mutation observations.
Generated source fragments use four project-declared registers and a
project-owned `rvw_test_fail` label. Source pin failure refuses generation.
Partial/trapping oracle streams earn no expected result. Overall status is
`reference_generated` or `inconclusive`. Endpoint binary identity remains
unattested. No DUT pass, general Sail compilation or C4 acceptance follows.

### Native coverage metrics per linked source line

`rvw.coverage-report/1` adds `scala_line_metrics`. Each file/line key contains
native metric summaries, statement_hit_status `undetermined`, and a unit string.
Each native point counts once per linked line and metric. Several linked lines
can refer to the same point. Native types, holes and exclusions remain separate.
This field adds no source attribution and makes no Scala statement-hit claim.

### Coverage counter interchange

`rvw cov exchange` and `cov_exchange` implement the declared UCIS 1.0 counter
profile `rvw-counter-profile/1`. Every original counter is a singleton ordinal
coverpoint bin. `rvw.counter` preserves its native kind, original bin tuple,
source link and exclusion metadata. `rvw.context` binds sources and plan/native
context. Native UCIS metric tags and arbitrary vendor profiles are unsupported.
Import returns `rvw.coverage-exchange/1`: context, rows with id/kind/count/metadata,
status `reported`, and `proof_exclusions_verified=false`. Unknown XML structures
are errors. Compatible merges require identical context and bin semantics.
Event counters add across compatible reports. Peak-active counters merge by
maximum. Active snapshots must agree and do not add.
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
recorded attempt artifacts and declared input identities. Declared initial inputs and implementation files are archived in a separate
immutable input generation. Raw attempts have their own immutable generations.
State pins each ID and manifest hash. Resume verifies those generations and
retained working files. Older unsealed state cannot resume under a changed
implementation identity. C1 input capture/source completeness, RTL hash and
reference C8 dependency identities gate credit. Native identity changes stop
the loop without new hits. Program-specific ELF/C2/C1 records and Python caches
are excluded from reference backend identity. Transitive dependency closure
and full cost accounting remain unqualified until native campaign validation.

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

## Mapped core description (`rvw.core-map/1`)

A project file, by convention `rvw/core-map.json`, that the generic RiscvSim
`MappedAdapter` reads through `RVW_CORE_MAP`. `rvw init --spinal-top` or
`--verilog-top` writes it. Fields: `schema`, `core`, `config`, `isa`, `xlen`,
`top` (`kind` `spinal` with `class`, or `verilog` with `module`, `files`
relative to the map, `defines`, `parameters`, `ports` of `name`/`dir`/`width`,
`clock`, `reset`, `reset_active`), `reset_pc`, `ram` (`base`, `size`),
`buses` (`name`, `protocol` `req-rsp` or `valid-ready`, `signals`,
`write_response`), `rvfi` (`{"prefix": P}` or null), `irq` (`mip` bit to port)
and `constants` (port to value). Numbers are integers or `0x` strings. Unknown
fields, unknown protocols and unknown or missing bus signals are errors. A
missing named port is a run error. The C1 `rtl_sha256` of a Verilog top covers
the generated wrapper, the defines and every source file. See
`RiscvSim/README.md`, "Mapped adapter".

## Adapter conformance diagnostics

`rvw doctor --conformance --smoke-elf ELF` adds named `conformance.*` checks
under `rvw.doctor/1`. It requests C2 for each adapter config. Each trace must
have a valid header, instructions and a passing end event. The header must
match the project's core, selected config, ISA and XLEN. An independent
reference check needs the reviewed `--smoke-platform`.

`adapter_conformance.requested_checks` is `ready`, `error`, `inconclusive` or
`not_run`. `full_c1` and `full_c2` stay `inconclusive`: this bounded program set
does not establish all-option or all-program conformance. A failed replay
command is an error even if it leaves a passing result file.

## Wired scaffold inputs

`rvw init --wire-build` declares standard external Spinal launcher inputs and
RTL identity capture. Custom adapter inputs must extend this declaration.
The generated project owns `Elaboration.config` and `Elaboration.top()`.
Simulation and database generation use this entry. Formal and lint use the
RTL recorded in that database. Both RTL identity hooks remain required.

## External runtime classpath cache

Wired launchers store `target/rvw-classpath.json` in the adapter project.
It is a build accelerator, not a result identity. Source and runtime file hashes
must match before reuse. Native identity capture still runs on every launch.
The generated sbt lock is private to the project name (`sbt-<name>`).
