# Equivalence and datapath checks contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Experimental C reference datapath result

`SpinalChecks/c2rtl/check.py` writes `rvw.c2rtl/1`. It is a standalone experiment,
not C1 run evidence or a C4 gate verdict. `status` is `proved`, `counterexample`
or `inconclusive` (exit 0, 1 or 3). `width`, `signed`, `latency_cycles`,
`handshake`, `depth` and `input_pairs` state the comparison contract and bound.
The supported domain has two unsigned inputs and one unsigned output, each
1 to 4 bits, no state, no handshake, no assumptions and depth 1.
`proved` means all enumerated input pairs match the compiled C truth table.
`counterexample` requires SBY FAIL and a witness testbench. Missing, timed out,
unsupported or ambiguous evidence is inconclusive. It never grants gate accept.
`inputs`, `tool_files`, `tools`, `environment`, `commands` and `artifacts` record
source identities and reproduction data. `traces` names witness artifacts;
`reason` explains inconclusive results. A new output directory is required.
See [the C reference flow](../SpinalChecks/c2rtl/README.md) for the C-model
review requirement, native runtime trust and FP limits.

### Counterexample replay observations

`rvw formal cex` and MCP `formal_cex` write `rvw.formal.cex/1` to a separate
output directory. This is an observation format, not `rvw.formal/1` proof evidence.
`status` is always `inconclusive` (CLI exit 1). `disposition` is `reproduced`,
`failure_not_observed`, or `inconclusive`. The first two require an original replay
that observes a property named in the formal failure report. Reproduction also
requires that same property in the edited replay. Assumption violations and tool
failures remain inconclusive. Absence of an observed failure is not a pass.

`original_result`, `input_capture`, `restrictions` and `edits` retain the declared
inputs and environment. `baseline` and `edited` contain the Yosys sim summaries.
`wave` and `fst` name the edited replay artifacts. Optional `navigation` records
type-check, cause-trace and viewer launch outcomes. A viewer launch does not
establish successful source navigation. See the formal command README for limits.

### Formal bounded depth-search termination

`rvw.formal-depth-search/1` records `stop_reason`: `max_depth_reached`,
`budget_exhausted`, or `attempt_<status>`. `support` records the doubling
schedule, initial and maximum depths, total budget, per-attempt timeout and
engine selection. Engine portfolios and depth search are separate choices.
Every attempt uses at most the remaining budget as its timeout. Frontend and
capture overhead can exceed this budget. No new attempt starts after expiry.
A bounded pass at the maximum depth remains `inconclusive`. Only a concrete
failed attempt gives aggregate `fail`. Search never claims an unbounded proof.

### Formal simulation-state swarm

`rvw.formal-swarm/1` has aggregate `status: inconclusive` and exit 1. `selection`
records the uniform cycle interval selection. `attempts` retains each cycle,
status, relative result path, restrictions and loaded-state coverage. A refused
state has `status: error` and a reason. `missing_cycles` lists tasks not started.
`bounded_passes` and `conditional_failures` count observations only. They cannot
earn reset reachability, gate acceptance or unbounded proof. Sources, includes,
checks and waveform are copied once in the parent `input_snapshot`. Child
results retain their own full tool/input captures and solver evidence.

### Formal exact proof reuse

`rvw.formal/1` results can include `proof_cache` with `key`, `hit` and the checked
`rule`. The optional `bmc`/`prove` cache stores complete successful SBY evidence
under a SHA-256 input key. `rvw.formal-proof-key/1` binds complete prepared input
artifacts, script, captured files, tool payloads/versions, captured environment,
Python identity and formal/common runner code. Only the owned output prefix is
normalized. Whole-model identity is required; no inferred cone independence is
accepted. Entry manifests hash all retained evidence and provenance. Fresh input
capture, frontend checks, tool verification and bounded reachability remain
mandatory on hits. An invalid entry is a miss. Only successful results with
assertions and reachable guards enter this cache. Mounted directory sharing
requires C8 trust; no remote authentication or gate acceptance is supplied.

### Formal memory encoding

`rvw.formal/1` BMC/prove results record `memory_model.requested` (`auto`, `array`,
`map`), `retained_memory_cells` (prepared `$mem_v2` count, or null without a
model), and `semantics`. Explicit array mode requires an SMTBMC-only portfolio.
Map mode uses Yosys `memory_map -formal`. Both model the supplied RTL memory.
Neither adds a RAM/blackbox refinement contract or resolves undefined RTL
behavior by choosing a value. The retained-cell count is not a refinement proof.

### CDC sequential reconvergence depth

Lint intent accepts `reconvergence_depth` (integer 1..64, default 1). It bounds
register boundaries between synchronizer outputs and each sink. Findings retain
each synchronized endpoint and its minimum register depth in `reconvergence`.
Combinational edges do not consume this bound. Cycles are bounded. Memory and
blackbox internals remain outside scope. This is structural evidence only.

Lint settings can select optional backend `yosys`. Native `check` warnings use
`yosys.combinational_feedback`, `yosys.conflicting_drivers`, `yosys.undriven`,
or fallback `yosys.warning`. Findings retain elaborated bit IDs and available
source attributes. Backend output includes `elaborated_modules` and `script`.
Blackbox modules cannot earn a completed connectivity check.

