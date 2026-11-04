# RISC-V decoupled front end in gem5

## Goal and scope

Issue [#72](https://github.com/riscPrint/risc-v-workstation/issues/72) stays an epic.
The first slice runs the existing gem5 BAC and fetch target queue (FTQ) with
RISC-V O3. It tests mixed 16-bit and 32-bit instructions. It does not model an
Apple or AMD core. Core parameters remain project data.

## Research and prior art

The pinned release is gem5 v25.1.0.1, commit
`c8222cc67a399bfc01e8658dd14b30d5bfd634f9`.
Inspection corrects three assumptions in the epic:

- `src/cpu/o3/bac.cc`, `ftq.cc` and `fetch.cc` already implement a decoupled
  predictor and FTQ. `BaseO3CPU.py` disables it by default. BAC searches BTB
  addresses without waiting for demand fetch. FTQ stores start, end, predicted
  next PC, sequence number and branch history. Fetch consumes these targets.
- `mem_dep_unit.hh` already uses store sets for memory dependence prediction.
  This is distinct from memory renaming. Neither proves wide-core fidelity.
- `BaseO3CPU.py` defaults to eight-wide rename. `limits.hh` permits width 16.
  A width of ten needs validation, not a second rename implementation.

MinorCPU splits line fetch (`fetch1.*`) from decode and prediction (`fetch2.*`).
Its stream and prediction sequence numbers reject stale responses. Its line
queues are not a predictor-ahead O3 FTQ. Reuse O3's existing implementation.

[Reinman, Calder and Austin, MICRO 1999](https://cseweb.ucsd.edu/~calder/papers/MICRO-99-FDP.pdf)
introduce predictor-ahead fetch targets and fetch-directed prefetching.
[Schall's gem5 FDP implementation](https://github.com/dhschall/gem5-fdp)
is the direct open implementation reference.
[The 2023 gem5 workshop model](https://www.gem5.org/assets/files/workshop-isca-2023/slides/modern-front-end-support-in-gem5.pdf)
uses an eight-wide model with an FTQ. Its ARM and x86 results do not validate RISC-V.
[XiangShan's published model](https://github.com/OpenXiangShan/GEM5/blob/xs-dev/ARCHITECTURE.md)
uses a separate predictor-ahead subsystem and fetch stream queue. It is useful
prior art for later multi-level BTBs. Importing its entire fork is outside this slice.

## Architecture and interfaces

Use existing scalar `cpu` parameters in `rvw.arch-core/1`:
`decoupledFrontEnd=true`, `minInstSize=2`, positive `numFTQEntries`, and
`fetchTargetWidth >= fetchBufferSize`. Use one hart. Keep the default coupled
mode unchanged. Refuse invalid decoupled settings before native execution.
No new predictor, pipeline queue or external dependency is needed.

BAC can find a cached 32-bit branch at a two-byte search step. Its fallthrough
must use the cached instruction length, not the search step. Test this path
before proposing a small generic upstream fix. An untrained region still uses
the search step; demand fetch handles target correction and branch discovery.
Preserve gem5's sequence numbers, branch history ownership, squash and retry paths.
Do not add an architectural success verdict from FTQ activity.

## Contracts C1-C9

C1 RTL execution is unchanged. C2 RVFI is unchanged. C3 regression and C4 gate
verdicts are unchanged. C5-C7 analysis interfaces are unchanged. C8 retains its
stable-input threat model and current C9 capture limits. C9 keeps its schema,
binary hash, copied description and ELF hash. Document the extra scalar
constraints in C9. Counters describe the model only. A complete tohost exit,
two ROI markers and positive ROI counts remain required. Record raw gem5
FTQ/BAC counters in native test output. Never infer a hardware speedup.

## Acceptance tests

1. Reject zero FTQ capacity, wrong RISC-V search step and an undersized target.
2. Build and run a mixed-width branch microbenchmark on the pinned native gem5
   under `scripts/with-lock.sh gem5 nice -n 10`. Select it with `RVW_GEM5`.
3. Compare coupled and decoupled runs on identical ELF bytes. Both must exit
   correctly and retire equal ROI instructions. Coupled mode must have no FTQ
   inserts. Decoupled mode must have inserts and removals.
4. Check a known 32-bit not-taken branch with a two-byte search step. Show a
   regression before any upstream fix. Run targeted Python contract tests.
5. Report actual results in the PR. A build or run not executed stays NOT RUN.

## Risks and phased plan

Compressed instructions make address-step and instruction-length errors likely.
Cold BTBs can cause fetch corrections. FTQ depth alone need not improve IPC.
This slice does not enable FDIP requests or promise lower cache miss rates.
Native tests must not treat any nonzero FTQ activity as cycle accuracy.

Phase 1 exposes and checks the existing RISC-V FTQ path, adds the benchmark,
and fixes a reproduced mixed-width defect if needed.
Phase 2 adds multi-level BTB and FDIP experiments with capacity and latency tests.
Phase 3 adds a micro-op cache with invalidation and compressed instruction tests.
Phase 4 studies memory renaming and validates widths eight and ten with resource
sweeps. The bounded follow-up issues are:

- [#357: multi-level BTB and FTQ-directed prefetching](https://github.com/riscPrint/risc-v-workstation/issues/357).
- [#359: micro-op cache](https://github.com/riscPrint/risc-v-workstation/issues/359).
- [#362: wide rename and memory renaming](https://github.com/riscPrint/risc-v-workstation/issues/362).
