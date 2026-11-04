# Compiler scheduling models

## Goal

Generate LLVM TableGen `SchedMachineModel` and GCC pipeline descriptions from
project data. Measure dependent and independent instruction streams on RTL.
Report signed cycle errors for each instruction class. An error report is not
a correctness verdict. Do not infer instruction latency from whole-program CPI.

## Prior art

- [LLVM scheduling interfaces](https://github.com/llvm/llvm-project/blob/main/llvm/include/llvm/Target/TargetSchedule.td)
  separate result latency, resource occupancy, unit count and issue width.
- [llvm-mca](https://llvm.org/docs/CommandGuide/llvm-mca.html) simulates a compiled
  target scheduling model. It does not load a TableGen file at runtime. A generated
  model needs target registration and an LLVM rebuild before MCA can test it.
- [llvm-exegesis](https://llvm.org/docs/CommandGuide/llvm-exegesis.html) uses serial
  streams for latency and parallel streams for inverse throughput. Reuse this
  method with C1 RTL instead of executing RISC-V code on the host Mac.
- [GCC pipeline descriptions](https://gcc.gnu.org/onlinedocs/gccint/Processor-pipeline-description.html)
  use DFA reservations. Result latency and resource occupancy have distinct roles.
- [DiffTune](https://arxiv.org/abs/2010.04017) fits simulator parameters. Fitting is
  a later phase. First preserve declared parameters and report measured gaps.

Existing `Arch/` supports gem5 calibration with C1 ROI counters. Its queue data
cannot specify all compiler instruction mappings. Add a small compiler-specific
JSON description beside project data. Reuse `rvw arch` and process-group cleanup.
Do not add a second simulator or change core RTL.

## Architecture and interfaces

`rvw arch sched-generate DESCRIPTION --out DIR` validates explicit issue width,
resource counts, result latencies, resource occupancies and instruction mappings.
It emits a partial LLVM model and GCC include. Unknown or overlapping mappings
fail. The first version supports one resource pool per class and integral cycles.
GCC also reserves one issue slot per instruction. Multiple unit instances are
alternatives; one instruction must occupy the same instance for its full duration.
The GCC target must select this include only for its intended CPU and set its
issue-rate hook. A fragment alone is not a complete GCC target.

`rvw arch sched-measure DESCRIPTION --out DIR` builds bare-metal microkernels,
runs the selected project's C1 adapter and calls native llvm-mca. It saves source,
ELF, commands, raw C1/C2 and MCA output outside Git. Project data select config,
ISA, entry address, instruction encodings and MCA CPU. No generic core names.

Use two unrolled sizes for each dependent and independent stream. Compute RTL
cycle slopes from first-to-last retirement spans, and MCA slopes from total
cycles with one iteration. Pairing removes constant startup cost but does not
remove fetch stalls. Report both raw spans and signed percent error. Independent
streams use eight destination registers; insufficient separation remains a limit.
Never call this an isolated execution-unit latency measurement. Validate exact
PC ranges and instruction encodings. Require a complete passing C1 result.

Homebrew MCA can provide a built-in baseline. Label it `builtin-baseline`.
Generated-model accuracy stays inconclusive until a rebuilt LLVM registers the
model. Never relabel a built-in CPU as the generated core model.

## Contracts C1 through C9

- C1: reuse project adapter, fixed memory latency, seed, config and cycle bound.
  Check pass status, ELF hash and requested options. Keep raw source identity.
- C2: require complete trace and end status; reject traps, missing instructions,
  unexpected encodings, nonmonotonic cycles and missing ROI endpoints.
- C3: no suite format change. Measurement output is a separate report.
- C4: no accept/reject output. Missing evidence cannot earn a match.
- C5: retain raw paths so a failure bundle can reference them.
- C6: design database queries may inform declared resources; no inferred timing.
- C7: first CLI increment; MCP registration is a later phase.
- C8: retain hashes and tool identities. Local files follow the existing threat
  model. No claim of complete immutable generation capture.
- C9: extend architecture tooling with versioned scheduling input and output.
  Do not change gem5 schemas or treat a model error as architectural failure.

## Acceptance tests

1. Reject invalid numbers, unknown fields, overlapping instruction mappings and
   unsupported resource layouts. Keep unit occupancy distinct from latency.
2. Parse generated TableGen with native llvm-tblgen. Check GCC reservation text.
   Full GCC integration remains unverified until a target build consumes it.
3. Build and run dependent and independent integer streams on VexRiscv.
   Run BOOM small with a finite wall timeout and cycle bound under its lock.
4. Check raw C1/C2 identity and exact stream boundaries. Test missing, incomplete,
   trapped, changed and unequal evidence. Such input must fail.
5. Run llvm-mca and report per-class slopes and errors. Test a known synthetic
   error. Label stock LLVM as a baseline and generated-model accuracy inconclusive.

## Risks and phased plan

First slice: integer ALU and multiply descriptions, partial model generation,
serial RTL measurement, built-in MCA comparison and focused tests. No core edits.
VexRiscv instruction-bus waits can dominate timing. BOOM retirement can hide
execution timing. Two-point slopes do not prove linear scaling. Keep raw samples.

Next: register generated models in a pinned LLVM source build; test held-out
mixed kernels; compile GCC DFA integration; add loads, branches, bypasses and
variable-latency instructions; add repeat intervals and MCP. Use separate issues
with acceptance checklists. Follow-up issue links will be added before delivery.
