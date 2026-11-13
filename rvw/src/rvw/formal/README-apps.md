# Formal apps and proof coverage

### Database autocheck candidates and waivers

`rvw formal autocheck PLAN.json --db DESIGN.db --out DIR` derives the module
ports and complete output enum encodings from a current SpinalDB database.
The plan still supplies `top`, `clock`, `reset` and `verilog`. `database_component`
selects a component path when a module has several instances. No state list is
needed. Each enum value and each pair of enum values becomes a reachability
target. Hashed encodings and internal enums without plain retained RTL names are
listed as skipped. Retained internal enums are exposed and width-checked. The database input capture is retained beside the result.

Database candidates also include output bit constants and toggles, one-hot
checks for complete one-hot enums, direct whole-width port addition/subtraction,
and memory addresses whose address and enable are exposed ports. Arithmetic
candidates require equal operand and destination widths and types. Conditional,
partial and widened assignments are not inferred. Unsupported address expressions
are skipped. These are candidates, not a complete inventory of design checks.
Use `--kind` repeatedly to select kinds. Use `--max-properties` to set the limit.

The plan can supply `contracts` for semantic endpoint roles that the database
does not encode. Available kinds include `onehot`, `mutex`, `array_bound`,
`arithmetic_overflow`, and `fifo`, plus the existing bounded progress kinds.
One-hot requires a nonzero value by default. Mutex permits zero. Array bounds
use `signal`, `size` and optional `enable`. Arithmetic checks use equal-width
`signal` and `other`, `operation=add|sub`, optional `signed`, and optional `enable`.
FIFO checks use accepted `push` and `pop` pulses, `write_data`, combinational
`read_data`, and `capacity`. They check overflow, underflow and ordering. Empty
fall-through and delayed read interfaces require another contract.

`waivers` maps generated property IDs to nonempty review reasons. Waived checks
run no solver and retain status `waived`. All-waived plans return `no_checks`.
Waivers do not earn proofs or coverage exclusions. General liveness under
fairness, automatic FIFO/arbiter role discovery and internal RTL exposure remain
open. Existing bounded progress contracts do not establish general liveness.

Generated database checks retain their module and Spinal source location.
`rvw formal testplan --manifest RUN/spec.json --out REPORT` can read the generated
app inventory directly and join the saved per-property formal results. Waived
checks retain their waiver status. Missing results stay `not_run`. This also
works with an explicitly written `rvw.formal-testplan/1` inventory for hand-written
properties and further core, activation and mutation evidence.
`arbiter_starvation` checks one-bit `request` and `grant` within a declared
`bound`. `handshake_progress` checks `valid` and `ready` within that bound.
These are bounded response contracts. They reject a `fairness` field because
this flow cannot establish general fairness-constrained liveness.

### Formal testplan evidence

`rvw formal testplan --manifest PLAN.json --out DIR` writes JSON and HTML.
The `rvw.formal-testplan/1` plan lists `properties`. Each property has
`property_id`, `module` and `origin` (`generated` or `hand_written`). Optional
fields are `requirement_ids`, `mutation_ids`, and `source` with `file` and `line`.
The source file can be a Spinal Scala file. The report groups evidence by module
and source line. It does not infer line coverage from SMT constraint counts.

An optional `evidence` list has `kind` and `path`. Paths are relative to the plan.
Use `kind=result` with a `property_id` for one captured formal result.
Use `kind=core` for `rvw.solver-core/1`, `kind=cones` for `rvw.proof-cones/1`,
and `kind=mutation` for `rvw cov mutate` JSON. Join mutation rows by the plan's
explicit IDs. Missing mutation rows remain missing. Duplicate property evidence
and evidence outside the inventory are errors. Files are captured and hashed.

