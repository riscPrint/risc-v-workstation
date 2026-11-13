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
