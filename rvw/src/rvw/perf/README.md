# rvw perf

Text and JSON measurements from any tab-separated Kanata 0004 log, including gzip.
No viewer, simulator, third-party Python package, or BOOM checkout is required.

```sh
cd rvw
uv run rvw perf pipeline.log --json
uv run rvw perf pipeline.log --isa riscv --queue-stage Iq --issue-stage Is \
  --head-stage Iq --in-order-retirement --window 1000
uv run rvw perf compare before.log after.log --json --tolerance 0.05
uv run rvw perf compare before-report.json after-report.json
uv run --extra dev pytest tests/test_perf.py -q
```

All measurements are available in `rvw.perf/1` JSON: stage per-visit distributions
(count, sum, mean, nearest-rank p50/p95, max), separate retired/discarded/open
populations, per-PC and per-class residence, admission-to-first-issue time,
completed instruction lifetime cycles by PC, discarded work, fixed time-window
IPC, and zero-retirement cycles with longest intervals and inferred head states.
The concise text report selects the largest lifetime PCs and inferred head states.
`summary.instret` counts R type 0 records; `summary.ipc` is **event IPC**. Their
architectural meaning depends on the producer. For example BOOM's existing probe
reports physical ROB commits, including predicated-off operations, whereas C1
instret counts architectural retirements. Counter mismatches emit an explicit
warning and are never corrected by guessing which instructions were predicated.

Stage names, lane, admission and issue names are configuration, never BOOM
assumptions. `--isa riscv` enables a separate disassembly classifier. Otherwise,
classes come only from an explicit `class=NAME` label; unknown means unknown.
PCs are recognized from hexadecimal label prefixes with an optional `0x` and
colon. Labels in another format retain all pipeline measurements, with PC unknown.
The optional classifier recognizes common objdump mnemonics and aliases, including
compressed loads/stores; it does not decode raw words or infer dependencies.

If `result.json` is adjacent to the log, or provided with `--result`, counters are
cross-checked. The report shows cycle, retirement and IPC deltas, run status and
whether C1's artifact names this log. An exact match is claimed only for exact
integer agreement. A matching numerical value does not establish equal scopes.
The C1 result must pass the shared conclusiveness check. Inconclusive results
are refused, including input changes, harness errors, synthesized results,
wall-clock timeouts and unresolved concurrent-run attribution. Conclusive failing
runs can still be measured. CLI and MCP use the same check.

## Decisions

- Capture logs, saved reports and C1 files before parsing. Capture both comparison
  inputs before either analysis. Decode gzip from the copy. Report its path and hash.
- Resolve the declared Konata artifact once, relative to the C1 lookup directory.
  This also applies when C1 is a symlink. `artifact_matches` is null with no
  declaration, false for a different or missing file, and true for the selected path.
  Broken links and access errors refuse. A path match does not prove historical
  execution identity if a producer overwrote the log without a trace-hash binding.
- Missing automatic C1 permits trace-only analysis. Missing explicit C1 and failed
  captures are inconclusive. Refuse inconclusive C1 before counter checks.
  Numerical equality does not establish equal execution or measurement scope.
- Reports include the command capture and `cache_key=null`. Remove private copies
  after calculation. Treat C1 provenance and saved report claims as producer data.
  Perf does not recapture producer ELFs, models, source revisions or toolchains.
- Classify only known mnemonics or explicit class labels. Unknown stays unknown.
  FP memory operations count as loads/stores; FP arithmetic and moves count as FP.
  Append type 0 labels; join type 1 and 2 labels with newlines.
- Observe `[first cursor, last cursor + 1)`. R type 0 counts retirement events.
  Quiet tails count only if the producer advances the cursor.
- Stage visits use half-open intervals. S closes the previous stage in that lane;
  E closes a stage and R closes all lanes. Replays add visits without resetting
  first-admission-to-first-issue latency. Open intervals at EOF are censored.
  Completed intervals on open instructions remain in the open population.
- Discarded lifetimes overlap. Their sum is instruction-cycles, not lost wall time
  or branch penalty. R type 1 does not identify a discard cause.
- Head analysis requires an admission stage and an assertion of in-order creation
  and retirement per thread. It infers the oldest live admitted instruction.
  It does not observe a hardware ROB head or identify which thread blocked shared
  retirement. Report head-state cycles only during global zero-retirement intervals.
