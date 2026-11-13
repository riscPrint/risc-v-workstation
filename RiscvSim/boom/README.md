# BOOM adapter

Use `SPINAL_BOOM` to select the private `spinal-boom-eda` clone. Do not edit
or build the working `spinal-boom` checkout. Select `small` for bounded runs.
Run native jobs through `scripts/with-lock.sh boom nice -n 15 ...`.

## Interface inventory, 2026-11-13

This inventory was read against main at `1ac5ea96`. Source support is not
native qualification. See `docs/INTEGRATION_GUIDE.md` and `docs/contracts/`.

| Interface | Current adapter state | Missing evidence or binding |
|---|---|---|
| C1 run, build, run-many | Implemented through generic Driver | Fresh smoke needed after harness changes |
| C2 integer state | RvfiProbe reads core RVFI; trap cause/tval and IRQ levels captured | Stored add example fails current cosim doctor: instruction order gap at line 152 |
| C2/2 FP registers and flags | Not exported | Need architectural FP writeback and per-retirement fcsr, not speculative FP writeback |
| C2/2 CSR snapshots | Not exported | Need per-slot state after each instruction; one live CSR map for all slots is insufficient |
| C2/2 fault records | Not exported | Need attempted access and completed-byte masks on faults |
| SpinalProbes, --probes | No binding; supportsProbes is false | Need adapter-owned taps and ProbeCollector lifecycle |
| --fault | Generic public-register phase and SimSession injector exist | BOOM native injection not qualified |
| Online lockstep | RvfiTraceWriter has socket transport | No BOOM LockstepDpi mailbox binding; native comparison not qualified |
| Interrupt schedules | Implemented; MSIP, MTIP, SEIP, MEIP | No new native scheduled-interrupt run in this inventory |
| Persistent server | Opted in with freshInstancePerRun | Each request starts a fresh instance; no BOOM reuse measurement here |
| Checkpoint and restore | Generic C++ checkpoint and bridge-state APIs exist | BOOM Scala memory agent and devices have no complete save/restore binding |
| Device plugins | Fixed SparseMemory with CLINT and interrupt generator | No LiveDevices/plugin dispatch; fixed map refuses other devices |
| OoO model and csim | Predictor data in examples/boom/csim | No small OoO project description or fresh RTL IPC correlation |

## Diagnostics

`rvw cosim doctor --core boom --trace
RiscvSim/boom/examples/pass-rv64ui-p-add/rvfi.jsonl --json` reports an error:
`C2 line 152: instruction orders must start at zero with no gaps`.
This is stored evidence, not a fresh run.

`rvw doctor --project examples/boom --features sim,cosim --json` reports
`not_ready`. The local native tool checks find JDK 21.0.13, Verilator 5.052
and the Spike shim. The installer check reports missing `env.sh` in this
worktree. No smoke ELF was supplied; C1 and C2 conformance are inconclusive.

`rvw probes list` requires `--db` or `--events`. There is no BOOM probe
stream in this adapter at this revision. Do not replace it with a synthetic
stream to claim BOOM coverage.

## Limits

A source binding does not establish event accuracy. Keep measured counters,
model estimates and unsupported consumers separate. Never infer an instruction
ID from a wrapping ROB index. Predicated-off ROB commits must be counted
separately from architectural commits (Refs: #49).

## Optional probe binding

`run --rvfi-trace --probes` enables `BoomProbes` and `ProbeCollector`.
The core sources stay unchanged. A plain run adds no probes. The binding
captures commit, architectural commit and predicated-off commit counts,
rename levels, dispatch stalls, ROB-full and head occupancy, collapsing
issue-queue occupancy, mispredict corrections, I-cache responses, I-TLB
misses and page-walk memory requests and responses.

The add smoke on `small`, seed 1, passed in 2487 cycles with 512 non-trapping
retirements. It captured 514 commit events, 53 mispredict corrections and
914 I-cache responses. Queue occupancy totals are slot-cycles: ROB head
1116; memory issue 18; ALU issue 1099; unique issue 36; FP issue 0.
Predicated-off commits, I-TLB misses and page-walk events were zero in this
program. A zero count does not exercise that binding.

`rvw probes convert` wrote 74 branch events, Kanata and C1/C2-bound counter
JSON. `rvw perf` read 514 retirements with no open IDs. Its event IPC is
0.21633 over cycles 112..2487, including two trap instructions. This is not
the C1 whole-run IPC or a full pipeline trace.

`rvw csim compare-rtl` is **inconclusive**: the 72 conditional branches have
no captured direction prediction. The binding captures resolved next PCs
but does not retain the prediction through the ROB. Do not infer a
prediction from a correction or use a wrapping ROB index as a trace ID.
Compressed control-flow decoding, full ROB occupancy, banked/matrix issue
queues, D-cache hit/miss classification and full TLB-fill records remain
open. `rob_head_occupancy` is only the head row, not the full ROB.

The first native capture stopped before retirement because an FP capture
register was unnamed. A corrected capture variant passed. There were two
native builds, one for each RTL variant. No regression suite or BOOM formal
job was run. Raw evidence remains in the local adoption run directory.
