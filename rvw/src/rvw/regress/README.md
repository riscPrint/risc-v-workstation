# rvw regress

Regression management for RISC-V cores: run test suites through a core's adapter, store the
results, compare two result sets, and gate a change. It replaces the regression side of
VCS/Xcelium flows (vManager-style result tracking, known-failure triage, accept/reject gates).

It is generic. A core is described by a TOML config (suites, tiers, configs, adapter command).
BOOM's is [`rvw/configs/boom.toml`](../../../configs/boom.toml). The simulator is reached only
through the core adapter of contract C1 (`docs/PLATFORM_CONTRACTS.md`); results follow C3 and
verdicts C4. Every command has `--json`: stdout is then one JSON document, or empty on an error (exit 2, the message on
stderr); progress goes to stderr.

## Commands

```sh
cd rvw && uv venv && uv pip install -e '.[dev]'
R=rvw/.venv/bin/rvw

$R regress list --core boom                       # suites, test counts, tiers
$R regress list --core boom --suite act4          # test ids of a suite
$R regress run --core boom --suite riscv-tests --config small [--jobs 4] [--seeds K] [--out DIR]
$R regress run --core boom --tier quick           # a tier: several suites and configs
$R regress run --core boom --tier full --dry-run # finished / cached / to-run counts, simulates nothing
$R regress run --core boom --suite benchmarks --rev 0cb0b69   # an older core revision
$R regress compare BASE CAND [--known FILE] [--perf-tolerance 0.01] [--allow-missing]
$R regress gate --core boom --base-rev BASE --cand-rev COMMIT [--tier quick|full]
$R regress gate --core boom --base RUN_ID         # against stored base results
$R regress known add --core boom --suite S --id ID --signature SIG --reason "..."
$R regress known add --core boom --from RESULTS --reason "..."   # every failure in a result set
$R regress known list|remove --core boom ...
$R regress history [--core boom] [--rev PREFIX] [--tier quick]
```

`BASE`/`CAND`/`--base`/`--from` accept a results dir, a run set dir, a run id (or unique prefix)
from the history, or `latest`.
For gate and `compare --core`, indexed lookups, including `latest`, use only that core's history.
Both comparison sides must name the same core. When a core is requested, both sides must
also name that core. A mismatch is a usage error (exit 2).

Exit codes: `run` 0 when every test passed conclusively, 1 otherwise (an inconclusive pass is
not a pass). `compare` and `gate` 0 accept, 1 reject,
3 inconclusive. 2 is a usage or config error (also: a run with no tests). An agent should use `gate` (or `compare`) to decide, not `run`'s
exit code, because only they know the base and the known failures.

## What a run writes

```
DIR/current                                atomic generation pointer
DIR/generations/<id>/run.json              sealed run manifest
DIR/run.json                               mutable progress copy of the run manifest
DIR/<suite>/<config>/results.json          mutable C3 workspace copy
DIR/<suite>/<config>/junit.xml             JUnit for CI dashboards
DIR/<suite>/<config>/adapter.log           everything the adapter printed
DIR/<suite>/<config>/manifest.jsonl        the run-many manifest it was given
DIR/<suite>/<config>/tests/<id>/           the adapter's C1 run dir (result.json, run.log, ...)
DIR/<suite>/<config>/tests/<id>/seed-<n>/  instead, when a test runs with several seeds
DIR/<suite>/<config>/tests/<id>/.rvw-job.json   the job's identity, for resume
```

C3 test entries keep the complete failure `message` for signature comparison.
Monitor failures also retain `details.rvfi_errcode` when C1 supplies it.
They carry the contract's fields plus `message`, `fail_code` (failures), `elf`,
`cached` (served from the cache), `synthesized` (rvw wrote the result because the adapter did not),
`wall_clock_timeout`, `inconclusive` (the reason, for a failure the adapter could not trust, any status;
C1) and `multi_seed`. `results.json` carries `seeds` (mode and base), `filter`
(when given) and may carry `perf_metrics`, the metrics `compare` checks.

`--fresh` clears the mutable workspace first, but only a run set (`run.json` with schema `rvw.regress-run/1`) or
an empty directory; published generations remain available. Anything else is refused, also under the results root (its `cache/` is there). A plan that runs no test is an error,
and so is an empty suite unless a `--filter` emptied it.

Default `DIR` is `$RVW_RESULTS/runs/<stamp>-<core>-<label>-<rev>-<random>`, created with an
exclusive `mkdir`, and a new run id ends in a random suffix too: two runs started in the same second
never share a directory or an id. One run at a time may write a `DIR`: `run` (resume, `--fresh`)
holds an exclusive lock on its real path (`$RVW_LOCK_DIR/out/`) and refuses (exit 2, "in use") a
second run on it. The results root
(`$RVW_RESULTS`, default `~/.cache/rvw/results`) also holds `index.jsonl` (the history) and
`cache/`.

