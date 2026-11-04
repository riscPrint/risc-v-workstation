# Trace-driven component simulators

## Goal and first increment

Build native component models for branch direction, BTB/RAS, prefetch and cache
replacement studies. Feed them with pinned workload traces. Report each workload
separately. Compare models with an independent reference and, when available,
with explicit RTL events. Model results do not establish RTL correctness or IPC.

The first working increment is a native C++17 direction simulator with bimodal,
gshare and perfect-direction models. It consumes a small checked text format.
A Python adapter reads successful `rvw workloads verify --trace` Spike reports.
It binds the input log and report hashes. It rejects ambiguous branch outcomes.
This increment is a subset of the requested first slice. TAGE-SC-L, BOOM-like
configuration and independent published-trace qualification remain open work.

## Prior art and source inspection

- [ChampSim module API](https://champsim.github.io/ChampSim/master/Modules.html)
  separates direction, target, prefetch and replacement modules. It uses native
  C++ objects. Its CPU/cache pointers make direct reuse larger than a standalone
  component runner. Keep an adapter boundary rather than copy its CPU model.
- [ChampSim license](https://github.com/ChampSim/ChampSim/blob/master/LICENSE)
  is Apache-2.0. This is source evidence, not a legal compatibility decision.
  Root license selection remains owner issue #37. No ChampSim source is copied
  into this increment. Review each imported predictor's terms before reuse.
- [Seznec, CBP 2016](https://jilp.org/cbp2016/paper/AndreSeznecLimited.pdf)
  specifies TAGE-SC-L: geometric tagged histories, a statistical corrector and
  loop prediction. A plain TAGE model must not be labelled TAGE-SC-L.
- [gem5 TAGE-SC-L implementation](https://github.com/gem5/gem5/blob/stable/src/cpu/pred/tage_sc_l.cc)
  is another reference for state/update rules. Pin the revision and model size
  before differential testing. Do not compare unlike configurations by name.
- Local `rvw/src/rvw/workloads/core.py:verify` already retains Spike `-l` logs,
  ELF hashes, oracle identity, expected-output checks and timeouts. Its profile
  module counts branch transitions, not predictor misses. Reuse that evidence.
- `examples/boom/arch/small.json` contains project TAGE sizes and history limits.
  `Arch/README.md` describes its LTAGE approximation. That description is not a
  faithful BOOM predictor specification. The read-only core files
  `ifu/bpd/tage.scala`, `bim.scala` and `common/parameters.scala` define additional
  banking, history, metadata and update rules. No core changes are needed here.
- Related issues: #282 (workloads), #12 (model fitting), #49 (RTL events).
  No current event contract supplies branch prediction outcomes. Absence means
  `rtl_comparison=inconclusive`, not zero misses or a match.

## Architecture

Keep three layers:

1. Capture adapters turn verified source traces into ordered component events.
   They retain workload, ELF, input, oracle and source identities.
2. A native engine owns predictor state. For each conditional branch it predicts
   before training, counts the error, trains, then updates history. Reset state
   between workloads. Bimodal uses two-bit saturating counters initialized to 1.
   Gshare XORs shifted PC with the prior conditional direction history.
3. A report adapter records raw counts, MPKI, warmup, input hashes and engine
   identity. It never emits C4 accept. Future CLI/MCP bindings share this layer.

The current execution policy is sequential actual-path training. It has no
speculative history, wrong-path events, fetch width, recovery or update delay.
History includes conditional branches only. PC shift is explicit (default 1 for
RISC-V halfword alignment). Do not substitute this model for a BOOM timing model.

Warmup uses an instruction ordinal cutoff. It trains state but excludes both
misses and instructions from the measured ROI. MPKI is
`1000 * direction_misses / measured_instructions`, not misses per branch.
Keep workload values separate. Any later aggregate must name its weighting.
The perfect-direction model reads the actual outcome. Zero direction MPKI is an
unattainable-information accuracy bound. It gives no cycle or speedup bound.

## Interfaces and C1-C9

| Contract | Use and boundary |
|---|---|
| C1 | Future RTL comparisons require a conclusive run, matching ELF and ROI. This tool does not create a C1 pass. |
| C2 | Future import must check hart/order/traps and explicit next PC. A retirement trace has no wrong-path history. |
| C3 | Component reports stay outside suite pass totals until an explicit adapter exists. |
| C4 | Reports use `reported`; incomplete evidence is an error or inconclusive comparison. No gate verdict. |
| C5 | Reports and raw traces can be bundle attachments. No bundle schema change is needed now. |
| C6 | Core sizes can come from project data or database queries. Signal names stay in project bindings. |
| C7 | Later cancellable jobs use the shared process supervisor. No MCP API in this increment. |
| C8 | Hash trace, configuration, engine and source evidence. This is local stable-input evidence, not complete hermetic capture. |
| C9 | Add component-specific schemas. Do not fabricate gem5 cycle/IPC reports or calibration fidelity. |

`rvw.branch-trace/1` has a header, conditional-branch rows and an explicit footer.
Instruction ordinals count all logged instructions. Require one hart, ordered
ordinals, a positive instruction count and an unambiguous direction per row.
The standalone adapter accepts only successful Spike workload verification with
matching log hashes and complete branch transitions. It includes startup and
checker code. It does not infer an ROI or sampling weight.

Future project configuration must name its model kind, revision, storage,
history lengths, tag widths, hashing, allocation/aging, loop/SC settings,
update policy and reset policy. Record the effective configuration in reports.
Refuse unknown knobs. BOOM-specific translation belongs under `examples/boom/`.
A configuration marked approximate cannot yield an RTL fidelity claim.

## Acceptance tests

- Native compiler builds the engine without containers or network downloads.
- Hand-derived traces check counter saturation, index aliasing, PC shift,
  alternating and correlated branches, prediction-before-update and reset.
- A separate scalar test oracle checks bimodal/gshare over deterministic traces.
- Warmup checks both numerator and instruction denominator, including no-branch
  intervals. Empty measurement regions, malformed/incomplete input and unknown
  models must fail without a result object.
- Spike adapter tests include compressed branches, multiple harts, traps,
  ambiguous target/fallthrough, terminal branches and changed evidence hashes.
- TAGE-SC-L later needs pinned independent per-branch predictions and internal
  state checks for allocation, aging, loop confidence and SC override. Test
  published reference traces under identical storage and history policies.
- RTL event comparison later requires ELF/ROI/ordinal alignment and matched
  counter semantics. Missing events produce inconclusive. Inject a difference
  and require a mismatch. Retirement direction alone cannot validate speculation.

## Risks and phases

1. Native baseline engine and verified Spike adapter. Validate small reference
   traces; document sequential-training limits. No workload-performance claim.
2. Qualify TAGE-SC-L against a pinned reference. Resolve imported-code terms
   through #37 first, or implement from the paper and keep differential checks.
   Add BOOM-like project settings with explicit approximation differences.
3. Add RTL direction/target event bindings under #49. Measure alignment and
   mismatch counts. Keep unavailable signals and speculative effects explicit.
4. Add BTB/RAS, with call/return classification, target accuracy and context rules.
5. Add memory-event traces, replacement and prefetch models. Include address
   space, line size, access type, latency/queue assumptions and pollution counts.
   A perfect prefetcher needs explicit capacity, bandwidth and timeliness rules;
   an unbounded future-address oracle is only an accuracy bound.

Trace storage can dominate execution. Stream rows; do not load full logs.
Source logs can contain traps or non-retired events. Refuse uncertain direction
rather than convert a discontinuity into a taken branch. Trace distributions,
warmup, sampling and address layout limit conclusions. Never report speedup
from MPKI alone. Licensed workload data stay outside this repository.

## Follow-up issues

- #351: [TAGE-SC-L and BOOM-like settings](https://github.com/riscPrint/risc-v-workstation/issues/351).
- #358: [explicit RTL event comparison](https://github.com/riscPrint/risc-v-workstation/issues/358).
- #360: [BTB and RAS](https://github.com/riscPrint/risc-v-workstation/issues/360).
- #365: [prefetch and cache replacement](https://github.com/riscPrint/risc-v-workstation/issues/365).

This design and the baseline increment are in draft PR #336. These issues own
remaining phases. The baseline does not complete the requested TAGE-SC-L slice.