The `formal_testplan` MCP tool uses the same inputs. Missing proof evidence is
`not_run`. Missing cores are `unavailable`. Reached activation is a separate
observation. Full non-vacuity and requirement obligations remain unestablished.
The aggregate status remains inconclusive. Existing guarded `rvw cov prove`
exclusions remain the only UNR exclusion path.
Captured assumptions are grouped by cell across all samples. `assumptions`
records whether each cell occurs in the returned core. Conflicting environments
also get deletion-minimal constraint reduction. A cell outside that core is not
needed for this query. This is not a general assumption-adequacy result. A SAT
property query does not produce a proof core or certify assumption necessity.
### Pinned solver rechecks

`rvw formal recheck --result FAILED_RUN --pin bad=0 --out RECHECK`
runs a bounded solver check over the captured RTLIL model. Repeat `--pin` for
more signals. A pin uses an exact net name in the captured top module and an
integer value. Pins can refer to inputs or internal nets exposed by that model.
Each pin adds an equality assumption at every formal sample. The original
drivers, state, assertions and assumptions remain in the captured model.

The command first checks that the pinned model can reach the full requested
depth. An inconsistent pin is `inconclusive`. A passing recheck is bounded and
conditional on the original restrictions plus all pins. It does not establish
that a source change fixes the design or authorize a coverage exclusion.
`--depth` defaults to the original BMC depth. The minimum depth is two samples.
The output retains both SBY jobs, their logs, the pinned model and captured
inputs. The `formal_recheck` MCP tool has the same inputs. Native tests check a
removed failure, a retained failure and an assumption conflict with Yosys/SBY/Z3.

## Counterexample what-if replay

Replay a failing `rvw formal bmc` result through native Yosys `sim`:

```sh
rvw formal cex --result out/bmc --out out/replay --json
rvw formal cex --result out/bmc --edit bad@0=0 --out out/whatif --json
```

`--trace-index` selects a witness from `result.json` (default 0). Each repeatable
`--edit PORT@TIME=INTEGER` changes a top-level input at an existing VCD timestamp.
Values use decimal, `0x` or `0b`. An edit lasts until the next change to that input
in the original witness. It does not tie the input for all later cycles. Clock and
reset are inputs too. Editing them changes the replay environment.

The command first replays the original witness. It then replays the edited witness
against the same captured model. It uses `sby/model/design.il`, before SBY clock
conversion. `clk2fflogic` and `chformal -lower` let `sim` evaluate clocked checks.
VCD input is converted to FST before simulation. Each replay writes `wave.vcd`,
`wave.fst`, `summary.json`, the Yosys script and log. Initial state comes from the
original witness where Yosys can map it. Missing state keeps the model's initial
state. The edited replay does not load later witness state over computed state.

`inputs/` retains the original result, witness, model, copied RTL, checks and
wrapper. `input_capture` maps source paths to copied bytes and hashes. The result
keeps the original declared `restrictions`. Assertions and assumptions stay in the
model. An observed assumption violation makes the disposition `inconclusive`.
Use a separate output directory. The command refuses output paths that overlap
the formal run. It does not change that run.

The result uses `rvw.formal.cex/1`. `status` is always `inconclusive`, with exit 1.
`disposition` is `reproduced` only when the original replay observes a property
listed in the formal failure report and the edited replay observes that same
property. `failure_not_observed` means that the original replay observed the
property and the edited replay did not. A tool error, missing baseline failure or
assumption violation gives `inconclusive`. No disposition proves correctness.
Unknown state can hide a failure. Only the selected finite witness is replayed.

For Spinal designs, supply metadata from the same elaboration:

```sh
rvw formal cex --result out/bmc --out out/debug --edit bad@0=0 \
  --hgldd build/spinalwaves/hgldd --pdg build/spinaltrace/pdg.json \
  --criterion line:Top.scala:20 --at-time 9 --open --json
```

