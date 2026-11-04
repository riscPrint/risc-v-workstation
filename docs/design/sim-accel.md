# Faster RTL simulation

## Goal and first slice

Epic: [#295](https://github.com/riscPrint/risc-v-workstation/issues/295).
Measure BOOM medium with the existing C1 adapter. Compare one, two and four
Verilator runtime threads on a long deterministic ELF. Keep the current default.
Offer a measured winner only as an explicit opt-in. A candidate must have
bit-identical complete C2 files, equal terminal results, and a paired speedup
95% confidence interval whose lower bound exceeds one. If no candidate meets
these conditions, retain no option. A failed build or missing tool is inconclusive.
This is a bounded first slice. It does not establish commercial parity.

## Prior art and existing code

- [Verilator runtime guidance](https://verilator.org/guide/latest/simulating.html)
  describes runtime threads, thread PGO, compiler PGO and save/restore.
  Thread PGO and compiler PGO are separate training and rebuild steps.
- [Hierarchical Verilation](https://verilator.org/guide/latest/verilating.html#hierarchical-verilation)
  compiles marked hierarchy blocks separately. It can reduce build cost.
  It can also reduce runtime speed. It is not the same as output splitting.
  Cross-boundary access to internal signals is restricted.
- [Verilator options](https://verilator.org/guide/latest/exe_verilator.html)
  define the flags. Check the installed binary before choosing a protocol.
- [circt-verilog](https://circt.llvm.org/docs/Tools/circt-verilog/)
  uses the slang frontend and needs a build with that frontend enabled.
- [Arc dialect](https://circt.llvm.org/docs/Dialects/Arc/)
  supports Arcilator lowering to LLVM. A compiler result alone cannot establish
  that the memory model, clock schedule or RVFI observations match RiscvSim.

Reuse `rvw/src/rvw/sim/speed.py` for paired execution and bootstrap intervals.
Reuse `RiscvSim/boom/run.sh`, the native input collector and its cache receipts.
Reuse `RiscvSimConfig`, `Driver` timing and the C2 reader. Do not create a second
BOOM harness. The existing comparison checks parsed C2 event equality. This
slice must add an explicit raw-file equality requirement for bit identity.
The native collector accepts bounded numeric thread and output-split flags.
It refuses PGO profile files, hierarchical control files and opaque wrappers.
Do not bypass those refusals to obtain a performance result.

## Architecture

The experiment runner owns the treatment list, warmup, alternating pair order,
process budgets and evidence paths. The adapter owns RTL generation and native
execution. Generic comparison code must not contain BOOM names or presets.
Put workload and preset choices in the BOOM example or experiment invocation.

Phase 1 uses the existing `SPINAL_VERILATOR_FLAGS='--threads N'` opt-in.
Each treatment keeps one native identity. Set build parallelism explicitly and
keep it fixed. Disable waves, coverage and Konata for throughput comparisons.
Keep complete C2 tracing enabled on both sides. Rates therefore include trace
cost. Separate trace-free rates require a later protocol and independent checks.

Phase 2 adds captured immutable profile and partition inputs to native identity.
A profile record includes file bytes, hash, source RTL hash, compiler identity,
training workload hashes and exact flags. Reject stale training data and
`PROFOUTOFDATE`. Bump the native namespace when capture changes. Use a separate
work directory for each training and optimized build. Never accept an arbitrary
file flag through the existing numeric flag parser.

Phase 3 adds an alternate backend at the adapter boundary. Lower the captured
Verilog through circt-verilog and Arcilator. Keep the same reset, memory latency,
interrupt schedule, tohost behavior and C2 fields. Define native accessors for
clock, reset, memory ports and RVFI ports. Test initial state and memory behavior
before the long ELF. Do not map unsupported operations to constants.

Phase 4 adds live snapshots through a native bridge API. `--savable` is only the
DUT serialization part. Save scheduler time, clock phase, sparse memory,
outstanding transactions, RNG, device state, interrupts, RVFI order, monitor
state and counters at a quiescent boundary. Restore in a fresh process.
Version the envelope and bind it to RTL, native build, harness and stimulus
identities. Reject external effects and unsupported devices. Existing
from-reset replay descriptors remain a separate operation.

## Interfaces and contracts

| Contract | Rule |
|---|---|
| C1 | Preserve run fields and statuses. Compare conclusive serial passes with equal seed, ELF, preset, stimulus, cycles and instret. Keep execution time separate from build and lock time. |
| C2 | Validate full streams and end records. Require raw SHA-256 equality for this slice in addition to parsed equality. No field stripping can earn bit identity. |
| C3 | Keep source and native identities. Do not publish an experiment as a regression suite pass. |
| C4 | Speed retention is diagnostic. It cannot grant gate acceptance or prove ISA correctness. |
| C5 | Keep failed build logs and reproducer inputs outside Git. Link blocker evidence from the PR. |
| C6 | Partition selection may inspect module hierarchy. A database match is not simulation equivalence. |
| C7 | Reuse current CLI and JSON interfaces. Add an MCP interface only with real CLI behavior. |
| C8 | Capture new input files before use. Missing inputs refuse reuse. Use committed harness sources and verified native receipts. |
| C9 | Report RTL throughput separately from architecture-model trends. Do not use gem5 as an RTL correctness oracle. |

Extend `rvw.sim-speed/1` additively with absolute baseline and candidate kHz
intervals and a raw C2 equality claim. Document fields in PLATFORM_CONTRACTS.md
in the same commit. Preserve existing speedup fields and conservative retention.
A later selection file must identify core, preset, host, native toolchain,
workload set and evidence hashes. It must fail closed outside that scope.
No automatic host-wide tuning or default change is proposed.

## Measurement and acceptance tests

1. Use the machine `boom` lock and `nice -n 10`. Hold `sbt` inside BOOM jobs.
   Bound each launch to at most 1800 seconds, including lock wait and build.
   Stop after a failed or timed-out launch. Save the command and observed cause.
2. Use a deterministic long loop with memory operations and a tohost pass.
   Fix seed and memory latency. Set a cycle limit and wall limit. First run a
   bounded calibration to select a duration of at least 10 seconds per sample.
   Prefer 30 seconds when the host budget permits. Never lower the duration
   threshold after seeing a candidate result.
3. Warm each treatment once. Exclude warmups from estimates. Run at least five
   fresh-process pairs. Alternate AB and BA order. Record load and run order.
   Pair-level bootstrap assumes independent pairs. Shared-host interference
   limits inference even while the BOOM lock excludes other BOOM jobs.
4. Validate C1 and C2 on every sample. Reject missing ends, wrong terminal
   counters, byte differences, reused execution IDs and changing native hashes.
   Mutation tests must fail before these checks are added.
5. Report absolute kHz and paired geometric speedup with bootstrap 95%
   intervals. Keep resample count and random seed. Do not pool presets or ELFs.
   Compare each candidate independently. Require a fresh confirmation campaign
   for a selected winner to avoid selection bias across many treatments.
6. Run a separate reference-model check on the complete workload. Trace equality
   only means agreement between simulator treatments. Keep ISA scope explicit.
7. Wire only a confirmed winner into an opt-in BOOM example. If none qualifies,
   document that no configuration was retained. Do not label an unmeasured option
   as best. Test that ordinary invocations keep their current behavior.

Later acceptance adds BOOM large, memory-heavy and branch-heavy workloads,
peak RSS, cold/warm build time and amortization. Profile training must differ
from held-out evaluation. A snapshot must match the uninterrupted C2 suffix and
terminal counters in a fresh process. Corrupt, stale and partial snapshots must
be refused. An Arcilator result must pass the same tests as Verilator.

## Risks and upstream blockers

The Scala/native bridge can dominate runtime and hide RTL thread gains.
Hierarchy boundaries can block access to internal simulation signals.
A native thread speedup on BOOM medium does not predict BOOM large behavior.
Snapshot DUT state alone omits harness state and can give false equivalence.
CIRCT lowering may reject generated memories, asynchronous resets or assertions.
These are risks until a reproducer establishes a specific failure.

Draft upstream reports only after reproducing a tool defect. Include exact
version/commit, host, minimal RTL, command, expected behavior, actual diagnostic
and a reference result. Keep drafts in the PR body. Do not post upstream.
A missing local tool or missing Spinal bridge feature is not a Verilator/CIRCT bug.

## Phased plan

- Phase 1: strict comparison, absolute rate intervals, bounded BOOM medium run,
  reference check and confirmed opt-in if a candidate qualifies.
- Phase 2: captured PGO and partition inputs; held-out BOOM medium/large trials.
- Phase 3: native circt-verilog to Arcilator adapter and complete C2 comparison.
- Phase 4: live snapshot bridge, full harness envelope and restore validation.

Follow-up issue links are added when the draft PR is open. Measurement output
belongs in the PR or issue comments. It must not be committed as a run ledger.