## How a suite runs

1. Discover the tests: files under `dir` matching `glob`, id = relative path minus `strip_suffix`,
   kept if any `include` regex and no `exclude` regex matches (plus `--filter` / tier `include`).
   Tests that would share an output directory are a config error (see Decisions).
2. Each test × seed is a job. Seeds are fixed (`--seed-base`, default 1, then +1 per extra seed),
   so base and candidate run the same seeds and results can be reused. `--random-seeds` draws them
   from the run id instead (kept on resume, recorded in the results).
3. Record the adapter, declared `cache_paths`, tools and environment once. Run the adapter
   on the selected real source checkout with the real `PATH`. `RVW_CAPTURE_SOURCE` supplies
   the selected C1 source descriptor. Copy selected ELF bytes for execution. Record declared
   stimulus file and directory identities for options and build arguments.
4. Take the core's heavy-job lock. For each config and model option set, call the adapter's
   `identity` once. With `identity_capture = true`, require `rvw.adapter-capture/2` and check
   every `result_claims` value against every C1 result. The RTL hash and adapter identity join
   job keys and C3 entries. Verify recorded tools before publication. Missing inputs or failed
   identities make results inconclusive and prevent cache or resume reuse. Only conclusive
   results with complete RTL identity, or passes with source identity, enter the cache.
   Resume reads one previous published generation. The adapter inherits
   the heavy-job and output lock descriptors. Writer records retain ownership after a runner
   crash. The watchdog limits a stalled batch.
5. With `wall_timeout = true` each manifest line carries `wall_timeout = timeout_s` and the adapter
   stops a test that runs longer (RiscvSim: a `timeout` with `wall_clock_timeout`). rvw also stops
   the batch when no new result appears for `timeout_s` + 10 s + 20% (plus `startup_s` before
   the first one), and at the latest after `startup_s + timeout_s × ceil(tests / jobs)`. Then, or
   when the adapter dies after writing some results, the tests without a result rerun one at a
   time with `startup_s + timeout_s` each, so a hang or crash is pinned on one test (`timeout` or
   `error`), not the whole suite. A hung test costs about one test timeout, not the batch budget.
6. Read each `result.json`, compute the failure signature (`rvw.results.failure_signature`), IPC,
   and the configured cycle/instret source (`cycles_key = "metrics.roi_cycles|cycles"`), then write
   `results.json` and `junit.xml`.

`kind = "build"` suites (elaboration) run `adapter build --config C --json` once per config; the
test id is `build`. A pass needs exit 0 and agreement with each reported build config.

## Compare and gate

Test the current working tree first:

```sh
rvw regress gate --core boom --base-rev BASE_COMMIT
```

A dirty candidate with no new failures, missing tests or performance regressions prints:

```text
TESTS PASS: 5 compared, 0 new failures, 1 still failing (rv64mi-p-instret_overflow).
NOT ACCEPTED: the candidate lacks a clean committed identity. Commit (a scratch branch is fine) and rerun; passing results can be reused.
```

`TESTS PASS` means that the comparison passed its checks. It can include unchanged failures
and known-failure waivers. Read their counts and details. It does not mean every program passed.
Commit the core change, then run the same command to earn `ACCEPT`. An explicit candidate
commit uses `--cand-rev COMMIT`. A dirty candidate can still produce `REJECT`.
Other incomplete evidence prints `INCONCLUSIVE` with its own reasons. The headline comes
first. Source revisions, causes and test details follow it.

Tests match on (suite, config, id). Seeds are checked first: with fixed seeds every base (test,
seed) must be in the candidate, else that seed is `missing`; with random seeds on either side the
candidate must run at least as many seeds per test (`--seed-policy auto|exact|count`). Different
seed sets remain inconclusive, even when counts agree. Then the
seeds of a test count as one test that fails if any seed fails.

A candidate result is *inconclusive* when it is a harness `error`, a result rvw wrote itself
(`synthesized`: no result.json from the adapter, build failure), a wall-clock timeout, or a
failure the adapter marked `inconclusive` (RiscvSim: an assertion printed while other simulations
ran that its serial rerun could not attribute to the test, or whose rerun never finished). It goes
to `inconclusive`, never to known or still failing, and is neither cached nor resumed. For each conclusive candidate failure signature:

- in the known-failures file (suite, id, signature, optional config; `*` wildcards allowed) → `known_failures`;
- the base failed the same test and seed with equal inputs and signature (conclusively) → `still_failing` (does not reject);
- otherwise → `new_failures` (rejects), with what the base did (`pass`, `absent`, `failed differently: …`).