HGLDD and PDG inputs are copied. `spinalwaves-check` checks typed lookup on the
edited wave. `--open` launches `surfer-tywaves` only after that check completes.
The result also gives its argument vector. SpinalTrace `dyn-pdg` runs on the
**original replay wave**, where the assertion fails. Select the failing assertion
with `--criterion`. Set `--at-time` to its pre-edge sample time in VCD units.
The wrapper scopes are `rvw_formal_top dut`. The top module is the original design.
Logs and `dynpdg.json` stay in the output directory. A missing tool or failed
lookup reports `inconclusive` in `navigation`. A launched GUI is not a verified
navigation result. Preserve the Scala files at the source paths in the metadata.

MCP exposes the same command as the background tool `formal_cex`. It accepts
`result`, `out`, `trace_index`, `edit` (array), `timeout`, `hgldd`, `pdg`,
`criterion`, `at_time`, and `open`. The timeout bounds each native subprocess.
Cancellation stops each native process group. A GUI explicitly opened by the
user stays open after the replay job ends.

## Table-driven apps

```sh
rvw formal apps SpinalChecks/examples/apps/apps.json --depth 10 --out /tmp/apps
rvw formal bench SpinalChecks/examples/bench/suite.json --timeout 30 --out /tmp/bench
```

The app manifest uses `rvw.formal-apps/1`. It lists self-contained `verilog`
files relative to the manifest, `top`, `clock`, an active-high synchronous
`reset`, an exact `ports` table, and `properties`. Each port declares `direction`
(`input` or `output`) and `width`. The captured native elaboration must match
this table. Each property has a unique plain `id`, `kind`, and optional
`requirement_ids`. These IDs stay in the report and identify its child result.
Use a fresh output directory. The runner freezes the sources and spec before
it starts a property. Each child uses the existing captured RTL and tool flow.

| Kind | Required fields | Contract |
|---|---|---|
| `connectivity` | `source`, `destination` | Equal values at the declared ports. A reviewed `source_expression` plus `source_width` can replace `source`. Optional `latency` (0..64), `enable` and `mode`. The condition samples with the source. Startup history is gated. |
| `csr` | `state`, `write_enable`, `write_data`, `reset_value` | Independent reference register. Optional `access` (`rw`, `ro`, `w1c`) and integer `write_mask`. |
| `deadlock`, `livelock` | `pending`, `progress`, `bound` | A continuously pending request must make progress within the declared bound. The counter saturates. |
| `unr` | `target` | Assert that the target is false outside reset. |

Expressions accept ports, decimal integers and basic Boolean/arithmetic
operators. Calls, hierarchical names, includes and macros in expressions are
not supported. CSR fields must fit their port widths. A CSR map expresses one
register per row. It does not implement address decoding, aliases, read side
effects, bus protocols or privilege checks. Map bus decode to `write_enable`
in a reviewed project wrapper when needed.

The default mode is BMC. `--mode prove` requests an unbounded safety proof.
Use a suitable engine, such as `--engine abc:pdr`. A progress proof establishes
the finite response contract. It does not establish general liveness or fairness.
All results depend on the supplied environment and spec. Requirement IDs are
links, not proof of requirement completeness. Activation is `not_measured`.
Forbidden connectivity needs structural or noninterference evidence. This app
refuses it. SpinalDB endpoint resolution and opaque blackbox contracts remain open.

For coverage exclusion export, use the existing guarded UNR flow:
`rvw cov prove DATABASE --config PLAN --work-dir OUT`. Apply its `exclusions.json`
with `rvw cov report DATABASE --exclusions OUT/exclusions.json`. That flow checks
sanity, point reachability and cone activation before export. App UNR results
cannot replace this evidence. `proof-cones.json` joins stable property and
requirement IDs, lists structural fan-in, outside-cone logic and untested
assumptions. See [coverage](../cov/README.md).
Solver proof cores remain `unavailable`. A structural cone is not a proof core
or a functional coverage percentage.

### Automatic checks and FSM observations

`rvw formal autocheck plan.json --out checks --depth 20` generates one zero and
one one constant candidate for each output bit. It also checks declared dead-code
conditions, FSM states and FSM transitions. Use `--mode prove` for unbounded
safety checks. `--max-properties` limits generated work and rejects larger plans.

