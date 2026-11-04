# Architectural checkpoint transfer

## Goal and scope

Resume RTL execution from architectural state captured by Spike. Use a generic
C1 adapter extension. Execute a warm-up window before a fixed measurement window.
Check the restored execution against an independent Spike continuation.

This document is a design proposal. The commands, schemas and Scala interfaces
below are proposed. They are not implemented. This design-agent slice delivers
contracts, acceptance tests and follow-up tasks. It does not establish a native
restore, an instruction match, a speedup or a warm-up bias result.

The first implementation target is the existing RV32IM VexRiscv example.
Use one hart, little-endian RAM, M mode, bare addressing and no asynchronous
inputs. Capture after K retired instructions, before the next instruction.
Require K > 0 and N > 0 for the native acceptance test. Reject enabled FP,
vector, virtual memory, debug, LR/SC reservation and unmodelled devices.
Keep explicit unsupported-state fields in the format so later producers cannot
silently discard state. Do not change either BOOM core checkout.

## Prior art and existing code

- [SimPoint](https://cseweb.ucsd.edu/~calder/simpoint/) selects representative
  execution intervals and weights them by phase size. Use its interval and
  weight files as inputs later. Checkpoint transfer does not select phases.
- [Chipyard architectural checkpoints](https://chipyard.readthedocs.io/en/latest/advanced-concepts/architectural-checkpoints/)
  already capture Spike memory, registers and CSRs and restore RTL through
  DMI and fast memory loading. Its documented restrictions include single-core
  systems and limited Linux devices. Reuse the architectural-state approach.
  The current VexRiscv example has no debug unit, so LOADARCH is not a direct
  integration. Do not claim file compatibility without a checked converter.
- [Dromajo](https://github.com/chipsalliance/dromajo) supports snapshots and
  RTL cosimulation for RV64GC. It is useful prior art, but does not replace the
  RV32 Spike oracle selected for the first slice.
- [gem5 SimPoint support](https://www.gem5.org/documentation/general_docs/stdlib_api/gem5.utils.simpoint.html)
  separates warm-up lengths from sample starts. Use the same separation in C1.
  Its checkpoints are not a portable RTL state format.
- [Spike processor state](https://github.com/riscv-software-src/riscv-isa-sim/blob/master/riscv/processor.h)
  is an implementation API. Pin the source, headers, libraries and shim ABI.
  Never serialize C++ object bytes or assume CSR writes restore hidden state.

Local code inspected on base `2c466e8`:

| Code | Existing behavior and required change |
|---|---|
| `RiscvSim/src/main/scala/riscvsim/Model.scala` | `CoreAdapter` has compile/run but no architectural-state hook. `RunContext` supplies captured ELF bytes. Add optional restore capability with a default refusal. |
| `RiscvSim/src/main/scala/riscvsim/Driver.scala` | Owns C1 files and run inputs. Capture checkpoint bytes here before compilation. Include them in replay and identity. |
| `examples/vexriscv/rvw/src/main/scala/rvwvex/VexTop.scala` | RV32IM, simple buses, SYNC register file, STATIC fetch prediction, no caches, MMU or debug. Add an optional adapter-owned simulation plugin. |
| `examples/vexriscv/rvw/src/main/scala/rvwvex/VexAdapter.scala` | Loads the ELF into sparse RAM, requires reset entry and tohost, starts fresh DUT state and records C2. Add a separate checkpoint path and bounded sample completion. |
| `Cosim/spike_shim.cc` | `Machine` owns sparse 4 KiB pages and a `processor_t`; exposes GPR writes and CSR reads, but no full state import/export. MMIO loads can be injected. Such injection is refused in the first checkpoint profile. |
| `rvw/src/rvw/cosim/checker.py` | Starts its tracked GPR state at zero. Seed it from the checkpoint, verify model identity and require a complete bounded trace. |
| `docs/PLATFORM_CONTRACTS.md` | `rvw.replay-checkpoint/1` means from-reset replay. Keep it separate from architectural transfer. |

Related issues: [#132](https://github.com/riscPrint/risc-v-workstation/issues/132)
(deterministic replay), [#295](https://github.com/riscPrint/risc-v-workstation/issues/295)
(simulation), [#282](https://github.com/riscPrint/risc-v-workstation/issues/282)
(workloads). Architectural transfer rebuilds microarchitecture. It does not
satisfy #132's complete DUT snapshot requirement.

## Checkpoint format

Propose `rvw.arch-checkpoint/1`: a JSON manifest plus relative binary page files.
All address and register values are unsigned hexadecimal strings. Counters and
instruction indices are decimal strings to avoid JSON precision loss.
Reject unknown schema versions, duplicate keys, overlapping regions, incomplete
register arrays, bad widths, out-of-range values and invalid file digests.

Required manifest fields:

| Field | Contract |
|---|---|
| `schema`, `id`, `profile` | Version, content digest, and an exact support profile such as `rv32im-m-bare-ram/1`. |
| `producer` | Spike source revision, executable/library hashes, shim ABI and hash, ISA, XLEN, FLEN, privilege implementation and platform hash. |
| `workload` | Captured ELF hash, input hashes, entry point and initial memory policy. |
| `boundary` | `retired_before=K`, `pc` of the next instruction, hart ID, privilege and `pending_trap=false`. Trap attempts do not increment K. |
| `gpr` | All 32 values, including x0=0. |
| `fp` | `absent` when ISA has no F/D; otherwise all 32 raw FLEN-bit values plus fcsr. Preserve NaN boxing and f0. Missing enabled state is an error. |
| `csr` | Address/value records for all implemented mutable state in the profile, plus read-only identity constraints. Record aliases once with explicit alias rules. Include counters, inhibit/enable bits, trap/delegation/interrupt state and translation/PMP state when implemented. |
| `memory` | Declared physical RAM regions and permissions, page size 4096, zero-fill rule, complete nonzero page list, file sizes and SHA-256 digests. RAM outside the ELF is included. Missing pages mean zero only under the declared rule. |
| `translation` | Mode and root CSR values. Page tables are ordinary physical RAM bytes, including A/D bits. TLB contents are excluded and start invalid. First profile requires bare mode. |
| `devices` | Complete platform inventory with device type/version, serialized state and pending events, or explicit `none`. No omitted active device is allowed. |
| `execution` | Reservation, debug, WFI, virtual privilege and pending external inputs, each explicit. First profile requires inactive/absent values. |

Hash the sorted compact UTF-8 manifest without `id`. The manifest includes each
page digest, so its ID binds the page bytes. Publish via a temporary directory
and a final rename. Refuse partial bundles. Capture all bundle bytes once under
C8. Apply bounded page counts and byte limits before allocation. Refuse paths
outside the bundle. Replay consumes the captured copy, not the original files.

Profile inventory is executable data shared by export, import and validation.
It lists each CSR, width, alias and restore rule. Do not accept an arbitrary
list of observed CSRs as complete. For VexRiscv, derive and test the inventory
against its actual `CsrPlugin` configuration. Values with no target equivalent
must cause refusal. Do not silently mask WARL differences.

## Capture, restore and sampling sequence

1. Start Spike with captured ELF and declared RAM/platform settings. Disable
   external effects and trace-driven MMIO injection. Advance to K retirements.
2. Finish the current instruction synchronously. Check for pending traps,
   unexported state and unsupported accesses. Export state and RAM at one boundary.
3. Keep the original Spike instance as the independent continuation oracle.
   Also import the bundle into a fresh Spike instance. Compare both continuations
   for N instructions before treating import/export as qualified.
4. Validate the complete bundle and adapter capabilities before DUT mutation.
   Create a fresh native RTL instance. Apply normal reset with fetch held.
5. Replace all RAM from the captured image. Do not overlay the ELF afterward.
   Set GPRs and all profile CSR storage while the pipeline and buses are empty.
   Set privilege and next PC last. Invalidate fetch/prefetch state. Read back
   architectural state and compare it with the bundle before release.
6. Release fetch. The first C2 instruction must have the saved PC and start
   local order zero. Setup writes and reset clocks are not sample execution.
7. Run W warm-up retirements, then L measurement retirements without resetting
   microarchitecture. Use separate counters for setup, warm-up and measurement.
   Check all W+L retirements against the oracle. Require N=W+L.
8. Stop at the exact boundary. Write a complete C2 end event and sample report.
   Do not require tohost for this path. An early tohost, trap outside the
   supported profile, timeout or missing final record is not sample completion.

The first native test uses a deterministic RAM-only program with a mid-loop
checkpoint, live nonzero GPRs, stack values and stores outside PT_LOAD data.
Its suffix has loads, stores, conditional branches, calls and CSR access.
Use aligned scalar instructions. Add a second checkpoint after changed CSR
state so a reset-state-only implementation cannot pass.

## Generic adapter interface

Propose an optional capability on `CoreAdapter`, default `None`:

```scala
def checkpointCapabilities(config: String): Option[CheckpointCapabilities]
```

Capabilities list profiles, CSR inventory identity, ISA/XLEN/FLEN, memory map,
readback support, devices and microarchitecture initialization policy.
The generic driver owns validated immutable `ArchitecturalCheckpoint` data.
`RunJob` carries a checkpoint selection and sampling options. `RunContext`
provides the captured bundle. An adapter-owned per-instance port implements:

```scala
trait ArchitecturalRestorePort {
  def holdAfterReset(): Unit
  def restore(state: ArchitecturalCheckpoint): Unit
  def readBack(): ArchitecturalState
  def releaseAt(pc: BigInt): Unit
}
```

These operations run on the simulation thread. `restore` returns only after
writes settle. Readback must use DUT storage. No Spike data may fill DUT
observations. Errors discard the native instance. Ordinary adapters continue
to boot from reset and reject checkpoint requests unless capability is present.

For VexRiscv, add the plugin beside `VexTop`, without editing upstream core
sources. It must control fetch hold/redirect, clear pipeline valid state and
expose typed CSR and register-file storage access. `RegFilePlugin` has a SYNC
memory; `CsrPlugin.csrMapping` includes computed fields and write callbacks.
Do not assume every readable CSR mapping is writable storage. The implementation
must prove the fetch release and CSR bindings with native tests. If those hooks
cannot be added safely in the adapter, stop and file a VexRiscv hook proposal.
Never replace restore with a reset-prefix replay and call it transfer.

BOOM needs a core-side hook. Its proposal must cover committed rename-map and
physical register state, free list reconstruction, empty ROB/LSQ/store buffers,
PC/privilege/CSRs, FP state and invalidation of caches/TLB/predictors. Default
hardware builds must omit it. A drained, architecturally exact boundary is
required. Do not expose raw physical-register indices in the portable format.

## Contracts C1 through C9

All extensions below remain proposed until implementation edits the canonical
contract in the same commit.

| Contract | Proposed integration |
|---|---|
| C1 | Add `--checkpoint DIR --warmup-instructions W --measure-instructions L`; require checkpoint-capable adapter and trace capture. Replay preserves captured identity and exact window. Keep existing status enum: bounded sample completion uses `inconclusive: sample_only`, with `details.checkpoint.sample_complete=true`. It must not earn program PASS or ordinary gate accept. A separate verification report gives the bounded cosim outcome. |
| C2 | Add an optional header `start_state` with checkpoint ID, K and initialization policy. Add `sample_complete` as an explicit end reason before enabling it in a producer. Retain full warm-up and measured trace. Define complete-sample semantics in parser and checker together. Bind verification to C1, start state and complete C2 digest. |
| C3 | Store checkpoint ID and window with each sample result. Refuse normal reset-run cache reuse. Bounded sample completion is not a passing suite test. |
| C4 | Keep sample-only runs inconclusive for functional gates. Performance aggregation requires compatible workload/window identity and separately qualified correctness and bias evidence. |
| C5 | Bundle manifest, pages, platform, C1/C2 and restore diagnostics. Reduction cannot rewrite the checkpoint without a new ID and revalidation. |
| C6 | No database schema change. Optional restore signal bindings stay in core-owned adapter code and source metadata. |
| C7 | Later expose capture, verify and sample reports with existing job cancellation. No MCP tool is needed for the first native increment. |
| C8 | Capture manifest, pages, ELF, platform, profile inventory, toolchain/shim and adapter/native inputs once. Bind seeds, memory latency and window counts into cache and replay identity. Incomplete capture refuses reuse and match publication. |
| C9 | Store sample index, phase weight, window, measurement counters and bias report references. Do not compare a sampled RTL IPC to whole-program model IPC. Aggregate CPI by instruction weights; derive IPC as the inverse weighted CPI. Partial phase coverage remains explicit. |

A proposed `rvw.checkpoint-verification/1` report carries checkpoint ID, original
oracle identity, imported-reference identity, C1/C2 hashes, requested N, checked
retirements, trap events, trace completeness, restore readback comparison,
synchronization count, mismatch location and scope. `match` requires exact N,
complete sample end, correct initial PC/state, matching effects and zero
synchronizations in the first profile. Never infer initial state from the first
DUT instruction. Missing readback or a truncated suffix is `inconclusive`.
A known, observed difference is `mismatch`. Invalid inputs are errors.

## Warm-up bias protocol

Let S be the fixed measurement start and L the fixed window length. For each
warm-up W, capture at K=S-W. Restore and run W instructions, then measure the
same interval [S,S+L). Clipping at program start must record the actual W.
Do not vary W from one fixed checkpoint and compare different program regions.

Run a from-reset RTL baseline through S+L on the same core and memory settings.
Compare architectural suffixes first. For each W report:

- `CPI(W) = measured_cycles(W) / L` and `IPC(W) = L / measured_cycles(W)`.
- `bias_pct(W) = 100 * (CPI(W) / CPI(reset_baseline) - 1)`.
- Raw cycles, retired counts and available cache-miss and branch-mispredict
  counts per instruction. Record unavailable counters as null with a reason.
- Paired seed results for randomized memory timing. With fixed latency, state
  the deterministic setting. No confidence claim comes from one execution.

Start the bounded experiment with W in {0, 100, 1000, 10000}, S >= 10000 and a
fixed L. These are experiment inputs, not a claimed sufficient warm-up length.
Report signed and absolute bias per sample. State a preselected error target
(for example 2% absolute CPI bias) before choosing W. Record failures too.
If the from-reset baseline is unavailable, report `bias: inconclusive`.
A larger W is a sensitivity comparison, not an independent bias oracle.

The current VexRiscv configuration has no caches and STATIC prediction. It can
validate window boundaries and pipeline startup cost. Cache and learned
predictor bias are `not_applicable` on this configuration. Quantifying those
requires a cached/predictor-equipped adapter or BOOM after its hook exists.
Until then, no cache/predictor warm-up qualification is claimed.

## Acceptance tests

| Test | Required result |
|---|---|
| Missing pages, bad hash, wrong ISA/platform/CSR inventory, FP omission, overlap, nonzero x0 | Refuse before DUT state changes. |
| Enabled translation, devices, interrupt, reservation, debug or unsupported privilege in first profile | Explicit unsupported-state error. |
| Original Spike continuation versus fresh imported Spike | Equal initial state and N effects, including RAM updates. A corrupted GPR, CSR or RAM byte must cause failure. |
| Native Spike to VexRiscv restore | Nonzero K, saved PC differs from reset, exact readback, N=W+L matching retirements and zero synchronization. Check against original Spike continuation. |
| Mutation of restore binding or next PC | Readback failure or first suffix mismatch. Never a match from checking a shorter prefix. |
| W=0, W=1, exact boundary, early termination and timeout | Correct counters and sample end; incomplete windows are inconclusive. |
| Same restore twice, including server use | Fresh native and harness state; identical architectural suffix for fixed inputs. |
| Ordinary ELF run | Existing reset, tohost and trace behavior remains unchanged. |
| Warm-up sweep | Fixed [S,S+L), baseline equality, explicit unavailable counters and raw bias values. No invented cache result on uncached VexRiscv. |

Add failing tests before each implementation step. Native tests must exercise
actual imported Spike and actual VexRiscv RTL; fixture tests cannot replace them.
Use `scripts/with-lock.sh vex nice -n 10` for Vex jobs and the nested `sbt` lock
for compilation. Run targeted Python tests only. Save measured results in the PR
or issue comments, not in repository evidence files.

## Risks and phased delivery

1. Implement the profile, strict bundle capture and Spike export/import first.
   Hidden CSR effects and counter write semantics are the main oracle risk.
   Verify against the original Spike continuation, not only two imported copies.
2. Implement the generic C1 request, adapter restore port and VexRiscv plugin.
   Publish a real native N-instruction match with negative restore tests.
   Do not promote a parser-only or generated-trampoline fixture as this slice.
3. Add measured fixed-window warm-up reporting. Use from-reset RTL baselines.
   Qualify caches and learned predictors only on a suitable core.
4. Add FP, S/U privilege, translation and device snapshots as separate profiles.
   Restore page-table RAM before enabling satp; flush TLBs. Restore interrupt
   controllers, timer state, deadlines, stimulus position and device PRNG state
   under one checkpoint ID. Refuse live host I/O without an exact replay model.
5. Implement the BOOM hook in its own repository after review. Add QEMU only
   through a versioned architectural-state exporter. QEMU migration images are
   not presumed portable. Multi-hart transfer requires a separate global cut
   and memory-order contract.

The first native increment is still required. A design commit alone does not
complete the hard research-and-build task. Follow-up issue links are added below.
