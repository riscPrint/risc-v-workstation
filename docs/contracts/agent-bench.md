# Agent benchmark contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Agent benchmark fixture formats

`rvw.agent-tasks/1` has a nonempty `tasks` array with unique IDs. Each task has
`public` requirements, width, statements, expression choices, source text and
artifact identity claims. Its evaluator-only `private` object has the cause
statement ID, injected artifact defects and `[a, b, expected]` vectors. These
fixtures are not C1 runs, C2 traces or C6 database IDs.

`rvw.agent-bench/1` records `track: "fixture"`, agent name, pack SHA-256, per-task
scores, final candidates and ordered tool transcripts. Elapsed times use a
monotonic clock. Missing root causes have null times and a censor flag. Summary
rates retain counts and denominators; empty conditional rates are null.
`native_validation: "NOT RUN"` is mandatory for this track. Scores cannot earn
C4 acceptance. The dedicated stdio server exposes only fixture tools and rvw job
status tools, not the normal rvw tool registry or plugins. See
[the benchmark guide](../rvw/src/rvw/agent_bench/README.md).

### Agent guide

`rvw.agent-guide/1` (`rvw agent guide --json`, MCP `agent_guide`, resource
`rvw://agent/guide`) has `conventions` and `workflows`. A workflow has `id`,
`title`, `when` and ordered `steps`. A step has `id`, `do`, an rvw argument list
`cli` or `manual: true`, an optional `mcp` object with `tool` and `arguments`, an
optional `optional` flag and `decide` rules (`if`, `then`, optional `note`).
`then` is a step id of the same workflow, another workflow id, `done` or `stop`.
Angle-bracket arguments are placeholders. The guide is not evidence. See
[the playbook README](../../rvw/src/rvw/agent/README.md).

### C2/2 V and H observations

An ISA declaring V requires a `vector: {"vlen": 128, "elen": 64}` header.
An ISA declaring H requires a `hypervisor: true` header. V1 traces for these
ISAs are refused. Each retirement carries the declared extension state.
Vector state has XLEN hex `vstart`, `vl`, `vtype`, 3-bit hex `vcsr`, 2-bit hex
`vs`, and `regs`: all 32 VLEN-bit hex register values after the step.
The complete snapshot checks register writes and mask v0, including unchanged
lanes. It does not identify writes that store an unchanged value. VLEN must
be a power of two from 128 to 65536. ELEN must be a power of two from 8 to 64.
The reference must have exactly the declared dimensions. No agnostic-bit
relaxation is implied.

Hypervisor state has boolean `virtual` (before), `virtual_after`, integer
`mode_after` (0, 1 or 3), `csrs`, and `translations`. Together with `mode`,
these distinguish M, HS, U, VS and VU entry and exit. `csrs` holds XLEN hex
values for 0x100, 0x105, 0x141, 0x142, 0x143, 0x300, 0x302, 0x303,
0x341, 0x342, 0x343, 0x600, 0x602, 0x603, 0x643, 0x64a, 0x680, 0x200, 0x205, 0x241,
0x242, 0x243, 0x280, 0x34a and 0x34b after the step. Translation records
have XLEN hex `va`, `gpa`, `pa` and `access` (fetch, load or store), in access
order. Missing intermediate translations are unavailable evidence. A backend
without translation observations must refuse nonempty records. An empty list
checks no translation. State comparison alone does not prove page walks.

The Spike walker checks successful RV64 guest fetch and scalar load mappings
with Bare/Sv39/Sv39x4. It refuses stores, faults and unsupported PTEs. HS
CSR addresses above always mean nonvirtual host state, including while in VS.

`state_coverage.two_stage_translations` counts matched translation records.
A zero count makes no translation comparison claim.

A regression config can set `[core] backend = "riscvsim-verilator"`.
Each suite can set `requires = ["two_state", "clock", "immediate_assertions"]`.
The shared native profile checker refuses unsupported or malformed requirements
before input capture and adapter launch. A nonempty requirement list without a
known profile is an error. Existing configs with no requirements stay valid.
The direct RiscvSim shell launch checks `RISCVSIM_REQUIRES`, a comma-separated
feature list, before it creates temporary launch state. This profile describes
the Spinal native interface, not the cocotb Verilator invocation. Coverage flags
retain their existing version checks and do not imply a coverage guarantee.