Base failures that pass in the candidate with the same inputs and seeds are `fixed`.
Tests or seeds in the base but not the candidate are `missing` and reject
unless `--allow-missing`. For suites with `perf_metrics` (BOOM: benchmark ROI
`cycles`), tests that pass on both sides are compared on the mean over seeds; a loss above the
tolerance rejects. `name` and `name:min` mean lower is better. `name:max` means higher is better,
as in `ipc:max`. `lower` and `higher` are aliases for `min` and `max`. Other directions and
duplicate metric names are config errors. Metric names match `[A-Za-z_][A-Za-z0-9_.-]*`.
The same finite, non-negative `perf_tolerance` applies to each declared metric separately.
A perf test whose base result is inconclusive cannot be compared and makes the verdict
inconclusive. So does a
configured metric that is missing, non-finite or non-positive for any compared seed on either
side. All samples of a metric must record the same origin. Missing origins make old performance
evidence inconclusive. A metric is never silently left out. A declared performance workload needs a passing
baseline and candidate on every seed. An added workload without a baseline, or a failed
workload (including a known or unchanged failure), makes performance evidence inconclusive.
Each C4 performance item reports base, candidate and paired sample counts. Its
`comparison_rule` is `relative_mean`. Its `confidence` is `not_estimated`. The threshold
applies to the relative change in arithmetic means. Equality with the threshold does not reject.
This rule supplies no statistical confidence and does not bound per-seed losses.

Verdict: `reject` if anything rejects; else `inconclusive` if any candidate result is
inconclusive, no test ran on both sides, or either source lacks a clean committed identity;
else `accept`. Stored results need a full `core_rev_full` and `core_dirty: false` on both sides.
C4 `rvw.verdict/2` records `tests: pass|fail|incomplete` separately from `verdict`.
Dirty or missing source identities record `uncommitted_sides`, add cause `candidate_not_committed`
without replacing another cause, and supply the hint
"commit (a scratch branch is fine) and rerun". This also applies to stored base results. An inconclusive verdict blocked by source identity
also records `not_accepted_reason: "uncommitted"`. A rejected comparison stays rejected.

`gate` runs the tier on both sides and compares. The base revision is checked out as a
`git clone --shared` at that commit in `$RVW_SRC_CACHE/<core>/<sha12>` (default `~/.cache/rvw/src`; reused only
while its HEAD is that commit and its tree is clean) and handed to the
adapter through `source_env` (BOOM: `SPINAL_BOOM`). With no `--cand-rev`, a clean core repo
uses its HEAD commit through the same private checkout path as an explicit revision.
A dirty tree still runs in place and can `reject`, but cannot `accept`.
`--base-rev WORKTREE` follows the same rule. Conclusive jobs with complete RTL identity can use the cache. Other failed jobs run again.
For a complete RTL identity with a clean committed harness and native tool digest, the core
commit and dirty flag are report metadata. The cache uses generated RTL, harness, tools,
ELF bytes, environment and options. Committing unchanged RTL reuses conclusive jobs, including unchanged failures.
Reuse preserves their failure status and signature. Use `--no-cache` for fresh simulations.
Identity still elaborates the core to establish the RTL hash. It does not start a simulation.
Without that complete RTL identity, source-based cache rules still apply.
Reused C1 results record the original source in `reused_from_source`; their `source` and C3
source fields name the current selection. Every claimed model value must still match.
The verdict goes to `<candidate run>/verdict.json`.

## Core config reference

```toml
[core]
name = "mycore"
adapter = "../path/run.sh"       # or a list; ${VAR:-default} allowed
configs = ["small", "large"]
default_config = "small"
lock = "mycore"                  # optional heavy-job lock name
source_repo = "../core"          # git repo of the core (for --rev and gate)
source_env = "MYCORE_SRC"        # env var the adapter reads the source tree from
input_complete = true             # user claim: all runtime inputs below are declared
input_env = ["HOME", "JAVA_HOME", "SPINAL_VERILATOR_FLAGS"]
input_tools = ["bash", "java", "verilator"]
input_commands = ["cat", "dirname"] # recorded commands without a --version interface
identity_capture = false          # true requires rvw.adapter-capture/2 and equal C1 claims
cache_paths = ["../adapter"]     # sources whose changes invalidate cached results
identity = false                 # true: `<adapter> identity` joins the cache key (C1, optional)
wall_timeout = false             # true: manifests carry wall_timeout = timeout_s (C1, optional)
known_failures = "mycore.known.toml"
jobs = 4                         # run-many --jobs
persistent = false               # opt-in serial server; skips the separate pre-build

build_first = true               # call `build` before `run-many`
build_timeout_s = 3600
startup_s = 120                  # adapter start-up allowance per batch
perf_tolerance = 0.01

[suites.NAME]
kind = "elf-dir"                 # or "build"
dir = "tests"  glob = "**/*.elf"  strip_suffix = ".elf"
include = ['^rv64ui-']  exclude = ['\.dump$']
configs = ["small"]  seeds = 1
max_cycles = 200000  mem_latency = 20   # absent mem_latency = randomized timing
timeout_s = 600                  # wall clock per test
options = {}                     # extra run-many manifest keys
cycles_key = "cycles"  instret_key = "instret"   # dotted paths into result.json, | for fallbacks
perf_metrics = ["cycles"]

[tiers.quick]
runs = [{ suite = "NAME", configs = ["small"], include = ['-p-'], seeds = 1 }]
```

