# Architecture model extensions contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## C9 compiler scheduling extension

`rvw arch sched-generate` reads `rvw.sched-core/1`. Required fields are `name`,
`config`, `isa` (rv32im or rv64im), `entry`, `issue_width`, `buffer_size`,
`resources` (identifier to instance count), `classes` and `mca_cpu`.
Each class requires `name`, `resource`, `latency`, `occupancy`, `llvm_opcodes`,
`gcc_type`, `mnemonic` and `encoding` (base RISC-V instruction word).
Cycles and counts are integers. Unknown fields, duplicate class/type/opcode
mappings and unsupported instructions fail. Occupancy is per unit instance.
The command writes partial `model.td` and `model.md` target fragments.

`rvw arch sched-measure` selects an existing project and C1 config. It builds
paired unrolled ELFs per class and mode. It requires passing C1 evidence with
matching ELF hash, core, config, seed 1 and fixed memory latency 0. C2 must end
with pass and contain every expected instruction at the exact PC and encoding.
Traps, order gaps and decreasing cycles are errors. Measurement output is
`rvw.sched-measure/1`, with `status=reported`, `model_kind=builtin-baseline`,
`generated_model_accuracy=inconclusive`, tool identities, raw evidence hashes,
per-size cycles and per-class signed slope errors. Missing evidence exits 2.
The report is local timing evidence, not a C4 verdict or complete C8 capture.
Stock llvm-mca cannot load generated TableGen. The built-in baseline does not
validate a generated model. See `Arch/SCHED_MODELS.md` for limits.

### Own-core correct-path branch overlap

`branch_speculation` is an optional boolean, default false. When enabled,
younger work can issue after an older branch's correct prediction and before
its completion. Mispredictions retain recovery stalls. Serial control rules
remain active. `correct_path_speculative_issues` counts such issues. Replay
clears younger prediction decisions. Predictor history checkpoint/restore is
not modeled. Optional front-end phase counters expose decode/fetch pressure,
and `cycle_order` includes decode when configured. Accuracy stays inconclusive.

## Own-core FP dependency timing

The own engine tracks separate integer and FP register dependency IDs. FP
operation-family classes use `fp_` plus the mnemonic prefix. FP loads/stores
retain memory classes. `physical_float_registers` is zero for unbounded
pressure or a total count of at least 33. `float_register_full` counts rename
stalls. FP destinations use decoded encoding fields, not integer C2 rd data.
This is dependency/resource timing. It does not execute FP arithmetic,
validate rounding or reproduce operand-dependent latency. Traps and vectors
remain unsupported. These streams use Python and retain inconclusive accuracy.

## Own-core non-trapping control timing

Projects can declare CSR, fence and system-return latencies. These operations
serialize older and younger execution. Only MRET/SRET system instructions
are admitted; blocking operations, traps and SFENCE.VMA remain unsupported.
FENCE.I with instruction/uop caches and possible SATP writes with component
translation are errors because required invalidation/context interfaces are
not available. The engine does not verify CSR or privilege semantics.

## Own-core component-library adapter

The optional `components` configuration object selects shared native
component study sections. The own model delegates cache hierarchy,
prefetch, TLB and branch component behavior to `rvw.csim.lib.Components`.
It does not implement their algorithms. `components` in the run report
retains native component statistics. Data service uses issue-cycle times
after translation. Instruction service requires explicit front-end timing.
The own translation object and component TLB cannot be enabled together.
BTB lookup delay adds to branch resolution delay. History is actual-path
history at issue. FTQ-directed prefetch, instruction TLB service and
speculative predictor repair remain unsupported. Accuracy is inconclusive.

## Shared O3 project descriptions

`rvw.arch-core/1` accepts an optional `ooo` object for O3 descriptions. gem5
ignores this object when constructing its model. The own engine uses its
explicit latency/policy fields and projects shared CPU widths and capacities.
Conflicting duplicate values are errors. The own engine checks the selected
C2 preset against the description. Shared dimensions do not establish timing
agreement. See `rvw/ooo/README.md` for the mapping and approximation limits.

## Own-core custom operation timing

`custom_instructions` declares nonoverlapping mask/match rules in reserved
32-bit custom major opcodes. A rule names a `custom_` latency class, source
register fields and destination-write behavior. C2 registers must match the
encoding. Only register operations with sequential next PC and no memory
mask are supported. Timing does not establish custom-operation correctness,
software cost or physical PPA. Search can vary declared custom latencies.

## Repeated scheduling studies

`rvw.sched-study/1` captures repeated N/2N/4N scheduling measurements. Each
seed uses fixed zero memory latency. It retains per-run C1/C2 captures and
reports fitted slopes, intercepts, adjacent slopes, residuals, nonlinearity
flags and bootstrap intervals across seeds. The middle length has two
measurements per seed. At least three repeats are required. The report uses
a built-in MCA model and keeps generated-model accuracy inconclusive. It
does not establish isolated unit latency or native generated-model support.

## Declared SoC traffic model

