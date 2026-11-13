# Small BOOM timing description

`small.json` uses the shared `rvw.arch-core/1` dimensions from
`../arch/small.json`. It adds the `ooo` timing table. It embeds the existing
`../csim/tage-l.json` predictor study without changes.

Run `rvw ooo examples/boom/ooo/small.json TRACE --json`.
Run `rvw csim compare-rtl examples/boom/csim/tage-l.json --trace TRACE --events EVENTS --json`.
Convert a native probe stream with `rvw probes convert EVENTS --to bp-events
--c2 TRACE --out BP_EVENTS` first.

## Limits

The four issue queues have 8 slots each. The timing engine combines them into
one 32-slot queue with issue width 5. It does not reproduce BOOM arbitration.
The fixed load latency is 4 model cycles. Memory stalls, cache misses and
wrong-path execution need separate calibration. The 5-cycle recovery cost is
an estimate. The frontend uses the project's fetch, decode and FTQ widths;
its delays are estimates. Predictor hashing and repair limits are listed
in the embedded study. No field claims an extracted effective configuration.

A run report is a model estimate. Compare exactly the same instruction region
with measured RTL cycles. Report startup, trap and device exclusions explicitly.
One short run cannot qualify model accuracy.

## Native timing observation

`RiscvSim/boom/tests/add-timing.S` runs a 16-iteration integer loop without
trap setup. Build it with RISC-V GCC, `-nostdlib -nostartfiles -march=rv64im
-mabi=lp64 -Wl,-Ttext=0x80000000,--no-relax`. Run it with the small adapter,
seed 1 and RVFI probes. Feed the complete C2 trace to the command above.

The bounded native run passed. RTL retired 57 instructions in 258 cycles
from reset: IPC 0.22093. The model predicted 96 cycles and IPC 0.59375 for
the same 57 instructions. Model IPC divided by RTL IPC is 2.6875. This large
gap is an observation, not calibrated accuracy. Real cold fetch and memory
latency differ from the fixed model delays. The model has no wrong-path
execution. `TIMING_OBSERVATION.json` records the artifact hashes and limits.
The committed source and predictor configuration permit another short run.

The same persistent-server JVM also ran `rv64uf-p-fadd`: pass, 1790 cycles,
217 non-trapping retirements. That server used the integer C2/1 probe model.
It does not validate C2/2 FP capture. Each job used a fresh native instance.

`event-map.json` names the counter inputs for `rvw arch ooo-calibrate`.
Convert probe events with `--to counts --c1 RESULT --c2 TRACE` to bind the
counts to the exact run. The timing loop has 57 architectural commits and
7 RTL mispredict corrections. The model issued 57 instructions and counted
3 branch misses. Correction pulses and committed-path model misses have
different speculative scope. This map exposes that gap; it does not assert
identical semantics. Do not map occupancy integrals to stall-cycle counters.
No calibration campaign or held-out accuracy test was run.