Seed counts (`seeds` in a suite or tier row, `--seeds`, MCP `seeds`) are whole numbers of at least
1; anything else is a config error (exit 2). A tier lists each suite/config once: two rows that
select the same suite and config (or `--suite isa,isa`) are an error, because both would write
`DIR/<suite>/<config>`. Merge their `include` patterns into one row.

`--core NAME` looks for `NAME.toml` in `$RVW_CORES` (`:`-separated), then `rvw/configs/`.
`--core path.toml` loads a file. `$RVW_CORE` sets the default.

## BOOM

The shipped config uses the generated Verilog hash (`rtl_sha256`), the RiscvSim source
revision and dirty flag, the native build tool identity, the ELF bytes and run options.
The adapter elaborates the selected source checkout and hashes the Verilog used by the model.
Regress checks the adapter's C1 claims and retains the RTL hash in C3. Missing evidence stays
inconclusive. See `RiscvSim/README.md` for build settings and current verification limits.

`boom.toml` uses the Scala specs of spinal-boom at `0cb0b69`, but retains the known
`rv64mi-p-instret_overflow` failure so gates can compare its signature:

| Suite | Tests | Config | Settings |
|---|---|---|---|
| riscv-tests | rv64{ui,um,ua,uf,ud,uc,mi,si,uzba,uzbb,uzbs}-{p,v}-*, minus `ma_data` (p, v) | small | 200k cycles |
| act4 | `ref/act4/work/boom-rv64gc/elfs/**/*.elf` (620) | small | 5M cycles |
| vm-tests | `spinal-boom/tests/vm/build/*` | small | 200k cycles |
| benchmarks | `examples/boom/out/arch/bench/*.riscv` (9, built by `rvw arch build`) | large | fixed latency 20, 50M cycles, perf on ROI cycles |
| stress | the benchmarks with randomized memory timing | large | 4 seeds |
| elaboration | `build` of each preset | all five | 2 h each |

Tiers: `quick` = riscv-tests p environment + VM tests on small. `full` = everything (riscv-tests on
small and large).

## Tests

```sh
RVW_LOCK_PYTHON="$PWD/.venv/bin/python" nice -n 10 .venv/bin/python -m pytest rvw/tests/test_regress*.py -q --basetemp=/tmp/pytest-simid-regress-tests-local
```

`tests/fake_adapter.py` implements C1 with text program directives. The regress tests cover
source selection, raw source bytes and index state, `/2` adapter identities, C1 claims,
resume and cache, declared stimulus changes, stored-plan coverage, immutable generations,
pooled model identity, failure classification, performance origins, output ownership and
cancellation. These fixtures do not validate BOOM hardware behavior.

## Decisions

- Gate accepts require clean committed source identities on both sides. Explicit revisions and
  clean default candidates use private Git checkouts. Raw tracked bytes, executable bits and
  index state must agree with the commit. `git status` alone is not enough. Private excludes
  cannot hide source files. A changed cached checkout stays in place; selection uses another slot.
- C8 assumes stable, honest inputs during a run. Record inputs once and run source and tools
  in place. Preserve copied ELF bytes for execution and replay. No source mirror, classpath
  capture or logical path projection is required. Declarations remain a user completeness claim.
- Adapter identity is per config and model options. `/2` documents must describe the selected
  source and supply non-empty C1 claims. Each C1 must contain equal claim values. A missing
  field cannot satisfy a null claim. Keep `rtl_sha256` and `adapter_identity` in C3 test entries.
- Job identity version 10 binds source or complete RTL identity, adapter and tool identities, declared environment,
  selected ELF bytes and names, options, build arguments and stimulus identities. Old keys
  miss the cache. Dirty core sources need complete RTL identity for passing-result caching.
  Dirty harness sources always disable result caching.
