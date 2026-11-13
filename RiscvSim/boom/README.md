# BOOM adapter

Set `SPINAL_BOOM` to the private `spinal-boom-eda` clone. Do not edit or build
the working `spinal-boom` checkout. Use `small` for bounded native checks.
Run BOOM jobs through `scripts/with-lock.sh boom nice -n 10 ...`.
Simulation-only probes and the DPI mailbox are off by default.

## Interface inventory, 2026-11-13

Source support does not establish native qualification. The evidence below
covers selected small programs. It does not qualify every option or preset.

| Interface | Current evidence | Remaining gap |
|---|---|---|
| C1 run, build, run-many | Native small ISA and trap-free loop runs pass | No broad option or preset qualification |
| C2 integer state | Fresh small traces compare with Spike | The stored legacy add example has an order gap |
| C2/2 FP registers and flags | Raw FP writes, fflags and fcsr; fadd has 40 FP writes | Wider presets and additional FP programs |
| C2/2 CSR snapshots | Small exports and compares CSR 0x340 | Other CSRs and wider-preset per-slot capture |
| C2/2 fault-access records | Not exported | Attempted-access and completed-byte masks |
| SpinalProbes | Native conditional predictions, commit counts, occupancy, cache lookups and stall samples | Full pipeline attribution, TLB fills and wider queue types |
| Predicated-off commits | SFB arithmetic check passes; 7 predicated-off commits | One architectural sample at the endpoint exceeds C1/C2 |
| Native --fault | Two cycle-200 register flips have read-back confirmation | Other injection kinds, memories and campaigns |
| Online DPI lockstep | Clean fadd match and injected mismatch; native cache reused | Checkpointed reference state and wider presets |
| Interrupt schedules | MSIP, MTIP, SEIP and MEIP bindings exist | No new scheduled-interrupt run in this continuation |
| Persistent server | Historical two-job smoke used fresh native instances | No fresh server throughput or restore qualification |
| Checkpoint and restore | Generic native and C2 APIs exist | No complete BOOM binding |
| Device plugins | Fixed SparseMemory, CLINT and interrupt generator | No LiveDevices or plugin dispatch |
| OoO model and csim | Native branch comparisons and two trap-free timing observations | Accuracy remains inconclusive |

## Full-state comparison

Small exports C2/2 raw IEEE FP writes, including f0, full fflags/fcsr and
mscratch at CSR 0x340. It uses the single retirement slot. Wider presets
retain C2/1 until per-slot state exists. Missing DUT values are not replaced
with zero constants.

The core leaves FCSR without reset. The platform declares
`fcsr_reset: "unspecified"`. The comparator can seed Spike once before the
neutral integer instruction at order zero. The shim preserves mstatus,
including FS. This is a recorded reset alignment, not an FP comparison mask.
Strict mode disables it. The separate mscratch reset policy tracks its
captured initial value. Later state changes remain checked.

The prior small captures of add, sub, beq and fadd were checked again with
the current comparator: all four matched. Fresh beq and fadd captures also
matched. The ordinary fadd capture has 219 instruction records, including
two traps. C1 counts 217 non-trapping retirements. The DPI sampling path
ends with 218 records and 40 FP writes. These paths have different host
sampling schedules; do not treat their endpoints as identical.

The stored legacy add trace under `examples/pass-rv64ui-p-add` still has an
order gap at line 152. It is historical evidence, not the current capture.
Doctor inspects capture and configuration. It does not run a reference.

## Optional probes and performance

`run --rvfi-trace --probes` enables `BoomProbes` and `ProbeCollector`.
The binding captures fetch prediction packets, execution resolution,
redirects, ROB commits, architectural and predicated-off commits, full ROB
validity, physical free-list levels, collapsing issue-queue occupancy,
D-cache lookups, D-TLB misses, I-cache responses and walk memory transfers.

ROB repair overwrites `uop.taken`. The binding therefore retains the enqueue
prediction. The first native capture failed the prediction regression.
The corrected beq, fadd, SFB and timing captures passed eight checks.
Branch conversion checks count, PC and outcome against C2. ROB indices only
address retained state. They are not external instruction IDs.

