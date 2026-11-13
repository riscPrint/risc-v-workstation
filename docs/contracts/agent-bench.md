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
