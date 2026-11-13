# Cached VexRiscv component studies

`caches.json` describes the 4 KiB caches. The data cache writes through and
does not allocate on a store miss. `measured.json` retains the first study
record. The current physical lookup and performance record is in
`perf-measured.json`.

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
