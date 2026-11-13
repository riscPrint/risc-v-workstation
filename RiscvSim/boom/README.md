# BOOM adapter

Set `SPINAL_BOOM` to the private `spinal-boom-eda` clone. Do not edit or build
the working `spinal-boom` checkout. Use `small` for bounded native checks.
Run BOOM jobs through `scripts/with-lock.sh boom nice -n 15 ...`.
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