### Sampled reset checks

Optional project bindings can emit `rdc.assertion`, `rdc.release`,
`rdc.unknown_control`, `rdc.release_order`, `rdc.isolation` and
`rdc.reconvergence_protocol` monitor findings. Each binding uses an independent
observation clock and normalized control levels. These findings do not discharge
the structural lint report's unrun release or reconvergence proofs. Missing
bindings provide no reset protocol evidence. Between-sample pulses and physical
timing are outside this sampled contract.

### Optional HPM control checks

`hpm.selector`, `hpm.overflow_pending` and `hpm.counter_interrupt` identify
optional project monitor rules. The selector policy is a declared WARL mask.
The interrupt policy is sticky modular overflow with clear priority and a
separate interrupt enable. Counts and event multiplicity come from independent
observations. These rules do not establish architectural CSR access compliance,
selector event meaning, or real-core coverage without explicit project bindings.

### Independent device bus checks

Optional `register.bus_decode`, `register.bus_data`, `register.bus_order` and
`register.bus_latency` rules check accepted bus request/response observations
against project register addresses and version-1 register models. One request
can be outstanding. Read data precedes the request's side effects. An unmapped
address must receive an error. A zero-cycle response is allowed. A delayed
response must arrive within the declared positive cycle bound. These rules
provide no real-device or CSR compliance claim without a concrete binding.

MMU observation inventories can add `walk_check` with `status` of `consistent`,
`mismatch` or `inconclusive`. This bounded check compares immutable PTE read
addresses and values with scenario data and observes the physical target range.
It does not change architectural bins or C1-C4 verdicts. See the regress README.

Optional MMU `device_state` events retain sampled harness register state and an
IRQ schedule override flag. `pma_check` uses declared PMA data plus these events
and accepted bus requests. Its `consistent` result has the same bounded scope
as `walk_check`; neither changes architectural coverage or gate verdicts.

### Architecture Pareto intervals

`rvw.arch-pareto-plan/1` has `points` with unique `id` and `report` paths.
Optional `objectives` defaults to `["cycles"]`. Optional point `costs` paths
select user input files. Paths are relative to the plan. Reports are checked
`rvw.arch-run/1` gem5 runs with identical ELF hashes and ROI instruction counts.
Without costs, cycles use summed ROI cycles for all three interval bounds.
`rvw.arch-costs/1` has `report_sha256`, nonempty source/method text in `method`,
and `cycles`. Optional `area_mm2` and `power_w` are user-supplied inputs only.
The workstation does not estimate or validate area or power. PPA estimation
and hardware gain claims are out of scope.

Intervals are null or positive ordered `[lower, nominal, upper]` values.
Nominal cycles equal summed ROI cycles. Bounds are user declarations.
`rvw.arch-pareto/1` records selected `objectives`, plan/report/cost hashes,
`cost_origin` (`user-supplied` or `absent`), intervals, `eligible`,
`evidence_class: model-only`, `nominal_frontier` and `conservative_frontier`.
Conservative dominance compares only selected objectives. It requires all
upper bounds no greater than the other point's lower bounds and one strict gain.
Missing selected objectives exclude a point and make status inconclusive
(CLI exit 3). Unselected missing inputs do not affect eligibility.
No point is RTL-confirmed by this command.

### Architecture topology channels and agents

The optional `rvw.arch-core/1` `soc.memory.kind: multi` uses `interleave_bytes`
and 2, 4 or 8 `controllers` (simple or DRAM memory objects). Channels stripe
across RAM at a power-of-two byte size of at least 64. Optional `soc.agents`
contains up to eight read-only linear generators. Fields are `start`, `size`,
`block_bytes`, `period_ticks`, `duration_ticks`, `max_outstanding` and `attach`
(`memory` or an existing cache level). Addresses and blocks must align and fit
RAM. Time units are 1 ps ticks. Agents start at instantiation and idle after
the duration. They are not CPU harts. Fixed-latency C1 calibration still refuses
SoC topologies. Native model execution alone is not RTL correlation.

### Native memory mappings