`rvw.traffic-plan/1` defines resources, agents and request routes. Each request
has an integer arrival cycle and byte size. Resources define bandwidth,
latency and finite capacity. Optional project power-state parameters need a
source and a plan clock frequency. `rvw.traffic-report/1` records model-only
per-request completion/latency, per-agent aggregates, resource pressure and
optional abstract energy. Missing energy stays null. Accuracy is inconclusive.
The output must be new. No cache behavior, coherence or RTL correlation is
inferred. See `Arch/README.md` for queue and power semantics.

## Own-core memory-dependence replay

`memory_policy=speculate` enables a bounded load/store PC-pair predictor.
`dependence_entries` is its capacity. `replay_penalty` is its recovery delay.
Both are positive integer configuration fields. A violating issued load
causes younger ROB work to execute again without changing retirement order.
Events count speculative loads, violations, store-triggered recoveries and
replayed instructions. `issued` includes reexecution. This policy is not
memory renaming. Translation precedes component service in cycle order.
Completed or pending component requests are not cancelled by replay.
Accuracy remains inconclusive. See `rvw/ooo/README.md` for limits.

## Own-core rename policies

The optional `rename` configuration object enables bounded move elimination,
zero elimination and adjacent immediate execution fusion. All flags default
to false. Eliminated operations retain ROB entries and architectural commit
slots. Events `move_eliminated`, `zero_eliminated`, and `fused_immediates`
count these operations. `issued` counts execution requests. Full free-list
alias reclamation, macro-op decode fusion, faults and memory renaming remain
unsupported. These policies run in Python. See `rvw/ooo/README.md`.

## Own-core model search

`rvw.ooo-search-plan/1` selects a project model, complete C2 traces, numeric
parameter choices, grid or Bayesian search, a point budget and a cycle budget.
Optional area and power objects are project analytic cost estimates with a
named source. `rvw.ooo-search/1` records model-only points, trace timings,
frontier IDs, objective names, missing cost dimensions and unmeasured
uncertainty. `results.sqlite` retains one row per completed point. Reports
remain inconclusive for accuracy. They are not C1 runs or hardware evidence.

## Own-core native scheduler selection

`rvw.ooo-run/1` adds `backend` (`python` or `native`). The optional native
integer scheduler preserves the reference schedule. Unsupported streams use
Python. The report engine hash includes the native source and wrapper, and
also the selected library bytes when native execution occurs. This is model
identity, not a hardware accuracy claim. See `rvw/ooo/README.md` for support.

## Own-core decoupled pipeline timing

The optional `rvw.ooo-run/1` configuration objects `frontend`, `execution`,
and `translation` select decoupled fetch/decode, shared execution port binding,
per-class issue capacity and fixed page-walk timing. Fields and units are in
`rvw/ooo/README.md`. Omission preserves the original schedule.

The additional `topdown` object gives `unit=commit_slots`, `total_slots`,
`slots`, `fractions`, and `method`. Categories are `retiring`, `frontend_bound`,
`bad_speculation`, and `backend_bound`. Total slots equal cycles times commit
width. This is a model partition, not a hardware top-down measurement.
Events include uop-cache block hits/misses, FTQ stalls, predictor delay cycles,
shared-port stalls, per-port issued counts, TLB hits/misses, page walks and
walker-capacity stalls. Translation events count admitted translation attempts, including replay;
walker-full counts failed admission attempts. Wrong-path fetch slots are a
penalty-based estimate. No wrong-path instructions execute. Accuracy remains
inconclusive. Native speed and RTL correlation are not established.

## Own-core timing configuration snapshots

`rvw.ooo-run/1` accepts optional timing policies for per-class issue counts,
integer physical-register capacity, committed-path branch recovery and traced
address disambiguation. These remain fixed-latency experiments. They do not
supply RTL accuracy evidence or model wrong-path resource use.

An optional `rvw.ooo-effective/1` snapshot contains `source_revision`, `config`,
`parameters`, `extraction_keys` and `required_structures`. `parameters` must
match every normalized model setting. Each setting needs an extraction key.
Unsupported required structures are errors. `configuration_status` becomes
`snapshot_checked` only after this comparison. `configuration_evidence` holds
the snapshot SHA-256, revision, selected config and extraction keys. Exporter
correctness and current RTL agreement remain unverified. `accuracy_status`
remains `inconclusive`. Without a snapshot the configuration stays `unchecked`.

## Saved own-core model calibration

`rvw.ooo-calibration-plan/1` selects one fixed configuration, an event map and
training/heldout samples. Paths resolve beside the plan. Each sample binds
saved C1, complete C2, ELF bytes and event counts. ELF and trace hash overlap
across splits is an error. Regions cover the whole program only.
`rvw.ooo-calibration/1` records captures, individual errors, event correlations
and declared budget comparisons. Missing events and zero denominators remain
explicit. Accuracy stays inconclusive. Event predicate equivalence is not
verified automatically. No fitting or RTL execution occurs.

