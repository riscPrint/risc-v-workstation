# Sampled RTL flow

## Study, request and report

`rvw.sample-study/1` selects ELF, Spike platform, captured shim, architectural
mapping, instruction budget and project adapter argv. Paths are relative to the
study. The adapter receives an absolute `rvw.sample-request/1` JSON path.
The request contains `elf`, `checkpoint`, `mapping`, `warmup`, `instructions`,
and `out`. `timeout` sets the adapter wall-time budget in seconds. `from_reset` selects reset execution when the checkpoint is at
instruction zero. This is required for the full-run reference. Checkpoints reuse `rvw.arch-injection/1`. Adapters must transfer the
state before executing the suffix. They write `out/rvfi.jsonl` using C2.
The trace starts at the first post-checkpoint retirement. Its end status must be
pass and its length must be exactly warmup plus measured instructions.

`rvw.sample-report/1` contains the clustering points, weights, measured cycles,
CPI, IPC and equality status per point. Scalar register and memory effects are
compared with normalized Spike effects. Memory data is compared only in the
accessed byte lanes, using the shared cosim mask helper. Traps and incomplete traces exclude a
point. Failed weight prevents a whole-workload estimate. `conditional_ipc`
refers only to surviving weight. It is not a substitute for `weighted_ipc`.
The latter is 1 / sum(weight * CPI) only with all points matched.
Timing is N-1 retirement gaps per N measured instructions.
Resume binds study and input hashes. Evidence is rechecked before reuse.
Reports have no confidence bound until a native validation study supplies one.

## Full-run validation

`rvw.sample-validation/1` records full RTL IPC, sampled IPC, interval size,
maximum cluster count, selected point count and signed relative IPC error.
It retains inconclusive settings. `max_observed_error_percent` covers only
successful settings and is null when none succeed. The whole study is
inconclusive if any setting fails. An observed maximum is not a statistical
confidence interval. The full reference uses reset execution.

## Fixed-interval warm-up

`rvw.sample-warmup/1` holds a fixed `start` and `length`, a full-prefix
reference and one row per warm-up length. Each row records capture order,
CPI, IPC, signed CPI bias, absolute bias and target comparison. Failed rows
are excluded explicitly. `smallest_observed_within_target` is an observation,
not a universal recommendation. Detailed execution is the fallback when the
core has no qualified functional cache/predictor injection port.

## Empirical confidence statement

Optional `validation_report` attaches the observed error from a completed
validation study with matching platform, mapping, adapter files, warm-up and
sampling settings. The report identifies the calibration ELF. The statement
is explicitly limited to the calibration prefix and is not a statistical
confidence interval or a guaranteed bound for another program. The report
hash is bound to the resume identity. RTL revision/configuration identity
remains the project adapter's responsibility and requires revalidation.

`program_complete` records a successful `tohost` completion during profiling.
`profiled_instructions` gives the actual profiling count. Without completion,
`scope` is `profiled prefix`; a prefix estimate is not a whole-program result.