`rvw.memory-mapping/1` has `inputs` (`stats`, `config`, `bare`, each with path
and SHA-256) and `observations`. Each observation has `point`, `region`, `hart`,
`workload` and `counters`. Counter keys use `rvw.memory-observations/1`; each
value has distinct `stats` names and positive `scale`. Names must start with
the native config object's point plus a dot. The first complete stats block
must have simFreq=1e12, simTicks equal to the difference of the two bare ROI
markers, and finalTick equal to the exit marker. Bare execution must pass.
`arch memory-extract` returns `rvw.memory-report/1` with `mapping_sha256` and
`native_inputs` hashes. It checks names and interval identity. The project
owns semantic mappings. Unmapped metrics and contention causes stay unobserved.

## Native task pack and qualification

`rvw.agent-native-tasks/1` declares a pinned `source` revision, source-copy paths,
source environment variable, adapter path, program directory, config, seed,
environment and run arguments. Adapter and program paths are relative to the
pack. Each task has a public summary and failing program names. Its private
fields hold a text mutation, fail-to-pass workloads and pass-to-pass controls.
A mutation can select a one-based occurrence. Core-specific data stays in the pack.

`rvw.agent-native-qualification/1` retains the pack digest, source and workstation
revisions and per-task seeded and repaired results. Each run retains C1/C2 paths,
identity, exit code and timeout state. `qualified` requires seeded failure,
passing controls and repaired workloads, complete C2, matching ELF/seed/config
identities and changed RTL hashes. Other verdicts are `unqualified` and
`inconclusive`. The evaluator supplies the repair. No agent reasoning, automatic
root cause or C4 acceptance follows from qualification.

## Inconclusive fixture tasks

Fixture task private data can set `requires_inconclusive: true`. Such a task
cannot earn `correct_fix`, even with a correct expression. A completed attempt
without a claimed fix sets `preserved_inconclusive`. Reports retain
`inconclusive_required` and `inconclusive_preserved` counts. Artifact rejection
reasons also accept `unsupported_fields`, `coverage` and `completion`.
Public evidence declares unsupported fields, observed and required coverage,
or `complete: false`. These are fixture claims, not native artifact checks.

## External fixture trials

`rvw.agent-external-trial/1` extends the fixture report with `client` command and
model label, `machine`, `budget_s`, `max_calls`, requested repetition count and
`attempts`. Each attempt retains exit code, timeout, wall time, admitted request
count, budget rejection count, request transcript and completion. The hidden
oracle stays in the parent evaluator. Client requests cannot query scores.
A token-authenticated loopback MCP connection exposes only fixture and job tools.
The CLI receives only its URL and token. The client must disable other tools.
No OS sandbox is claimed. A wall timeout stops the whole client process group.
Partial attempts remain scored as incomplete, with censored root causes. The
fixture report's native validation field remains `NOT RUN`.

## Native repair challenge and result

`rvw.agent-repair-challenge/1` records the task pack path and digest, source,
workspace, baseline revision, seeded workload evidence, reproduction flag and
bundle/cosim diagnostics. `ready` requires reproduced failures and passing
controls. Other results are inconclusive. Task packs can declare `project_copy`,
`project_mutations` and `program_copy` inputs for usable disposable projects.
Each copy maps `source` relative to the pack to `dest` in the workspace.
Build output directories are excluded from project copies. Public task text
contains no mutation or expected fix.

`rvw.agent-repair-check/1` records the task digest, candidate patch hash, source
and ignored file lists, seeded/repaired C1/C2 evidence and reproduction state.
Only source-copy paths enter the independent checker. The evaluator's programs
and adapter remain authoritative. Verdicts are `repair_verified`,
`repair_rejected` and `inconclusive`. No dynamic cause is inferred from a correct
patch. The result keeps root cause unknown, requires human review and claims
no C4 acceptance. Changed evaluator packs are refused.

Native qualification also requires equal, present `source.tools_rev` values
for seeded and repaired runs. A changed harness revision is inconclusive.

## Three-phase native qualification

Native qualification records `baseline`, `seeded` and `repaired` results.
Each workload has `batch_wall_s`. This is the total adapter batch duration,
including compilation. It is not a separate per-program runtime.
Each `cosim` record has status, first `mismatch`, wall seconds, exit code,
timeout state and the path to the full output. The pack declares `platform`
relative to itself. Qualification uses strict Spike comparison. Baseline and
repair must pass C1 and match Spike. Seeded failing tests must fail C1 and have
an explicit Spike mismatch. Seeded controls must pass and match. Missing
reference evidence is inconclusive. Baseline and repair retain equal ELF,
seed, config and harness revision. Existing repair-loop scores remain separate;
the three-phase rule applies to `native-qualify`.