The SFB loop reports 92 ROB commits: 85 architectural and 7 predicated off.
C1/C2 contain 84 instructions. The endpoint alignment difference remains
open. Keep predicated-off counts separate from architectural retirement.
Refs: #49.

`rvw csim compare-rtl` with `examples/boom/csim/tage-l.json` reports
`compared` on the converted conditional branch streams. The study is
approximate. Perf attributes measured nack and dispatch-blocked cycles.
It also reports unattributed zero-retirement intervals. Causes can overlap.
The bare-mode programs do not exercise TLB miss or walk bindings.

| Trap-free program | RTL cycles | Model cycles | RTL IPC | Model IPC | Model / RTL IPC |
|---|---:|---:|---:|---:|---:|
| Timing loop | 258 | 96 | 0.22093 | 0.59375 | 2.6875 |
| SFB loop | 314 | 160 | 0.26752 | 0.52500 | 1.9625 |

These whole-program regions include startup. No fitting was done.
The calibration uses one training and one held-out program. Its accuracy
status is `inconclusive`. The OoO model refuses the ISA traces with traps.
See [probe bindings](PROBE_BINDINGS.md) and the
[timing report](../../examples/boom/ooo/PROBE_OBSERVATION.md).

## Native fault injection and DPI

The adapter uses the generic public-register phase and SimSession injector.
Two cycle-200 flips in FFLAGS and mscratch were confirmed by read-back.
The integer program passed. Offline comparison detected fflags, fcsr and
CSR 0x340 differences at order 13, cycle 228. Inspect `details.fault.applied`.
Program pass alone does not qualify an injection.

Set `RVW_COSIM_DPI=1` to elaborate the mailbox. With `RVW_COSIM_PORT`, the
writer uses the generic DPI observer. The mailbox is absent by default.
The existing socket transport remains available without the mailbox.
Use `rvw cosim live --lockstep --elf ELF --core boom --out OUT
--simulator COMMAND` with the adapter command and explicit DPI environment.

The first native DPI run exposed a sampling-context error. A sampling
callback cannot yield to the mailbox. The DPI path now samples on the main
simulation thread and sends the end record before that thread stops.
The ordinary callback path is unchanged. Its post-fix beq run passed at
1844 cycles and 333 C1 instructions, with both capture checks passing.

The clean DPI fadd run matched with FP/CSR comparison active and a complete
trace. A one-bit FFLAGS injection produced an online fflags/fcsr mismatch at
cycle 228. The host stopped the simulator, leaving an incomplete trace.
Host cancellation can occur before a native exception log is written.
Three native fault/DPI evidence checks passed.
[NATIVE_FAULT_DPI.json](NATIVE_FAULT_DPI.json) records the results and hashes.

## Native cache identity

Native identity v29 excludes frontend call/thread/session IDs, macOS XPC
service labels, the runtime cosim port and trace-flush setting. Unknown
settings, DPI elaboration, tool bytes, compiler flags and generated RTL
still identify the build. The namespace change invalidates old receipts.
The identity unit tests passed: 39 tests.

Both DPI launches and the ordinary post-fix run confirmed Verilator cache
hits. The Scala scheduling fix needed no new native build. This continuation
used two native builds. The first exposed lost prediction history; the
second retained enqueue predictions and used `-O0`. No regression suite,
wider-preset campaign or BOOM formal job ran. Raw captures remain local.

## Deferred bindings and source review

Checkpoint restore and device plugins remain unimplemented. See
[the binding gaps](CHECKPOINT_GAPS.md). A native RTL snapshot alone cannot
restore the Scala memory agent, pending transfers, devices, counters and
trace position. Lockstep resume also needs matched reference state.

The [stream review](../../SpinalChecks/boom/STREAM_REVIEW.md) maps the internal
`arbiter.ups_0_a` stage by source. It adds no waiver or native pass claim.
The original historical firing inventory remains incomplete. Refs: #5.