- Compare identical settings. Tolerance must be finite and nonnegative. A significant difference exceeds relative tolerance
  and the absolute threshold: one cycle/count or 0.01 IPC/flush fraction.
  This is a practical threshold, not statistical confidence from one run.
- Warn on unknown extension records. Refuse malformed known records, duplicate IDs,
  backwards time and events after R. Do not infer dependencies or causal stalls.
- Store instructions and visits. Sweep bubble boundaries without expanding each
  cycle. Bound output to one million IPC windows and 20 longest head intervals.

Format reference: [upstream Kanata 0004 documentation](https://github.com/shioyadan/Konata/blob/master/docs/kanata-log-format.md).

## MCP tools

`rvw mcp` exposes read-only `perf_report` and `perf_compare`. Report takes `path` (Kanata log,
gzip log, or saved `rvw.perf/1` JSON), analysis options such as `window`, `isa`, `lane`,
`queue_stage`, `issue_stage`, `head_stage`, `in_order_retirement`, and optional C1 `result`.
Compare takes `base`, `candidate`, the same analysis options and `tolerance`.

Both return jobs so large traces can be cancelled without blocking the server. Follow with
`job_status(wait_s=60)` for the same JSON as the CLI, or use `job_log`/`job_cancel`.
The shared calculation preserves settings checks, counter warnings and inferred-state limits.

## Limit ownership

Additional probe events: [#49](https://github.com/riscPrint/risc-v-workstation/issues/49).

Retained limit: Inferred pipeline states, counter warnings and settings checks remain part of the report. A trace report is not independent execution proof.

## Explicit causes and commit kinds

Perf reads the optional `#rvw` version 1 comment extension. See
[the contract](../../../../docs/PLATFORM_CONTRACTS.md#pipeline-cause-event-extension).
JSON adds `stall_causes`, `replays` and `commit_kinds`. Text shows each cause's
scope and evidence kind. Existing saved reports without these fields still render.

A stall sample covers one cycle. Repeated samples with the same scope, cause and
evidence in that cycle count once. `by_cause` keeps measured and inferred counts
separate. `measured_cycles` is the union across scopes. `overlaps` lists exact
sets of simultaneous measured causes. Cause counts are not additive. Each cause
also reports its overlap with global zero R-retirement cycles. A blocked unit
can coexist with retirement elsewhere. This overlap does not establish a global
retirement cause or an additive CPI breakdown.

`unknown_zero_retirement_cycles` counts zero R-retirement cycles with no measured
cause. Inferred causes do not reduce this count. Idle, warmup and uninstrumented
cycles remain unknown. `unknown_intervals` counts these intervals;
`longest_unknown` lists at most 20 half-open intervals. No per-cycle expansion is
needed for a quiet tail. Inferred head states remain separate from measured causes.
A repeated stage visit or a dependency edge never supplies a cause by itself.

`commit_kinds` counts only explicit commit annotations as observed physical,
architectural or predicated-off commits. Unannotated R type 0 events remain
`unknown`. `architectural_total` is null when any commit kind is unknown.
`summary.instret`, IPC windows and C1 cross-checks still use all R type 0 events.
The report never silently changes their meaning. `replays` counts explicit
replay events by cause and evidence; it does not turn replay counts into lost cycles.

Predictor direction/target/return outcomes, recovery latency, predictor aliasing
and context analysis are not implemented by this extension. A flush alone does
not establish a prediction outcome. BOOM still needs core-owned probe signals.

## Observed predictor outcomes

`#rvw` prediction records add direction, target and return outcomes, observed
recovery cycles and wrong-path admission counts. See the
[wire contract](../../../../docs/PLATFORM_CONTRACTS.md#observed-prediction-outcome-extension).
The `predictions` report groups observations by predictor, kind, warmup,
alias and context. Each cost gives observed samples, unknown samples, sum and
maximum. Unknown is not zero. Overlapping groups must not be summed as global
cost. Flags and contexts describe observations; they do not prove causal effects.

`PredictionOutcome` in SpinalKonata emits this record. Use `PipelineTags.event`
to bind a project's observed signals. Complete recovery/work counts can arrive
at recovery completion, before the resolving instruction's terminal R. Leave
unavailable fields unknown. BOOM stall/commit probe wiring remains core-owned:
[riscPrint/spinal-boom #12](https://github.com/riscPrint/spinal-boom/issues/12) and
[#13](https://github.com/riscPrint/spinal-boom/issues/13). BOOM predictor event
bindings and DUT validation remain open under #49. No predictor measurements
are claimed from legacy logs.