- Stored results must cover the requested suite, config, filter, seeds, options, build
  arguments, stimulus bytes and performance declarations. Equal old folders cannot satisfy
  a changed request. A larger stored plan may cover a smaller requested plan.
- A comparison side has one source identity. Each suite/config also has one RTL and adapter
  identity, including consistent presence of those fields. Disjoint seed shards cannot pool
  different designs. Base and candidate may use different designs. Duplicate test/seed entries
  are errors. Several incomplete C3 files cannot be pooled into a verdict.
- Published results and cache entries use immutable generations. Readers pin one generation.
  Resume validates job parameters, C1 provenance, requested options and claims. Only conclusive
  results with complete RTL identity, or passes with source identity, enter the cache.
  Missing evidence never earns a pass, fix, known failure or accept.
- Output locks and durable writer records prevent reuse while an old writer can still publish.
  Unresolved writer records block reuse. Adapters must keep writers in their process group.
  Resource locks cover build and execution. Cancellation stops the adapter process tree.
- Seeds are fixed by default. Random seeds are retained on resume. Missing tests or seeds reject
  unless the caller allows missing results. Equal deterministic failures with equal inputs and
  signatures are `still_failing`. Wall-clock timeouts and build failures are inconclusive.
- Performance comparisons retain metric origins and all declared metrics. Missing, non-finite,
  non-positive or inconsistent samples are inconclusive. Apply tolerance before display rounding.
- Failure signatures preserve Scala or HDL source locations. Without a location, hash the full
  message. Old assertion evidence without a message or complete location needs a rerun.
- Known-failure files accept only supported fields and types. Imports retain config scope,
  check the requested core and skip inconclusive failures. Source and gate selectors are
  exclusive. Empty plans, invalid seeds and duplicate suite/config selections are errors.
- `--fresh` accepts only a run set or an empty directory. It preserves published generations.
  JUnit escapes invalid XML characters. Benchmark cycles use the configured ROI counter when
  present, then the configured fallback. Build suites use the adapter's `build` command.

## Limitations

- Input declarations remain a user completeness claim. This is not a sandbox. Computed paths,
  interpreter libraries and tool data need declarations or the recorded stable-tool identity.
  The shipped BOOM config declares its inputs and requires a `/2` adapter identity. Missing
  inputs return inconclusive. Normal completion and cancellation remove private ELF capture
  directories. SIGKILL or machine failure can leave these directories behind.
- One adapter process per (suite, config) batch; suites run one after another.
- The wall-clock budget is per batch; a slow but not hung test can push a large batch over it,
  after which the remaining tests run singly (slower, still correct).
