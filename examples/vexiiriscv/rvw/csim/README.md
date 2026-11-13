# Cached VexiiRiscv component studies

`caches.json` describes the 4 KiB L1 caches. `predictors.json` describes the
upstream stack selected by `rv32im_cached`: a 4 KiB GShare table with 2-bit
counters and 12 history bits, a 512-set BTB with a 16-bit hash, and a
four-entry RAS. These values come from the pinned core's `Param.scala`.

The model is approximate. RTL reverses PC hash bits, uses speculative
history, trains carried counter values with bypass, and initializes RAM
with seed 42. The model has a standard GShare hash and trains in trace
order. Its BTB and RAS do not reproduce all upstream recovery behavior.

## Native predictor comparison

On 2026-11-13, the cached `branches` run completed 35,661 C2 instructions
in 108,567 cycles. The probe explicitly covers conditional branches,
calls and returns. All 9,001 events aligned with C2: 6,001 conditional
branches, 1,500 calls and 1,500 returns. Direct non-link jumps and ordinary
indirect jumps are outside this measurement. A full learn-port experiment
had one event beyond C2, which the converter refused. No tail is dropped.

Conditional direction agreement is 93.1845 percent. RTL has 844 misses;
the model has 1,065. Target availability and wrong addresses are reported
separately. Among 7,189 events where both sides used a target, addresses
agree in every case. RTL has 461 not-predicted taken events. The model has
606 not-predicted events and five BTB misses. Neither side has a wrong
used target in this run. The RTL probe does not capture an explicit BTB-hit
bit, so its not-predicted category does not identify the cause.

The return site executes 1,500 times. RTL has one missing prediction;
the model has none. The call site executes 1,500 times. Each side has
one missing prediction. These selected cases do not establish RAS or BTB
fidelity. Target scoring excludes unused targets on not-taken branches.
The older target-only correctness metric is superseded by the availability
categories in the current component report.

`ProbeTapPlugin` carries `ALIGNED_JUMPED` and `ALIGNED_JUMPED_PC` to the
learn port. It does not infer direction from `wasWrong`, which also
includes target errors. The cacheless path retains its conditional-only
sequential-prediction mapping. Probe-disabled elaboration adds no context.

See [the comparison](predictor-measured.json) and
[input hashes and event scope](predictor-inputs.json).

```sh
rvw probes convert RUN/probe-events.jsonl --to bp-events \
  --c2 RUN/rvfi.jsonl --out branches.jsonl
rvw csim compare-rtl examples/vexiiriscv/rvw/csim/predictors.json \
  --trace RUN/rvfi.jsonl --events branches.jsonl --json
```

## Native performance and calibration

`perf-measured.json` records four native runs: `smoke`, `branches`, the
cache sweep with `FENCE.I`, and the same sweep with `nop`. Both caches
emit physical lookup or access events. The instruction cache also emits
`refill_beat` events. The independent checker verifies early-restart words
before it permits a hit on a line whose refill is not complete. All eight
core/program combinations were consistent with these checks. This is
selected simulation evidence. It is not a cache proof.

Retired instruction `access` events have `retired-refill-attribution`
semantics. They are separate from physical `lookup` events. The component
comparison uses the retired stream. Its report names that semantic boundary.
The physical stream includes wrong-path and redo fetches.

The data-cache `flush` uses `writeback-only` semantics. It records completion
of a dirty-line clean and retains tags. The cache sweep records one clean
and 512 writebacks. The component model omits that clean and has 449
writebacks. Its aggregate count error is -63, although all 769 access
hit/miss results agree. `compare-rtl --cache dcache` reports both measures.
The instruction-cache flush invalidates its resident lines.

Convert probes to Kanata, then run `rvw perf` with the same C1 result. A
stream with explicit `first_cycle` and `last_cycle` retains quiet clock
samples at its start and end. Legacy streams without bounds retain their
observed event window. Cache refill spans and mispredict recovery spans can overlap. Inferred spans are
reported separately. Do not sum them as lost CPU cycles. VexiiRiscv has a
commit-stage view only. Its C1 completion count differs from its commit-port
count. The performance report retains that difference.

`ooo.json` is a frozen approximate in-order timing model. It includes the
component caches and predictor. It does not model reset and cache-init time
in the same way as RTL. It was not fitted to the reported programs. Run the
existing calibration command through the saved-evidence helper:

```sh
rvw/.venv/bin/python examples/vexriscv/rvw/csim/calibrate.py \
  --config examples/EXAMPLE/rvw/csim/ooo.json \
  --runs RUN_ROOT --out NEW_CALIBRATION_DIR
```

Replace `EXAMPLE` with `vexriscv` or `vexiiriscv`. `RUN_ROOT` must contain
`smoke`, `branches` and `throughput` C1 directories, each with C2 and probes.
The helper writes counts and a plan, then calls `rvw arch ooo-calibrate`.
It refuses to overwrite its output directory. Both measured calibrations
report `accuracy_status=inconclusive`. Their IPC errors are recorded.
The model refuses `FENCE.I`. Build the throughput variant with
`-DRVW_NO_FENCE` to replace that instruction with `nop`; run that ELF in
RTL before calibration. Do not remove instructions from a captured trace.
