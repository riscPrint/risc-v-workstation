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

`store_policy` is `ordered` (default) or `buffered`. A buffered store issues
when its inputs are ready, independent of older memory operations, and its
component service delay is counted in `buffered_store_service_cycles` instead
of being added to its completion. It needs `memory_policy` `disambiguate` or
`speculate`.
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
across splits is an error. Regions cover the whole program only. An optional
positive integer `max_cycles` (default 1,000,000) bounds every model run of
the plan, including `rvw arch ooo-fit` candidates.
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
## Native OoO scheduler ABI 2

The optional native scheduler adds fixed ordered memory and static sequential
branch timing. It preserves the `rvw.ooo-run/1` fields and reports `backend:
native`. Unsupported policies use Python in auto mode. Explicit native mode
refuses them. Rebuild the library with `scripts/install.sh --with-ooo` after
an ABI change. Component algorithms remain in ComponentSims. Benchmarks report
kernel and Python-call times separately. `benchmark-results-e2e.json` also
measures public runs that include C2 validation, packing and hashes.

## OoO slot profiles

`rvw.ooo-profile/1` holds trace, configuration and region-map hashes, cycles,
instret, IPC, the model result and attribution. Attribution uses five disjoint
commit-slot categories: retiring, frontend_bound, bad_speculation,
backend_memory_bound and backend_core_bound. Each region has slot counts and
fractions. Region totals equal the run total. ELF symbols or explicit half-open
PC ranges define regions. Unmapped PCs remain explicit.

`rvw.ooo-profile-diff/1` requires identical trace and region-map hashes and
retirement counts. It gives base minus candidate cycles saved, candidate minus
base IPC and slots, base/candidate cycle speedup and per-region slot deltas.
These are model estimates. They do not establish hardware top-down accuracy.

## Oracle memory rename policy

The optional own-model `memory_rename` object is empty by default. The only
accepted nonempty value is `{"mode":"oracle_store_data"}`. It aliases LD
consumer dependencies to the youngest exactly overlapping SD data producer.
The load retains execution, memory verification and ordered commit. It does
not allocate a new physical register. Traced addresses are an early oracle.
`memory_renamed_loads` counts aliases. Partial overlaps, barriers and unsupported
widths stop lookup. Speculative dependence replay is refused. This policy has
no failed alias prediction, fault recovery or predictor recovery evidence.

## Own-model sensitivity

`rvw.ooo-sensitivity-plan/1` selects a config, trace paths, numeric parameter
paths, perturbation fraction and cycle budget. `rvw.ooo-sensitivity/1` records
input hashes, baseline pooled IPC, per-trace runs, both perturbations, explicit
invalid candidates and ranking by absolute IPC elasticity. Zero-valued switches
and lists are excluded. Results measure local model effects, not RTL limits.

## Shared compiler scheduling exports

`compiler-export` consumes an O3 shared description and creates a new directory
with LLVM and GCC fragments, an issue-rate include and source projection data.
`rvw.compiler-roundtrip/1` reports parsed widths, resources, latency/occupancy
pairs and reservations. The checker rejects drift from the projection.
Assumed independent resources and unit occupancy remain explicit. Partial
opcode mappings do not establish native compiler integration or RTL accuracy.

## gem5 configuration file export

`rvw.gem5-export/1` records shared-description and adapter hashes, the target
gem5 version, invocation, CPU parameters and projected issue capacity. Export
writes `core.json`, `ooo.json`, `model.py` and `report.json` to a new directory.
It copies the existing adapter. It does not build gem5 or establish timing parity.

## Own-model parameter fitting

`rvw.ooo-fit-plan/1` references a saved calibration plan and candidate parameter
lists. A grid has at most 32 points. `rvw.ooo-fit/1` records candidate scores,
the selected config and the final calibration/held-out evidence. Training-only
cycle and event errors select the winner. Missing training events are errors.
Probe `counts` exports use the existing C1/C2-bound event-count input. No RTL
job, continuous service or accuracy qualification is implied.

## Shared simulation-point timing

`rvw.ooo-sampled/1` joins a C2 trace with `rvw.csim-simpoints/1`. The normalized
trace hash and full instruction count must match. Each point records actual
warmup, measured instructions/cycles and weight. Weighted CPI produces estimated
cycles and IPC. An optional complete model run reports signed cycle error.
Cold starts, bounded warmup and end drain remain explicit bias sources. Without
a full run, sampling error stays unmeasured. Accuracy remains inconclusive.

## Abstract system energy

`rvw.system-energy-plan/1` names a saved own-model run, a common GHz clock and
components with kind, source, state cycle counts and state mW. Optional event
pJ and transition count/energy terms add incremental energy. State counts
partition the run cycles. Missing model activity counts are errors.
`rvw.system-energy/1` reports input hashes, per-component pJ, total pJ and
average mW. Calibration is not performed. State residency and coefficients
remain producer declarations. This is abstract system energy, not cell power.

## Custom-instruction trade-off report

