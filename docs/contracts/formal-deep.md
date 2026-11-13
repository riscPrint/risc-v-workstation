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
Only `pass` and `fail` count as solved. Missing tools and unsupported modes do
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
`operator`; sequence rows also record `strength`, a `minimum` or `count`, and
`completion` where applicable. Assert and assume sequence consequents default to
weak. Explicit strong sequences require finite completion for every request.
A latched fatal predicate records finite impossibility. Count buckets retain
overlapping attempts. A separate owed set gives acceptance when each old group
finishes, even when requests continue. It never resets an old attempt on a new
request. Both native-live and liveness-to-safety routes use these predicates.

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
is a bounded lasso search. Justice feasibility and existential CTL deadlock
freedom are not established. Existing safety assertions are removed from this
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