### Selected CDC protocol and simulation results

`rvw lint --protocol MANIFEST --out NEW_DIRECTORY` accepts
`rvw.cdc-protocol/1` with exactly `schema`, `kind`, `top` and `verilog`.
The selected kinds, fixed port interfaces and digital sampling abstraction are
specified in the lint guide. Sources are frozen before native elaboration.
`rvw.cdc-protocol-result/1` records `status`, `proof_kind`, `kind`, source hashes,
the native child `result`, model, limits and `activation: not_measured`.
A pass only applies to the selected monitor and environment. It is not a
structural waiver or whole-design CDC verdict. No C4 acceptance is emitted.
`--simulate SAMPLES --seed SEED` instead emits `rvw.cdc-simulation/1` with
status, kind, seed, requested sample count, input hashes and limits. Missing
tools and incomplete execution are inconclusive. A simulation pass needs the
completion marker and no failed monitor assertion. It is not a proof.

Selected CDC protocol kinds also include `pulse_capture` (single injected pulse,
four destination-event response bound) and `coherent_bus` (equal-coded two-bit
output). The lint guide defines their exact interfaces and assumptions.
`rvw lint --benchmark MANIFEST --out NEW_DIRECTORY` accepts `rvw.cdc-bench/1`.
Cases pin source hashes and independent expected results. Optional commercial
adapters receive the same frozen spec and monitor, but not the expected verdict.
`rvw.cdc-adapter-response/1` must bind the exact request hash, mode, tool version
and verdict. BMC passes must reach the requested depth. All observations and
per-tool qualifications stay in `rvw.cdc-bench-result/1`. Missing commercial
adapters are `not_run`. Suite agreement is not signoff or commercial parity.

## Symbolic datapath result

`rvw.datapath/1` records the `yosys-boolean-cbmc` backend, source and tool hashes,
width, rounding, case split and fixed transaction latency. `proved` exits 0 only
when CBMC exits 0 and every property succeeds, including the result assertion.
`counterexample` exits 1 only for result, flags or completion violations.
C safety failures, unwinding failures, missing tools and timeouts are
`inconclusive`, exit 3. This is not a C4 acceptance result. The `properties`
array retains CBMC property descriptions, statuses and available traces.
The reference model and dependencies are trusted specification inputs.

#### Bounded datapath completion

`rvw.datapath/1.max_latency` is null for the existing fixed-latency contract.
A positive value selects a first-done completion bound in 1..256 clocks after
start. Result bits and flags are checked at that first completion. Missing done
is a completion failure. Operands stay stable. `inputs.binding.json` captures the
optional project top and canonical-to-project port map by SHA-256. A binding
can rename ports and set explicitly declared constant input ports. Constants
must fit each input width. Their bits replace every mapped use of that input.
The proof applies only to those recorded control values. Other ports, widths,
state and drivers remain subject to the existing checks. The normalized model must provide required reference and handshake ports.
Optional `unused_inputs` maps absent reference operands `b`/`c` to bit widths.
It adds fresh unconnected symbolic reference inputs. It does not fix their values
or reduce the reference input domain. Every added width still passes the
existing interface check. All constants and unused arguments remain in the
captured binding.

## Sampled clock-event equivalence

`rvw.formal.equiv/1.event_model` records the `yosys clk2fflogic` backend,
global-sample scope and `stable_at_edge` input names. Simple `$dlatch` cells are
allowed only through the explicit sampled-event equivalence frontend. Both
wrappers are normalized before eqy output partitioning. Each declared input
setup constraint is captured as an assumption in both wrappers. Reset/settle
count root-clock edges. There is no between-sample transition or analog claim.
A completed query reports status `conditional` and a separate `contract_verdict`.
CLI exit is 1. Default formal flows retain their prior state/clock restrictions.

## Mixed-width datapath bindings and literal definedness

`rvw.datapath/1.case_width` records the source FP format used for case splitting.
It defaults to `width`. An explicit value is 16, 32 or 64 and cannot exceed
`width`. Case `normal` excludes zero, subnormal, infinity and NaN operands.
The case restriction still applies only to operand `a`.

A captured datapath binding can declare `input_widths` for `a`, `b` and `c`.
Each value widens an existing port to the reference word width. The added high
bits are fresh symbolic reference inputs. They do not connect to the physical
DUT. A proof therefore requires the reference to ignore those bits. It does not
assume that they are zero. `output_widths` can widen only `y`. It pads the physical
result with constant zero high bits. No adapter truncates a port. The normalized
interface must still pass the existing width, direction and driver checks.
These fields do not change flag or handshake widths.

`rtl_definedness` is `not_checked`, `proved` or `inconclusive`. The Boolean C
backend carries conservative literal X/Z propagation through gates and register
updates. Unknown bits have unconstrained binary values. Separate assertions
require defined result bits and flags at each result observation. Sequential
checks also require defined completion signals at each completion observation.
Both `proved` and `counterexample` require all required definedness assertions
to succeed. A reachable unknown, incomplete query or missing obligation cannot
earn either status. The gate rules can retain unknowns after reconvergence, so
some defined circuits can remain inconclusive. Register initial values retain
the existing arbitrary two-state contract. This is not four-state event
simulation or an initial-state reachability result.
