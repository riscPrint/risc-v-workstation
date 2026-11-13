# Generic OoO timing experiment

`rvw ooo CONFIG TRACE --max-cycles 1000000 --json` predicts timing from a
complete single-hart C2 trace. This engine does not use gem5. Spike traces
must first be exported as C2. RTL cycle timestamps are validated but do not
drive the prediction. The full trace is the measured region.

The latest NaxRiscv drain study has 10 wrong structure deltas out of 24.
Five of 15 nonzero RTL changes meet the error criterion. The earlier
PR #1218 result was two of 15. See [the drain stage](#resource-study-drain)
and [PR #1231](https://github.com/riscPrint/risc-v-workstation/pull/1231).
Structure-size choices still need RTL measurements.
See the measured structure-delta section below.

Create CONFIG in your core project. This generic example is not a core preset:

```json
{
  "fetch_width": 2, "fetch_entries": 4, "rename_width": 2,
  "rob_entries": 8, "issue_width": 2, "issue_entries": 4,
  "load_entries": 2, "store_entries": 2, "commit_width": 2,
  "latencies": {"alu": 1, "multiply": 3, "divide": 12, "load": 4, "store": 2}
}
```

The fields in the example are required. Unknown fields are errors. Sizes, widths and latencies
must be positive integers. These example latency classes cover integer instructions. Additional project
classes enable the control and FP timing described below. Compressed integer instructions use the shared decoder.
Atomics, trapping privileged operations and vector operations remain unsupported.
FP timing needs explicit project latency classes. Optional control timing is described below. Branches and jumps need explicit latency classes. The engine rejects their traces. A missing or unsuccessful end
marker is an error. An exhausted model cycle budget is an error.

## Decisions

Within a cycle the engine commits, issues, renames, then fetches. Latency one
completes on the next cycle. Instructions can issue out of order. Rename
binds source operands to older producers. Integer x0 has no dependency.
Issue uses one shared queue and oldest-ready selection. Execution uses a
shared issue width with unlimited pipelined units. ROB and LSQ slots remain
allocated until commit. Memory instructions wait for older memory completion.
Optional address disambiguation, forwarding and buffered stores are described below.

`cycles` includes fill and drain from cycle zero through the last commit.
The report gives IPC, issued instructions, queue peaks and event counts.
`rob_full`, `issue_full`, `load_full` and `store_full` count rename stall
cycles. At most one is counted per cycle, in that precedence order.
`dependency_blocked` counts issue phases with an inspected unready entry.
It can overlap queue stalls. A counter absent from `events` is zero.
This phase-sampled counter is not a hardware stall-cause measurement.

## Limits

`rvw.ooo-run/1` is an experimental C9 extension. Report creation exits zero.
Bad input or budget exhaustion exits two with a JSON error. Success does not
establish core correctness, configuration agreement or model accuracy.
`accuracy_status` is always `inconclusive`. `configuration_status` is `unchecked` unless an exported snapshot is checked. No native RTL speedup has been measured. The 50x and accuracy
budgets in the design note are targets.

The default engine uses fixed latencies. Optional pipeline structures are
described below. Optional replay and bounded wrong-path experiments are described below.
It retains the full trace in memory. Project exports remain producer declarations. Calibration and RTL correlation
do not establish whole-core fidelity.
Do not use the existing gem5 report readers to certify this model.

Run targeted tests from the workstation root:

```sh
PYTHONPATH=rvw/src python -m pytest rvw/tests/test_ooo.py -q
```

See [the design](../../../../docs/design/own-core-model.md) for phases,
contracts, prior art and acceptance targets. Keep tuned core values in the
core project. Keep raw traces and native builds outside versioned source. Retain compact
measured tables and input hashes with project documentation.

## Optional timing structures

Configuration also accepts `ports` (per-class pipelined issue counts),
`physical_registers` (total integer registers, zero means unbounded),
`branch_penalty` (extra cycles after branch completion), `memory_policy`
(`ordered` or `disambiguate`), and `forwarding_latency` (default one cycle).
The original required fields remain required. Add `branch` and `jump` to
`latencies` to enable those decoded classes.

The branch policy predicts the sequential PC. Python callers can pass a
predictor with `predict(pc, fallthrough)` and `update(pc, actual_next)` methods
to `simulate`. Prediction and update occur at issue. Younger instructions wait
for the branch to complete. A miss also stops issue, rename and fetch for the
recovery interval. The model does not execute wrong-path instructions or model
speculative predictor history. These costs are an approximation.

Disambiguation lets loads pass older loads and issued non-aliasing stores.
A load waits until all older stores issue. At that point traced addresses
are available. The youngest overlapping store forwards a fully covered load.
Partial coverage waits for overlapping stores to finish. Stores stay ordered
behind older memory operations. This policy has no speculative dependence
prediction, replay, cache hierarchy or store drain buffer.

Use `--effective-config FILE` to compare every model field with a project-owned
snapshot. The snapshot has schema `rvw.ooo-effective/1`, `source_revision`
(full 40-character revision), `config` (selected preset), `parameters`
(the complete normalized configuration including defaults), `extraction_keys`
(one nonempty source key for each parameter), and `required_structures`.
Supported required structures are `integer`, `branches`, `ports`, `registers`
and `address_disambiguation`. Other required structures cause an error.
The core's own exporter must produce this file. This repository does not
elaborate the core or verify the exporter. A successful comparison reports
`configuration_status: snapshot_checked`. It does not certify RTL agreement.
The snapshot hash and source keys are retained in the report.

`ooo_run` exposes the same operation as a cancellable MCP job. Tests use small
synthetic schedules. No RTL accuracy or native speed qualification was run.

## Saved calibration and predictions

```
rvw arch ooo-calibrate PLAN --out calibration.json --json
rvw arch ooo-predict calibration.json CONFIG TRACE --out prediction.json --json
rvw arch ooo-score prediction.json LATER_C1 --out score.json --json
```

All output files must be new. The matching MCP jobs are `ooo_calibrate`,
`ooo_predict` and `ooo_score_prediction`. They support cancellation.

PLAN uses schema `rvw.ooo-calibration-plan/1`. Its `config` and `event_map`
paths and each sample's `elf`, `trace`, `c1` and `events` paths resolve beside
PLAN. Each sample also has a unique `id` and `split` (`training` or `heldout`).
Both splits must be nonempty. Equal ELF or trace hashes across splits are
errors. This command scores a frozen configuration. It does not fit settings.
Optional `max_cycles` (default 1,000,000) bounds each model run of the plan and
of `rvw arch ooo-fit` on it; long programs need a larger value.

The event map is an object keyed by report event name. Each value defines
`model_event`, `rtl_event`, `edge`, `unit`, `identity`, `family` and
`region: whole-program`. The producer must use equivalent event predicates.
The RTL event file has `c1_sha256`, `trace_sha256` and a `counts` object keyed
by RTL event name. Missing counts and zero denominators stay explicit.
Correlation needs at least three nonconstant samples. Coverage needs five
held-out samples and three declared event families. Per-workload IPC errors
and per-event errors are compared with 10% and 15% budgets. The result retains
raw input hashes. Budget comparisons do not certify fidelity.

Only complete whole-program regions are supported. C1 must be a conclusive
pass with the captured ELF hash. C1/C2 core, config, ELF identity and retired
instruction count must match. ROI slicing and event-map semantic verification
are not implemented. Event counts remain producer declarations.

Predictions use a frozen held-out trace, configuration and engine. Scores go
in separate files. Scoring rechecks calibration captures, prediction hashes,
C1 identity, seed, memory timing and instruction count. The later C1 file must
have a local modification time after prediction creation. Local times are
not trusted chronology. A later C2 stream comparison, later event scoring,
three-repeat native speed qualification and hardware accuracy remain open.

## Decoupled pipeline timing

The optional `frontend`, `execution`, and `translation` objects add timing
structures to the same C2 engine. An omitted object keeps the original path.
For example:

```json
{
  "frontend": {
    "decode_width": 8, "decode_entries": 64, "decode_latency": 2,
    "fetch_latency": 2, "ftq_entries": 32, "block_bytes": 32,
    "predictor_latency": 2, "uop_cache_entries": 128,
    "uop_cache_width": 8, "uop_cache_latency": 1
  },
  "execution": {
    "ports": {"p0": 1, "p1": 1},
    "bindings": {"alu": ["p0", "p1"], "divide": ["p0"]},
    "intervals": {"divide": 12},
    "queues": {"alu": 48, "divide": 8}
  },
  "translation": {
    "entries": 64, "page_bytes": 4096, "hit_latency": 1,
    "walk_latency": 80, "walkers": 4
  }
}
```

Merge these objects into the required configuration above. These are generic
example values. They are not measured parameters for a particular core.

Fetch and decode use separate buffers. An FTQ slot holds a fetch block until
its operations leave the fetch buffer. Decode width and delay constrain misses
in the micro-op cache. Cache hits use a separate width and delay. The cache
holds decoded contiguous blocks, uses FIFO replacement, and fills at the last
operation's decode. `uop_cache_entries` counts blocks. Predictor latency stops
fetch at each branch. Branch recovery still uses the committed-path policy
above. The engine has no wrong-path instruction bytes.

Execution bindings allow classes to share ports. Each port has the declared
number of lanes. `intervals` gives the minimum cycles between issues to one
lane. Latency remains separate in `latencies`. Per-class `queues` constrain
scheduler admission in addition to the shared `issue_entries` limit.

Translation uses traced addresses as page tags. A miss takes `walk_latency`.
Requests to a pending page share its walk. Walker capacity causes backpressure.
Entries fill at walk completion and use FIFO replacement. This is a single
translation level with a fixed page size. It does not read page tables, check
permissions, reproduce page faults, or model physical placement.

Python callers can pass `memory=` to `simulate`. Its interface is
`access(address, size, write, cycle) -> additional_cycles`. This boundary is
for the component library. Forwarded loads do not request that service.
The CLI can select the shared component provider described below. Detailed
interconnect contention and protocol behavior remain separate work.

`topdown` partitions commit slots. Retired instructions use `retiring` slots.
Remaining slots use `bad_speculation` during recovery, then `backend_bound`
when the ROB is nonempty, else `frontend_bound`. Fractions sum to one. This
simple model partition is not the hardware top-down method. Counters can be
compared with RTL only after matching their predicates. The wrong-path fetch
slot estimate is recovery penalty times fetch width per branch miss. It does
not consume issue or cache resources. Synthetic tests establish timing rules;
they do not establish RTL accuracy. Full macro-op decode fusion, memory renaming, and speculative dependence
replay remain open. Bounded rename policies are described below.

## Optional compiled scheduler

Use `scripts/install.sh --with-ooo` to compile the C scheduler with the host C
compiler. Use the same flag with `--check` to check its ABI. No download is
needed. The library is `.tools/ooo/libooo.so` on Linux and macOS. The suffix
is fixed for discovery; macOS builds a native dynamic library.

The engine selects ABI 2 for integer ALU, multiply, divide, ordered load/store,
branch and jump streams with at most two integer sources. It preserves fetch,
rename, ROB, issue, commit, fixed latencies, class issue limits, physical-register
pressure, queue occupancy, static sequential branch prediction, recovery and
optional correct-path branch overlap. Memory uses fixed latency and ordered
issue. Component data caches, TLB and predictors can use the native issue
service. Front-end objects, own translation, execution-port objects,
rename policies, FP and memory disambiguation also use Python.

Reports name the selected `backend`. Missing libraries use Python. An invalid
selected library is an error. Rebuild older ABI 1 installations. Set
`RVW_OOO_NATIVE=0` to force Python, or set it to an explicit library path.
Python callers can select `backend="python"` or `backend="native"`. The latter
requires a supported stream and installed library. The flat C2/1 reader can
validate and pack integer streams directly. Other inputs use Python.

Parity tests check 100 seeded integer and 150 seeded mixed schedules, including
queue limits, dependencies, physical-register capacity, branch recovery and
speculation. This is parity with the reference. RTL accuracy is unmeasured.

Run `nice -n 10 rvw/.venv/bin/python Arch/ooo/benchmark.py` from the repository
root for warmed alternating trials. The saved `Arch/ooo/benchmark-results.json`
records host, individual times, rates and speedups. Public `simulate` times
include Python validation and input packing. Kernel times exclude those costs.
Neither measure includes C2 parsing or file I/O. These synthetic streams do not
establish application throughput or component-backed throughput.

## Design-space search

Run `rvw arch ooo-search PLAN --out NEW_DIRECTORY --json`. The matching
cancellable MCP tool is `arch_ooo_search`. The plan uses paths relative to
its own directory:

```json
{
  "schema": "rvw.ooo-search-plan/1",
  "config": "model.json",
  "traces": ["kernel-a.jsonl", "kernel-b.jsonl"],
  "parameters": {"issue_width": [2, 4, 8], "rob_entries": [64, 128]},
  "method": "bayesian",
  "budget": 6,
  "max_cycles": 1000000,
  "area": {
    "base": 100,
    "coefficients": {"rob_entries": 0.2, "issue_width": 5},
    "source": "project analytic estimate; arbitrary area units"
  }
}
```

`grid` visits Cartesian points in sorted parameter order. `bayesian` reuses
the architecture search Gaussian-process expected-improvement method. Its
objective is the sum of model cycles across the supplied traces. Each run
has at most 32 points from a space of at most 4096 candidates. Numeric paths
can select nested fields such as `frontend.decode_width` or `latencies.load`.
An optional object such as `frontend` must first exist in the base config.

Each point is committed to `results.sqlite`. `report.json` contains the
configurations, individual trace results, and a Pareto frontier over cycles
and any supplied area or power estimates. Each optional cost object defines
`base + sum(coefficient * parameter)`. The project must name its source and
units. These are analytic estimates. No RTL, cell area, or measured power is
inferred. Missing costs remain unobserved. Uncertainty stays unmeasured.
A partial failed run can retain completed SQLite points, but has no final
report. The same committed C2 paths drive every candidate. This cannot model
changes to the program path or validate a custom instruction's semantics.

## Rename elimination and immediate fusion

The optional `rename` object accepts boolean `move_elimination`,
`zero_elimination`, and `immediate_fusion`. All default to false. Width remains
`rename_width`, so projects can select eight or ten lanes without another
rename stage.

Move elimination covers ADDI with zero immediate, C.MV, and ADD/OR with a
zero-register input. Zero elimination covers XOR/SUB with equal source
registers and zero-valued moves. It removes execution work. A move still
waits for its older source producer. A zero operation breaks that dependency.
Eliminated destinations do not allocate a new physical register in this
bounded pressure model. Each instruction still uses a ROB entry and a commit
slot. This model does not account for alias reference counts in a real free
list. It is not a full physical-register reclamation model.

Immediate fusion covers an adjacent LUI/AUIPC and ADDI that reads and writes
the first instruction's destination. Both instructions retire. The pair
shares one execution completion. Fetch, decode and rename still count both
instructions. This is execution fusion only. It does not reproduce a core's
macro-op decode or exception rules. Traps remain unsupported. Other pairs,
memory renaming and speculative dependence replay remain open. Rename
policies currently use the Python engine.

## Memory-dependence prediction and replay

`memory_policy: speculate` permits a load to pass stores whose inputs are not
ready. A finite FIFO table records violating load-PC/store-PC pairs. The
`dependence_entries` capacity defaults to 1024 pairs. A learned pair waits for
the store address. Resolved stores use the same forwarding rules as
`disambiguate`.

When a store issues, it checks younger issued loads for overlapping bytes.
A violation trains the table and replays every younger ROB entry. Dependent
consumers execute again. The ROB keeps its architectural order. The recovery
interval is `replay_penalty`, default five cycles. Existing execution-port
reservations and component service requests remain consumed. They represent
work already started. The model has no wrong-path instruction bytes, cache
request cancellation, speculative store data, or store-set union algorithm.
This is dependence prediction and replay, not memory renaming.

Counters are `speculative_loads`, `memory_order_violations` (overlapping
issued loads), `memory_order_replays` (store-triggered recoveries), and
`replayed_instructions`. `issued` includes repeated execution. Recovery
slots enter the approximate `bad_speculation` category. TLB walks start
before memory execution. A component request starts only after translation
completes. Component callbacks therefore receive nondecreasing cycle times.

Translation counters count attempts, including replays. Synthetic alias and
non-alias tests check these policies.

## Buffered stores

`store_policy` is `ordered` (default) or `buffered`. An `ordered` store issues
only after every older load and store completes, and a component memory
service delay is added to its completion. A `buffered` store issues when its
inputs are ready, in any order with other memory operations. Its component
access still updates cache state, but the service delay is not added: a store
buffer writes the line after commit. The counter
`buffered_store_service_cycles` sums the hidden delay. `buffered` needs
`memory_policy` `disambiguate` or `speculate`. The model has no store-buffer
drain: a store queue entry is free at commit. The Python engine runs this
policy. NaxRiscv's Lsu2 is an example (see `examples/naxriscv/README.md`).
This is a timing approximation. It does not model a finite store buffer or
prove memory-order correctness.

## Register-only custom instruction timing

Add a `custom_instructions` list and one latency class per project operation:

```json
{
  "latencies": {"alu": 1, "custom_mac": 3},
  "custom_instructions": [
    {"name": "custom_mac", "mask": 127, "match": 11,
     "sources": ["rs1", "rs2"], "writes_rd": true}
  ]
}
```

This example selects the custom-0 major opcode. Use narrower masks to split
operations. Rules must select a reserved custom major opcode. They cannot
override standard instructions or overlap one another. C2 operand registers
must agree with the encoding. A custom operation must fall through by four
bytes and have no memory mask. Traps remain unsupported.

The declared sources create normal dependencies. Execution ports can bind
the custom latency class. `ooo-search` can sweep its latency and declared cost
parameters on the fixed committed C2 path. This models timing only. It does
not execute the operation, validate its semantics, estimate software effort,
or infer physical PPA. Compare separately generated baseline and extension
traces under one project workload and independent RTL checks. Custom memory,
control-flow, FP and vector operations remain unsupported.

## One project description for gem5 and the own model

`rvw ooo` and `arch ooo-search` can read an O3 `rvw.arch-core/1` file directly.
Add an `ooo` object to that project-owned description. It must include the
own-model `latencies` table. Other own-model policies can be added there.
The native gem5 runner validates that this object is an O3 table and ignores
it when constructing gem5 objects. The own engine also runs the common
static description validator.

Shared dimensions come from `cpu`: fetch width/queue size, rename width, ROB
capacity, issue width, load/store capacities, commit width and integer physical
register count. Total own issue capacity is the sum of declared issue-queue
entries. Decode width and FTQ capacity come from `cpu.decodeWidth` and
`cpu.numFTQEntries`. These source fields must be explicit. Duplicated own
values must agree, or the command fails. The C2 preset must match `config`.

The own model does not infer execution latencies from broad gem5 FU classes.
Its project latency table and port bindings stay explicit. Queue partitioning,
cache policies, predictor internals and stage boundaries can differ between
engines. The projected issue capacity is a unified capacity unless separate
own-model class limits are supplied. Equal dimensions do not imply equal
microarchitecture or timing fidelity. The report keeps the normalized own
configuration so these assumptions remain visible.

## Shared native component models

The optional `components` object uses the in-process `rvw.csim.lib.Components`
API. It accepts the component study's `branch`, `btb`, `ras`, `indirect`, and
`memory` sections. For example:

```json
{
  "components": {
    "branch": {"model": "bimodal", "entries": 1024},
    "btb": {"levels": [
      {"entries": 64, "ways": 2, "latency": 0},
      {"entries": 2048, "ways": 4, "latency": 2}
    ]},
    "ras": {"entries": 32},
    "memory": {
      "dram_latency": 200,
      "l1d": {"size_kib": 32, "ways": 8, "latency": 4},
      "l2": {"size_kib": 512, "ways": 8, "latency": 12},
      "llc": {"size_kib": 4096, "ways": 16, "latency": 40},
      "tlb": {"levels": 3, "l1": {"entries": 32, "ways": 4}}
    }
  }
}
```

The component worker owns these algorithms and their parameter validation.
The library builds on first use when a native C++ compiler is available.
`rvw csim build` can build it in advance. See `ComponentSims/README.md` for
models, prefetch policies, supported configurations and fidelity limits.
This adapter does not copy cache replacement or predictor implementations.

Data cache service begins after own-model translation completes. A component
TLB and the own `translation` object cannot both be selected. Component cache
and translation latency is added to the own execution latency. Set the own
load/store latency to the core execution cost that excludes memory service.
Cross-line and cross-page operations issue one component access per segment.
Forwarded loads bypass data cache service. Replay retains component requests
already made and their cache effects.

Declare `memory.l1i` to add instruction cache service. This requires an explicit
own `frontend` object. Fetch coalesces requests to the same line within a
cycle and handles instructions that cross a line boundary. Native instruction
prefetch policies can operate on this traffic. The explicit prefetch API supports FTQ-directed instruction requests.
Instruction TLB walks remain unavailable.

Branch lookup uses the shared direction model, multi-level BTB, indirect
predictor and RAS when configured. Actual-path history and training occur at
issue. BTB lookup delay adds to the modeled branch resolution delay. This is
a committed-path approximation. Speculative history repair and fetch-time
prediction remain open. The report's `components` object retains native
statistics. Own branch and recovery events remain in `events`. Instruction frontend timing uses the Python loop. Ordered integer data and
branch components can use the native scheduler. No RTL fidelity is established.

## Non-trapping control instructions

Projects can add `csr`, `fence`, and `system` to `latencies`. CSR and fence
operations wait for older ROB work to complete. Younger work waits for the
control operation. MRET and SRET also use the committed-path branch recovery
policy. Blocking WFI, ECALL/EBREAK traps, SFENCE.VMA, interrupts and fault
handling remain unsupported. The model does not execute CSR semantics.

A trace with FENCE.I is refused when an instruction cache or micro-op cache
is active. The component interface has no invalidation operation. A possible
SATP write is refused when the component TLB is active because its context
change cannot be applied through this interface. Read-only SATP accesses can
be timed. The engine does not silently retain invalid instruction or
translation state. `control_serialize_blocked` counts inspected control
operations that cannot start. This remains timing evidence, not privilege or
CSR correctness verification.

## Floating-point dependency timing

The shared decoder supplies integer and FP register banks. The own model
keeps them separate. Integer x0 has no producer. FP f0 is a mutable register.
FP loads, stores, arithmetic, conversions and FMA operations use the decoded
bank and up to three source operands. FP destinations come from the encoding;
C2 integer `rd` fields do not stand in for FP writeback data.

Projects declare operation-family latencies such as `fp_fadd`, `fp_fsub`,
`fp_fmul`, `fp_fdiv`, `fp_fsqrt`, `fp_fmadd` and `fp_fcvt`. The name is `fp_`
plus the mnemonic before its first dot. The same class names select execution
port bindings. FP loads and stores keep the `load` and `store` latency classes.
A missing class remains an error. Fixed latency does not model operand-dependent
iteration counts, denormal handling or rounding behavior.

`physical_float_registers` is the total FP register count. Zero keeps pressure
unbounded. A finite count must be at least 33. The model reserves 32 architectural
FP names and counts pending destination allocations separately from integer
allocations. `float_register_full` counts rename stalls from this limit. Shared
project descriptions derive this count from `cpu.numPhysFloatRegs` when present.
This remains a bounded pressure model, not a physical free-list implementation.

The Python loop handles these streams. Vector operations, FP result validation,
rounding semantics and trapping execution remain unsupported. The C2 producer
and independent execution checks must establish architectural correctness.

### Component events for RTL comparison

Native cache and translation counts also enter the flat `events` map used
by `ooo-calibrate`. Cache names have the level prefix, for example
`l1d_demand_accesses`, `l1d_demand_misses`, `llc_demand_misses`,
`l2_prefetch_issued` and `l1d_prefetch_useful`. Translation examples are
`tlb_walks`, `tlb_walk_memory_references`, `tlb_l1_accesses` and `tlb_l2_misses`.
Only present integer counts are copied. Ratios, configuration sizes and
latency averages are not event counts. The nested native report stays intact.

Cache requests include replay attempts and can include page-walk traffic
when the component TLB uses the cache. Instruction requests are line accesses,
not retired instructions. RTL event maps must declare matching predicates,
units and regions. Equal counter names alone do not establish comparability.

## Correct-path branch overlap

`branch_speculation` defaults to false for the original conservative schedule.
Set it to true to let younger operations issue under a correctly predicted
branch before that branch completes. Rename and fetch can also continue.
A branch must issue and obtain its prediction before younger work can pass it.
Mispredictions keep the existing recovery cost. Serial CSR/fence operations
and system returns retain their ordering rules.

`correct_path_speculative_issues` counts execution requests made while an
older correctly predicted branch is unresolved. Memory replay clears younger
branch prediction decisions before reexecution. Shared predictor history is
not checkpointed or restored by this approximation. Prediction still occurs
at issue, and miss handling stops committed-path work rather than executing
wrong-path bytes. Use this option for timing exploration, not predictor
recovery qualification.

Front-end events also report `decode_output_full`, `decode_input_not_ready`,
`decode_width_limited`, `uop_cache_width_limited`, and `fetch_buffer_full`.
They sample the named phase and can overlap. Reports name the optional decode
phase in `cycle_order`. These are model predicates, not measured hardware
stall classifications.

## Region profiles and configuration differences

Use `rvw arch ooo-profile CONFIG TRACE --elf PROGRAM.elf --json > base.json`.
The cancellable MCP tool is `arch_ooo_profile`. An ELF join uses sized symbols
from executable sections. Aliases share one name. Overlapping ranges are refused.
Zero-sized symbols and stripped addresses remain `<unmapped>`. Inlined functions
are not split. PCs must use the ELF link addresses. No relocation is inferred.
Alternatively, `--regions ranges.json` reads a list such as
`[{"start":4096,"end":8192,"name":"kernel"}]`. Ranges are half open.

The report partitions commit slots into retiring, front-end bound, bad
speculation, back-end memory bound and back-end core bound. Retiring slots
use the retiring PC. Unused slots use the oldest remaining ROB PC, or the
next unretired PC when the ROB is empty. Recovery takes priority. An unfinished
memory operation at the head or in its dependency chain gives memory bound.
Other nonempty ROB states give core bound. This includes commit-width limits.
Slots with no remaining PC use `<pipeline-empty>`. Region counts sum to run
counts. These are model predicates, not hardware top-down counters or a causal
measurement of each independent bottleneck. Detailed profiling uses Python,
including when shared components are selected.

Run both configurations on the same C2 trace and region map. Then use
`rvw arch ooo-diff base.json candidate.json --json` or `arch_ooo_diff`.
The report gives cycles saved, IPC gain, speedup, and slot changes per region.
Slot changes are candidate minus base. Negative stall slots mean fewer stalls.
Changed program paths require separate workload comparison. They are refused
by this same-trace command. Reports keep input hashes. Accuracy stays inconclusive.

## Oracle store-data renaming bound

Set `"memory_rename": {"mode": "oracle_store_data"}` for an optimistic,
nonpredictive experiment. At rename, a full-width integer LD can alias the data
producer of the youngest overlapping SD in the ROB. The addresses come from
the committed trace. This oracle can see them before address calculation.
A younger partial overlap blocks the alias. CSR, fence and system operations
also block the lookup. Other widths, FP and load-to-load aliases are excluded.

Consumers use the store data producer directly. The load does not allocate a
new physical register. It still occupies the ROB, issue queue and load queue.
It executes normal ordering, translation and memory service, then commits in
order. This verification work is not eliminated. Independent consumers can
start before it completes. Queue limits and rename width stay unchanged.
`memory_renamed_loads` counts successful aliases. These are neither forwarding
hits nor dependence-predictor hits. Dependence replay mode is refused because
its alias recovery has not been implemented.

This is an upper-opportunity experiment using correct traced addresses. It
has no alias predictor, confidence state, failed prediction or predictor repair.
Trapping C2 inputs remain refused. It does not model fault recovery. Branch
recovery retains the committed-path policy. It does not validate speculative
architectural state. A timing difference is not a proven error bound on RTL.

The distinction follows the communication bypass described in
[Moshovos and Sohi, Streamlining Inter-operation Memory Communication](https://www.eecg.utoronto.ca/~moshovos/research/microcloaking.pdf).
That work links store/load communication to register producers and requires
verification for predicted values. This model uses an oracle instead of its
prediction mechanism. Tests cover dependent chains, nonaliases, partial aliases
and rename widths eight and ten. Native gem5 comparison and an upstream engine
patch are NOT RUN. Issue #362 remains open for that work.

## Approximate starting descriptions

`Arch/reference/` contains Zen-5-like, M1-like, BOOM large/mega and a serial
VexRiscv-class comparison point. Read `Arch/reference/README.md` before use.
It identifies public anchors, assumed dimensions and limits. These are RISC-V
experiments. Commercial names do not establish product accuracy or ISA support.

## Parameter sensitivity

Run `rvw arch ooo-sensitivity PLAN --out NEW_REPORT.json --json` or use
`arch_ooo_sensitivity`. A `rvw.ooo-sensitivity-plan/1` plan has `config`,
`traces`, optional `parameters` (numeric dot paths), `fraction` (default 0.1)
and `max_cycles`. Paths are relative to the plan. Without `parameters`, all
positive numeric scalar fields are selected. At most 128 paths are supported.
Zero-valued switches, booleans and lists are not perturbed.

The command runs the baseline, then changes each parameter down and up in
isolation. Integer changes round to at least one. Invalid candidates remain
explicit. Each run uses the same workload traces. Pooled IPC is total retired
instructions divided by total cycles. The ranking uses the largest absolute
relative IPC change divided by the relative parameter change. Per-trace cycles
and IPC remain in each result. This is local finite-difference sensitivity.
It does not capture interactions, identify a global optimum or validate RTL.

## Fit saved event evidence

Run `rvw arch ooo-fit FIT_PLAN --out NEW_DIRECTORY --json`, or use
`arch_ooo_fit`. A `rvw.ooo-fit-plan/1` object names `calibration_plan` and
`parameters`, a map of numeric dot paths to candidate lists. Paths are relative
to the fit plan. The full Cartesian grid must contain at most 32 candidates.
The referenced plan uses the existing C1/C2 calibration format and separate
training and held-out samples. Identity, input hashes, regions and split checks
remain active.

Use `rvw probes convert EVENTS --to counts --c1 RESULT --c2 TRACE --out COUNTS`
for new probe streams. The calibration plan's `events` path accepts these saved
counts. Each event mapping must declare matching model and RTL predicates.
The command launches no RTL. Run it again with a new output directory when a
new saved observation set is ready.

The default objective uses mean absolute relative cycle and mapped-event errors
on training only. Set `objective: ipc` to use relative IPC error instead. Zero measured counts use denominator one. Missing training counts stop
fitting. Baseline validation reads all evidence, but held-out errors do not
select the winner. Only the winner receives the final held-out calibration.
Candidate configs, scores, the best config, and calibration evidence are saved.
A finite grid cannot establish unique parameter identification or model fidelity.
The report remains inconclusive about accuracy.

## Shared SimPoint runs

Choose points with `rvw csim simpoint TRACE --interval 100000 --json > points.json`.
Then run `rvw arch ooo-sampled CONFIG TRACE points.json --out NEW_REPORT.json
--warmup 10000 --full --json`. The cancellable MCP tool is `arch_ooo_sampled`.
The input must be the same complete C2 trace. The command checks the normalized
ComponentSims trace hash and instruction count before using its point weights.
It calls the existing converter and does not copy the clustering algorithm.

Each sample starts cold before its bounded warmup. Measurement begins at warmup
retirement and ends at the last sample retirement. A boundary cycle that also
retires measured instructions counts once. Warmup fills queues and component
state, but includes no checkpoint restore. The final sample drains without
future instructions. Both boundaries can bias timing. Reports keep warmup and
measured instruction counts and cycles for each point. Weighted CPI gives the
sampled IPC and estimated full cycles. This is not the arithmetic mean of IPC.

`--full` also runs the complete model and reports signed sampled cycle error.
Without it, sampling error remains unmeasured. No error bound or RTL accuracy
is inferred. Tests join the actual ComponentSims SimPoint format and check a
full-trace point against a complete model run. Large-workload sampling accuracy remains unmeasured. System power-state models
under #201 and custom-extension trade-offs under #196 are separate tasks.

### Native scan throughput

The scheduler now carries branch and memory prefix state through one oldest-to-
youngest scan per issue phase. It no longer walks older branches for every
candidate. The same 250 seeded schedules still match the Python reference.
`Arch/ooo/benchmark-results-prefix.json` records the updated warmed trials.
Raw kernel trials use 500,000 instructions to reduce timer noise. Public-call
trials use 5,000 instructions and include Python validation and packing. The
original result file remains a historical measurement. The host was shared
with other workers, so the two files are not a controlled before/after study.
C2 parsing remains outside both rates.

### End-to-end native path

The native reader accepts flat single-hart C2/1 integer records. It validates
field types, widths, order, cycles, masks and the passing end marker. It packs
scheduler arrays directly. It caches static instruction decoding within each
read. It does not cache trace validation between runs. Other syntax, fields,
C2/2 and unsupported instructions use the shared Python validator and decoder.
`trace_reader` records `native-c2` or `python-c2` in the run report.

Ordered-memory native schedules can now call the shared component library
through `csim_ooo_service`. Direction prediction, BTB, RAS, indirect prediction,
data caches and TLB service stay in the shared component implementation.
The scheduler adds the returned service latency at issue. Cross-line and
cross-page accesses split as in the Python adapter. Instruction cache timing,
explicit frontend timing, replay and other advanced policies still use Python.
Old scheduler libraries keep the Python component fallback. Rebuild with
`python -m rvw.ooo.native --build .tools/ooo/libooo.so` to enable both paths.

`Arch/ooo/benchmark-e2e.py` measures the full `run()` call. It includes file
reads, C2 validation, packing, scheduling and identity hashes. It excludes
trace generation and compilation. Results are in
`Arch/ooo/benchmark-results-e2e.json`. These synthetic shared-host runs have
large wall-time variation. The measurements are reported below. The requested
millions/s end-to-end target is **not met**. These rates do not establish RTL
accuracy or performance on large open workloads.

| Synthetic stream | Full-run instructions/s | Instructions/CPU-second |
|---|---:|---:|
| integer | 491,947 | 1,617,299 |
| components | 544,234 | 1,418,677 |

CPU time includes the hashing thread. It is not elapsed run throughput. Each
trial uses 500,000 instructions. Four trials follow one warmup.

## FTQ-directed instruction prefetch

Set `frontend.fdip` to `true` with an explicit `components.memory.l1i`.
The Python timing loop sends one target per cycle into a queue bounded by
`frontend.ftq_entries`. A target ends at a branch, a discontinuity or a
`frontend.block_bytes` boundary. It becomes available to fetch after
`frontend.predictor_latency`. Fetch drains the queue. Back pressure stops
new target admission when the queue is full. Recovery stops target admission
and instruction prefetch requests. Existing targets remain queued.

At target admission, the adapter calls the shared native instruction cache
prefetch service for each covered line. Requests use the component cache's
MSHR limits, lower hierarchy, completion times and prefetch counters.
`fdip_targets` counts admitted targets. `fdip_line_requests` counts requests
before native duplicate and queue-full filtering. `fdip_ftq_full` and
`fdip_target_not_ready` count model phase observations. Native cache counters
remain under `components.memory.l1i.prefetch` and in the flat event map.

This first integration reads targets from the actual committed trace. It has
oracle path lookahead. It does not predict target addresses at fetch, replay
wrong-path bytes, repair predictor history or discard queued targets on a
misprediction. It is an optimistic instruction-prefetch experiment. The
existing issue-time branch miss and recovery model remains active. A speed
change does not establish a hardware benefit.

Wrong-path error bounds for FDIP are **NOT MEASURED**. The optional replay
experiment below adds functional PC redirect and restore for bounded sequential
prediction. It does not repair FDIP targets or dynamic predictor history.
The default FDIP run still uses committed targets and supplies no replay evidence.

## In-order RTL correlation

`issue_order: in_order` prevents a ready instruction from passing an older
unissued instruction. Fetch, decode, completion and commit can overlap.
A blocked queue head stops issue. This is a generic in-order timing mode.
It does not reproduce all interlocks or bypass paths of an RTL pipeline.
The default remains `out_of_order`. In-order mode uses the Python engine.

Minor `rvw.arch-core/1` descriptions can carry an `ooo` table. They require
`issue_order: in_order`. Their issue and commit widths must match
`cpu.executeIssueLimit` and `cpu.executeCommitLimit`. Other own-model values
must be explicit in that table. gem5 still uses its Minor configuration.

The example descriptions are `examples/vexriscv/rvw/arch/own.json` and
`examples/vexiiriscv/rvw/arch/own.json`. Both represent a single-issue RV32IM
pipeline with uncached physical memory. These are timing approximations.
They are not elaborated parameter snapshots.

`Arch/ooo/correlation/prepare.py OUT` builds six distinct RV32IM programs and
C1 manifests. Run each manifest with the matching example's `run-many`.
Use a private core copy, the `vex-arch` lock, and private `RISCVSIM_WORK`.
Then run `Arch/ooo/correlation/score.py OUT vexriscv` or `vexiiriscv`.
The scorer converts VexRiscv probe counters with `rvw probes convert counts`.
It runs the fitting command `rvw arch ooo-fit`.
Training uses chain, multiply and memory. Held-out scoring uses independent,
divide and branch. The fit searches only fetch delay and branch recovery.

An empty event map selects IPC-only calibration. The saved VexiiRiscv batch
uses this mode because it contains no probe streams. The current adapter has
a SpinalProbes binding. New preparation enables probes for both cores.
Missing historical events are not zero observations. IPC-only calibration
cannot satisfy event coverage budgets.

An inactive C2 `irq` declaration with `levels=0` has no timing effect.
Asserted interrupt inputs and actual interrupt or trap records are refused.

The [native correlation sample](../../../../Arch/ooo/correlation/README.md#native-sample-on-2026-11-13)
records six real RTL runs per core. On VexRiscv, fitted held-out IPC errors are
+3.41% for independent, +11.34% for divide and -6.20% for branch. Divide is
outside the 10% budget. The linked table also records VexiiRiscv results.
The sample has insufficient event coverage for an accuracy verdict.

## Workload designer report

`rvw arch ooo-designer PLAN --out NEW_DIRECTORY --json` writes JSON and
Markdown reports for a workload set. MCP tool: `arch_ooo_designer`.
It combines IPC, per-function slot attribution, the existing sensitivity
ranking and the next three improving DSE points. It reports fewer points
when the declared search finds fewer than three improvements.
See [the plan and limits](../../../../Arch/ooo/DESIGNER.md) and
[the six-kernel model sample](../../../../Arch/ooo/DESIGNER_SAMPLE.md).

### Static predictor correlation

`branch_prediction` accepts `sequential` or `static_btfn`. The VexRiscv example
now selects `static_btfn`. Decoded targets give 1, 1, 1, 1, 1 and 101 misses
on the six saved RTL programs, equal to their RTL counters. Fitted held-out
IPC errors are +2.62%, +31.35% and -2.46%. Accuracy remains inconclusive.
See [the corrected experiment](../../../../Arch/ooo/correlation/README.md#static-predictor-correction).

## Bounded Spike wrong paths

`rvw arch ooo-wrong-path` compares the committed-path policy with bounded
real Spike paths and shared speculative resources. MCP: `arch_ooo_wrong_path`.
The native controls restore PC, registers, memory, mscratch and minstret.
The two small samples give baseline IPC gaps +19.34% and -13.41%. These are
model-policy gaps, not error against RTL. Dynamic prediction stays unsupported.
See [the experiment and native results](../../../../Arch/ooo/WRONG_PATH.md).

## Native instruction-word decoding

The supported flat C2/1 IMC path now decodes new instruction words in C.
Other classes retain the Python template fallback. Reports identify the
`c2_decoder`. Old native libraries remain supported.

The warmed full-run synthetic sample records 518,985 instructions/s for
cached integer, 483,155 for diverse integer and 282,968 for diverse components.
The cached stream regressed in wall time. The other two streams improved.
These shared-host results do not meet millions/s end-to-end throughput.
See [the method, CPU rates and all trials](../../../../Arch/ooo/NATIVE_DECODE.md).

## One-parameter what-if report

Run `rvw arch ooo-what-if CONFIG TRACE --set PARAMETER=JSON --out NEW_DIRECTORY`.
It validates one numeric, Boolean or string change and reports cycle, IPC and
event deltas. Both runs use the same trace. The source configuration stays
unchanged. Outputs include JSON and Markdown. MCP: `arch_ooo_what_if`.
See [usage and limits](../../../../Arch/ooo/WHAT_IF.md).

The workload evaluator reuses validated sample windows across compatible model
configurations. It retains source hash checks. Project descriptions must still
match the C2 selection.
It resets timing and component state for each model. This reduces repeated C2
validation. It does not reuse warmed hardware state or change sampling accuracy.

## Paired structure deltas

`rvw arch ooo-delta PLAN --out NEW_DIRECTORY --json` compares measured
and predicted IPC changes. MCP `arch_ooo_delta` runs the same command.
The plan uses schema `rvw.ooo-delta-plan/1`. Paths resolve beside the plan.
It names `config`, a saved base `calibration`, optional `max_cycles`,
`variants` and `samples`. Each variant has a unique `id` and a `changes`
object with exactly one numeric parameter path, such as
`{"id":"small-iq","changes":{"issue_entries":16}}`.
Each sample has `id`, `base` and `variants`. The base and each variant
capture contain `elf`, `c1` and `trace` paths. Sample variant keys must
match the declared IDs.

The command checks conclusive C1 passes, ELF hashes, C1/C2 identity, complete
traces and equal decoded instruction and address streams. Each pair must use the
same seed and memory timing. It checks the saved calibration captures and
the base configuration and engine hashes. It does not fit any parameter.
Every model variant uses the base instruction stream.

Changes are `variant_ipc/base_ipc - 1`. A wrong delta has a wrong sign or
an absolute prediction error greater than half the measured change.
The report gives percentage-point error and relative error separately.
A zero measured change has no relative error. Its exact sign is still
checked. This is a retrospective comparison. The command does not run RTL
or Spike and does not establish predictive fidelity.

The [initial NaxRiscv delta table](../../../../examples/naxriscv/rvw/arch/delta-initial-results.json)
records all 24 program/variant pairs. Fourteen fail the sign or half-size
criterion. All nine zero RTL changes are predicted correctly. Only one
of the 15 nonzero changes meets the criterion. This table uses one fixed
base fit. It does not establish reliable structure-size predictions.

## Compacting issue queue

Optional `issue_queue_policy: compacting` allocates a line of
`rename_width` slots for each rename group. A line stays allocated until
all its operations complete. Only complete oldest lines can be reused.
This represents age-ordered queue compaction and delayed wakeup reuse.
Younger empty slots cannot admit another group while the oldest line is
busy. Partial rename groups still use a whole line. Capacity must be a
multiple of rename width. The default `associative` policy keeps the
existing individual slot reuse at issue.

This policy runs in Python. It approximates wakeup with operation
completion. It does not reproduce every registered queue handshake.
The RTL adapter selects this policy in project data. The generic model
contains no core signal names.

The compacting policy includes one registered cycle between completion and
line reuse. It shares queue capacity with captured wrong-path operations.
Replay can keep pending operations while rename waits for queue capacity.

Optional `frontend.fetch_blocks_per_cycle` limits the number of distinct
PC blocks fetched in one cycle. Zero is the default and keeps the existing
unlimited block policy. One models a single fetch-block port. The
`block_bytes` field sets the block size. An entry point in the last lane
can therefore use only one instruction slot from that block. The next
block waits for another cycle. `fetch_block_limit_cycles` counts this
restriction. Instruction count width remains a separate limit.

A fit plan can set `objective: ipc` to minimize relative IPC error instead
of the default relative cycle error. Mapped-event errors keep equal
weight with that timing metric. Selection still uses training samples
only. Cycle error and IPC error are different ratios, so they can select
different candidates. The fit report names its objective.

## Measured structure deltas

The PR #1218 model meets the delta criterion on only two of 15 nonzero RTL changes. All nine zero changes match. The later drain stage reaches five of 15; ten deltas still fail. Structure-size choices still need RTL measurements. Use the model to select experiments and inspect possible bottlenecks. The current results do not qualify design decisions for Apple M-series or Zen 5 class cores.

| Variant | Initial outside criterion | Revised outside criterion |
|---|---:|---:|
| iq16 | 6/6 | 4/6 |
| rob128 | 0/6 | 0/6 |
| lq8 | 5/6 | 6/6 |
| sq8 | 3/6 | 3/6 |

The revised base-only fit gives 10.7% mean absolute IPC error on training,
7.6% on the original five held-out programs and 7.5% across six.
The buffered baseline gave 20.7%, 13.0% and 12.4%.
Better base IPC does not establish delta accuracy. Towers still has
+20.3% IPC error. Only two nonzero deltas meet the sign and half-size
criterion. Sensitivity identifies IQ first but ties SQ, LQ and ROB;
Kendall tau-b is 0.707 with three unresolved pairs.

See [all RTL, delta, fit and rank tables](../../../../examples/naxriscv/README.md#measured-delta-study-2026-11-13).
Finite store drain, wrong-path queue pressure and exact replay remain open.

## Delta diagnosis before resource changes

The 13 failures all underpredict a loss. None predicts a gain. The table
uses the retained paired probe counters and `rvw perf topdown` results in
`examples/naxriscv/rvw/arch/mechanism-results.json`. Counter occupancy is
a sum over cycles, not a peak. B is the back-end slot fraction.

| Structure | Program | RTL / model change (%) | Pressure counter, base to variant | B (%), base to variant |
|---|---|---:|---|---|
| iq16 | median | -1.682 / -0.155 | iq_push_blocked: 132 to 525 | 49.47 to 50.25 |
| iq16 | qsort | -0.617 / -0.276 | iq_push_blocked: 1419 to 5649 | 46.46 to 46.83 |
| iq16 | multiply | -0.303 / -0.088 | iq_push_blocked: 17 to 153 | 25.71 to 25.81 |
| iq16 | memcpy | -12.497 / -5.890 | iq_push_blocked: 5731 to 11187 | 36.30 to 44.08 |
| lq8 | median | -1.057 / +0.000 | lq_full_cycles: 0 to 483 | 49.47 to 49.98 |
| lq8 | qsort | -0.359 / +0.000 | lq_full_cycles: 0 to 6681 | 46.46 to 46.66 |
| lq8 | multiply | -0.021 / +0.000 | lq_full_cycles: 0 to 92 | 25.71 to 25.73 |
| lq8 | towers | -1.388 / -0.108 | lq_full_cycles: 130 to 1213 | 47.00 to 48.35 |
| lq8 | vvadd | -2.902 / +0.000 | lq_full_cycles: 0 to 1545 | 28.22 to 30.28 |
| lq8 | memcpy | -7.988 / -3.490 | lq_full_cycles: 0 to 17122 | 36.30 to 41.43 |
| sq8 | qsort | -0.294 / +0.000 | sq_full_cycles: 0 to 1180 | 46.46 to 46.65 |
| sq8 | towers | -4.393 / -0.054 | sq_full_cycles: 124 to 2432 | 47.00 to 49.68 |
| sq8 | memcpy | -10.902 / -2.602 | sq_full_cycles: 2982 to 8768 | 36.30 to 43.26 |

IQ: four failures. Median, qsort and multiply have small losses below 2%.
Memcopy has a 12.5% loss. Dispatch blocking increases in both groups.
The model has compacting lines, but committed instructions omit speculative
queue demand. Missing demand and registered scheduling can hide capacity cost.

LQ: six failures. Five predicted changes are zero or below 0.11% in size.
Memcopy loses 7.99% in RTL and 3.49% in the model. Smaller capacity increases
back-end slots. The committed trace omits loads that are later squashed.
Replay can also retain entries while a miss or address hazard resolves.

SQ: three failures. Qsort predicts zero for a 0.294% loss. Towers predicts
0.054% loss for 4.393%. Memcopy predicts 2.602% loss for 10.902%.
The buffered model frees stores at commit. RTL can retain stores until drain.
This hides store pressure and forwarding from undrained stores.

ROB: no failed pairs. Doubling capacity changes no measured IPC here.
This does not test whether the model predicts a cost when ROB capacity shrinks.

These are mechanism hypotheses, not isolated causes. Execute and commit
reschedule counters include branch recovery. They do not identify individual
cache or memory-order replays. Refill counts alone give no replay window.
The paired partitions describe where slots went. They cannot prove which
missing mechanism caused a specific IPC loss. Exact replay needs typed,
instruction-linked reschedule events before it can be claimed.

## Statistical wrong-path occupancy

`wrong_path_occupancy: true` enables a deterministic filler when a functional
path provider is absent. It samples the full committed instruction mix in
trace order. Branch and system instructions become inert ALU work. Prediction occurs at rename. Filler enters rename at the fetch rate
until branch resolution, including time when the branch waits to issue.
It uses shared ROB, IQ and LSQ capacity and is squashed before commit.
Its loads and stores do not change component cache state. It has no invented
register dependencies. This is an occupancy approximation, not exact replay.
The existing explicit Spike path provider takes precedence.

The Spike path capture on main only supports sequential prediction. It cannot
supply paths for the gshare study. The filler therefore supports that study,
but its mix is a committed-path proxy. Actual wrong-path mix is unmeasured.
Predictor training occurs at issue. Nested speculation and speculative
history repair remain absent. These limits can hide queue-size costs.

## Resource study: occupancy

This stage meets the criterion on 13/24 pairs and 4/15 nonzero changes.
Training mean absolute IPC error is 7.15%.
Held-out mean absolute IPC error is 9.48% across six programs.
Same-step pooled elasticity rank tau-b is 0.667, with 0 model ties.
This rank uses the measured large steps. It is separate from the original
local sensitivity tau-b of 0.707 with three unresolved ties. The original
same-step rank is 0.667. Parameters stay fixed at the base-only fit.
No variant result selects a parameter.

| Variant | Program | RTL change (%) | Model change (%) | Criterion |
|---|---|---:|---:|---|
| iq16 | median | -1.682 | -0.613 | outside |
| rob128 | median | +0.000 | +0.000 | within |
| lq8 | median | -1.057 | +0.000 | outside |
| sq8 | median | +0.000 | +0.000 | within |
| iq16 | qsort | -0.617 | -0.221 | outside |
| rob128 | qsort | +0.000 | +0.000 | within |
| lq8 | qsort | -0.359 | +0.000 | outside |
| sq8 | qsort | -0.294 | +0.000 | outside |
| iq16 | multiply | -0.303 | -0.217 | within |
| rob128 | multiply | +0.000 | +0.000 | within |
| lq8 | multiply | -0.021 | +0.000 | outside |
| sq8 | multiply | +0.000 | +0.000 | within |
| iq16 | towers | -0.627 | -1.705 | outside |
| rob128 | towers | +0.000 | +0.000 | within |
| lq8 | towers | -1.388 | -0.041 | outside |
| sq8 | towers | -4.393 | -0.069 | outside |
| iq16 | vvadd | -8.244 | -8.658 | within |
| rob128 | vvadd | +0.000 | +0.000 | within |
| lq8 | vvadd | -2.902 | +0.595 | outside |
| sq8 | vvadd | +0.000 | +0.000 | within |
| iq16 | memcpy | -12.497 | -8.715 | within |
| rob128 | memcpy | +0.000 | +0.000 | within |
| lq8 | memcpy | -7.988 | -4.075 | within |
| sq8 | memcpy | -10.902 | -3.090 | outside |

[Retained results](../../../../examples/naxriscv/rvw/arch/occupancy-results.json) include
the configuration, engine hash, absolute errors and paired results.

## Finite store drain

`store_drain_width` defaults to zero and keeps the earlier policy. A positive
value needs `store_policy: buffered`. Stores keep their shared store-queue
slot after commit. A FIFO sends committed stores to the cache at this width.
Hit latency is pipelined. Additional refill delay blocks the head. A full
store queue stops rename. Commit uses slots already reserved at rename, so
it needs no second buffer allocation. Fences wait for drain acceptance.
Loads check undrained stores as well as older ROB stores. Full overlap
forwards. Partial overlap waits until the undrained store leaves the queue.

Cache writes start at drain, not at speculative store execution. The run
still ends at last retirement. It does not add final store visibility time
after the measured program ends. `stores_drained`, `store_drain_blocked`,
`store_drain_service_cycles` and `store_drain_fence_wait` describe this policy.
This model does not reproduce cache-coherence acknowledgement or device I/O.

## Resource study: drain

This stage meets the criterion on 14/24 pairs and 5/15 nonzero changes.
Training mean absolute IPC error is 7.33%.
Held-out mean absolute IPC error is 9.48% across six programs.
Same-step pooled elasticity rank tau-b is 1.000, with 0 model ties.
This rank uses the measured large steps. It is separate from the original
local sensitivity tau-b of 0.707 with three unresolved ties. The original
same-step rank is 0.667. Parameters stay fixed at the base-only fit.
No variant result selects a parameter.

| Variant | Program | RTL change (%) | Model change (%) | Criterion |
|---|---|---:|---:|---|
| iq16 | median | -1.682 | -0.613 | outside |
| rob128 | median | +0.000 | +0.000 | within |
| lq8 | median | -1.057 | +0.000 | outside |
| sq8 | median | +0.000 | +0.000 | within |
| iq16 | qsort | -0.617 | -0.274 | outside |
| rob128 | qsort | +0.000 | +0.000 | within |
| lq8 | qsort | -0.359 | +0.000 | outside |
| sq8 | qsort | -0.294 | +0.000 | outside |
| iq16 | multiply | -0.303 | -0.217 | within |
| rob128 | multiply | +0.000 | +0.000 | within |
| lq8 | multiply | -0.021 | +0.000 | outside |
| sq8 | multiply | +0.000 | +0.000 | within |
| iq16 | towers | -0.627 | -1.719 | outside |
| rob128 | towers | +0.000 | +0.000 | within |
| lq8 | towers | -1.388 | -0.041 | outside |
| sq8 | towers | -4.393 | -0.507 | outside |
| iq16 | vvadd | -8.244 | -8.658 | within |
| rob128 | vvadd | +0.000 | +0.000 | within |
| lq8 | vvadd | -2.902 | +0.595 | outside |
| sq8 | vvadd | +0.000 | +0.000 | within |
| iq16 | memcpy | -12.497 | -8.699 | within |
| rob128 | memcpy | +0.000 | +0.000 | within |
| lq8 | memcpy | -7.988 | -4.058 | within |
| sq8 | memcpy | -10.902 | -9.613 | within |

[Retained results](../../../../examples/naxriscv/rvw/arch/drain-results.json) include
the configuration, engine hash, absolute errors and paired results.

## Bounded memory retry window

`cache_miss_replay: true` needs an explicit component L1 data cache. A load
response longer than the declared hit latency schedules one retry at response
completion. The load keeps its compacting queue line while it waits. At the
response, the load and all younger ROB instructions lose their completion
state. They enter a pending retry window and re-enter the IQ at rename width.
IQ and per-class capacities still apply. New rename waits for pending retries.
The existing `replay_penalty` applies. The missed load retries at most once.
Already started cache requests and execution reservations remain consumed.

Memory-order violations now use the same bounded readmission path. Replayed
instructions retain ROB and LSQ slots. Completed younger queue lines can be
released, so their operations wait outside the IQ until readmission has space.
`cache_miss_replays`, `replay_readmitted`, `replay_queue_blocked` and the
`replay_pending` peak distinguish these costs from ordinary branch recovery.

This policy is an approximation. A long response can include contention or a
TLB walk. It does not prove that RTL replays every cache miss. The retained
execute and commit reschedule counters combine branch, trap and LSU causes.
They do not identify a typed LSU retry window. The existing penalty of five
cycles stays fixed. It was not derived from those mixed counters. Exact
probe-driven replay is **not implemented or validated**. Typed reason and
instruction-linked retry events are needed before that claim can be made.

A memory retry also squashes active wrong-path filler. It must not occupy the
IQ while older correct-path instructions wait for readmission. The legacy
`replayed_instructions` counter counts selected ROB invalidations, including
unissued work and filler later squashed. `issued` counts actual execution
attempts. Use `replay_readmitted` for admission demand. These counters have
different predicates and cannot be equated with RTL reschedule totals.

### Retry counters and RTL observation limits

| Program | Model cache retries | Model memory-order recoveries | RTL execute reschedules | RTL commit reschedules | RTL D-cache refills |
|---|---:|---:|---:|---:|---:|
| towers | 0 | 6 | 208 | 207 | 10 |
| vvadd | 56 | 0 | 51 | 51 | 79 |
| rsort | 536 | 9 | 644 | 643 | 1082 |
| memcpy | 506 | 0 | 48 | 47 | 1009 |
| dhrystone | 8 | 1 | 657 | 644 | 28 |
| spmv | 901 | 4 | 11369 | 10833 | 1238 |
| median | 50 | 0 | 1158 | 1042 | 80 |
| qsort | 264 | 0 | 14915 | 14042 | 272 |
| multiply | 17 | 0 | 286 | 285 | 29 |

These predicates differ. RTL reschedules combine causes. Refills include
stores and speculative traffic. Neither total is an LSU retry count. The
model penalty stays five cycles. No rate or window is inferred from these
totals, and no matching-event error ratio is reported.

## Resource study: replay

This stage meets the criterion on 9/24 pairs and 1/15 nonzero changes.
Training mean absolute IPC error is 9.46%.
Held-out mean absolute IPC error is 9.54% across six programs.
Same-step pooled elasticity rank tau-b is 1.000, with 0 model ties.
This rank uses the measured large steps. It is separate from the original
local sensitivity tau-b of 0.707 with three unresolved ties. The original
same-step rank is 0.667. Parameters stay fixed at the base-only fit.
No variant result selects a parameter.

| Variant | Program | RTL change (%) | Model change (%) | Criterion |
|---|---|---:|---:|---|
| iq16 | median | -1.682 | +0.649 | outside |
| rob128 | median | +0.000 | +0.000 | within |
| lq8 | median | -1.057 | +0.000 | outside |
| sq8 | median | +0.000 | +0.000 | within |
| iq16 | qsort | -0.617 | +0.400 | outside |
| rob128 | qsort | +0.000 | +0.000 | within |
| lq8 | qsort | -0.359 | +0.064 | outside |
| sq8 | qsort | -0.294 | +0.000 | outside |
| iq16 | multiply | -0.303 | +0.182 | outside |
| rob128 | multiply | +0.000 | +0.000 | within |
| lq8 | multiply | -0.021 | +0.000 | outside |
| sq8 | multiply | +0.000 | +0.000 | within |
| iq16 | towers | -0.627 | -1.317 | outside |
| rob128 | towers | +0.000 | -0.067 | outside |
| lq8 | towers | -1.388 | -0.736 | within |
| sq8 | towers | -4.393 | -0.523 | outside |
| iq16 | vvadd | -8.244 | -0.981 | outside |
| rob128 | vvadd | +0.000 | +0.000 | within |
| lq8 | vvadd | -2.902 | +0.000 | outside |
| sq8 | vvadd | +0.000 | +0.000 | within |
| iq16 | memcpy | -12.497 | -0.770 | outside |
| rob128 | memcpy | +0.000 | +0.000 | within |
| lq8 | memcpy | -7.988 | +0.037 | outside |
| sq8 | memcpy | -10.902 | -0.734 | outside |

[Retained results](../../../../examples/naxriscv/rvw/arch/replay-results.json) include
the configuration, engine hash, absolute errors and paired results.

## Filler independence and corrected ablation

The earlier cursor advanced for every generated filler instruction, including
instructions never admitted. A larger ROB could therefore change a later
branch's mix. That was an artifact of generation capacity. Filler now starts
at the same dynamic branch position in the measured trace for every variant.
The per-branch prefix is independent of ROB and queue sizes.

`replay_window: true` selects bounded memory-order readmission without a
component cache. `cache_miss_replay: true` also enables this path. With both
false, the earlier memory-order admission policy stays available for ablation.
Recovery still discards active wrong work in every policy.

The corrected baseline, occupancy, drain and retry scores below share one
engine and the same fitted timing parameters. The earlier stage tables and
`*-preseed-results.json` files are historical. They must not be mixed with
the corrected stage results when comparing mechanism effects.

## Resource study: baseline

This stage meets the criterion on 11/24 pairs and 2/15 nonzero changes.
Training mean absolute IPC error is 10.67%.
Held-out mean absolute IPC error is 7.47% across six programs.
Same-step pooled elasticity rank tau-b is 0.667, with 0 model ties.
This rank uses the measured large steps. It is separate from the original
local sensitivity tau-b of 0.707 with three unresolved ties. The original
same-step rank is 0.667. Parameters stay fixed at the base-only fit.
No variant result selects a parameter.

| Variant | Program | RTL change (%) | Model change (%) | Criterion |
|---|---|---:|---:|---|
| iq16 | median | -1.682 | -0.155 | outside |
| rob128 | median | +0.000 | +0.000 | within |
| lq8 | median | -1.057 | +0.000 | outside |
| sq8 | median | +0.000 | +0.000 | within |
| iq16 | qsort | -0.617 | -0.276 | outside |
| rob128 | qsort | +0.000 | +0.000 | within |
| lq8 | qsort | -0.359 | +0.000 | outside |
| sq8 | qsort | -0.294 | +0.000 | outside |
| iq16 | multiply | -0.303 | -0.088 | outside |
| rob128 | multiply | +0.000 | +0.000 | within |
| lq8 | multiply | -0.021 | +0.000 | outside |
| sq8 | multiply | +0.000 | +0.000 | within |
| iq16 | towers | -0.627 | -0.860 | within |
| rob128 | towers | +0.000 | +0.000 | within |
| lq8 | towers | -1.388 | -0.108 | outside |
| sq8 | towers | -4.393 | -0.054 | outside |
| iq16 | vvadd | -8.244 | -7.976 | within |
| rob128 | vvadd | +0.000 | +0.000 | within |
| lq8 | vvadd | -2.902 | +0.000 | outside |
| sq8 | vvadd | +0.000 | +0.000 | within |
| iq16 | memcpy | -12.497 | -5.890 | outside |
| rob128 | memcpy | +0.000 | +0.000 | within |
| lq8 | memcpy | -7.988 | -3.490 | outside |
| sq8 | memcpy | -10.902 | -2.602 | outside |

[Retained results](../../../../examples/naxriscv/rvw/arch/baseline-results.json) include
the configuration, engine hash, absolute errors and paired results.

## Resource study: occupancy

This stage meets the criterion on 15/24 pairs and 6/15 nonzero changes.
Training mean absolute IPC error is 7.15%.
Held-out mean absolute IPC error is 9.11% across six programs.
Same-step pooled elasticity rank tau-b is 0.667, with 0 model ties.
This rank uses the measured large steps. It is separate from the original
local sensitivity tau-b of 0.707 with three unresolved ties. The original
same-step rank is 0.667. Parameters stay fixed at the base-only fit.
No variant result selects a parameter.

| Variant | Program | RTL change (%) | Model change (%) | Criterion |
|---|---|---:|---:|---|
| iq16 | median | -1.682 | -0.825 | outside |
| rob128 | median | +0.000 | +0.000 | within |
| lq8 | median | -1.057 | +0.000 | outside |
| sq8 | median | +0.000 | +0.000 | within |
| iq16 | qsort | -0.617 | -0.342 | within |
| rob128 | qsort | +0.000 | +0.000 | within |
| lq8 | qsort | -0.359 | +0.000 | outside |
| sq8 | qsort | -0.294 | +0.000 | outside |
| iq16 | multiply | -0.303 | -0.214 | within |
| rob128 | multiply | +0.000 | +0.000 | within |
| lq8 | multiply | -0.021 | +0.000 | outside |
| sq8 | multiply | +0.000 | +0.000 | within |
| iq16 | towers | -0.627 | -1.477 | outside |
| rob128 | towers | +0.000 | +0.000 | within |
| lq8 | towers | -1.388 | -0.804 | within |
| sq8 | towers | -4.393 | -0.216 | outside |
| iq16 | vvadd | -8.244 | -8.659 | within |
| rob128 | vvadd | +0.000 | +0.000 | within |
| lq8 | vvadd | -2.902 | +0.596 | outside |
| sq8 | vvadd | +0.000 | +0.000 | within |
| iq16 | memcpy | -12.497 | -8.691 | within |
| rob128 | memcpy | +0.000 | +0.000 | within |
| lq8 | memcpy | -7.988 | -4.072 | within |
| sq8 | memcpy | -10.902 | -3.079 | outside |

[Retained results](../../../../examples/naxriscv/rvw/arch/occupancy-results.json) include
the configuration, engine hash, absolute errors and paired results.

## Resource study: drain

This stage meets the criterion on 15/24 pairs and 6/15 nonzero changes.
Training mean absolute IPC error is 7.31%.
Held-out mean absolute IPC error is 9.11% across six programs.
Same-step pooled elasticity rank tau-b is 1.000, with 0 model ties.
This rank uses the measured large steps. It is separate from the original
local sensitivity tau-b of 0.707 with three unresolved ties. The original
same-step rank is 0.667. Parameters stay fixed at the base-only fit.
No variant result selects a parameter.

| Variant | Program | RTL change (%) | Model change (%) | Criterion |
|---|---|---:|---:|---|
| iq16 | median | -1.682 | -0.825 | outside |
| rob128 | median | +0.000 | +0.000 | within |
| lq8 | median | -1.057 | +0.000 | outside |
| sq8 | median | +0.000 | +0.000 | within |
| iq16 | qsort | -0.617 | -0.173 | outside |
| rob128 | qsort | +0.000 | +0.000 | within |
| lq8 | qsort | -0.359 | +0.000 | outside |
| sq8 | qsort | -0.294 | +0.000 | outside |
| iq16 | multiply | -0.303 | -0.214 | within |
| rob128 | multiply | +0.000 | +0.000 | within |
| lq8 | multiply | -0.021 | +0.000 | outside |
| sq8 | multiply | +0.000 | +0.000 | within |
| iq16 | towers | -0.627 | -1.477 | outside |
| rob128 | towers | +0.000 | +0.000 | within |
| lq8 | towers | -1.388 | -0.804 | within |
| sq8 | towers | -4.393 | -0.658 | outside |
| iq16 | vvadd | -8.244 | -8.659 | within |
| rob128 | vvadd | +0.000 | +0.000 | within |
| lq8 | vvadd | -2.902 | +0.596 | outside |
| sq8 | vvadd | +0.000 | +0.000 | within |
| iq16 | memcpy | -12.497 | -8.691 | within |
| rob128 | memcpy | +0.000 | +0.000 | within |
| lq8 | memcpy | -7.988 | -4.072 | within |
| sq8 | memcpy | -10.902 | -9.605 | within |

[Retained results](../../../../examples/naxriscv/rvw/arch/drain-results.json) include
the configuration, engine hash, absolute errors and paired results.

## Resource study: replay

This stage meets the criterion on 10/24 pairs and 1/15 nonzero changes.
Training mean absolute IPC error is 9.46%.
Held-out mean absolute IPC error is 9.55% across six programs.
Same-step pooled elasticity rank tau-b is 1.000, with 0 model ties.
This rank uses the measured large steps. It is separate from the original
local sensitivity tau-b of 0.707 with three unresolved ties. The original
same-step rank is 0.667. Parameters stay fixed at the base-only fit.
No variant result selects a parameter.

| Variant | Program | RTL change (%) | Model change (%) | Criterion |
|---|---|---:|---:|---|
| iq16 | median | -1.682 | +0.649 | outside |
| rob128 | median | +0.000 | +0.000 | within |
| lq8 | median | -1.057 | +0.000 | outside |
| sq8 | median | +0.000 | +0.000 | within |
| iq16 | qsort | -0.617 | +0.400 | outside |
| rob128 | qsort | +0.000 | +0.000 | within |
| lq8 | qsort | -0.359 | +0.064 | outside |
| sq8 | qsort | -0.294 | +0.000 | outside |
| iq16 | multiply | -0.303 | +0.182 | outside |
| rob128 | multiply | +0.000 | +0.000 | within |
| lq8 | multiply | -0.021 | +0.000 | outside |
| sq8 | multiply | +0.000 | +0.000 | within |
| iq16 | towers | -0.627 | -1.384 | outside |
| rob128 | towers | +0.000 | +0.000 | within |
| lq8 | towers | -1.388 | -0.816 | within |
| sq8 | towers | -4.393 | -0.590 | outside |
| iq16 | vvadd | -8.244 | -0.981 | outside |
| rob128 | vvadd | +0.000 | +0.000 | within |
| lq8 | vvadd | -2.902 | +0.000 | outside |
| sq8 | vvadd | +0.000 | +0.000 | within |
| iq16 | memcpy | -12.497 | -0.770 | outside |
| rob128 | memcpy | +0.000 | +0.000 | within |
| lq8 | memcpy | -7.988 | +0.037 | outside |
| sq8 | memcpy | -10.902 | -0.734 | outside |

[Retained results](../../../../examples/naxriscv/rvw/arch/replay-results.json) include
the configuration, engine hash, absolute errors and paired results.

## Resource study: window

This stage meets the criterion on 15/24 pairs and 6/15 nonzero changes.
Training mean absolute IPC error is 7.31%.
Held-out mean absolute IPC error is 9.08% across six programs.
Same-step pooled elasticity rank tau-b is 1.000, with 0 model ties.
This rank uses the measured large steps. It is separate from the original
local sensitivity tau-b of 0.707 with three unresolved ties. The original
same-step rank is 0.667. Parameters stay fixed at the base-only fit.
No variant result selects a parameter.

| Variant | Program | RTL change (%) | Model change (%) | Criterion |
|---|---|---:|---:|---|
| iq16 | median | -1.682 | -0.825 | outside |
| rob128 | median | +0.000 | +0.000 | within |
| lq8 | median | -1.057 | +0.000 | outside |
| sq8 | median | +0.000 | +0.000 | within |
| iq16 | qsort | -0.617 | -0.173 | outside |
| rob128 | qsort | +0.000 | +0.000 | within |
| lq8 | qsort | -0.359 | +0.000 | outside |
| sq8 | qsort | -0.294 | +0.000 | outside |
| iq16 | multiply | -0.303 | -0.214 | within |
| rob128 | multiply | +0.000 | +0.000 | within |
| lq8 | multiply | -0.021 | +0.000 | outside |
| sq8 | multiply | +0.000 | +0.000 | within |
| iq16 | towers | -0.627 | -1.384 | outside |
| rob128 | towers | +0.000 | +0.000 | within |
| lq8 | towers | -1.388 | -0.816 | within |
| sq8 | towers | -4.393 | -0.590 | outside |
| iq16 | vvadd | -8.244 | -8.659 | within |
| rob128 | vvadd | +0.000 | +0.000 | within |
| lq8 | vvadd | -2.902 | +0.596 | outside |
| sq8 | vvadd | +0.000 | +0.000 | within |
| iq16 | memcpy | -12.497 | -8.691 | within |
| rob128 | memcpy | +0.000 | +0.000 | within |
| lq8 | memcpy | -7.988 | -4.072 | within |
| sq8 | memcpy | -10.902 | -9.605 | within |

[Retained results](../../../../examples/naxriscv/rvw/arch/window-results.json) include
the configuration, engine hash, absolute errors and paired results.