- Perf comparison uses means over seeds and does not model noise; use fixed memory latency for
  perf suites (BOOM's benchmarks do).

## MCP tools

`rvw mcp` discovers `regress_list`, `regress_run`, `regress_compare`, `regress_gate`,
`regress_history`, and `regress_known_list`, `regress_known_add`, `regress_known_remove`.
Start with list/history. Edit, commit (a scratch branch is fine), then use gate with
`base_rev` and `cand_rev` for the accept/reject decision.
Arguments match CLI options with underscores (`dry_run`, `base_rev`, `perf_tolerance`);
`from_` names `known add --from`. Core defaults to `RVW_CORE`.

Run and gate return a job ID. Use `job_status(wait_s=60)` for the final CLI JSON, `job_log`
for progress and `job_cancel` to stop the adapter process tree and release its resource lock.
The runner still owns locking, cache/resume, provenance and verdict generation. Compare writes
`verdict.json`; known add/remove update TOML. List/history/known list are read-only.

## Limit ownership

Waivers/signatures: [#2](https://github.com/riscPrint/risc-v-workstation/issues/2). Stored-folder and performance gates: [#4](https://github.com/riscPrint/risc-v-workstation/issues/4). Full-tier timing: [#73](https://github.com/riscPrint/risc-v-workstation/issues/73).

Retained limit: Committed revisions and complete captured inputs remain necessary for acceptance. Watchdog expiry and unqualified identity cannot earn a pass.

## Review status and close rules

Waivers and failure signatures remain experimental (#2). The review covers changed RVFI
messages, stale saved fail codes and status changes. Compare derives RVFI identity from the
full saved message. Without a monitor code or message, old RVFI evidence needs a rerun.
A saved fail code overrides its saved signature. Unchanged failures must also have the same status.

The close rule requires negative tests for changed failures, legacy evidence and waiver scope.
It also requires a policy for wildcard waivers, config-wide waivers and coarse identities
(cycle timeout, fail code, monitor code or source line). These identities can group different
root causes. A wildcard can deliberately cover a changed failure. This review does not prove
that such a waiver is safe. Check each waiver and its full failure evidence before use.

Stored-folder gates and performance metrics remain experimental (#4). Keep these reviews separate:

- Stored identity: negative tests must cover wrong core, mixed source or model, changed ELF,
  options, metric selectors, stimulus bytes, missing seeds and missing required workloads.
  Existing plan tests include quick folders requested as full, even with `allow_missing`.
  This round reruns those fixtures. It does not establish native historical-folder compatibility.
- Performance: use the same workload, seeds, options and measurement origins on both sides.
  Declare ROI counters through `cycles_key` and `instret_key`. A selector name alone does not
  define semantic ROI boundaries. The adapter must keep those boundaries stable and identify
  changes in its inputs. The tests use repeated fixed-seed fixtures, not native noise experiments.
  A mean can cancel a slow seed with a fast seed. Sample counts are visible, but confidence is
  not estimated. The close rule requires native repeated-seed experiments, stable ROI boundaries
  and a reviewed statistical acceptance rule. Do not treat this increment as that evidence.

A quick gate covers only its requested tier. It must not substitute for required performance
workloads in a full tier. Request that tier explicitly. A stored gate checks the requested plan;
standalone `compare` does not load the current project plan.

## Native shared cache

Set `RVW_REMOTE_CACHE=HOST:/absolute/cache/path` to use a shared cache over SSH.
The selected host needs SSH and rsync. Use a trusted SSH host entry and login key.
`RVW_CACHE_SSH_OPTIONS` can hold a JSON array of SSH options, for example a port
and a private known-hosts file. Paths currently use plain path characters.

The runner still computes the full C8 version-10 key. There is no prefix or
partial-identity lookup. Transfer cannot make an incomplete identity cacheable.
An imported generation must match its inventory hashes and stored full key.
A missing, partial, invalid or evicted remote entry is a miss. Upload sends the
immutable generation before the atomic pointer update. Transfer failure does not
change a measured result. `--no-cache` disables local and remote cache use.

Downloads keep private staging under `cache/.downloads/`, keyed by remote location
and full cache key. A file lock serializes commands for that staging directory.
Interrupted bytes survive the command. A later rsync checks file checksums and
repairs partial or corrupt files. Inventory and full-key checks run again before
local publication. A successful import removes its staging directory. Partial
bytes never earn reused success. Owners can remove abandoned staging directories
between commands.

Uploads include `.rvw-owner.json` and `owners/<generation-id>.json` with the publishing host, user, full key,
generation ID and upload time. This record is metadata, not evidence. To apply
retention, stop transfers and run this on the cache host:

```sh
python -m rvw.regress.remote_cache --root /absolute/cache/path --max-bytes 10737418240 --max-age-s 2592000
```

The policy removes invalid managed entries first, then entries older than the
age limit, then oldest publications until the byte limit is met. It reports each
removed key and reason. It checks generation integrity and exact stored keys.
It removes whole entries, including obsolete generations. It leaves unmarked
folders in place. This is explicit maintenance, not a background service. An
evicted entry is a miss. Retention uses publication age, not access time.

For gate budgets and cost reports, see [common](../common/README.md#native-job-budgets).

## Native backend capabilities

`rvw regress backends --json` lists the supported native semantic profiles.
See [native simulation](../sim/README.md). Requirements are explicit feature
names. Unsupported requirements must fail before compilation.

## Cocotb components

`rvw regress cocotb manifest.json --out NEW_DIRECTORY --seed 1 --json` runs a
native component suite on Icarus or Verilator. It writes standalone C3 results.
See [manifest, clock/reset, result and artifact contracts](../sim/README.md).
It is separate from ELF suite scheduling and cannot earn C4 gate acceptance.

## Directed Sv39 programs

`rvw regress mmu build DESCRIPTION --out EMPTY_DIR --json` builds RV64 ELFs
from `rvw.mmu/1` JSON. Set `--gcc` to the native cross compiler if needed.
`rvw regress mmu reference DIR --timeout 10 --json` runs each ELF on Spike
before RTL use. Each program checks one declared load or store. It checks the
value, or `mcause`, `mtval` and `mepc` for a page fault. Failure writes 3 to
`tohost`. Success writes 1. A timeout is inconclusive.

The description contains `schema` and a nonempty `scenarios` list. Each scenario
has `id`, `level` (0, 1 or 2), PTE `flags` (`VRWXUGAD`), `access` (`load` or
`store`), `expect` (`success` or `page-fault`) and a nonempty `bins` list.
Optional fields are `va`, `pa`, `privilege` (`S` or `U`), `sum`, `mxr`,
`ad_expect` (A/D mask), `asid` and `fence` (`all`, `va`, `asid`, `va-asid`).
Unknown fields are errors. Expectations are explicit requirements. The generator
does not use a DUT result to set them.

Programs require RV64IM, Zicsr, Zifencei, S/U, Sv39 and PMP entry 0. They use
MPRV for S/U data accesses. Fetch stays in M-mode. The linker reserves text at
0x80000000, `tohost` at 0x80008000, tables at 0x80010000 and data at 0x80200000.
This first increment uses a fixed RAM layout. Other S-mode platforms must map
this RAM layout. It does not yet support RV32/Sv32 or arbitrary device layouts.

The build writes source, ELFs and `manifest.json`. The manifest binds the
input and ELF hashes. Reference results contain per-scenario bins. A bin earns
`pass` only when its whole self-check program completes on that model. Generated
bins alone are not coverage. These bins measure architectural effects only.
They do not measure page-walk bus traffic, physical address signals, TLB contents,
A/D atomicity or device effects. Use the pinned [Supervisor ISA 1.13,
20260120](https://docs.riscv.org/reference/isa/v20260120/priv/supervisor.html),
sections 11.1.1.1.2, 11.1.1.11 and the Sv39 translation algorithm.

Use any C1 project's `elf-dir` suite with `glob = "*.elf"` and
`strip_suffix = ".elf"`. Set its `dir` to the generated directory. Keep this
suite outside default tiers until it has reference and RTL results. The BOOM
example declares `mmu-priv`. It keeps all failures visible, including the known
ACT4 Sv39 exception failures. It applies no waiver.

Set `remap = true` on a successful level-0 load to prime a translation, replace
its leaf PPN, execute the selected fence and check the new page's distinct value.
The fixture uses ASID 7 for ASID scope tests. Global mappings require an
all-ASID fence. Over-invalidation is legal. This does not prove that unrelated
entries stay cached. ASID switching, cross-hart shootdowns and software races
remain unchecked. The test makes no claim about an unfenced stale translation.

Set `ad_mode = "svade"` to require faults for clear A/D bits. The Spike
reference enables Svade explicitly. `ad_expect` reads the physical leaf PTE
after the access or trap and checks both bits. The BOOM scenario file selects
Svade for these cases. `hardware-ad.json` is a separate opt-in Svadu campaign.
It sets `menvcfg.ADUE` and selects Svadu on Spike. Build it in another empty
directory. Run it on RTL only when the project declares Svadu support. These
checks verify final PTE bits. They do not prove atomic updates, concurrent
software changes or faults during page-table accesses.

`build --pma PLATFORM.json` records a core-owned `rvw.mmu-pma/1` declaration.
It contains `schema` and `regions`. Each region requires `name`, `start`, `size`,
`widths` (bytes), and boolean `read`, `write`, `execute`, `idempotent`,
`cacheable` and `atomic` attributes. Ranges use an inclusive start and an
exclusive end. Overlaps are errors. Resolve conflicts in project data first.
The manifest binds the declaration hash. This is platform input validation,
not a device model or PMA test. Spike's RAM backend does not check these
attributes. No PMA coverage bin earns a pass from this declaration. Boundary
accesses, attribute conflicts and independent device observations remain open.

The privilege cases cover SUM off/on, MXR off/on, effective U-mode permissions,
MPRV off/on and `satp` Bare/Sv39. Set `mprv = false` to test physical M-mode
access. Set `satp_mode = "bare"` to test address-translation bypass. These
programs do not enter S-mode for instruction fetch. TVM, TW, TSR, SRET, disabled
features and unsupported WARL mode writes still need separate campaigns.

After a traced RTL suite run, use the independent checker:

```sh
rvw regress mmu check ELF_DIR --results RUN_DIR --platform PROJECT/cosim.json --model spike --json
rvw regress mmu check ELF_DIR --results RUN_DIR --platform PROJECT/cosim.json --model sail --json
```

It finds C1 `result.json` files by ELF hash. Each scenario needs exactly one
conclusive C1 result. A pass also requires a complete C2 trace, a passing end
event and an independent model match with `--strict` (zero synchronizations).
Missing traces, prefix matches and unavailable models remain inconclusive.
A conclusive RTL failure or architectural mismatch fails the scenario. Each
scenario's bins carry that same status. Run separate directories for seeds or
configs. Match the model platform, including Svade/Svadu, to the selected suite.
Sail uses the existing `rvw cosim` platform configuration and `--sail` option.
The checker preserves the full comparison result and its captured input identity.
It checks architectural effects; page-walk transactions need a separate observer.

### Privilege controls and observation reports

Control scenarios use a separate row shape in `rvw.mmu/1`: `id`, `control`
(`tvm`, `tw`, `tsr`), boolean `enabled`, `instruction`, `privilege` (`S`, `U`),
and `bins`. TVM selects `satp-read`, `satp-write` or `sfence`. TW selects `wfi`.
TSR selects `sret`. These programs use Bare mode and MRET to enter S/U mode.
They check illegal-instruction cause 2 and the exact fault PC. Allowed S-mode
operations exit through a checked cause-9 ECALL. Successful SRET must branch
to its declared return PC. U-mode checks keep supervisor instructions illegal
when the machine control is clear. TW-clear WFI is refused because it needs
an interrupt wakeup schedule. These rules use the pinned Machine ISA 1.13
(20260120), Machine Status register, TVM, TW and TSR sections.

Data scenarios also accept `offset` (0..4088), `value` (expected load value),
`walk_deny`, `unfenced` and `switch_asid` (booleans). Expectations also accept
`access-fault` and `misaligned`. Faults check exact cause, address and PC.
`walk_deny` uses three PMP TOR entries to deny S-mode reads of the table pages.
It checks an access fault, not a page fault. `unfenced` and `switch_asid` require
`remap`. The unfenced read permits either old or new data before the required
fence. The ASID case switches to a second ASID, then reuses the first ASID.
It fences each switch and requires the new data. This does not test ASID width
or require unrelated entries to stay cached. Software changes are sequential.

On BOOM, `--rvfi-trace` also writes `mmu-observations.jsonl`. C1 names it under
`details.mmu_observations`. Its header has schema `rvw.mmu-observations/1` and
an `identity` object from the C2 header. Event rows carry `cycle` and `kind`:
`walk_request` has physical `address` and memory `command`; `walk_response`
has `address` and `data`; `bus_a` has physical `address`, TileLink `opcode`
and `size_log2`. Addresses and data use hexadecimal strings. These are sampled
PTW/cache and accepted external A-channel events. Requests may be killed or
retried. Responses do not establish an atomic update. Cached device accesses
and device state need separate checks. Bus events alone cannot identify walks.

`rvw regress mmu report ELF_DIR --results RUN_DIR --checked CHECK.json --json`
writes `rvw.mmu-coverage/1`. The optional check file must come from `mmu check`.
The report binds its manifest and C1 hashes. It lists every scenario and every
unique bin in the declared denominator. Only strict oracle checks can pass
architectural bins. Without a bound check, bins remain inconclusive. Observation
files have separate paths, hashes and event counts. `recorded` means capture
exists. It gives no walk or device correctness verdict. The report lists the
remaining protocol, PMA, atomicity and multi-hart obligations explicitly.

For `unfenced` scenarios, a strict oracle mismatch is retained and the checker
returns inconclusive. Two models can select different permitted translations.
No mismatch in that scenario earns coverage. The C1 self-check still fails
wrong values and a wrong result after the required fence. Other scenarios keep
the normal strict mismatch failure rule. Raw `c1_status` remains in check rows.

For a Spike-to-Sail reference cross-check, use a separate platform file with
`illegal_insn_tval: "insn"`. Spike-generated traces contain the instruction bits
for illegal-instruction traps. BOOM's `"zero"` setting describes BOOM and makes
Sail expect zero. It is not the platform setting for those Spike traces. Keep
this reference-only file separate from the DUT platform. Do not waive the
strict comparison or change the DUT contract to make two oracles agree.
An unfenced translation can still differ under the correct reference platform.
Keep that comparison inconclusive and retain both values.

Scenario `access_width` selects 1, 2, 4 or 8 bytes (default 8). Loads use
`lb`, `lh`, `lw` or `ld`. Stores use the matching width. Optional
`register_width` declares 8, 16, 32 or 64 bits. Generation refuses an
access wider than that declaration. The project owns the declaration.
The BOOM MSIP scenario uses 4 bytes for its declared 32-bit register.
Remap scenarios require the default 8-byte access.

## Accellera UVM components

`rvw regress uvm --out NEW_DIRECTORY --seed 1 --seeds 3 --json` runs a
bounded native SystemVerilog UVM suite. Use the machine lock for compilation.
See [the UVM suite](../../../../Uvm/README.md) for dependencies, checksum and
licence checks, supported test scope and limits. It writes standalone C3.
It does not schedule ELF suites or earn C4 acceptance.

`rvw regress uvm-ral` generates UVM register models from `rvw.soc/1`.
`rvw regress uvm-cpu` checks completed C1 captures through a UVM analysis
subscriber and the native Spike DPI bridge. See [the UVM guide](../../../../../Uvm/README.md)
for the strict profile and the offline replay boundary.