`rvw.custom-tradeoff-plan/1` joins a declared workload identity, two model
config/trace/ELF inputs and source-labelled software cost. Optional C1 evidence
must pass identity and retired-count checks. Optional `rvw.early-ppa/1` files
provide source, RTL revision and area_mm2/delay_ns/power_mw metrics.
`rvw.custom-tradeoff/1` separates model speedup, RTL speedup, software cost and
PPA deltas. It hashes check references but gives no aggregate correctness pass.
Missing RTL and PPA remain `no_checks`. Workload equivalence and PPA provenance
are producer declarations, not independent proofs made by this tool.

## Native C2 timing reader and component issue service

`rvw.ooo-run/1` adds `trace_reader`: `native-c2` identifies the narrow flat
single-hart C2/1 reader; `python-c2` identifies the shared Python reader.
Unsupported native syntax falls back to the shared validator. Native decoding
uses the same Python decoder per static encoding and destination register.
Both readers require a complete passing trace. The native reader, scheduler
and component sources enter engine identity.

`csim_ooo_service(handle, cycle, kind, info, out)` is a synchronous C interface
for the native scheduler. `info` holds six unsigned 64-bit values: PC, next PC,
instruction length, memory address, memory size and component branch kind.
`out` holds service cycles, a misprediction flag and BTB level. Level -1 is a
lookup miss; -2 means no lookup. Requests use actual-path training at issue.
The caller owns the handle and arrays. This API does not introduce speculative
history or wrong-path execution. End-to-end throughput remains measured
separately from kernel throughput.

## FTQ-directed instruction prefetch interface

The own-model `frontend.fdip` boolean defaults to false. True requires an
explicit `components.memory.l1i`. It selects bounded actual-path target
runahead through the existing FTQ dimensions. Reports remain inconclusive.
The target source is the committed C2 stream, not a speculative Spike stream.

`csim_ifetch_prefetch(handle, cycle, pc, address)` requests one instruction
line. Address is in bytes. It returns zero after submission, including native
filtering, or -1 when the handle has no instruction cache. The Python API is
`Components.prefetch_instruction(cycle, pc, address)`. It validates unsigned
64-bit arguments. Submission does not promise an issued request or a completed
fill. Use native prefetch statistics to distinguish those outcomes.

## In-order own-model descriptions

Minor `rvw.arch-core/1` descriptions can supply an `ooo` object with the full
own-model configuration. `issue_order` must be `in_order`. The own-model
issue and commit widths must equal the corresponding explicit Minor limits.
No other Minor defaults are projected. In-order issue blocks younger unissued
operations at the oldest unissued operation. Completion can overlap.
Native scheduling does not yet support this mode.

The `rvw.ooo-calibration-plan/1` event map can be an empty object for IPC-only
scoring. Such a result has no event correlation and insufficient event
coverage. It does not treat unavailable RTL probes as zero counts.

## Designer reports

`rvw.ooo-designer-plan/1` selects a configuration, uniquely named workloads
with trace and optional ELF paths, sensitivity parameters, search choices,
and optional budget and cycle limit. Paths resolve beside the plan.
`rvw arch ooo-designer` and `arch_ooo_designer` write a new directory with
`report.json`, `report.md`, sensitivity evidence, search evidence and SQLite
points. `rvw.ooo-designer/1` contains instruction-pooled IPC, per-workload
function slot attribution, ranked local sensitivities and up to three DSE
points that improve aggregate cycles. Fewer improvements remain explicit.
All evidence is model-only. Function attribution uses the supplied ELF
symbols. It is not hardware top-down measurement or a physical feasibility
claim. Report creation supplies no fidelity verdict.
## Base-I architecture selections

Architecture descriptions and static inspection accept RV32I and RV64I for
Minor/Timing; RV64I is also accepted for O3. Scheduling descriptions accept
`rv32i` and `rv64i`. Preserve the declared ISA. This selection does not validate
instruction behavior or exclude extra instructions supported by the gem5 backend.

## Compiler-only benchmark builds

`rvw arch build` needs the RISC-V compiler and benchmark sources. It does not
probe or require gem5. Its `rvw.arch-build/1` record has `backend: "riscv-gcc"`
and compiler identity. gem5 identity belongs to the later model run record.
`rvw arch run` and `calibrate` still require the supported gem5 binary.
Inspection, report comparison and the `rvw ooo` trace model do not require it.

## Static branch timing policy

The own-model `branch_prediction` field accepts `sequential` by default or
`static_btfn`. Static prediction decodes conditional targets and predicts
backward branches taken. It predicts direct jumps taken and indirect jumps
sequential. It does not use the observed outcome to predict a target.
Static prediction uses the Python scheduler and cannot combine with component
branch prediction. It models direction and targets, not RTL prediction stages.

## Default workload evaluation

`rvw.workload-evaluation/1` groups pinned workload recipes and model paths.
`rvw workloads evaluate` and `workloads_evaluate` build or reuse those recipes,
check outputs on Spike, capture complete C2, select shared SimPoint-style
intervals and report sampled model IPC. The new output directory contains
`rvw.workload-evaluation-report/1` JSON and Markdown. Its per-workload rows
retain ELF, C2 and model-source hashes. A supplied C2 must name the verified
ELF path. An available producer ELF hash must match too. Missing hash binding
is explicit as `producer_path`. These reports are approximate model evidence.
They do not issue a correctness gate or qualify commercial CPU performance.

