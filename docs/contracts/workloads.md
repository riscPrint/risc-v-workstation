# Workloads contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

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
Each build row can include `build_log`, the path to compiler stdout and stderr.
Failed rows retain that log and `build_error` when the caller selects keep-going.
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