The plan uses `rvw.autocheck/1`. It has the same `top`, `ports`, `clock`, `reset`
and `verilog` fields as `rvw.formal-apps/1`. The clock and active-high synchronous
reset are one-bit input ports. Optional `dead_code` rows have `id` and `expression`.
Optional `fsms` rows have `signal`, integer `states`, and `transitions` as pairs
of integer state values. FSM signals must be exposed in the reviewed port map.
For example:

```json
{"schema":"rvw.autocheck/1", "top":"Top", "clock":"clk", "reset":"reset",
 "verilog":["Top.sv"],
 "ports":{"clk":{"direction":"input","width":1},
          "reset":{"direction":"input","width":1},
          "state":{"direction":"output","width":2}},
 "fsms":[{"signal":"state","states":[0,1,2],"transitions":[[0,1],[1,2],[2,0]]}],
 "dead_code":[{"id":"state3","expression":"state == 3"}]}
```

Each row retains its native proof result. `observation` separates `reached`,
`not_observed_bounded`, `unreachable_conditional`, `not_constant`, `holds_bounded`
and `constant_conditional`. A bounded absence is not unreachability or a constant
proof. A reached target uses a failing negated assertion as its witness. Reports
with reachability targets have aggregate status `inconclusive`; read each row.
FSM transitions exclude the first sample and reset-crossing samples.
These reports do not authorize coverage exclusions. Use `rvw cov prove` for UNR.

`--xprop` also runs the existing bounded output X-propagation flow. Its separate
result is retained under `xprop/`. It does not replace native four-state replay.
MCP tools: `formal_autocheck` and `formal_apps`. The latter also exposes the
existing deadlock and livelock progress contracts. Those contracts check a
reviewed response bound. They do not establish general liveness or discover
all possible deadlocks. Automatic checks use declared ports and expressions;
they do not claim automatic extraction of all RTL FSMs or source dead branches.
### Counterexample reduction and simulation export

`rvw formal cex --result FAILED_RUN --out DEBUG --minimize --max-checks 100`
tries shorter prefixes in time order, then removes input changes. Each retained
change must replay the same assertion path and source location without an
assumption violation. Initial input values and the full formal model remain.
The output retains each replay log and a `reduced.vcd`. The check budget can
stop reduction. The result reports this limit. This is a greedy reduction, not
a global minimum. It does not remove assumptions or authorize a proof claim.

Add `--emit-testbench` to export `replay_model.v` and `replay_tb.sv` from the
captured model and edited stimulus. Formal cells are removed from this simulation
model. Compile with `iverilog -g2012 -s rvw_replay_tb -o replay replay_model.v
replay_tb.sv`, then run `vvp replay`. Verilator can use `--binary --timing
--top-module rvw_replay_tb`. Compilation and simulation do not prove that the
original formal failure was reproduced. The Yosys replay supplies that check.

Add `--db design.db --signal SIGNAL` for source locations, assignments, and a
structural fan-in graph from the `rvw query` reader. `--pdg`, `--criterion`, and
`--at-time` use the existing SpinalTrace dynamic cause flow. `--hgldd` and `--open`
use the existing typed SpinalWaves and Surfer flow. The `formal_cex` MCP tool
accepts the same options. Native viewer navigation still needs a captured Spinal
design and the viewer tools. These additions do not establish that integration.


### Shortest solver counterexample

`rvw formal shortest --result RUN --max-depth 20 --out DIR` checks increasing
sample depths in a captured BMC model. Each selected assertion gets an independent search. The default selects all assertions.
The first FAIL is shortest only if all smaller depths passed. An unknown or
failed solver invocation stops the search as inconclusive. Reaching the depth
limit with PASS results also stays inconclusive. This is not an unbounded proof.
The original assumptions and restrictions remain. Each SBY job and trace is
retained. `formal_shortest` provides the same operation through MCP.

