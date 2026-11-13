# BOOM adapter

Use `SPINAL_BOOM` to select the private `spinal-boom-eda` clone. Do not edit
or build the working `spinal-boom` checkout. Select `small` for bounded runs.
Run native jobs through `scripts/with-lock.sh boom nice -n 15 ...`.

## Interface inventory, 2026-11-13

The initial inventory used main at `1ac5ea96`. The table includes the adapter
changes below. Source support is not
native qualification. See `docs/INTEGRATION_GUIDE.md` and `docs/contracts/`.

| Interface | Current adapter state | Missing evidence or binding |
|---|---|---|
| C1 run, build, run-many | Implemented through generic Driver | Fresh smoke needed after harness changes |
| C2 integer state | Native add and timing captures complete; trap and IRQ levels captured | Stored legacy add example still has an order gap |
| C2/2 FP registers and flags | Small captures raw FP writes and full flags; 40 writes in native fadd | Wider presets and independent state agreement remain open |
| C2/2 CSR snapshots | Small declares 0x340 | More CSRs and wider-preset per-slot capture remain open |
| C2/2 fault records | Not exported | Need attempted access and completed-byte masks on faults |
| SpinalProbes, --probes | Optional binding; native events converted to branch, Kanata and counts formats | Prediction retention, full ROB and cache/TLB coverage remain incomplete |
| --fault | Generic public-register phase and SimSession injector exist | BOOM native injection not qualified |
| Online lockstep | Optional DPI mailbox bound; existing socket transport retained | Enabled DPI elaboration and native lockstep NOT RUN |
| Interrupt schedules | Implemented; MSIP, MTIP, SEIP, MEIP | No new native scheduled-interrupt run in this inventory |
| Persistent server | Two native jobs completed in one JVM with fresh instances | No checkpoint restore or throughput qualification |
| Checkpoint and restore | Generic C++ checkpoint and bridge-state APIs exist | BOOM Scala memory agent and devices have no complete save/restore binding |
| Device plugins | Fixed SparseMemory with CLINT and interrupt generator | No LiveDevices/plugin dispatch; fixed map refuses other devices |
| OoO model and csim | Small description, predictor study and one native timing observation | Model IPC is 2.6875 times RTL IPC; accuracy is inconclusive |

## Diagnostics

`rvw cosim doctor --core boom --trace
RiscvSim/boom/examples/pass-rv64ui-p-add/rvfi.jsonl --json` reports an error:
`C2 line 152: instruction orders must start at zero with no gaps`.
This is stored evidence, not a fresh run.

`rvw doctor --project examples/boom --features sim,cosim --json` reports
`not_ready`. The local native tool checks find JDK 21.0.13, Verilator 5.052
and the Spike shim. The installer check reports missing `env.sh` in this
worktree. No smoke ELF was supplied; C1 and C2 conformance are inconclusive.

The initial `rvw probes list` check required `--db` or `--events`. There was
no BOOM probe stream at the initial revision. Do not replace it with a synthetic
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
Compressed control-flow decoding and conditional branches whose target equals
fall-through need a direct taken binding. Full ROB occupancy, banked/matrix issue
queues, D-cache hit/miss classification and full TLB-fill records remain
open. `rob_head_occupancy` is only the head row, not the full ROB.

The first native capture stopped before retirement because an FP capture
register was unnamed. A corrected capture variant passed. There were two
native builds, one for each RTL variant. No regression suite or BOOM formal
job was run. Raw evidence remains in the local adoption run directory.

## C2 version 2 on small

RVFI runs on `small` export raw IEEE FP destination writes, including f0,
full `fflags` and `fcsr`, and the declared `mscratch` CSR snapshot at 0x340.
The adapter uses the single retirement slot. It does not copy a shared CSR
map into several slots. Wider presets retain C2/1 until per-slot state exists.
FP registers, flags and scratch state are sampled from the DUT. No missing
value is replaced with a zero constant.

Before: cosim doctor rejects the stored add example at line 152 for an order
gap. After: the fresh add capture is inspected as complete C2/2 with `state`
and `csr`, 514 instruction records, two trap events and one IRQ-level event.
Doctor marks FP and CSR comparison configured. It reports `compared: false`.
This is capture evidence, not an independent state match.

Only 0x340 is declared as a CSR snapshot. Other CSRs, wide-preset per-slot
state and fault-access records remain open. FP reset state is not initialized
by the adapter. Software and the reference policy must handle unspecified
reset state without changing captured DUT values.

The C2/2 `rv64uf-p-fadd` capture passed in 1790 cycles with 217 non-trapping
retirements and 40 FP destination writes. A captured single-precision load
writes raw boxed data `0xffffffff40200000` to f10. The five Scala mapping and
state-encoding tests passed.

Independent Spike comparison of the add capture stops at order 0: DUT
`fflags=0x19`, `fcsr=0xd9`; reference values are zero. The core leaves these
registers without reset. This is a reset-state integration mismatch, not
proof of an ISA defect. The adapter preserves the values. No state match is
claimed. Configure an explicit initialization policy before a wider state
campaign.

There were four native builds across three RTL hashes in this work session.
The last capture rebuilt the same `f7fd1396...` RTL hash as the corrected add
capture instead of reusing its cache. This violates the requested one-build
limit for that variant. The recorded native tool and declared environment
fields match. Only the inherited-environment digest and native identity digest
differ. Cache identity/reuse needs follow-up. No further BOOM
build was run. All five short jobs used `small`, the BOOM lock, two make jobs
and `nice -n 15`. No regression suite or BOOM formal job was run.

## Fault injection and online DPI

Generic harness support is on main. BOOM uses `RiscvSimConfig`'s `_fault`
public-register phase and `SimSession`'s `FaultInjector`. No second BOOM
injection engine is needed. Supply `--fault FILE` with register paths from
the matching design database. An unknown site is recorded as unapplied.
A fault campaign must inspect `details.fault.applied`, not just C1 status.
Native BOOM injection is NOT RUN in this update. Refs: #52.

The adapter adds an optional `LockstepDpi` mailbox when
`RVW_COSIM_DPI=1`. It initializes the mailbox before creating the C2 writer.
With `RVW_COSIM_PORT`, each header, instruction, trap, IRQ and end record
uses the generic blocking DPI observer. Without a mailbox, the writer keeps
its existing socket path. The mailbox is absent by default.

Use `rvw cosim live --lockstep --elf ELF --core boom --out OUT
--simulator COMMAND` with the adapter command. The generic launcher selects
the DPI environment. The binding compiles with the adapter. Enabled DPI
elaboration, native lockstep and native fault injection are NOT RUN. The
reset FP-state mismatch above must be resolved by an explicit initialization
policy before a full-state online match can succeed. Checkpoint restore
still has no BOOM binding.

## Stable native launch identity

Native identity v28 excludes the agent call, thread and session IDs. These
values change between launches. The standard native tools do not use them.
Unknown environment settings, tool bytes, compiler flags and generated RTL
still identify the build. The namespace change invalidates old cache receipts;
old binaries are not promoted into the new namespace without verification.
Unit tests change each frontend ID and require the same native identity.
They also require changed compiler flags and unknown settings to change it.
