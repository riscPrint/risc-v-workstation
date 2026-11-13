# Deep formal runs contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Formal capacity reports

`rvw formal contracts` writes `rvw.formal-contracts/1` in a fresh output directory.
Fields are `status`, `plan_sha256`, `obligations`, `restrictions` and `input_capture`.
Each obligation has an `id`, `status`, and either a child `result` with `proof_kind`
or a reason that it was not run. Run obligations also list assumption cells and
their source locations. `conditional_proved` requires fresh unbounded
passes for every component and the closed composition. Other outcomes give
`inconclusive`. The command returns 0 only for `conditional_proved`. Input errors
return 2. This report is not a C4 acceptance gate or a reusable proof certificate.
The copied plan and child input captures bind the report to its inputs.

`rvw formal strengthen` writes `rvw.formal-strengthen/1`. It records `status`,
`candidates`, `certified`, `obligations` and `semantics`. Only fresh unbounded passes
can add a candidate to `certified`. The final target proof supplies `status`.
Certified candidates remain assertions in the final target. Source assumptions
remain environment restrictions. Neither observations nor bounded passes can
certify an invariant. Missing evidence gives an inconclusive result.

BMC/prove abstraction entries extend `cut_points` with `kind` and `plan_sha256`.
The semantics remain `unconstrained_anyseq`. No abstraction assumption is implicit.
See the [formal capacity interface](../rvw/src/rvw/formal/README.md#capacity-templates-and-contracts).

## Deep formal experiment reports

`rvw.formal-portfolio/1` records pinned self-contained RTL hashes, source
assumptions, engine rows, the first conclusive winner and observed cross-checks.
Its `pass` requires an unbounded engine answer. Bounded success is
`bounded_pass` on the engine row and cannot earn portfolio `pass`. Disagreement
makes the report `inconclusive`. Unavailable backends are `not_installed`.
No checks or failed preparation makes the report inconclusive without a winner.
The raw experiment adds no environment or activation guards.

`rvw.formal-engine-bench/1` records one row per case/engine pair. Its `pass`
means verdict agreement on each case, including agreement on a fault. It is not
a proof verdict for the benchmark design. Wall time includes engine preparation.
A requested depth does not claim a measured reached depth.

`rvw.formal-model-grid/1` records the canonical explicit-model SHA-256 and one
row per property. `pass` requires every row to prove its safety property.
`fail` requires a concrete graph counterexample. A spurious projected trace is
inconclusive until replay and refinement. Helper invariants require initiation
and consecution. The graph, including all memory choices, is a supplied input.
No RTL-to-graph correspondence or whole-core result is implied.

A distributed explicit-model grid adds `shards`, expected property names and
adapter source identities. The existing farm worker transports JSON model bytes
and formal result artifacts. It adds no C1 simulation claims. Transfer, identity
or coverage failure leaves that shard inconclusive. Real SSH execution requires
compatible installed adapters and trusted hosts.

`rvw.formal-rtl-refine/1` records frozen source hashes, automatically selected
state/RAM cuts and each refinement round. Abstract counterexamples remain
inconclusive. Only a cut-free failure reports `fail`. An unbounded proof of an
overapproximation can report `pass`. Budget expiry and engine errors remain
inconclusive. This flow preserves the existing guarded proof runner.

Raw engine portfolios with source assumptions remain inconclusive until a
separate activation check exists. Engine rows retain the observed conditional
answer. AIGER imports record original input bytes and the translated Verilog
and importer SHA-256 identities. Justice/fairness inputs are unsupported.
Relational strengthening uses `rvw.formal-strengthen/1` with independently
certified relational candidates in addition to unsigned bounds.

`rvw.formal-rtl-grid/1` reports one result per independently exported RTL
property case. It uses pinned source bundles and the same farm artifact adapter
as explicit-model grids. `pass` requires every case to earn a portfolio proof.
A concrete case failure reports `fail`. Missing remote properties are
inconclusive. The full exported property set must be supplied by the caller.

## Native formal engine diagnostics and benchmark totals

`rvw.formal-doctor/1` records installed dependencies, executable paths, supported
modes, and enabled adapter features. `qualification` is `not_measured`.
`status: pass` means the diagnostic completed. It does not mean a proof passed.
The `formal_doctor` MCP tool returns the same report.

`rvw.formal-engine-bench/1` adds `total_wall_s` per row, including preparation,
and `summary` per engine with solved, bounded passes, cases, and total wall time.
Only conclusive problem `pass` and `fail` count as solved. Missing tools and unsupported modes do
not count. SBY `UNKNOWN` with exit 4 is inconclusive. Inconsistent status and
exit code pairs are errors.

## SVA liveness-to-safety adapter

`rvw.formal-live/1` can select `backend=l2s`. The runner exposes generated live
and fair predicates, then uses `rvw.liveness-app/1` jobs. Result `jobs` retain
property id, engine status, proof kind, converted state-bit count, justice list,
limits and the native report path. Engine passes remain unknown at the frontend.
Bounded searches retain `bounded_lasso_search`; they do not become liveness proofs.

This adapter requires `--run`, one synchronous clock, a scalar active-high reset
and canonical net ranges. It applies one startup reset cycle, then deasserts
reset permanently. Fairness is conditional. Feasibility, activation and full
attribution remain unqualified. The underlying runner's state refusals remain.

## Unbounded SVA progress automata

`rvw.formal-live/1` accepts Boolean strong/weak until operators and a tested
single-clock unbounded sequence subset. Extended property rows record
`operator`; sequence rows also record `strength`, a `minimum` or `count`,
optional `maximum` for a literal count range, and
`completion` where applicable. Assert and assume sequence consequents default to
weak. Explicit strong sequences require finite completion for every request.
Optional `throughout=true` records a Boolean guard on an unbounded sequence.
The guard holds for every active sample, including completion. A latched failure
retains any guard violation. Idle samples after completion do not fail that
attempt. Nested guards combine without changing weak/strong completion rules.
Clock-local sampled functions use the same history emitter as finite SVA.
The converted full state includes their history registers. Depth, nesting,
width/sign and four-state comparison rules match the finite frontend. No
cross-clock sampled history is inferred. A latched fatal predicate records
finite impossibility. Count buckets retain
overlapping attempts. Goto and nonconsecutive literal ranges keep each permitted
completion until one succeeds or the maximum makes completion impossible. A separate owed set gives acceptance when each old group
finishes, even when requests continue. It never resets an old attempt on a new
request. Both native-live and liveness-to-safety routes use these predicates. Module-local
zero-argument named properties and aliases expand before this lowering. They
retain the assertion label. Recursive and duplicate definitions are refused.

The supported syntax and tested capacity limits are in the formal README and
generated support table. No finite cutoff replaces an unbounded endpoint.
Finite checks, general sequence composition, multi-clock sequences and reset
cancellation remain separate or unsupported. Native engine evidence keeps the
same conditional and inconclusive limits as the Boolean response adapter.

## Eventual-response liveness jobs

`rvw.formal-live/1` records `status`, `observation`, property ids, clock names,
`live` or `fair` cell wires, input capture and restrictions. The frontend accepts
single-clock Boolean eventual response and emits SBY `mode live` with
`aiger suprove`. It never substitutes a bounded response. Generated jobs report
`not_run`. Missing tools report `missing_tool`. Engine PASS remains unknown;
engine FAIL is a failure. The result does not certify activation or non-vacuity.
CLI `formal liveness` and MCP `formal_liveness` share this result.

## Bounded bug-hunting campaigns

`rvw.formal-bug-hunt/1` captures pinned source bytes once. Its manifest has the
same `top` and `sources` fields as engine-race, plus increasing positive
`depths`, bounded `engines`, and unique unsigned 64-bit `seeds`. Seeds apply to
rIC3 only. Every other engine runs once per depth. `attempts` records depth,
engine, seed, native rows and retained result path. `unstarted` records work
left after the budget expires or a counterexample stops the campaign. A complete
bounded schedule remains inconclusive. Only a concrete failure earns `fail`.
CLI `bug-hunt` and MCP `formal_bug_hunt` expose a budget and per-stage timeout.

Portfolio manifests can set `ric3_seed`. BMC probes the rIC3 help interface.
When it has `--end`, a recorded wrapper translates SBY's older bounded flags.
The wrapper clears inherited Python launcher variables and preserves native
output and exit status. `compatibility_sha256` identifies its captured bytes.


Composite SVA intents use `payloads` with per-field signal and width for Stream,
or per-field maximum value for Flow. Single-payload intent inputs remain valid.
Optional database binding emits `rvw.channel-bindings/1` beside the generated
SVA. It contains `bindings`, `input_capture` and `db_warnings`. Domain anchors,
clock/reset ports and widths resolve from SpinalDB. Ambiguous or mixed domains
are refused. A database warning is not a current-RTL match or timing result.

## EBMC native AIGER input

For an AIGER source, the EBMC adapter gives the original hash-checked `.aig`
bytes to EBMC's native reader. It does not pass a top-module override. EBMC
uses its own `aiger::main` transition system. The engine row records
`input_format: aiger_native`. Yosys's separate safety inventory still uses the
captured Verilog translation. `source_transforms` describes that preparation
translation; it is not EBMC's verification input. The importer rejects justice,
fairness and mixed ordinary-output/bad-state models before native execution.

## Formal app liveness-to-safety

`rvw.liveness-app/1` binds self-contained RTL, top, clock, active-high reset,
request, response and state-justice fairness expressions. `rvw.liveness-app-result/1`
retains the full state width, native safety result and captured inputs. Only an
unbounded safety pass receives `proof_kind=liveness_to_safety`. A bounded pass
is a bounded lasso search. `fairness_check` is `no_fairness`, `free_inputs`
(every fairness expression names only top-level inputs other than clock and
reset, and the design has no assumptions) or `not_checked`. A safety pass with
`not_checked` fairness is `inconclusive` (exit 3): fairness on outputs or state
can exclude the hung loop itself. Existential CTL deadlock freedom is not
established. Existing safety assertions are removed from this
separate job. Original assumptions remain.

## Typed uninterpreted arithmetic reports

`rvw.formal-smt-uf/1` records original and transformed SMT2 hashes, the
transformer hash, selected operators and global function names, operand widths
and occurrence counts. One global function serves each operator and width
across all states. Functions use named bit-vector sorts. Yosys witness and
assertion comments stay in the transformed file.

`rvw.formal-uf-prove/1` records `status`, `proof_kind`, `native_status`,
`native_result`, pinned source hashes, wrapper hash and captured `smt_models`.
`rewritten_operations` is the winning model's occurrence count, or null when
there is no winner. `pass` requires a captured model and an unbounded native
pass with no unchecked source assumptions. Its proof kind is
`unbounded_uf_overapproximation`, or `unbounded_concrete` when no operation
was replaced. Abstract failures remain inconclusive. Only a captured model
with zero replacements and a native failure can report `fail` with
`proof_kind: counterexample`. Cross-check disagreement remains inconclusive.
The SMTBMC jobs use explicit `QF_AUFBV` logic. No performance claim is implied.
CLI `uf-prove` and MCP `formal_uf_prove` expose the same plan and report.

## Native fair AIGER liveness reports

`rvw.formal-aiger-live/1` records pinned ASCII AIGER bytes, reducer and tool
hashes, source latch count, justice group, fairness literals, invariant
constraints and native stages. It accepts exactly one bad justice group and
no ordinary outputs or safety properties. Each justice member and fairness
literal must recur infinitely for a violating execution.

`method` is `l2s`, `k-live` or experimental `rlive`. Exact L2S captures every
source latch and requires a nonempty loop with all goals seen. K-liveness
counts complete goal rounds; `k_bound_reached` is inconclusive. Only unbounded
safety passes or a native rlive safe result can earn `pass`. Source constraints
or fairness require a separate exact fair-path feasibility result. If no
fair path exists, `fairness_check: infeasible` keeps the report inconclusive.
A native accepting-cycle result earns `fail` only for L2S or rlive.

`proof_kind` is `liveness_to_safety`, `k_liveness`, `native_rlive`,
`fair_accepting_cycle` or `none`. Stages retain command, engine, time, model
hash, log paths and return code. Native rIC3 SAT/10, UNSAT/20 and UNKNOWN/30
pairs are required. Errors, timeouts and inconsistent pairs stay inconclusive.
CLI `aiger-live` and MCP `formal_aiger_live` share these semantics. This does
not certify an SVA translation or independently validate engine certificates.

## IC3/PDR invariant libraries and reuse

`rvw.formal-lemma-cone/1` identifies a named predicate's complete transition
cone. It contains root expression hashes, deterministic expression records,
named sequential state, initialization and all sequential inputs and
parameters. Numeric wire ids and generated deterministic cell names are
excluded. Input names, widths, clock/reset/enable logic and nondeterministic
cell identities remain dependencies. Unsupported cones cannot match.

`rvw.formal-lemma-library/1` stores mapped PDR cube predicates with `id`,
`literals`, `expression`, `cone_sha256` and `certification: fresh_unbounded`.
It records source and PLA/AIM hashes and the separate certification result.
Library publication requires a fresh unbounded conjunction proof with source
assertions removed. Auxiliary or unmapped PDR columns are not RTL predicates.

`rvw.formal-ic3-lemmas/1` records export or reuse mode, source hashes, selected
entries, rejected entries, discovery/certification or fresh target results,
and `proof_kind`. Export pass uses `unbounded_candidate_certification`.
Reuse pass uses `fresh_unbounded_with_helpers`. Source assumptions and empty
original property sets are refused. Cone or certification mismatch rejects
an entry. A cache supplies candidates, never an acceptance verdict. Helpers
remain assertions in the fresh target proof. A failure with selected helpers
stays inconclusive. A failure without helpers is the original target's
native result. CLI `ic3-lemmas` and MCP `formal_ic3_lemmas` share this report.

## Exhaustive initial-state RTL partition

CLI `initial-split` and MCP `formal_initial_split` read a hash-pinned Verilog
manifest with `top`, `sources`, `split_variable`, optional `engines`, `depth`
and `max_cases`. The variable names a flattened Yosys net with distinct,
nonconstant bits. The runner enumerates every initial bit pattern. Each case
adds only `$initstate -> variable == value` and retains all original transitions.
The default limit is 16 cases. The maximum is 256. No partial selection earns
a partition proof.

`rvw.formal-initial-split-plan/1` records every value, source hash and generated
case problem. `rvw.formal-initial-split/1` records each case result and the plan
hash. A pass requires unbounded success on every case and no original source
environment assumptions. The generated partition guard is discharged by
exhaustive initial-value coverage. Other source assumptions remain unqualified.
A failed case is a counterexample in a subset of the original initial states.
The split does not constrain a variable to stay constant after initialization.

## Lazy RAM word-state refinement

CLI `lazy-ram` and MCP `formal_lazy_ram` read pinned Verilog `top` and `sources`,
plus a collected Yosys `memory` cell name. The runner uses `memory_map -formal`
to retain source read, write, initialization and collision behavior. It then
replaces each untracked word's flip-flop driver with an unconstrained per-step
input. It removes initialization constraints from those freed word aliases.
Tracked word dynamics remain unchanged. Aliased word state, negative offsets,
missing word names and ambiguous whole-word drivers are rejected.

`rvw.formal-lazy-ram/1` records original selected-memory state bits, tracked
addresses, per-round `memory_state_bits`, result paths and source hashes. A
source-conditional engine pass stays inconclusive. An unbounded pass on an
overapproximation proves the original supplied safety problem. An abstract
counterexample requests refinement only. Read-address constants and sampled
counterexample addresses prioritize the next restored word. Missing samples
fall back to the next word. Only a failure after all words are restored can
become a concrete counterexample. The report does not claim total design-state
or runtime savings. `max_words` defaults to 64 and cannot exceed 4096.

EBMC Verilog inputs receive explicit `FORMAL` and `YOSYS` preprocessor defines,
matching the Yosys formal read. Engine rows record these `defines`. Unsupported
formal builtins remain native conversion errors. The adapter never falls back
to a non-formal source branch to obtain a result.


## Reset-policy counter quotient certificate

CLI `counter-quotient` and MCP `formal_counter_quotient` read pinned Verilog
`top` and `sources`, `width`, and `keep_bits` with
`1 <= keep_bits < width <= 256`. Optional `ports` maps exactly `clock`, `reset`,
`enable`, and `count` to simple identifiers. The concrete interface must match
one-bit control inputs and the declared output width. Extra ports are refused.
Optional `reset_active` selects high or low polarity.

`rvw.formal-counter-quotient/1` certifies a generated smaller enabled counter
only after a fresh unbounded relation proof and guarded reset reachability.
The relation is `abstract_count = concrete_count mod 2**keep_bits` under the
recorded initial-reset and clock policy. Source assumptions keep it
inconclusive. A failed obligation reports `obligation_failed` and leaves the
candidate uncertified. Source assertions remain in the obligation.

The report retains source, model and manifest hashes, the proof path and
restrictions. `abstract.sv` is the candidate model. A successful certificate
covers projected low bits only. It does not replace a wider design. The reset
policy resets once at startup, then holds reset inactive. Arbitrary future
reset sequences are outside this certificate.

## Cover-directed bounded campaign reports

`rvw.formal-cover-hunt/1` records source, transformer and elaborated model
hashes, preparation passes, available covers, target rows, covered count and
unstarted targets. Each selected lowered cover becomes the only safety check
in its target problem: assert the inverse of its predicate with its original
enable. Original assertions and other covers are removed. Assumptions and
transitions stay in place. Native liveness constraints are unsupported.

A target has `status: covered` and `proof_kind: bounded_reachability` only
after a concrete native counterexample to that generated check. Other target
results remain inconclusive. An all-covered selection gives root `covered`,
never safety `pass`. Bounded exhaustion does not mean unreachable. Target rows
retain source location, attempt records and the native campaign result path.
The captured campaign retains the generated sources and witness artifacts.
CLI `cover-hunt` and MCP `formal_cover_hunt` expose the same budget and timeout.
No reset, multi-clock scheduling or whole-design coverage result is implied.

## Qualified engine benchmark counts

`rvw.formal-engine-bench/1` rows add `problem_status` and `environment_check`
from the complete portfolio result. `status` still retains the observed
native engine answer. Summary `solved` counts only conclusive problem results.
A native pass with unchecked source assumptions remains inconclusive and does
not count as solved. `conditional_passes` records native passes that did not
earn a problem pass. `bounded_passes` remains a separate observation count.
Agreement compares observed native answers and is not a proof verdict.

## Native engine failure diagnostics

Portfolio Avy error rows can add `reason=avy_sigsegv`, `aiger_shape`,
`observed_input_classes` and `unsupported_input`. These describe a failed
native invocation. They do not qualify a proof or claim a root cause.
Native AIGER rlive rows can record `reason=unsupported_backend_cli` and
`unsupported_input_class=native_rlive_with_internal_no_ic3_pred_prop`.
The problem remains inconclusive. Raw stdout and stderr remain evidence.

## Source conditions in portfolio and benchmark results

Each portfolio assumption records its module, cell, source span, `predicate_bits`
and `enable_bits`. These bit identifiers refer to the captured `design.json`.
`condition_model` pins that file by SHA-256. Where the source span resolves,
`source_excerpt` retains its exact lines and `source_sha256` pins the source.
Engine benchmark rows retain these assumptions and the model reference.
A conditional native pass remains inconclusive. Recording a condition does not
prove its feasibility, activation or match to the intended environment.

## Compiled portfolio sources

Portfolio source entries accept `format=rtlil`, with the same path and SHA-256
pin as Verilog. Snapshot files use `.il` and `read_rtlil`. Mixed source entries
are read in manifest order. EBMC returns `unsupported_input` with reason
`ebmc_does_not_read_rtlil`. At most three engine workers run concurrently.
Compiled variant plans retain the original model hash, variant kind and
transformed model hash. They are overapproximations. Failed variant answers
are not concrete failures of the original problem.

## Strategy plans

`rvw formal strategy` and MCP `formal_strategy` consume a Yosys model and
optional engine-bench history. `rvw.formal-strategy/1` has status `planned`,
feature counts, ordered engines, candidate abstractions, accepted history
samples and reasons. Only rows with qualified `problem_status=pass|fail` and
positive elapsed time affect learning. Bounded and conditional rows cannot.
No proof result is emitted. Liveness returns reduction candidates and no raw
safety engine order. Counter candidates require explicit leaf bindings.

## Revision timing experiments

`revision-bench` and MCP `formal_revision_bench` emit
`rvw.formal-revision-bench/1`. Source hashes identify base and revised problems.
The report retains export time, alternating trial order, fresh proof statuses,
selected lemma counts and result paths. When every target proof passes, it
records cold/reuse median wall times, signed `saved_s` and their ratio.
Failed or inconclusive trials cannot produce savings fields. The one-time
library export is separate. Cone-matched helpers remain assertions and the
target proof is fresh. Local timing does not predict another workload.

## Live engine progress JSONL

Engine-race results name `progress_events=progress.jsonl`.
Each line has schema `rvw.formal-progress/1`, event `started|sample|finished`,
`property_id`, `property_scope=manifest_problem`, `engine`, per-engine `sequence`,
`elapsed_s`, `depth_reached`, `depth_meaning`, `pdr_frame`, `memory_bytes`,
`memory_scope=sampled_process_group_rss`, `native_status` and
`status_scope=native_engine_observation`. Native status is null before finish.
Missing observations are null. The reported step has started, not necessarily
completed. A PDR frame is not proof depth. RSS is a current group sample, not
peak memory. One-second samples do not establish memory bounds. The manifest
property can be a bundled problem. A native event cannot override conditional
assumptions, disagreement or the final problem verdict.