When counterexample replay uses `--pdg`, successful SpinalTrace output also
writes `explanation.json`. The agent-readable chain lists source locations,
observed values, timestamps and dependencies. It keeps the dynamic graph's
accuracy status. Missing accuracy is incomplete. The chain is observed trace
evidence. It does not prove counterfactual causality or a source repair.

See [formal apps and proof coverage](README-apps.md).

## Fair response liveness

`rvw formal app-live --manifest PLAN.json --out DIR` reduces response liveness
to safety. The `rvw.liveness-app/1` plan supplies `verilog`, `top`, `clock`,
`reset`, Boolean `request` and `response` expressions, and a `fairness` list.
Each fairness expression must hold infinitely often. Expressions use top ports.
The tool maps memories, flattens the design and saves every synchronous state
bit. It detects a nonempty loop with an outstanding request, no response and
all fairness conditions observed. The native safety proof rules out these loops.
The default mode is `prove`. Mode `bmc` only searches bounded lassos.

A handshake request must remain represented until completion. A transient request
can still leave an obligation. Fair `ready` cannot repair a design that drops it.
The native smoke test proves a retained request under fair `ready`. A mutant
that never acknowledges fails. All state must use one rising-edge clock.
Unsupported state and black boxes cause an error. Fairness feasibility is not
proved. A pass is a proof only when every fairness expression names only
top-level inputs (not clock or reset) and the design has no assumptions
(`fairness_check: free_inputs` or `no_fairness`). Otherwise a safety pass is
`inconclusive` (exit 3), because fairness on an output such as `!busy` can
exclude the hung loop itself. This command checks universal fair response. It does not establish the
CTL claim that every reachable state has some path to progress.

## Typed roles and internal FSMs

Database autocheck now reports roles with their database evidence. It finds Stream
and Flow bundles by Spinal type. Output Streams receive payload and valid hold
checks under backpressure. Self-updating signed and unsigned registers are counter
candidates. Complete enum encodings receive FSM state and transition observations.
Retained internal enum signals are exposed by exact RTL name with Yosys. The tool
checks each exposed width before it builds a wrapper. No hierarchical name is guessed.

FIFO, arbiter and CAM class candidates retain type and memory evidence. The
automatic component contracts below bind supported typed interfaces. Unbound roles
retain an explicit unsupported reason. Counter wrap requirements are not inferred;
wrap events are observations. Automatic binding does not cover every design.
The report counts generated, proven, bounded, failed and unsupported checks.
A failed reachability assertion can mean that a requested observation was reached.
Read each row's `observation` before treating it as a design failure.

## Bounded cell cores and requirement obligations

`rvw formal proof-core --result RUN --cell-level --depth 8 --out DIR` maps the
captured model to Boolean cells. Each cell equation at each sample has a named
solver constraint. The report lists every mapped logic cell, selected core cells
and cells outside the core. This is bounded dependency coverage of the captured
model. It includes generated reset and monitor helpers. It is not full RTL
functional coverage. Unknown cells and multiple clocks cause an error.

A testplan can declare `requirements` with `requirement_id` and `obligations`.
Each obligation names `property_id`. It requires an unbounded pass and reached
activation by default. Set `activation: false` only for an obligation that does
not need this evidence. Set `cell_core: true` to require bounded cell-core evidence
as well. Missing properties and missing evidence remain inconclusive. Discharged
obligations remain conditional on the captured assumptions. Complete logical
non-vacuity and requirement completeness remain unproved.

Cell cores also test logical assertion-leaf replacements. For each leaf of the
combinational assertion expression, the tool substitutes false and true in the
specification. It keeps the design equations and assumptions unchanged. If both
failure queries are UNSAT, that leaf is `replacement_vacuous_bounded`. A SAT
replacement is `sensitive_bounded`. Missing solver evidence is inconclusive.
The analysis stops at state bits and checks at most 64 atoms per assertion.
It does not claim full temporal or unbounded non-vacuity.