## Expanded small probe run, 2026-11-13

These fresh runs use private BOOM revision `0cb0b69`, preset `small`,
the BOOM lock and `nice -n 10`. The core RTL is unchanged. Random memory
timing and whole-program regions include startup. No model fitting was done.

| Program | RTL cycles | Instructions | RTL IPC | Model cycles | Model IPC | Model / RTL IPC |
|---|---:|---:|---:|---:|---:|---:|
| add-timing | 266 | 57 | 0.21429 | 96 | 0.59375 | 2.77083 |
| sfb-predication | 339 | 84 | 0.24779 | 160 | 0.52500 | 2.11875 |
| rv64ui-p-beq | 1802 | 333 | 0.18479 | unsupported traps | unavailable | unavailable |
| rv64uf-p-fadd | 1668 | 217 | 0.13010 | unsupported traps | unavailable | unavailable |

| Conditional branch stream | Events | RTL misses | Model misses | Direction disagreements |
|---|---:|---:|---:|---:|
| add-timing | 16 | 8 | 2 | 6 |
| sfb-predication | 33 | 18 | 5 | 13 |
| rv64ui-p-beq | 76 | 45 | 43 | 62 |
| rv64uf-p-fadd | 25 | 21 | 5 | 24 |

All four programs pass their C1 completion checks. Each predictor report has
status `compared` with `examples/boom/csim/tage-l.json`. The predictor is
approximate. These disagreements do not establish core defects.
`rvw perf topdown` rejects all four captures: the binding lacks
`topdown_slots`, `topdown_retiring`, `topdown_bad_speculation`,
`topdown_backend_bound` and `topdown_frontend_bound`. No slot partition
or top-down percentage is earned. Existing stall samples are separate.

Regenerate the timing ELFs from `tests/add-timing.S` and
`tests/sfb-predication.S` with GCC `-nostdlib -nostartfiles -march=rv64im
-mabi=lp64 -Wl,-Ttext=0x80000000,--no-relax`. Run each with:

```sh
scripts/with-lock.sh boom nice -n 10 RiscvSim/boom/run.sh run \
  --config small --elf "$ELF" --out "$RUN" --rvfi-trace --probes --json
rvw probes convert "$RUN/probe-events.jsonl" --to bp-events \
  --probe conditional_commit_0 --c2 "$RUN/rvfi.jsonl" --out "$RUN/bp.jsonl"
rvw csim compare-rtl examples/boom/csim/tage-l.json \
  --trace "$RUN/rvfi.jsonl" --events "$RUN/bp.jsonl" --json
rvw perf topdown "$RUN/probe-events.jsonl" --c2 "$RUN/rvfi.jsonl" --json
rvw ooo examples/boom/ooo/small.json "$RUN/rvfi.jsonl" --json
```

The fresh beq strict comparison also exposes unspecified initial mscratch and
FP status values. It is not counted as a strict match. No synchronization or
output mask was used for that comparison. Raw captures remain local.

## Quick-tier generated checks, 2026-11-13

| Programs | Inserted checks | Existing waived/disabled | Distinct firing IDs | Clean instrumented passes |
|---:|---:|---:|---:|---:|
| 174 | 519 | 101 | 10 | 0 |

The underlying tohost outcomes are 173 pass and one known instret failure.
All 24 named source-review stream IDs are absent from the new firing set.
The original historical mapping remains incomplete. The 10 current IDs
cover one A request violation, one simulation-agent D response violation,
and two stream binding gaps. Wave reruns reproduce every current ID.
See [the findings and wave windows](../../examples/boom/FINDINGS.md).
No waiver or core RTL change was made. Refs: #5.

Regenerate with `spinalchecks.boom.BoomChecks run small OUT --max-cycles
200000 ELFS` from `SpinalChecks/boom`, through
`scripts/with-lock.sh boom nice -n 10 sbt -J-Xmx8g -batch`.
Select ELFs from `tier_plan(load_config('boom'), 'quick', None)` and
`discover(item.suite, item.include)`. Use `--wave` on add, icache-alias
and ae_ptw for the windows. Reuse the first run's `sim/.cache` directory
for another output directory. These checks use the private clone's
simulation harness; they do not capture C2 for an independent Spike run.

