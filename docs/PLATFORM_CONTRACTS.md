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
| `checks` | `settings`, `waivers` | Project adapter settings and waiver file paths. Their format belongs to the adapter. The launcher must consume them. |
| `query` | `build`, `db` | Build command list and output database path. `rvw query build` calls `build CONFIG OUT`; `--config` and `--out` override the core default and `db`. Query reads use `db` unless `--db` is explicit. |
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

The cosim platform JSON declares `privilege_modes`, `misaligned` outcomes,
`endianness`, `absent_pmp_csrs` and `ecall_tval`. Missing keys retain the legacy
MSU, alignment-trap, little-endian, absent-PMP-trap and ECALL-zero defaults.
Unsupported policies must be refused. These settings do not permit arbitrary
trace values or broad CSR masks. See the exact settings and the
[C2/Spike/Sail comparison matrix](../Cosim/README.md#architectural-comparison-coverage).
C2 does not carry partial memory effects, FP state or per-hart state.

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
Compare derives assertion signatures again from saved messages, including older C3 results.
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
RiscvSim native identity namespace `native-inputs-v26` excludes that declared checkout selector
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
failed-run and mutation-control checks still apply.

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

## C9. Native architecture models

These reports measure model performance. They do not produce C4 gate verdicts
or claim C8 completeness. Every CLI action supports `--json`. A bad selection,
invalid input, failed run or comparison mismatch exits 2. Stdout then contains
one error object with `--json`. Success exits 0 and means a report was produced.

`[arch]` in `rvw.project/1` has three path fields: `description`, `sources`,
and `benchmarks`. Each path resolves against the project file. An absent or
invalid selected section is an error. No core preset is selected implicitly.

`rvw.arch-core/1` describes one RV64 O3 hart. Required fields are `schema`,
`config` (C1 preset), `isa`, `kind="o3"`, `cpu`, `queues`, `predictor`, `icache`,
`dcache`, `itlb_entries`, `dtlb_entries`, `line_bytes`, `bus_bytes`, and
`memory_latency`. Unknown top-level fields are errors. `cpu` contains scalar
gem5 RiscvO3CPU parameters. The cache tables contain scalar Cache parameters.
Unknown gem5 parameters and object references are errors. Omitted scalar
parameters use gem5 defaults. Each queue has `entries` and `units`. Each unit
has `ops` (gem5 opclass names), `count`, `latency`, and `pipelined`.
`predictor` has `tage`, `loop`, `btb`, and `ras_entries`. TAGE has
`nHistoryTables`, `minHist`, `maxHist`, `tagTableTagWidths`, `logTagTableSizes`,
and `logUResetPeriod`. Loop has `logSizeLoopPred` and `logLoopTableAssoc`.
BTB has `numEntries` and `associativity`. Clock is 1 GHz. Memory is 512 MiB
at 0x80000000. `memory_latency` is a positive whole number of cycles.

`rvw.arch-build/1` records config, ISA, source path, gem5 and compiler identity (path, SHA-256,
version), and benchmark IDs, paths and SHA-256 hashes. Builds use native
newlib GCC and the description's ISA. Only RV64GC with optional Zba/Zbb/Zbs
is supported in this version. The source path points to riscv-tests.

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