## MCP evidence workflow records

`rvw.agent-evidence-solver/1` has a `native-tools` track, ordered transcript,
wall seconds, tool-call count, timeout flag and unique source `candidates`.
The evaluator can add `true_line_rank`. Candidate order follows the query
and wave response traversal. It does not imply causal confidence.
`observed` means all five workflow requests returned. `inconclusive` means a
request failed or its budget expired. Neither is a repair or C4 verdict.

A run also records `trace_complete`. A complete C1 cycle-limit timeout may
qualify a seeded failure when its strict Spike result has an explicit mismatch.
This rule applies only to fail-to-pass seeds. Controls and repairs must pass.
A wall timeout, missing end or matching prefix stays inconclusive. Raw C1
status is never changed in the report.

## Native evidence admission

`agent-bench audit-run` and MCP `agent_bench_audit_run` return
`rvw.agent-evidence-audit/1`. They validate actual C1/C2 syntax, identity equality,
ELF bytes, a nonempty trace and its end status. Optional `expected_identity`
checks task-owned RTL, ELF, source, seed or config values. Without this input,
a consistent old C1/C2 pair is not bound to a current task. `task_identity_fields`
records which task fields were checked. Optional relative `required_artifacts`
checks file presence only. It does not check coverage completeness or properties.
`evidence_consistent` is an admission result, never a repair or C4 verdict.
Missing or mismatched inputs are `inconclusive`. Both results retain `repair:
NOT CLAIMED` and `c4_acceptance: NOT CLAIMED`.

## External native-tool evidence trials

`agent-bench evidence-trial` and MCP `agent_bench_evidence_trial` use the existing
`rvw.agent-external-trial/1` report and bounded external transport with
`track: native-tools`. A plan has an `id`, the evidence solver's five `steps`
and optional evaluator-only `truth` with file and line. The client gets the
steps and budgets through `bench_inspect`. It never gets truth or the plan path.
The registry exposes those five normal tools, finish/inspect and job tools.
It has no source patch or independent repair-check tool.

Requests can retain `result` or `error` in the existing request log. Per-task
scores retain candidates, `true_line_rank`, returned-step count, evaluator
`workflow_outcome`, separate `client_workflow_outcome` and evidence timeout.
A returned native job counts only after a completed job response. Location rank
uses tool traversal order. It is not root-cause confidence. Root causes stay
censored. No source repair can earn credit on this evidence-only surface.
A client that claims a fix earns a false-fix result. Native repair checks and
C4 acceptance remain separate. Parent wall and call budgets retain partial
attempts. Client wall time excludes server startup and shutdown.

## Bounded qualification retries

`native-qualify --reuse-workspace` retains the existing private source path and
its compiler caches. It first checks the original source pin, tracked path set,
clean workspace and every source byte. Dirty or changed source copies are refused.
It reruns the baseline and all selected seed/repair checks. No prior score or
passing result is reused. A new `attempt` directory keeps raw outputs separate.
The previous report is archived before the next result replaces the main report.
Reports retain the attempt number and `previous_pack_sha256`. A changed task pack
is recorded as a new attempt with its own digest and fresh checks. It does not
change the pinned source requirement or combine scores across task packs.

## Observed mismatch wave time

Evidence steps can declare `mismatch_signals`, a project-owned mapping from
C2 difference fields to observable wave/database signals. The client selects
the first mapped field present in the live `cosim_check` response. A wave step
can declare `wave_time` with `order_signal` and `valid_signal`. The client calls
MCP `wave_find` for the mismatching retirement order and valid state. It uses
the first matching wave time. An absent retirement makes the step inconclusive.
Without a mismatch, it calls `wave_info` and labels the explanation as the run
end. It does not invent a divergent instruction. These calls share the existing
wall and call limits. The external evidence registry also exposes these two
read-only wave tools. The step transcript retains the time query and its basis.
No source cause, repair credit or wave/database identity proof is added.
