# Own core performance model

## Goal and scope

Build a native, trace-driven timing model of the selected core's own pipeline.
The engine does not use gem5. Target at least 50 times the RTL simulation rate.
This is a target, not a measured result. Use a generic small OoO configuration
for initial model tests. Do not use VexRiscv as an OoO calibration target.
Keep all BOOM settings, signal maps and fitted values in the core project.
No core source changes are part of this work.

The first increment models fetch buffering, rename dependencies, ROB capacity,
oldest-ready issue, load and store queue capacity, execution latency, and ordered
commit. It consumes complete C2 traces. Spike producers must first export C2.
Fixed latency and conservative memory order are explicit approximations.
It must reject unsupported instructions and incomplete traces.

## Research and existing code

- [ChampSim](https://github.com/ChampSim/ChampSim) is an open trace-driven
  simulator. Reuse its staged timing approach as prior art. A separate small
  engine gives direct control over Spinal configuration and event contracts.
  Do not copy its code or choose a new project license here.
- [Interval simulation](https://snipersim.org/w/Interval_Simulation) abstracts
  instruction timing into miss intervals. It is a later optimization candidate.
  Start with individual instructions to expose resource and dependency errors.
- [Correct Wrong Path](https://arxiv.org/abs/2408.05912) describes timing effects
  lost with committed-path traces. Do not claim that a fixed branch penalty
  reconstructs wrong-path cache pollution or resource use.
- `rvw/common/riscv.py` provides operand decoding. `rvw/cosim/trace.py`
  validates C2 and its terminal marker. Reuse both.
- `rvw/arch/core.py`, `Arch/README.md` and C9 already provide gem5 fitting,
  event correlations, repeated measurements and a prediction ledger (#12).
  Their gem5-specific evidence checks cannot certify this engine.
- `SpinalKonata/README.md` distinguishes physical commits from architectural
  retirement. Match C2 order IDs only where the adapter establishes the mapping.
- Core configuration exists in `boom/common/parameters.scala`: widths,
  issue queues, ROB, LDQ, STQ and fetch buffering. Presets can override defaults.
  Reading Scala defaults alone is not configuration extraction.

## Architecture

Keep the engine under `rvw/ooo/`. Keep usage and limits in its README.
A project-owned exporter will emit the effective elaborated configuration.
Every modeled field will carry its source path, source revision and expression
or extraction key. Predictor, cache, TLB and memory settings must be exported,
including fields the current engine does not support. Unknown fields must not
silently select defaults. Comparison must report unsupported structures.

Phase 1 takes an explicit generic configuration file. It is an experiment,
not an independently checked core model. No presets or BOOM fitted values are
bundled. A source-check adapter is required before the report can claim that
its configuration matches a core.

Within a cycle, commit completed instructions, issue oldest ready instructions,
rename fetched instructions, then fetch. Execution finishes after the declared
latency. Rename binds each source to its latest older writer. Integer x0 has
no writer. Issue slots release on issue. ROB and memory slots release at commit.
Memory instructions issue in program order after earlier memory completion.
This is conservative and does not model store forwarding or replay.

Initial metrics are cycles, architectural instructions, IPC, resource-full
rename stall cycles, dependency-blocked issue cycles, and maximum occupancies.
A stall counter names the exact sampling phase and predicate. Counters can
overlap. They must not be added to reconstruct elapsed cycles.

## Interfaces and C1 through C9

| Contract | Use and boundary |
|---|---|
| C1 | RTL remains the timing reference. Require conclusive results, bound ELF and source identity, exact ROI and trace artifact hashes. A successful model run is not a successful RTL run. |
| C2 | Validate complete single-hart input. Preserve order, PC, operands and memory addresses. Ignore RTL cycle values when predicting. Reject traps, interrupts, unsupported operations and incomplete termination in phase 1. |
| C3 | Do not inject model predictions into measured regression metrics. |
| C4 | Produce no correctness or gate verdict. |
| C5 | Link later correlation diagnostics to original artifacts. Do not synthesize core failures from model error. |
| C6 | Use the future effective configuration export with source identity. Database presence alone does not establish timing semantics. |
| C7 | Add cancellable model jobs after the CLI and report contracts stabilize. |
| C8 | Capture configuration, trace, engine and event-map hashes. Do not claim complete C8 evidence from local files alone. |
| C9 | Add a distinct timing-model report. Keep existing gem5 schemas and evidence checks intact. Reuse formulas and fitting mechanisms only after engine-neutral identity checks exist. |

`rvw ooo CONFIG TRACE --max-cycles N --json` is the first interface.
CONFIG is explicit JSON. A report uses `rvw.ooo-run/1` and records config,
trace and engine hashes, exact stage semantics, cycles, IPC, event counters,
occupancy, host wall time, and `accuracy_status=inconclusive`.
The cycle budget bounds a model hang. It is not an RTL timeout.

Future `rvw.ooo-events/1` records cycle, event name, count, ROI and order ID
where applicable. Each event map defines unit, sampling edge, denominator,
physical versus architectural identity and aggregation. Missing mappings are
inconclusive. Never use held-out RTL stalls as prediction inputs.

## Calibration, correlation and ledger

Use disjoint training and held-out workload hashes. Include dependency chains,
independent ALU work, pointer chase, independent loads and branch loops. Reject
overlap by ELF and trace hashes. Fit only declared latency and penalty ranges.
Do not fit structural sizes away from exported hardware values.

Freeze the engine, configuration, fit, event maps and split before held-out RTL.
Record predictions in exclusive files with UTC time and input hashes. Score in
separate files bound to the prediction hash. Local timestamps provide ordering,
not trusted proof of blinding. Retain raw evidence outside the repository.

For every held-out workload report signed and absolute cycle and IPC errors.
For each event report absolute error, relative error when RTL is nonzero, and
Pearson correlation across at least three nonconstant workload samples.
Zero reference values and constant samples need explicit treatment. Correlation
alone does not establish event accuracy. No aggregate may hide a failed workload.

Initial proposed accuracy budget: at most 10% absolute IPC error per held-out
workload and 15% relative error for each mapped nonzero event. Report zero-event
false positives separately. These are acceptance targets, not evidence.
Require at least five held-out workloads and three event families before any
bounded fidelity statement. Label all unsupported events and configurations.

Measure model wall time including C2 parsing. Compare against warmed native RTL
simulation for the same instruction ROI, host and trace settings. Report model
startup, trace capture and build cost separately. Use at least three repeats,
medians, individual times and host/tool identity. Claim 50x only if each selected
held-out workload meets it. Do not use synthetic tests to claim RTL speedup.

## Acceptance tests

1. Hand-computed small schedules cover dependency latency, independent issue,
   WAW renaming, x0, ROB, issue and LSQ backpressure, and ordered commit.
2. Negative cases reject invalid sizes, unknown config keys, unsupported opcodes,
   traps, multi-hart input, missing end markers and exhausted cycle budgets.
3. Mutating only C2 cycle timestamps does not change predictions.
4. Configuration export tests detect changed widths, queues, predictor and cache
   settings. No tuned core values enter this repository.
5. Bounded BOOM small runs establish equal ELF/ROI identity and mapped events.
   Report IPC errors and each event error on held-out workloads.
6. The frozen prediction ledger rejects changed inputs and split overlap.
7. Repeated native timing establishes speed and accuracy together.

## Risks and phases

Python may miss the throughput target. Profile before choosing a native kernel.
A retired trace omits wrong-path instructions, replay and speculative accesses.
Flat issue queues and conservative memory order can cause systematic error.
Fetch width measured in instructions can differ from hardware packet width.
FP, vector, atomics, fences, privileged code, devices and multi-hart need explicit
semantics before support. Warmup and ROI entry state can dominate short runs.

- Phase 1: tested generic trace-driven pipeline and honest report contract.
- Phase 2: effective configuration export/check and predictor/cache modules.
- Phase 3: generic calibration and held-out RTL event correlation, with bounded
  BOOM small runs in project data. No VexRiscv OoO calibration.
- Phase 4: frozen prediction ledger, repeated timing and the joint speed/accuracy
  acceptance. Optimize only after profile evidence identifies the bottleneck.

Follow-up issue links will be added after the first working increment.