`rvw.csim-simpoints/1` can supply `source_c2_sha256` for direct byte identity
with a complete C2 source. The own-model sampler validates that hash and C2
instruction count instead of converting the trace again for the normalized
hash. Older point files retain the normalized-hash check. The whole C2 stream
gets structural validation. Only selected warmup and measurement windows get
instruction decoding. Unsupported instructions outside those windows do not
supply modeled timing. An explicit full run still decodes the complete stream.

The own-model C2 readers accept shifted contiguous RVFI byte masks. They
convert the mask's first set bit to a byte offset from `mem_addr`, then use
the contiguous byte count as the access size. Sparse masks with holes remain
unsupported. A byte access with mask `0x20` at base `0x1000` therefore reaches
`0x1005`. This applies to Python window decoding and native C2 packing.

## Bounded wrong-path timing

`rvw arch ooo-wrong-path` and `arch_ooo_wrong_path` check committed C2 effects
with Spike and capture bounded sequential-prediction wrong paths. The new
output directory holds `rvw.ooo-wrong-path/1`. It records input hashes, native
source and library hashes, capture coverage, both timing runs and their gap.
The gap compares model policies. It is not an RTL error bound. Dynamic branch
predictors, entropy, custom extensions and multi-hart replay are refused.

## Native C2 instruction decoding

Own-model run reports add `c2_decoder`: `native-imc`, `python-template`,
or `python`. The native IMC decoder packs supported instruction words without
new-word Python callbacks. Other classes use the existing template decoder.
Old libraries keep the callback path. The shared C2 validator remains the
fallback for unsupported syntax. Decoder source and loaded library bytes
remain part of engine identity. This field does not validate architectural
execution or establish timing accuracy.

## Single-parameter comparisons

`rvw arch ooo-what-if` and `arch_ooo_what_if` change one existing scalar field.
The value must keep its numeric, Boolean or string type. Both descriptions
are validated. A new directory holds both configurations, JSON and Markdown.
`rvw.ooo-what-if/1` records the source hash, old and new values, both runs and
cycle, IPC and event deltas. Both runs must have the same trace hash. Invalid
configuration values fail before output creation. A run failure can leave a
partial directory. The comparison predicts no changed path or RTL accuracy.

## Shared sampled inputs

Workload evaluation can share validated windows across configurations with
identical custom instruction definitions. Each group validates the complete C2
structure, point identity and instruction count once. A raw trace hash check
precedes each reuse. Each project description must match the C2 selection.
Each model creates fresh timing state. Distinct custom definitions get separate validation. The
`rvw.ooo-sampled/1` report format and timing semantics stay unchanged.

## Paired OoO deltas

`rvw.ooo-delta-plan/1` names a frozen base configuration and calibration,
one-field numeric variants, and paired whole-program C1/C2/ELF captures.
Every sample includes the base and every variant. Paired captures must have
equal core, ELF hash, seed, memory timing and decoded instruction streams.
Each C1 must pass and agree with its complete C2 identity and count.
`rvw.ooo-delta/1` retains base and variant model reports, input hashes,
measured and predicted relative IPC changes, sign agreement and errors.
Relative change is variant IPC divided by base IPC minus one.
A wrong delta has a wrong sign or an error greater than half the measured
change. Zero measured changes have null relative error.
The report does not claim a Spike match or a fidelity pass.

## OoO issue queue reuse

Optional `issue_queue_policy` selects `associative` or `compacting`.
The default remains `associative`. Compacting queues allocate whole rename
lines. Only completed oldest lines can be released. Capacity must contain
whole lines. Completion approximates the hardware wakeup event.

Compacting line reuse waits one registered cycle after completion.
Optional `frontend.fetch_blocks_per_cycle` is a nonnegative integer.
Zero preserves unlimited PC-block selection. A positive value limits distinct
PC blocks per fetch cycle. It does not change instruction fetch width.

## Statistical speculative occupancy

The own-model configuration accepts `wrong_path_occupancy` (Boolean, default
false). True enables deterministic committed-mix speculative filler on the
Python scheduler. Explicit functional path providers take precedence. Filler
uses shared queue capacity, never retires, and makes no cache transactions.
This option does not claim that captured wrong-path instructions were used.

## Finite store acceptance

`store_drain_width` is a nonnegative integer, default zero. A positive value
requires buffered stores. Committed stores retain their existing shared
store-queue slots until FIFO cache acceptance. Additional service beyond
component L1 hit latency blocks drain. The positive width limits accepted
stores per cycle. The measured region still ends at final retirement.

## Bounded memory retries

`cache_miss_replay` is Boolean, default false. True requires explicit component
`memory.l1d`. Responses above hit latency trigger at most one retry per dynamic
load. The load and younger ROB window re-enter finite issue capacity after
`replay_penalty`. Memory-order recoveries use the same pending admission queue.
Reports distinguish cache retries from memory-order recoveries. Mixed RTL
reschedule totals are not treated as typed LSU events or exact replay evidence.