## Generic ACT4 suite, 2026-11-13

| Set | Built/run | Latest C1 pass | Self-check/assert fail | RVFI error | Strict Spike matches |
|---|---:|---:|---:|---:|---:|
| RV64 instructions | 378 | 376 | 2 | 0 | 0 |
| M/S/U and Sv39 | 232 | 196 | 26 | 10 | 0 |

Instruction tests ran first. Two false REMW/REMUW checker failures pass
on rerun after a generic model correction. Two false canonical-PC adapter
assertions also pass after sign extension. The table counts unique ELFs.
All 610 strict checks stop at unspecified reset FCSR state. No mask or
synchronization was used. These counts do not establish qualification.
See the [profile and exact regeneration commands](../../rvw/configs/act4/boom/README.md)
and [failure triage with minimal programs](../../examples/boom/FINDINGS.md).

## Generated RV64 families, 2026-11-13

`rvw regress plan --features examples/boom/verification.json --json`
selects 11 families. The following program counts use seed 1 and `small`.

| Family | Built/run | C1 pass | C1 fail | Strict Spike matches |
|---|---:|---:|---:|---:|
| Sv39 permissions, faults, SATP and TLB | 145 | 145 | 0 | 0 |
| PMP regions, privilege and locking | 394 | 379 | 15 | 0 |
| Privilege controls | 30 | 30 | 0 | 0 |
| Random privilege transitions | 4 | 4 | 0 | 0 |
| CLINT WFI | 4 | 4 | 0 | 0 |
| Scheduled WFI interrupts | 6 | 6 | 0 | 0 |
| LR/SC | 1 | 1 | 0 | 0 |
| AMO | 1 | 1 | 0 | 0 |
| AMO faults | 1 | 1 | 0 | 0 |
| FENCE | 1 | 1 | 0 | 0 |
| FENCE.I | 1 | 1 | 0 | 0 |
| Total | 588 | 573 | 15 | 0 |

Sv39 contains 120 permission cases, five superpage cases, three canonical
address cases, two walk faults, two fault-based A/D cases, three SATP/MPRV
cases and ten fence/root/global cases. ASID_WIDTH is zero. Use ASID 0;
these runs do not test isolation between nonzero ASID tags. Svadu hardware
A/D updates are absent. The first unfiltered matrix had eight ASID readback
failures with ASID 7 and two unsupported hardware A/D failures. These
remain setup findings, outside the corrected 145-program selection.

All 15 PMP failures are NA4 execute cases. The isolated NA4 and TOR
programs in [FINDINGS.md](../../examples/boom/FINDINGS.md) reproduce an
instruction access fault where Spike reaches the data access. No PMP
expectation was weakened. The AMO fault suite needs 38,498 cycles. Its
first 30,000-cycle attempt timed out; it passes with the generator's
200,000-cycle budget. The table uses that completed rerun.

The harness binds CLINT and an interrupt generator for MEIP/SEIP. It does
not bind a PLIC register device. Six scheduled cases exercise MSIP, MTIP
and MEIP schedules. PLIC claim/complete, SEIP handler coverage, multiple
harts and broad atomic concurrency remain unmeasured.

Strict Spike checks ran for every selected program. Each stops at
unspecified reset FP state, often with mscratch as well. No complete
strict match or whole-core qualification is earned. No output mask,
synchronization or core RTL change was added. Raw outputs stay local.

Regenerate the full build, C1 run and strict comparison from the root with
`examples/boom/run-generated.sh NEW_OUTPUT_DIRECTORY`. Set `SPINAL_BOOM`
to the private clone and put the RISC-V GCC bin directory on PATH. The
script uses the BOOM lock, `nice -n 10`, four workers and the existing
native cache. Its matrix explicitly selects the implemented A/D and ASID
settings. The script's build phase was rerun and produces all 588 ELFs.