## Multiple shortest witnesses and typed output

`rvw formal shortest --result RUN --out DIR` isolates each captured assertion
before searching increasing sample depths. Repeat `--property` to select exact
assertion cell names. Each property has its own attempts and shortest certificate.
A shared time budget covers all properties. Unknown earlier depths cannot certify
a shortest witness. The original assumptions remain in every isolated model.

Add `--hgldd DIR` to run `spinalwaves-check` on each failing witness and export
`property-N/typed.vcd`. Missing tools or a failed type lookup report inconclusive
typed output. Solver evidence remains separate. Native type export passed after an offline 24-second build of `spinalwaves-check`.
A real shortest witness was converted with explicit UInt test metadata. This
checks export, not automatic source-type extraction or viewer navigation.

## Real library autocheck run

A native run on 2026-11-13 used SpinalHDL 1.15.0 `StreamFifo(Bits(2 bits), 2)`.
The reproducible source is [AutocheckFifo.scala](examples/AutocheckFifo.scala).
`rvwformal.AutocheckDatabase` generates a synchronous-reset database and RTL.
Compile it as an added unmanaged source in `SpinalDB/spinaldb` under the `sbt`
lock. Run its main with the database path and RTL output directory. The Vex lock
attempt did not acquire the lock within 180 seconds. No VexRiscv result is claimed.

The library database has 2 components, 54 signals and 1 memory. The autocheck plan
selects top `AutocheckFifo`, clock `clk`, reset `reset` and its generated RTL.
The command used `--mode prove --engine abc:pdr --depth 8 --timeout 8`.
Counts: **13 generated, 1 proven, 0 bounded passes, 12 solver failures, 1 unsupported**.
The proof is the output Stream hold check. Eight failures show outputs are not
constant. Four failures reach toggle targets. These are observations, not FIFO
faults. The unsupported record is the input Stream producer, which belongs to the
environment. This run does not establish full FIFO ordering or full core coverage.
The first default asynchronous-reset export was refused before proof.

## Progress possibility and deadlock

`rvw formal app-deadlock --manifest GRAPH.json --out DIR` checks that progress
remains possible from every reachable state in an explicit finite graph. The
input supplies `states`, `initial`, `edges` and `progress`. An optional `fairness`
list gives state sets that must recur infinitely. The checker finds fair cyclic
components and paths to them. A progress path must have an admissible fair suffix.
An infeasible fair continuation is inconclusive. A reachable admissible state
with no path to progress fails. Terminal states are reported separately.

This checks progress possibility. A state can pass even if it can wait forever,
provided a path to progress exists. Use `app-live` for universal fair eventual
response. The graph result does not certify an RTL-to-graph translation.

## Automatic component contracts

Autocheck binds a FIFO when the selected component has FIFO type evidence, one
input Stream, one output Stream and one memory with known depth and payload width.
The generated `fifo_stream` app checks accepted-transfer ordering and capacity.
It supports an empty bypass transfer and the standard `StreamFifo` flush input.
It does not infer contracts for composite payloads or multiple memories.

An arbiter with several input Streams and one output Stream gets an
`arbiter_transfer` app. It checks one accepted input per accepted output and
matching payload data. It does not assume a grant fairness policy. Structurally
self-incrementing or decrementing registers get `counter_wrap` observations.
Internal counter and memory-address endpoints are exposed by exact RTL name.
CAM candidates get memory-address bounds when these endpoints are available.
CAM key matching and duplicate-entry policies remain unsupported.

A second real library run selected component `fifo`, module `StreamFifo`, and
`--kind fifo_stream --mode prove --engine abc:pdr --depth 8 --timeout 30`.
Counts: **1 generated, 1 proven, 0 bounded passes, 0 failed, 7 unsupported discovery
records**. The queue reference was bound automatically from typed channels and
memory structure. Native two-input arbiter proof and double-accept mutant checks
also passed. The earlier wrapper counts above remain the recorded baseline.
