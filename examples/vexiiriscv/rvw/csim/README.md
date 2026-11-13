# Cached VexiiRiscv component studies

`caches.json` describes the 4 KiB L1 caches. `predictors.json` describes the
upstream default stack selected by `rv32im_cached`: a 4 KiB GShare table with
2-bit counters and 12 history bits, a 512-set BTB with a 16-bit hash, and a
four-entry RAS. These values come from the pinned core's `Param.scala`.

The model is approximate. RTL reverses PC hash bits, uses speculative history,
trains carried counter values with bypass, and initializes RAM with seed 42.
The model has a standard GShare hash and trains in trace order. The model's
BTB and RAS do not reproduce all upstream chunk and recovery behavior.

On 2026-11-13, the cached native `branches` run retired 35,661 instructions
in 108,567 cycles. Its 6,001 conditional branch events aligned with C2. RTL
recorded 844 direction misses. The model recorded 1,065. Per-branch direction
agreement was 93.1845 percent. `predictor-measured.json` records the result
and per-PC differences. Conditional target agreement was 89.9017 percent
across 6,001 events. RTL recorded 4 target misses; the model recorded 610.
Targets on not-taken branches are unused and do not count as misses.
Call/return target alignment remains unmeasured. A full learn-port experiment
had one event beyond C2; its converter refused it. RAS agreement is not claimed. The run does not establish predictor fidelity.

```sh
rvw probes convert RUN/probe-events.jsonl --to bp-events \
  --c2 RUN/rvfi.jsonl --out branches.jsonl
rvw csim compare-rtl examples/vexiiriscv/rvw/csim/predictors.json \
  --trace RUN/rvfi.jsonl --events branches.jsonl --json
```

With a BTB, `ProbeTapPlugin` carries `ALIGNED_JUMPED` and
`ALIGNED_JUMPED_PC` to the learn port. It does not infer direction from
`wasWrong`, which also includes target errors. The cacheless path retains
its sequential-prediction mapping. Probe-disabled elaboration adds no context.

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

Convert probes to Kanata, then run `rvw perf` with the same C1 result. A
stream with explicit `first_cycle` and `last_cycle` retains quiet clock
samples at its start and end. Legacy streams without bounds retain their
observed event window. Cache
refill spans and mispredict recovery spans can overlap. Inferred spans are
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