`rvw.ooo-prediction/1` records the frozen calibration hash, held-out trace,
config, engine, identity and local creation time. `rvw.ooo-prediction-score/1`
binds its hash and the later conclusive C1 hash in a separate exclusive file.
Scoring rechecks captures and exact identities. Local timestamp checks are
not trusted chronology. No native speed qualification is established.

## Saved checkpoint warmup observations

`rvw.arch-warmup-plan/1` declares captured ELF bytes, a fixed `[start,start+length)`
instruction ROI, an error target, a from-reset baseline and warmup samples.
Each sample binds saved C1/C2 and W. C1 metrics declare ROI start, instruction
count and measured cycles. Samples use start order W; baseline uses start.
`rvw.arch-warmup-bias/1` records input captures, cycles, CPI, IPC and signed and
absolute CPI bias. Architectural suffix records must match after excluding
order and cycle. Seeds, memory timing, ELF and core identities must match.
Missing evidence causes an error. Budget comparisons are observations only.
Accuracy remains inconclusive. No checkpoint or RTL job is launched.

## C2 BBV sampling plans

`rvw.arch-sampling/1` binds a complete single-hart C2 trace hash to fixed
instruction intervals, BBV counts, deterministic clusters and selected actual
intervals. Each sample gives `[start,end)`, capture order, actual planned
warmup, represented instruction count and its instruction fraction `weight`.
The final short interval uses its actual length. Weights sum to one.
`accuracy_status` remains inconclusive. Phase selection is not checkpoint
restore or timing qualification. The CPI helper checks each measured sample's
instruction count and weights CPI by represented instructions.

## Experimental trace-driven OoO timing reports

`rvw ooo CONFIG TRACE --max-cycles N --json` is a separate native timing
experiment. It does not use gem5 or emit `rvw.arch-run/1`.
CONFIG is explicit JSON with positive integer `fetch_width`, `fetch_entries`,
`rename_width`, `rob_entries`, `issue_width`, `issue_entries`, `load_entries`,
`store_entries`, `commit_width`, and a nonempty `latencies` map. Map keys are
`alu`, `multiply`, `divide`, `load`, `store`, `branch` and `jump`; values are positive integer
cycles. Unknown or missing fields are errors. Only configured classes can run.

The input is complete single-hart C2. Traps, interrupts, external events,
atomics, fences, privileged, FP and vector operations are
unsupported. End status must be `pass`. C2 cycles do not enter prediction.
The entire instruction stream defines the region. There is no ROI slicing.

`rvw.ooo-run/1` contains `config`, SHA-256 fields `config_sha256`,
`trace_sha256`, `engine_sha256`, `cycles`, `instret`, `ipc`, `wall_s`,
`events`, `max_occupancy`, `cycle_order`, `limits`,
`accuracy_status="inconclusive"` and `configuration_status="unchecked"`.
Engine identity hashes the kernel, decoder and C2 parser. It does not claim
complete C8 identity. Wall time includes file capture, parsing and simulation.
Cycle order is commit, issue, rename, fetch. Cycles include fill and drain.
Events count issued instructions and phase-sampled dependency/queue stalls.
Absent event keys mean zero. See `rvw/ooo/README.md` for exact predicates.
This is not a C1 run, a C4 verdict, a configuration check or an accuracy result.
Success exits 0 for a produced report. Bad input or exhausted cycle budget
exits 2 with a JSON error. No 50x speedup is established by this schema.

## C9 decoupled RISC-V O3 settings

The existing `cpu` scalar fields can enable gem5's BAC and FTQ.
`decoupledFrontEnd` must be a boolean. When true, the model requires O3,
`minInstSize=2`, positive FTQ capacity and prediction rates, and
`fetchTargetWidth >= fetchBufferSize`. Omitted numeric settings use the
pinned gem5 defaults. The default target width (32) is smaller than the
default fetch buffer (64), so set compatible values explicitly. Invalid
settings fail before native execution. C9 evidence and verdict rules do not
change. See `Arch/patches/README.md` for the optional mixed-width BAC fix.

## Named SMT core reports

`rvw.smt-bindings/1` binds one SMT query to `property_id`, optional
`requirement_ids`, and a `constraints` object indexed by every named assertion.
Each constraint can list design `signals`. Bindings are caller-supplied metadata.
`rvw.solver-core/1` retains the query SHA-256, solver calls, core labels and their
bindings, optional SpinalDB locations, and the input capture. `status=pass` means
only that this SMT query is UNSAT. `minimal=true` means deletion minimality was
checked with SAT on each single-constraint removal. Unknown removal results set
`minimal=false`. This report is not a coverage exclusion or an RTL proof result.

## Own-core component event projection

Native cache demand/writeback/prefetch counts and TLB/walk counts are copied
to the flat timing `events` map with cache-level or `tlb_` prefixes. Only
present integer counts are projected. Nested native statistics are retained.
Project RTL maps must use matching predicates, including replay and page-walk
traffic. Ratios and averages are not projected as counts. No counter match
or accuracy claim is implied by this projection.
