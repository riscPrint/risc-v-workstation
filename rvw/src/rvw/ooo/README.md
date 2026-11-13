# Generic OoO timing experiment

`rvw ooo CONFIG TRACE --max-cycles 1000000 --json` predicts timing from a
complete single-hart C2 trace. This engine does not use gem5. Spike traces
must first be exported as C2. RTL cycle timestamps are validated but do not
drive the prediction. The full trace is the measured region.

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
must be positive integers. These latency classes support decoded integer
instructions only. Compressed integer instructions use the shared decoder.
Fences, atomics, privileged, FP and vector operations are
unsupported. Branches and jumps need explicit latency classes. The engine rejects their traces. A missing or unsuccessful end
marker is an error. An exhausted model cycle budget is an error.

## Decisions

Within a cycle the engine commits, issues, renames, then fetches. Latency one
completes on the next cycle. Instructions can issue out of order. Rename
binds source operands to older producers. Integer x0 has no dependency.
Issue uses one shared queue and oldest-ready selection. Execution uses a
shared issue width with unlimited pipelined units. ROB and LSQ slots remain
allocated until commit. Memory instructions wait for older memory completion.
There is no address disambiguation, forwarding or store buffer model.

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
described below. Wrong-path execution and replay remain unsupported.
It retains the full trace in memory. Core elaboration export, calibration, held-out RTL correlation and prediction
ledgers remain separate work.
Do not use the existing gem5 report readers to certify this model.

Run targeted tests from the workstation root:

```sh
PYTHONPATH=rvw/src python -m pytest rvw/tests/test_ooo.py -q
```

See [the design](../../../../docs/design/own-core-model.md) for phases,
contracts, prior art and acceptance targets. Keep tuned core values in the
core project. Store measured evidence outside the repository.

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
The CLI has no cache provider yet. L1/L2/L3 cache policies, prefetch, memory
interconnect contention, and component-library adapters remain open.

`topdown` partitions commit slots. Retired instructions use `retiring` slots.
Remaining slots use `bad_speculation` during recovery, then `backend_bound`
when the ROB is nonempty, else `frontend_bound`. Fractions sum to one. This
simple model partition is not the hardware top-down method. Counters can be
compared with RTL only after matching their predicates. The wrong-path fetch
slot estimate is recovery penalty times fetch width per branch miss. It does
not consume issue or cache resources. Synthetic tests establish timing rules;
they do not establish RTL accuracy. Macro-op fusion, move/zero elimination,
memory renaming, and speculative dependence replay remain open.

## Optional compiled scheduler

Use `scripts/install.sh --with-ooo` to compile the C scheduler with the host C
compiler. Use the same flag with `--check` to check its ABI. No download is
needed. The library is `.tools/ooo/libooo.so` on Linux and macOS. The suffix
is fixed for discovery; macOS builds a native dynamic library.

The engine selects the library for integer ALU, multiply and divide streams
with at most two source registers. It preserves fetch, rename, ROB, issue,
commit, fixed execution latencies and physical-register pressure. Other
streams and configurations use Python. Front-end, translation, execution port
objects, class port limits, branches and memory are not accelerated yet.
Reports name the selected `backend`. Missing libraries use Python. An invalid
selected library is an error. Set `RVW_OOO_NATIVE=0` to force Python, or set it
to an explicit library path. Python callers can select `backend="python"` or
`backend="native"`. The latter requires a supported stream and installed
library. C2 parsing and input conversion still use Python.

The parity test checks 100 seeded synthetic integer schedules against Python,
including queue limits, dependencies, and physical-register capacity. This is
schedule parity with the reference model. It does not establish RTL accuracy.
