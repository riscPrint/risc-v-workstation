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
