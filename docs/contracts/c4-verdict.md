# C4. Verdict (`rvw regress compare`)

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

## Filtered gate scope

The C4 `gate` block records `filter`: the list of `--filter` regular
expressions, or null when no command filter was given. It also records
`selected_tests` and `total_tests`. These count test/config cells within the
tier before seed expansion. The total keeps the tier and suite exclusions.
A non-null filter makes this a subset gate. Its result carries
`scope: filtered`. An `accept` covers only the selected tests.
A consumer that needs tier acceptance must treat a subset `accept` as
`inconclusive` with cause `filtered_gate`. Plan checks and native farm gate
intake enforce this rule. Unfiltered gates keep their verdict behavior.
