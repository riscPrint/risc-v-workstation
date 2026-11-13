# Co-simulation transports contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## TestRIG socket transport (`rvw.dii/1`)

`rvw cosim dii serve` and `replay` use RVFI-DII v1, separate from C1/C2.
See [the hook contract](TESTRIG.md) for wire pins, reset, timing and memory.
The server accepts at most 65,536 tokens per stream and a finite stream count.
Socket operations share a per-stream deadline. Replay accepts exactly one
nonempty stream terminated by EndOfTrace. It records the token SHA-256 and
both endpoints. These labels do not verify the remote model or its ISA config.
The caller must supply an independent Sail model. Each endpoint returns ordered
88-byte retirement packets and a halt delimiter. Empty, short, truncated,
unsupported or timed-out streams cannot earn a match. Exit codes: match or
served 0, mismatch 1, error 2, inconclusive 3. `served` is not equivalence.
The result has `schema`, `protocol` and `status`. Mismatch adds `index` and
`differences`; match adds `instructions` and `trace_complete`. Short streams add
`cause`, `core_retired` and `sail_retired`. Errors add `message`. All results
print one JSON document. This CLI mode has no MCP endpoint yet.


### Observed prediction outcome extension

Kanata comments can contain one measured outcome per live instruction, predictor
and kind. Emit it before terminal R. Fields are tab separated:

```text
#rvw  1  prediction  ID  PREDICTOR  KIND  PREDICTED  ACTUAL  RECOVERY  WORK  WARMUP  ALIAS  CONTEXT
```

`KIND` is `direction`, `target` or `return`. Direction values are `taken` or
`not_taken`. Target and return values are nonnegative decimal or `0x` addresses.
`RECOVERY` counts cycles from resolution to resumed correct-path fetch.
`WORK` counts admitted wrong-path instructions attributed to this resolution.
Both are nonnegative integers, or `?` for unknown. The producer must observe
these quantities. R type 1 and stage residence cannot supply them.
`WARMUP` and `ALIAS` are observed `true`, `false` or `?`. `CONTEXT` is a project
context token, or `?`. Tokens cannot contain tabs or newlines. A predictor name
is required. Duplicate outcomes, ended IDs and malformed known records fail.

Reports separate predictor, kind, warmup, alias and context groups. Unknown
costs stay unknown. Shared recovery costs can occur in multiple kinds. Do not
sum these groups as global lost cycles. Context differences and alias flags
do not establish causal effects. Project probes own the event bindings; the
generic reader does not simulate a predictor or infer missing observations.
`rvw.perf/1` adds `predictions.effects` (additive): per predictor and kind,
`overall`, `steady_state` (warmup=false and alias=false only) and `by_warmup`,
`by_alias`, `by_context` maps. Each holds `outcomes`, `correct`, `incorrect`,
`accuracy` (null when empty) and mispredict-only `mispredict_recovery_cycles`
and `mispredict_wrong_path_instructions` with `samples`, `unknown`, `sum`, `max`
and, when observed, `mean`, `p50`, `p95`.

### Property activation and requirement links

A `cov prove` point can declare an `activation` SystemVerilog expression. The
runner creates a separate cover job with the same captured inputs and assumptions.
The expression must be one statement-free expression. A successful cover needs
exit 0, PASS, no free wires and the existing sanity guard. Only then does
`proof_cones.properties[].activation.status` become `reached`. Other evidence is
`inconclusive`; an absent predicate is `not_measured`. This is a user-declared
activation predicate. It does not establish full property non-vacuity.

The additive `rvw.proof-cones/1` `requirements` array joins each declared
`requirement_id` to sorted `property_ids`. Property records join activation,
structural cones and the unavailable solver core through `property_id`. Every
requirement status stays `inconclusive`. A list of linked properties is not a
complete set of functional obligations. A structural cone is not a solver core.
These fields do not change exclusion or gate verdicts.


### Related clocks as periodic sampled schedules

Event BMC accepts repeated `--clock-schedule PORT=BITS` options. Declare every
clock, including `--clock`, or declare none. `clk=01` and `other=0011` describe
a 2:1 rate ratio. Rotate the bit strings to declare a phase. The leftmost bit is
sample zero. Each pattern repeats forever. Each must contain both levels and
2..256 samples. The joint period must not exceed 4096 samples. These are explicit
proof restrictions, not measured hardware clock relationships.

One solver step advances one global sample. The wrapper constrains clock levels
at that sample. The event backend samples property data before its triggering
edge; data that changes with a clock uses its previous sample at that edge.
Clock schedules do not add analog timing, delta cycles, jitter or events between
samples. When no schedule is given, the independent arbitrary-rate event model applies.
The existing reset harness still counts primary-clock edges. Async reset state
requires the separate `--async-reset` option. Unsupported state controls and raw
async-triggered properties remain refused. Replay and X flows remain unchanged.
`event_model.schedules` records the exact patterns; `relationships` states whether
the run used periodic schedules or unrelated clocks. Native phase tests require
both a passing same-phase reference and a failing opposite-phase reference.


### Sequential equivalence latency restrictions

The additive `rvw.formal.equiv/1` `restrictions.latency` is the nonnegative
candidate lag in clocks (0..64). The reference wrapper delays all output ports by
that amount. Both wrappers mask outputs until reset cycles plus settle cycles
plus latency cycles have elapsed. There is no input shift or protocol adapter.
`restrictions.unmatched_state` is `refuse` by default. With `prove`, unmatched
register names remain in the inventory but do not block a complete closed-output
proof. State equality is never assumed. Every partition must still have no
internal crossbits. Missing partitions, unknown results and tool failures remain
inconclusive. No named state relation or blackbox obligation is inferred.


### Imported single-sample implication

The slang import subset also accepts one top-level `Boolean |-> Boolean` in an
inline clocked assert or assume property. The pinned frontend patch evaluates
both operands at the same pre-update sample and checks `!antecedent || consequent`.
The existing `disable iff` condition gates the check. There are no pending threads.
`|=>`, delays, repetition, chained and nested implication remain refused before
a proof job. Qualified engines remain SMTBMC/Yices and ABC BMC3. The captured
plugin bytes identify the applied lowering. This is not full temporal SVA support.

### Init platform review marker

An optional `rvw init --linker-script` platform template carries
`review_required: true`. The cosim platform loader refuses it. The owner must
check the RAM, reset PC, MMIO, PMP, interrupt, privilege and fault policies
against the core specification before removing the marker. A linker map alone
does not establish these policies.
### C1 simulation throughput extension

Optional C1 `metrics.sim_khz` is `cycles / details.execution_s / 1000`.
`metrics.sim_instructions_per_s` is `instret / details.execution_s`.
The denominator includes adapter execution and artifact handling after model
readiness. It excludes model compilation and elaboration. The rates are absent
if seconds are missing, non-finite or non-positive, or counters are invalid.
These are throughput measurements, not architectural IPC or correctness claims.
C3 keeps the metrics. The history dashboard groups them by core, suite and preset.
Short workloads and concurrent jobs can give noisy samples. Use repeated long
workloads with fixed stimulus and equivalent complete C2 traces for comparisons.

`rvw.sim-speed/1` is a diagnostic report from `rvw regress speed-compare`.
It records `core`, `config`, `pairs`, geometric mean `speedup`, bootstrap
`speedup_ci95`, `resamples`, `bootstrap_seed` and `retain`. Each pair records
baseline/candidate C1 paths and hashes, native build hashes, complete C2 hashes,
execution run IDs, seconds and derived rates. A sample cannot be used twice.
At least five pairs of conclusive serial passing runs are required. Complete
validated C2 events, terminal counters, ELF, seed, preset and run inputs must
match. Each side must keep one native build identity. Default minimum sample
time is one second. Missing evidence or a difference gives exit 3.
`status: equivalent` is trace/result equivalence only. It is not ISA correctness,
C8 capture completeness or C4 acceptance. `retain` is a diagnostic timing filter:
the 95% interval lower bound must exceed one and all complete C2 files must
have the same raw SHA-256. `trace_bit_identical` reports this byte check.
Parsed equality alone can still report `equivalent`, but cannot retain an option.
`sim_khz.baseline` and `sim_khz.candidate` each record `geomean` and `ci95`.
These marginal percentile bootstrap intervals use the same pair resamples.
They include adapter and trace cost. They exclude model compilation.
The report does not change any options.

`rvw.sim-speed-sweep/1` records an explicit adapter, ELF hash, preset, host,
logical CPU count, seed, repeat count, thread counts, minimum sample seconds,
launch timeout, actual `order` of commands and completed `comparisons`.
Warmups are excluded from comparisons. Baseline/candidate order alternates
between pairs. Each process holds the selected core lock and uses `nice`.
The launch timeout includes the lock wait and is at most 1800 seconds.
Status stays `inconclusive` until all requested comparisons are equivalent.
A failed run stops the sweep. Cancellation stops the active process group.
Build costs, peak RSS, PGO and checkpoints are outside this report.


### UVM component results in C3

`rvw regress uvm` writes standalone `rvw.results/1` for the pinned
Accellera library and the bounded component suite in `Uvm/README.md`.
Entries use `kind: "uvm"` and the runtime seed. Normal passes require
successful exit, all expected test markers, one completion marker and no
UVM errors or fatals. The fault-detection entry requires the specific
RVFI mismatch and a failed simulation. A timeout, missing evidence or a
build failure is inconclusive with status `error`. These files have no
C1 ELF or complete C8 identity. They cannot establish C4 gate acceptance.

## Co-simulation capture inspection

`rvw cosim doctor --trace FILE` and MCP `cosim_doctor` return
`rvw.cosim-doctor/1`. Status `inspected` means all supplied C2 records validated.
It never means an architectural match. `compared` is always false.
`comparisons` describes configured checker scope from capture declarations.
`conditional_masks` gives allowed synchronization with its reason, not evidence
that it occurred. `platform_policy` gives explicit reference choices.
`trace_complete` requires a validated C2 end record. An incomplete valid prefix
can be inspected. Errors return status `error` and CLI exit 2. Inspection returns
CLI exit 0, including valid incomplete traces. No reference executable is needed.
