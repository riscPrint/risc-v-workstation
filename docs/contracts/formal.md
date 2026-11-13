# Formal checks and SVA contracts

## Native typed SVA inspection

`formal sva-inspect` and MCP `formal_sva_inspect` emit
`rvw.sva-inspection/1`. Inputs are Verilog files, the top module, an output
directory, a native Slang plugin and a positive timeout. `RVW_SLANG` is the
default plugin selection. The command captures the input files, literal
includes, compiler identity and plugin hash. It writes the typed native tree
to `ast.json`. `properties` gives each native concurrent assertion an index,
AST `node_path` and `assertion_kind`. `node_kinds` and `operators` contain
native syntax counts. Native AST addresses have process scope only.

`proof_status` and `lowering_status` are always `not_run`. `status=parsed`
means native compilation succeeded and the native dependency report verified
the captured source closure. A missing report gives `inconclusive` with cause
`missing_native_dependency_report`. A missing active assertion gives
`no_checks`. Native compilation errors, an invalid AST or unsealed native
source dependencies give `error`. A timeout gives `timeout`. Only `parsed`
returns exit code 0. All other result statuses return exit code 1.

The result keeps compiler logs and source capture records. Runtime libraries
are not sealed. This inspection result is not a formal result or a support
claim for synthesis, property lowering or proof engines.

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Formal X campaign result extension

`rvw.formal/1` X results can include `backend: "yosys-xprop"`, `inventory`, and `replay`.
Each inventory target retains its assertion, signal, label and valid condition. Its
`disposition` is `candidate`, `confirmed`, `inconclusive`, or `not_reported`.
Only native 4-state replay can set `confirmed`. A formal encoded failure alone cannot.
`replay.backend: "icarus"` names the source RTL backend. Replay observations preserve
X/Z binary strings. Existing formal status and exit codes do not change. `unencoded_cells` lists data
cell types that Yosys could not encode. A nonempty list prevents a pass.

`rvw.formal.x-sweep/1` records `top`, `wall_s` and a `modules` array. Each module has its
name, disposition, target inventory, and result path or reason for missing evidence.
Module dispositions are `bounded_clean`, `confirmed`, or `inconclusive`. Bounded clean
requires a formal pass with reachability evidence. It applies only to this module's
free boundary inputs and selected bound. Campaign `status` is always `inconclusive`
and exit is 1. The inventory does not establish distinct bugs or core reachability.

### Native parent X context

`rvw formal x-context` writes `rvw.formal.x-context/1`. It records `top`,
`backend: "icarus"`, `depth`, `reset_cycles`, explicit constant `ties`,
`restrictions`, input capture identities and an `inventory`.
Each inventory entry has `signal`, `disposition` and `observations`.
An observation has `step` and a four-state binary `bits` string.
`reachable-in-core` requires a complete native run with X/Z after reset.
It is an unconditional signal observation in the selected top, not a claim that
a transaction is valid or a core bug exists. All other entries are `inconclusive`;
absence of X is not an unreachability proof. Overall `status` is always
`inconclusive`, and exit is 1. Invalid inputs exit 2.
`xprop` and `x-sweep` accept `--first-failure` to limit formal witness
collection. Unreported targets retain their existing disposition.

## Formal event model extension

BMC can explicitly select a sampled event model with `--event-model` and repeatable
`--event-clock PORT`. Extra clocks must be rising-edge top inputs.
`--async-reset` separately enables constant-value reset FFs (`$adff`, `$adffe`).
SBY `multiclock on` applies Yosys `clk2fflogic`. Each step is a global input
sample, with arbitrary clock rates, phases, simultaneous edges and stalls.
Optional periodic schedules constrain sampled clock ratios and phases, as specified
below. Unscheduled clocks have no ratio constraints. No fairness is inferred.
Async reset pulses visible for a sample are represented without a clock edge.
Pulses wholly between samples and analog timing are outside the model.

`rvw.formal/1` BMC results in this mode add `event_model`:
`backend`, `step`, `clocks`, `relationships` and boolean `async_reset`.
Failure `step` counts global samples; `cycle` is null.
The reset harness counts primary-clock edges, not global samples.
Other domains need not see an edge during that reset interval.
`from-sim` and X flows retain their single-clock refusals.

Inserted `rvw.checks/1` check entries add nullable `clock_domain`:
`clock`, `edge`, `reset`, `reset_kind`, `reset_active` and `clock_enable`.
Signal names are relative to the design top. Unavailable signal names are null.
This field records the check's Spinal domain, not a relationship constraint.
Older reports without this field remain readable.

### Dynamic PMP access monitor

`rvw.formal-apps/1` kind `pmp` binds request, grant, physical address, log2 size,
effective privilege, access operation, MML, MMWP and an ordered `entries` list of
config/address port names. Config width is 8. PMP address width is physical width
minus 2. Modes OFF/TOR/NA4/NAPOT use four-byte granularity. The monitor checks
first-touch priority and full access containment with base and MML permissions.
Latency 0 uses current policy. Latency 1..64 stores request-time permission and
valid bits. Grant safety does not imply completion or correct denial behavior.
CSR-bank identity is a reviewed project binding. CSR updates, lock rules,
WARL legalization, variable response ordering and other initiators are outside
this monitor unless checked separately. Native app proof results retain C7 scope.

### Digital entropy monitor

`rvw.formal-apps/1` property kind `entropy` binds a 32/64-bit `seed` output,
scalar `illegal` output and scalar input events `access`, `write`, `allowed`,
`refill`, `fatal`. Seed state is continuously exposed at bits 31:30. Controls
are sampled at the declared clock. A refill denotes fresh accepted entropy.
The monitor checks access errors, inactive data masking, RV64 extension,
consumption, BIST retention and fatal/DEAD persistence. It uses the existing
native app proof report. No result establishes physical entropy quality,
health-test certification, privilege decoding or independence of refill data.

### Two-copy security and reset contract

`rvw.security-pair/1` uses a reviewed top/port map, one RTL source, public clock
and reset, secret inputs, architectural outputs and digital observation outputs.
The result retains the plan, RTL hash and nested `rvw.formal/1` unbounded proof.
Status is `pass`, `fail` or `inconclusive`. CLI exit is zero only for `pass`.
Equal architectural observation prefixes require equal current observations.
No retirement alignment or implicit declassification is added. `initialization`
shares every input and compares independent RTL initial states after reset.
`constant_time` has declared operation names and no architectural guard. Those
names document project binding, not checked instruction decoding. `reset_values`
adds expected output values after reset edges. `reset_coverage` counts declared,
total output and proved bits. A nonpassing proof has zero proved bits. This
format does not record internal-register or whole-core security qualification.

### Equivalence witness simulation

`rvw.formal.cex/1` can set `source_flow` to `equiv`. The input must be a
`not_equivalent` result or a conditional `contract_verdict=not_equivalent` result with a witness inside a failed native eqy partition.
Simulation uses the captured partition RTLIL model and retains both source
snapshots. `reproduced` requires the same observed assertion path and source
in baseline and edited replay, without an assumption failure. It is simulation
evidence only. Status remains `inconclusive` and CLI exit remains 1. Generated
model and testbench files keep their existing generation-only contract.

### Conditional blackbox models

`rvw.equiv-blackbox/1` contains a nonempty `models` source-path list and a
nonempty list of prose `obligations`. Paths resolve from the manifest directory.
`rvw.formal.equiv/1.blackbox_contract` records manifest/model hashes and the
unproved model obligations. Both source snapshots include the model files.
A completed model-based proof has status `conditional`; `contract_verdict` is
`equivalent` or `not_equivalent`. CLI exit is always 1 for this status. Missing
evidence remains `inconclusive`. These models do not establish implementation
correspondence, physical behavior or unconditional equivalence. Unresolved
blackboxes and model assumptions/nondeterministic cells remain refused.

### Sequential equivalence result (`rvw.formal.equiv/1`)

`rvw formal equiv` compares two captured RTL file sets. It writes `result.json`.
`status` is `equivalent`, `not_equivalent`, `inconclusive`, or the model-based
`conditional` status defined above. Exit 0 requires a
successful eqy run, at least one partition, PASS for every output partition, and
complete register matching by default. `--unmatched-state prove` instead checks
closed output cones without name pairing, as specified below. A timeout or unknown
partition cannot earn equivalence. Exit 1 covers all other statuses. A busy or invalid
output directory exits 2. `not_equivalent` requires a failed output partition and
a VCD counterexample in `traces`. There are no internal state equality assumptions.
`state_mapping` records automatic or manual pairs and their widths. `unmatched`
lists unpaired registers on each side. `partitions` records each partition status.
`inputs` contains each side's capture and snapshot records. `restrictions` records
the single-clock, two-state model, reset alignment, unchecked startup clocks and
the declared fixed output latency difference. Blackbox obligations are refused. Optional `dsec` evidence
is advisory; `scorr; pdr` partition evidence sets the verdict. See the formal README
for the supported subset and initialization limits. This contract is separate from
bounded assertion results in `rvw.formal/1`; equivalence is an unbounded proof under
the recorded restrictions. A wall-time budget does not bound the cycles proved.

#### Register relocation matching

`state_mapping.method=unique_leaf` records an unmatched register pair with the
same leaf name and width. Each leaf must occur once on each unmatched side.
Manual and exact-name pairs have priority. This mapping adds no assumptions.
Ambiguous leaves and width changes remain unmatched.

### Directed MMU regression inputs

`rvw regress mmu` extends the existing ELF suite flow. It does not change C1–C4.
Its tool-local formats are `rvw.mmu/1` (scenario description),
`rvw.mmu-pma/1` (core-owned PMA declarations), `rvw.mmu-build/1` (ELF/hash manifest),
`rvw.mmu-reference/1` (Spike self-check results) and `rvw.mmu-check/1`
(C1 completion plus strict C2 oracle comparison). Field rules and limits are in
`rvw/src/rvw/regress/README.md`. Scenario bins are architectural-effect coverage.
A declaration or generated program alone gives no coverage. PMA declarations
are recorded inputs and do not imply PMA device observations.

### C1 persistent simulation session extension

`serve` requires `CoreAdapter.freshInstancePerRun = true`. The adapter declares
fresh DUT and harness state for each run. Other adapters cannot use `serve` and
record `reset: "adapter-defined"` in ordinary run metadata.
`serve` accepts JSONL run-option objects on stdin. Each response uses
`schema: "rvw.sim-server/1"` and contains `result` (C1) or `error` (a string).
`{"op":"shutdown"}` returns `shutdown: true` and ends the server. EOF also ends
it. Cancellation ends the whole process group. An abandoned worker ends the
server with exit 2 after its timeout response. Other run failures do not end it.
C1 `execution_mode` is `server` for server requests and `process` for ordinary
runs. Error and abandoned results also retain this field.
C1 `details.simulation_session` has `id` (process UUID), `model_run` (one-based
completed-run number per model), `rtl_sha256` (the generated Verilog hash,
null when unavailable), `reset: "new-native-instance"` and
`verilator_cached` (native cache hit at model compilation). These fields are
metadata. They do not prove reset equivalence. `details.execution_s` measures
adapter execution after model readiness. Existing RTL, native and source
identity fields still apply. Source edits require a server restart.
C1 `details.model_timing`, when present, records `elaboration_s` and
`native_and_setup_s`. The latter includes native cache lookup, workspace setup
and loading. Scala compilation and lock waits are outside these measurements.

Native identity namespace `native-inputs-v27` also accepts numeric Verilator
`--threads`, `--output-split` and `--output-split-cfuncs` options. Threads must be
positive. Values contain at most nine decimal digits. Unknown options and file
inputs still refuse capture. All exact option bytes remain identity inputs.

### C1 regression persistent worker pool

Regression defaults to persistent runs for `core.backend = "riscvsim-verilator"`.
An explicit `core.persistent = false` disables this default. Other adapters stay
opt-in. Each worker receives `run-many --persistent --jobs 1` and owns a separate
process group. `core.jobs` or regression `--jobs` selects the pool size. Each
process reuses its compiled models and requires the fresh-instance declaration.
Crash or timeout results do not grant a pass. Regression retries missing results
in a new process. Generated RTL identity remains required for result reuse.
The direct RiscvSim `run-many --persistent` command remains serial.

### From-reset replay descriptor

`rvw.replay-checkpoint/1` has `mode: "from-reset"`, a selected cycle, original
C1 path and SHA-256, C2 SHA-256, input identity, trace suffix and descriptor `id`.
The ID hashes the sorted compact JSON object without `id`. Verification rereads
original evidence. `rvw.replay-equivalence/1` with `status: "equivalent"` means
only that input identity, terminal result and suffix events match. It is not a
live snapshot or an architectural correctness verdict. External effects are
unsupported. Missing identity, changed evidence or differences exit 2.

### Source-revision equivalence export

`rvw formal equiv --gold-rev REV --gate-rev REV --top MODULE` selects
committed revisions from the selected project's `core.source_repo`. It requires
`core.source_env`, `query.build` and `formal.export_dependencies` (a nonempty
list of generator repository paths). Each generator repository must be clean.
The export records its commit. The build runs on a `git archive` source copy,
with `core.source_env` set to that copy, under the project's lock.
`query.build CONFIG DB --rtl DIR --no-pdg --no-blocks --no-hgldd` must generate
Verilog in DIR. Yosys selects MODULE and its child modules with `hierarchy -check`.
Missing modules or build failures cannot earn an equivalence verdict.

The result's `exports` records source commits, generator commits, configuration,
commands and RTL hashes. Each side retains source, generated RTL, selected module,
logs and `export.json`. Export directories must be new. This supports declared
sbt dependencies. It does not capture arbitrary external generator file reads,
network services or environment effects. Project authors must declare all generator
repositories. Submodule source content is not exported by `git archive`.

Directed MMU extensions retain the existing C1-C4 verdict rules. Control rows,
data corner fields, the optional adapter `rvw.mmu-observations/1` capture and
`rvw.mmu-coverage/1` inventory follow the regress README. `mmu check` additionally
binds `manifest_sha256` and each row's `c1_sha256`. A coverage report verifies
these hashes before using architectural bins. Observation counts are separate
from coverage. `recorded` is not a correctness pass.

Native farm collection also checks explicitly requested `max_cycles` and `mem_latency`
against C1 results. Missing or different values make collection inconclusive.

### C1 firmware payload extension

RiscvSim accepts `--elf-load-bias BYTES` (nonnegative decimal, default zero).
It applies only to self-relocating ET_DYN firmware. `elf_load_bias` records it
as a decimal string in C1. The ELF hash still identifies the original bytes.
ET_REL and PT_INTERP are unsupported. The loader does not apply dynamic
relocations. The adapter controls initial PC, privilege and GPRs.

`--boot-payloads PATH` selects a `rvw.boot-payloads/1` JSON object with `ram`
(`base`, `size`) and `payloads` (`file`, `address`) arrays. Addresses and sizes
are strings, in decimal or `0x` notation. Resolve files relative to the manifest.
Capture bytes before compilation. Reject overflow, overlap (including BSS),
empty payloads and ranges outside the declared RAM before the first write.
An adapter must declare support and load through `RunContext.loadMemory`.
Unsupported adapters must refuse this option. C1 `details.boot_payloads`
contains `path` and `sha256` for each input. `details.boot_loads` lists each
segment's `address` (hex string) and `size` (decimal string), in load order.
The replay command retains both loader options. These fields describe memory
placement only. They make no device, reset, Linux boot or timing claim.

### C9 RV32 in-order extension

Descriptions accept `kind="minor"` or `kind="timing"` only with `isa="rv32im"`.
O3 keeps its RV64 ISA choices. The CPU classes are RiscvMinorCPU and
RiscvTimingSimpleCPU. In-order descriptions require `queues=[]` and
`predictor=null`; CPU defaults apply. `cpu={}` selects all defaults.
Both caches can be null to bypass them. In-order SoC extensions are refused.
Optional `ram_bytes` selects page-aligned RAM capacity up to 512 MiB at the
existing base. The default remains 512 MiB. ELF segments must fit that range.
RV32 builds use ilp32 and stable high/low/high reads of 64-bit mcycle/minstret.
The guest still exports two 64-bit bench_stats words.
Static compatibility does not certify native execution or cycle fidelity.

C1 adapters can publish project-defined live ROI event numbers in `metrics`.
The project owns event names, observation points and mappings to gem5 stats.
They must not be inferred from model statistics. The VexRiscv example observes
RVFI retirement, excludes the first retired setStats entry and includes the
second. It publishes roi_retired, roi_loads, roi_stores and roi_branches only
with two markers and complete bench_stats stores. The CSR delta window stays
separate. Missing events remain missing; fitting refuses them. See the example
architecture README for opcodes, limitations and the saved-candidate fit plan.

### Generated SoC runtime input

C1 jobs can set `soc_map` / `--soc-map` to generated `rvw.sim-map/1`.
The parser captures the map bytes. C1 records `soc_map_sha256` and lists the
saved `sim-map.json` and `soc-transactions.jsonl` in `artifacts`.
`rvw.soc-capture/1` starts with `map_sha256`, `identity` (source and RTL hash), and
`observation` (`harness_decoder` or `map_monitor`). A map monitor classifies
accepted requests. It does not observe an actual RTL decoder select.
Request lines have `cycle` (integer string), `bus`, `address` (hex string),
`size` (byte count string), `write` (boolean) and `selected` (region name or null).
`{"event":"end"}` ends capture. These are harness request/endpoint observations.
They are not software-to-bus pairs. An incomplete stream cannot establish coverage.
`rvw soc capture-check` gives mismatch (1), inconclusive (3), or input error (2).
It has no pass verdict. `--platform` in cosim can also read `rvw.soc/1` directly.

SoC capture request identity: `rvw.soc-capture/1` headers carry a nonempty
`identity.run_id`. It is a fresh UUID for each simulation request. C1 records the
same value in `details.simulation_session.run_id`. `soc capture-check` requires
both values to match. A session UUID, ELF hash and seed alone do not identify one
request in a persistent session. Captures without a request ID are refused.

Request and process UUIDs belong to `RunContext.captureIdentity`. They do not
appear in the C2 header (`RunContext.rvfiHeader`). Equal simulation inputs keep
stable trace header bytes across fresh and persistent runs.

### Coverage semantic plans and closure suggestions

`rvw.isa/1` may include `semantics` with `version: 1`, `privilege_modes` and
an `exceptions` map from pinned instruction names to expected synchronous cause
numbers. These declarations participate in functional plan identity. They are
coverage targets, not reference outcomes or reachability proofs. Semantic operand
classes use C2 operand values. A per-instruction exception hit requires adjacent,
same-cycle trapped-instruction and synchronous trap records. Incomplete cause
correlation earns no hit. Sequence plans may select `kinds` as well as `distances`.

`rvw.coverage-candidates/1` has a `tests` array. Each item has `id`, `targets`
(nonempty glob patterns over bin IDs), integer `priority`, and `reason`.
`rvw.coverage-closure/1` hashes the report and candidates. It lists `unhit` bins
with separate `observation`, `reachability`, and `excluded` fields. Each bin has
ranked `candidate_tests`. Candidate rank is declared priority, not a measured
probability. No candidate changes a hit count or a reachability result.

RiscvSim exports native Spinal event tags as the existing `rvw.rtl-plan/1`.
IDs include physical instance paths. The complete plan hash supplies merge
identity. The exporter rejects pruned signals and conflicting source/type links.
Code coverage collection uses native `--coverage-per-instance` on checked
Verilator 5.052 or newer. Older or unknown tools keep collapsed coverage. Existing wildcard
hierarchies retain unknown exact instance denominators. Optional SpinalDB
attribution verifies the captured RTL hash and maps covered assignment targets
to Scala declarations. This attribution does not prove Scala statement coverage.
Schema `/20` memory-key `MemSymbolesTag` names can supply exact emitted memory
aliases for declaration attribution. Unknown or conflicting aliases are not guessed.
Coverage source links record comment, declaration, or mixed attribution methods.
Branch-operand declaration links are navigation evidence, not Scala statement hits.
Instance scope records include mapped and unmapped point counts.
Uncompleted RTL sequence goals can appear in `unhit` with `kind: sequence` and
`pending`. Pending activations do not establish unreachability.

The optional lint settings `intent` object contains `protocols` and `reset_order`.
The lint guide defines their exact fields. Structural `depth` records matched or
invalid protocol declarations, direct two-stage structures and declared reset
ordering. Protocol declarations and reset-order pairs are assumptions. They do
not earn protocol or release proof. New rule IDs are `cdc.handshake_candidate`,
`cdc.handshake_invalid`, `cdc.async_fifo_candidate`, `cdc.async_fifo_invalid`,
`cdc.reconvergence`, `rdc.reconvergence` and `rdc.release_order_unproved`.
Functional reconvergence and async FIFO rules retain `not_run` status as
`cdc.reconvergence_protocol`, `rdc.reconvergence_protocol` and
`cdc.async_fifo_protocol`. Structural findings retain the domain-bound waiver
identity. Protocol findings also bind their exact declaration in the message.
FIFO candidates require exact unconditional typed Gray encoder expressions.
`protocol_evidence` retains these keys and the selected memory/port records in
the finding, so they contribute to its waiver ID. This establishes an encoder
shape only. Pointer transitions and transfer behavior remain unproved.

## Formal app and benchmark reports

`rvw formal apps` reads `rvw.formal-apps/1` and writes
`rvw.formal-app-results/1`. Each row retains `property_id`, `requirement_ids`,
app kind, native status, proof kind and child result path. Status is `pass`
only when every child passes. Any failure gives `fail`; other cases give
`inconclusive`. Exit codes are 0 for pass and 1 for a written nonpass report.
Each child retains the existing `rvw.formal/1` evidence. A bounded app pass
cannot authorize an UNR coverage exclusion. The existing `cov prove` contract
still controls exclusion export. Activation and solver cores are not inferred.

`rvw formal bench` reads `rvw.formal-bench/1` and writes
`rvw.formal-bench-results/1`. Rows retain the case, engine, mode, requested
depth, explicitly observed depth or null, elapsed wall seconds, native peak
RSS bytes or null, native status, tool identity and result path. Absent engines
use `not_installed`; incompatible modes use `unsupported_mode`. Agreement is
`agree`, `disagree` or `inconclusive`. Exit 0 requires agreement for every case;
exit 1 means at least one disagreement or incomplete comparison. Agreement
is not a correctness or gate verdict. Pair comparisons require decisive,
matching verdicts on every case. Time ratios describe only the supplied suite.

Licensed adapters use `rvw.formal-adapter-request/1` and
`rvw.formal-adapter-response/1`. A response must bind to the SHA-256 of its
exact request bytes, retain the mode and engine version, and report finite
nonnegative measurements. A BMC pass requires an integer `reached_depth` at
least `depth - 1` (zero-based assertion step). Adapter verdicts are trusted observations. Invalid,
missing or timed-out responses stay inconclusive. See the formal README for
input fields and limits. Neither command emits gate acceptance.

### SVA frontend selection

`rvw.formal/1` results can add `frontend`, with value `verilog` or `slang`.
Absent means the default Verilog frontend. `slang` selects the restricted native
SVA subset for single-clock BMC. It preserves the existing bounded status and
reachability rules. It does not establish an unbounded proof or gate acceptance.
The plugin bytes appear in `input_capture.files`. The frontend's RTL dependency
report must stay within the copied inputs. See
[the supported subset](../rvw/src/rvw/formal/README.md#imported-sva-through-slang).

### Passive bus observations

An adapter can name `memory-bus.jsonl` in C1 `details.bus_observations`.
The JSONL header uses `rvw.bus-observations/1`. It gives C2 `identity`,
`bus_bytes`, `boundary: accepted-external-tilelink` and `independent: true`.
Each row records an accepted handshake with `channel`, decimal-string `cycle`
and `sequence`. A rows give `source`, `address`, `opcode`, `size_log2`, `mask`
and `data`. D rows give `source`, `opcode`, `size_log2`, `denied` and `data`.
Hex values use strings. Opcode and size use JSON integers. Same-cycle rows keep
capture order; this order does not imply an order between hardware effects.
An end row gives `kind: end`, `cycle` and the terminal C1 `status`.
Missing end rows mean incomplete capture. A terminal pass does not prove ordering.
The boundary excludes cache hits, buffered stores and device-side completion.
Adapters must not infer those events from retirement or from these handshakes.

The optional `rvw.mmu-observations/1` stream can also contain BOOM cache-stage
rows. `icache_response` gives hex `physical_address`, hex raw `data` and integer
`bytes`. `icache_invalidate` gives Boolean `refill_pending`.
`icache_refill_request` gives hex `address`. These share the stream's cycle clock.
They include speculative responses. They are not consumed-instruction evidence.

`fetch_consumed` rows in the optional observation stream give hex `pc` and
`instruction` from each accepted decode slot. These original instruction bits
come from the fetch buffer, independently of retirement. Wrong-path entries can
still occur. The project must map publication epochs and fence redirects before
using them as synchronized-byte checks.

Bus capture can include B, C and E rows. B gives `source`, `address`, `opcode`,
`param` and `size_log2`. C adds `data`. E gives `sink`. A and D rows also give
`param`; D gives `sink`. These accepted-channel observations do not identify
internal hits or replacement ways. Do not infer cache residency from capture
alone: clean evictions can be silent.

## Automatic formal checks

`rvw.autocheck/1` extends the reviewed formal app port manifest with optional
`dead_code` rows (`id`, `expression`) and `fsms` rows (`signal`, integer `states`,
`transitions` as integer pairs). Generated app plans use `rvw.formal-apps/1`.
The added kinds are `stuck_at` (`signal`, `bit`, `value`), `dead_code` (`target`),
`fsm_state` (`signal`, `value`) and `fsm_transition` (`signal`, `source_value`,
`value`). Report rows add `observation` without changing their raw native status.
A failing negated reachability target means `reached`. A passing bounded target
means `not_observed_bounded`. Unbounded passing targets mean
`unreachable_conditional`. Constant checks distinguish `not_constant`,
`holds_bounded` and `constant_conditional`. Existing safety contracts use
`violated`, `holds_bounded` or `holds_conditional`. Unknown results are
`inconclusive`.
Plans with reachability targets have aggregate status `inconclusive` because
reached targets are observations. No exclusion is authorized. Optional `xprop`
records the status and path of a separate bounded output X-propagation result.

## Portable scenario plans and observations

`rvw.scenario/1` declares resources, inputs, actions and backend timing bindings.
Actions carry ordering/data dependencies, resource claims, literal argument
constraints and expected outcomes. Planning emits `rvw.scenario-plan/1` with
`status=planned`, logical `scenario_id`, backend `plan_id`, timing unit and
scheduled actions. Operations do not execute during planning.

`rvw.scenario-observation/1` binds supplied records to a plan id, backend and
unit. Action records have operation, start/end, output, produced-data and
consumed-input fields. `rvw.scenario-check/1` reports match, mismatch or
inconclusive, comparison counts, missing evidence and failures. It checks the
supplied outcomes, data dependencies, ordering and resource occupancy. A match
does not infer execution provenance, hardware evidence or design acceptance.
Missing outcomes and zero expected comparisons remain inconclusive. See
`rvw/src/rvw/formal/SCENARIOS.md` for the finite contract and native PSS limits.

## Native unbounded assertion observations

Timed simulation accepts Boolean eventual response and until forms on both
backends. C1 `unbounded_properties` records `id`, `kind`, private `clock`, source
`event`, parsed `terms`, `operator`, `nonoverlap`, `monitor`, optional `disable_iff` and its
`disable_inputs` dependencies. Zero-argument
named properties expand before native lowering. Clock-local sampled functions
use the shared history emitter. The probe removes these statements only for
interface extraction. The sealed simulation model contains the actual monitors.

Assertion records add optional `pending`. Every request retains an obligation.
Completions produce pass or cover observations. A violated until hold condition
produces failure or miss observations. A final nonoverlapping request remains
pending until a later property event starts its consequent. No finite deadline
is substituted. Pending assertions make C1 inconclusive. Pending assumptions
prevent a design-fault verdict under an unresolved environment. Cover counts
include only observed completions. Failed assumptions retain their existing
inconclusive result. Native runner cancellation uses the shared process cleanup.

This is finite observation evidence. Native replay does not prove unbounded
liveness, restore earlier assertion obligations from a DUT trace, or qualify
full scheduling semantics. Native unbounded sequence composition, local captures,
cross-clock response remain unsupported. Native disable cancellation is defined
below.

## Native asynchronous assertion cancellation

Native eventual-response and until monitors accept `disable iff` on top-input
Boolean controls. They cancel active and delayed requests asynchronously.
Assertion records add optional `cancelled`. Cancellation is neither a pass nor
a failure. Previously recorded failures remain failures. Sampled history keeps
running. Disable conditions cancel only when their Boolean value is true.
Finite temporal monitors use the same true-only rule for X/Z disable values.

Native unbounded disable dependencies must be top inputs, must not include the
property event inputs, and must stay stable at matching event timestamps.
Internal and sampled disable expressions remain refused. These restrictions
preserve current-value disable semantics beside pre-event property sampling.
The formal liveness adapter still refuses cancellation. This native format does
not extend the engine's asynchronous-state support.

## Typed finite local captures

Typed finite local captures add optional `local_variables` to each
`rvw.sva-lowering/1` property row. The map records local names, widths and
signedness. A named property can capture design expressions in one Boolean
antecedent and use them in a finite consequent. Capture-list assignments run in
order. Each assignment applies the declared width and sign. Later assignments
can read or reassign a previously assigned local. An earlier assignment keeps
its value even when that local is later reassigned. History keeps overlapping
attempts independent. Reads before assignment, general sequence-local flow,
initializers, consequent slices and sampled uses of locals remain unsupported. The existing
single-clock sampled history and finite deadline limits still apply.

## Finite temporal SVA and parallel SBY observations

`rvw formal sva-lower SOURCE --out FILE` lowers finite clocked SVA to native
Yosys statements. It reports `rvw.sva-lowering/1` on stdout, with per-property
`id`, `kind`, `clock`, `disable_iff` and `horizon`. Unsupported syntax raises a
named `unsupported:CONSTRUCT` error before any output write. BMC accepts
`--frontend temporal`; its sealed source record contains the generated bytes.
Its `temporal_properties` array records each lowering horizon. Sampling, finite
bounds and asynchronous cancellation limits are in the formal README.

`rvw formal regress [MANIFEST] --jobs N --timeout SECONDS --out DIR` selects
one task per `[[property]]` row. `[formal] regress` in project data supplies the
manifest if omitted. A row has `id`, `sby`, `top`, optional `task`, `requirements`,
`assumptions`, and `config`. Paths are relative to the manifest. The new optional
project key is a path. Each resolved job has one assertion and one engine.
Workers are capped by N and CPU count. Listed inputs and tools are frozen first.

C3 `formal-regress` rows add `formal_status`, `mode`, requested `depth`, `traces`,
`task`, `requirements`, `assumptions`, `configuration`, `job_sha256`, `activation`
and an `inconclusive` reason. Unsupported rows carry `diagnostic`. Status values
are `proven`, `bounded-pass`, `failed`, `unknown`, `timeout`, `unsupported`,
`vacuous`, `error`. `proven` means an unbounded engine observation only. PREUNSAT
is vacuous. All other activation remains unmeasured. Input closure, full
attribution and non-vacuity are not certified. These rows cannot grant acceptance.
C3 and JUnit retain that restriction. `rvw.formal-regress/1` in `result.json`
has `status: unknown`, `suite`, `junit`, `workers`, and `properties`. Exit is 1
for these conditional observations. MCP `formal_regress` returns this summary.

## SVA intent generation

`rvw formal properties SPEC.json [--channels CHECKS.json] --out FILE` writes
module-body SVA snippets. MCP `formal_properties` returns the output path.
Without `--channels`, the spec has a nonempty `properties` array with unique
IDs. Supported `kind` values are `handshake`, `fifo`, `one-hot`,
`arbiter-fairness`, `request-response`, `flow`. Each row declares exact RTL
identifiers, an optional `clock` and optional active-high `reset`. The formal
README defines each finite contract and its fields. No environment assumption
is generated. Output generation is not a proof result.

With `--channels`, CHECKS uses the existing `rvw.checks/1` channel list. SPEC
maps each exact `path.object` to `id`, `clock`, optional `reset`, `width`, and
`ports`. `ports` maps reported qualified signal names to local RTL identifiers.
Flow also requires `max_value`. Missing clock/port bindings and composite
payloads are unsupported. This explicit mapping preserves independent channel
clocks without guessing domain semantics absent from the report.

The finite temporal frontend also accepts finite `throughout`, `within`, and
`intersect`. Endpoints remain part of the path semantics. Single-argument
sampled-value functions use the property clock, with unconstrained history
before the first event. `$rose` and `$fell` use bit zero; `$stable` and `$changed`
compare full vectors. Positive decimal `$past` depths from 1 to 64 and up to
eight nested sampled calls are supported. Historic values retain expression
width and signedness. Simulation comparisons preserve X/Z changes. Gated history,
alternate clock arguments and sampled reset conditions remain refused.
These are sampled formal observations, not simulator-region qualification.

### Equivalence output alignment

`rvw.formal.equiv/1` can include `output_mapping` and
`restrictions.latency_map`. The map keys are reference output names. Each signed
latency in -64..64 gives candidate lag in clocks. Negative values delay the
candidate in the comparison harness. Other outputs use `--latency`.
The startup mask adds the maximum absolute output lag to reset and settle.
An output rename changes only the boundary name. It adds no assumptions.
Separate output partitions remain closed proofs. A whole-design equivalence
result needs eqy PASS and PASS for every partition, without crossbits.

## Database autocheck candidates

`rvw.autocheck/1` can supply semantic `contracts`, `toggle` and a `waivers` map
from property ID to reason. Database mode derives ports, complete output enum
state and transition targets, simple arithmetic candidates and exposed memory
address candidates. `rvw.formal-app-results/1` can include `database` diagnostics
and `database_capture`. Skipped extraction is explicit. Waived property rows use
`status=waived`, `proof_kind=none` and a reason. An all-waived result has
`status=no_checks`. No waiver is a proof or a coverage exclusion. `toggle`
assertion failure means a transition was reached. Bounded non-observation is
not unreachability. FIFO contracts use accepted events and a combinational read
interface without empty fall-through. They are safety checks, not liveness.
Generated app properties can retain `module`, `origin=generated` and `source`
with the database's Spinal file and line. The testplan reader also accepts an
app `spec.json` inventory and captures its existing per-property C7 results.
Missing results are not run. Waived entries remain waived.

## Captured assertion enable measurements

`rvw.solver-core/1` can contain `property_activation` records with native property
ID, bounded depth, status, scope, blocking core and blocking assumption cells.
Only exported Yosys assertion-enable expressions are measured. SAT means reached.
UNSAT means not reached in this bounded model. Unknown results and infeasible
environments stay inconclusive. Missing patterns are not measured. These fields
do not establish full logical non-vacuity or grant coverage exclusions.
Core evidence can declare a testplan `property_id` alias. The report preserves
the native ID under `proof_core.captured_property_id`. The input capture binds
this declared association. It is not a semantic-equivalence certificate.

## Formal testplan evidence joins

`rvw.formal-testplan/1` lists property IDs, modules, origins, optional source
locations, requirement IDs, mutation IDs and external evidence paths.
`rvw.formal-testplan-report/1` retains each property result, depth, proof kind,
activation, core labels and explicit mutation outcomes. It groups counts by
module and source line. Missing evidence remains explicit. Requirements and the
aggregate report remain inconclusive. `cell_coverage=unavailable` prevents SMT
constraint labels from becoming cell coverage. `exclusion=not_authorized` grants
no new waivers. The input capture binds the plan and every evidence file.
Solver-core reports can include `assumptions`, with captured cell names, labels
and `in_core`. An UNSAT environment gets a reduced `environment_core` and an
`environment_minimal` flag. This is deletion minimality over constraint groups,
not minimum cardinality or full assumption adequacy.

## Coverage-directed replay selection and finite-graph fairness

`rvw.formal-swarm/1` can select cycles from a state plan. The plan declares
`trace_sha256`, unique `holes`, and `states` with unique positive `cycle` and
`targets` from those hole IDs. The runner checks the captured trace hash. It
selects the state with most remaining targets first, then the lowest cycle.
Targets are priorities, not proof evidence. `selection` records the plan hash,
trace hash and unrepresented targets. `engine_pool` rotates across attempts.
Every attempt records its engine. The campaign remains inconclusive.

`rvw.formal-model-live/1` checks `GF progress` on an explicit transition graph.
`progress` lists states. Each entry in `fairness` is a state set that must recur
infinitely. The checker searches reachable nonprogress strongly connected
components that contain a cycle and meet every fairness set. Such a component
is a counterexample. No feasible fair infinite execution is inconclusive.
Deadlocks are listed separately. A pass proves the supplied graph only under
its declared justice assumptions. It does not certify an RTL translation.
`model_sha256` identifies the exact captured model. CLI `model-live` and MCP
`formal_model_live` return the same report. MCP `formal_swarm` runs replay.

## Timed finite-SVA simulation

`rvw.formal-events/1` contains `timescale`, `clocks` and `events`. Each event has
`time` and an `inputs` map of exact-width four-state binary strings. Time starts
at zero with every input declared. Later times strictly increase. Clock changes
and data/reset changes have distinct timestamps. No periodic clock is inferred.

`formal simulate` and MCP `formal_simulate` write C1 `rvw.run/1`. Additional
fields include `assertions` with per-property pass/fail/cover/miss counts,
`observations`, `unknowns`, `backend`, `x_semantics`, `scope` and captured inputs.
Assumption failures and absent checks are inconclusive errors. Assertion faults
use C1 `assert`; requested X observations use `fail`. Verilator results cannot
claim four-state X evidence. The coverage artifact contains sampled monitor
points in Verilator point-record format, attributed to generated simulation RTL.
It is consumable by `rvw cov`, and is not native RTL code coverage. Source hashes
keep different generated models separate. Pending future obligations and full
simulator scheduling-region conformance remain outside a finite replay pass.

## Database app role evidence

Formal app reports retain `database.roles` with role, source database evidence,
generated check IDs and unsupported reasons. Exact internal enum exposure is
recorded in the captured generated plan as `internal_ports` with widths.
`counts` separates generated obligations, unbounded passes, bounded passes,
solver failures and unsupported discovery records. Reachability failures retain
their observation semantics. Counts do not grant a design pass.

## Generated ISA monitors

### Sail binary bit-manipulation generation

`rvw.sail-bitmanip/1` records 19 RV32 binary result slices from pinned Zba, Zbb,
Zbs and Zbc source files. It uses the Sail Zicond generator's file and compiler
identity fields. `rule` maps source groups to pinned paths and hashes. Each
`files` entry includes the extracted execution body, encoding layout, extension,
operand lowerings and generated hashes. Prelude and carryless arithmetic helper
hashes are part of the source identity. The instruction shell is generated by
this tool. Full architectural state and extension-disabled traps are excluded.
The manifest is generation evidence. It is not a proof verdict.

## Architectural-state monitor generation

`rvw.architectural-state/1` maps named RTL observations to one retirement-aligned
architectural pre/post state. It declares XLEN, the top module, clock/reset,
self-contained source files, complete register snapshots, source/destination
indices, PC, trap/interrupt/mode and memory fields. Optional named CSR snapshots
are observations only. No signal defaults silently to zero.

`rvw.architectural-state-generation/1` records `generated` status, input and
manifest hashes, derived file hashes, widths, a runnable `rvw.toml` project and
explicit limits. Yosys flatten/expose retains observation drivers. The monitor
asserts x0 and register frame effects. Order is derived from retirement events.
In simulation, a failed x0 or frame assertion stops with a nonzero exit code.
Unknown compared state also fails the simulation assertion. Formal checks keep
their native assertions. The PicoRV32 example also stops on validity mismatches.
Generation does not establish snapshot alignment, memory pairing, CSR semantics,
independent order conformance or an ISA proof.

|---|---|---|

## Internal RTL path observations

`rvw.internal-path/1` records directed bit dependencies in captured RTL after
Yosys flattening and memory mapping. It reports `no_path`, `path_found` or
`incomplete`. Cell inputs conservatively influence all cell outputs. Clock,
reset and control inputs remain in that graph. Black boxes and unknown port
directions cannot establish absence. A node bound also makes absence incomplete.
The report records source and flattened-netlist hashes. A witness is a sequence
of bit IDs and cells. It is not a Boolean sensitization or transfer proof.
Exit 0 means no path in this captured conservative graph. Exit 1 means a path
was found. Exit 3 means incomplete evidence. No design acceptance is granted.

## Secure path policy proofs

`rvw.secure-path/1` records a project-owned source/sink or resolved static
isolation policy. It retains the RTL hash, mapping tool identity, explicit
unmodeled channels and nested C7 proof. `pass` exits 0 only when the assertion
flow exits 0 with status pass. `fail` requires a failing C7 result. Missing or
incomplete evidence is inconclusive, exit 1. This result grants no C4 acceptance.
IFT sink checks start after public synchronous reset. An optional public
`declassifier` disables sink checks only while asserted. Constant-time policies
check declared timing sinks on every cycle. Static isolation policies check
observed grants against priority byte ranges and explicit master/privilege
permissions. CSR policy derivation and dynamic policy updates remain unmodeled.

## Raw property event replay

The timed simulation route can rewrite top-level finite SVA property clocks to
private replay pulses when a source has raw events. `property_events` in its C1
result records each original `event`, parsed `terms` and private `clock`.
Terms use `edge=change|posedge|negedge` and a top-input `signal`.
The time-zero event row initializes inputs. Each later row fires matching
monitor pulses once before updating design inputs. Monitors sample preceding
settled values. Output observations use post-update settled values.

Raw events use four-state semantics on Icarus. Verilator accepts only two-state
inputs and refuses X checks. Icarus rising edges include 0 to X/Z
and X/Z to 1. Falling edges include 1 to X/Z and X/Z to 0. Change events compare
all vector bits. This scope refuses internal events, event expressions,
same-event disable cancellation and properties outside the top module.
It does not change the formal solver's event or state model. Simulation counts
and code coverage retain finite-prefix evidence limits. A failed compilation
cannot retain earlier coverage or runtime logs.

## Sail state slices

`rvw formal sail-state` and MCP `formal_sail_state` emit
`rvw.sail-state-slices/1` in `manifest.json`. Status `generated` means source
compilation succeeded. It is not a proof verdict. The manifest records the
pinned model commit, each source path/hash, each rule's source text and line,
operand and result widths, lowerings, compiler/library hashes and output
hashes. Each output has a pure kernel and a clocked result checker.

The exported slices cover H/S/D sign injection, RV32 CSR access and proposed
write values, and MRET/SRET/WFI entry decisions. The command README defines
each port and control field. Project wrappers must bind decoded operands,
valid operation events and observed results. FP outputs have no x0
suppression. Invalid privilege encodings disable privileged entry checks.
Full CSR, privileged and FP state transitions remain excluded. A passing
kernel oracle does not prove a core instruction implementation.

## Boolean two-clock assertion replay

Timed Icarus and two-state Verilator replay accept top-module Boolean implication from one
explicit input-clock edge to another. `|->` selects the nearest target event,
including a simultaneous event. `|=>` selects the nearest strictly later event.
The replay coordinator samples both domains before the timestamp input update.
Runtime nonblocking driver phases preserve this ordering on both backends.
Its pending counter retains every request. One target event can check several
obligations and produces one assertion observation per activated request.

C1 `cross_clock_properties` records each property id, kind, `clock`,
`target_clock`, `clock_events`, parsed `terms`, `monitor` and `overlap`.
False or unknown antecedents do not activate requests. An unknown consequent
fails an active assertion. Pending obligations at the trace end do not become
passes. The route refuses sequences, sampled functions, non-top properties and
implicit clocks. Zero-argument named properties and module-local aliases expand
before replay lowering. Finite named properties with local captures keep their
existing scope. This does not enable cross-clock properties in formal lowering.


## Trace-selected timed replay state

`rvw.formal-events/1` can contain `state` with `trace`, `time`, `scope` and
`registers`. The trace is VCD or FST and is captured with the event input.
Relative trace paths use the event file's directory. The initial input row must
match every trace input at the selected timestamp. Named register values must
cover all elaborated DUT state bits. Generated monitor registers and native
formal samplers are excluded. Alias wires do not exempt DUT state.

The route loads complete elaborated flip-flop state through named instances.
State-bit identities include the instance path. Register names must be actual
RTLIL flip-flop Q destinations, so combinational aliases cannot satisfy coverage.
It refuses memories, black boxes, incomplete state and input-phase mismatches.
Icarus input setup settles before all recorded registers are forced. Derived
clock and asynchronous-control events settle while every register remains
forced. All registers are then released. Logical replay time starts at release. Property clocks
use private pre-update pulses, so setup cannot count as a property attempt.
Monitor histories restart. C1 `state_load` records the captured trace hash,
timestamp, timescale, scope, loaded register values, state-bit count and limits.
Native four-state observations retain finite-continuation scope. This format
adds no multi-clock state loading to the formal solver.

## PSL to SVA lowering

CLI `formal psl` and MCP `formal_psl` translate a finite Verilog-flavor PSL subset
to the existing SVA frontend. An explicit rising-edge clock or matching default
clock is required. Generation reports `rvw.psl-lowering/1`, `status=generated`,
and the output path. This is not a verification result. Unsupported PSL forms
are errors. The adapter does not silently replace liveness with finite bounds.

## Autocheck event reset selection

`formal autocheck` and MCP `formal_autocheck` accept `event_model` and
`async_reset` (CLI `--event-model --async-reset`). These select the existing
constant-value ASYNC-reset event BMC model. Default single-clock flows still
refuse asynchronous state before proof execution and give a fix hint.

## Exact regression observation cache

`formal regress --proof-cache DIR` and MCP `formal_regress(proof_cache=DIR)`
can reuse a conditional successful engine observation. C3 rows add `cache.hit`
and `cache.scope`. The scope is `conditional engine observation`. A cache hit
preserves `formal_status`, BMC depth and activation limits. It does not upgrade
a bounded pass or certify non-vacuity. JUnit retains the conditional outcome.

The cache accepts self-contained `read_verilog`, `prep`, `async2sync` and
`dffunmap` scripts. It refuses includes, memory files, file I/O and other script
commands. Keys include captured source bytes, job settings, property metadata,
formal/common Python code, executable identities and the tool environment.
Restoration checks stored artifact hashes and current tool bindings. Failed,
vacuous, unknown and timeout outcomes are not published. General SBY input
closure remains outside this restricted cache route.

## Antecedent observations and DSL locations

Finite temporal simulation adds `assertions[].activated`. It counts complete
antecedent matches at their own endpoint. It does not wait for the consequent.
False antecedents do not increment this field. Pass counts retain their existing
implication semantics. Other monitor routes report null when activation is not
measured. A count of zero reports no witnessed match in this finite run.

A regression property can declare `activation_sby` and optional
`activation_task`. The selected job must use cover mode, the same engine as the
assertion job and exactly one cover cell after preparation. C3 `activation`
records `status`, `depth`, traces and elapsed time. `reached` means that this
bounded cover has a witness. `not_reached_within_bound` does not prove that an
antecedent is unreachable. Other engine outcomes retain their error or unknown
status. The cache key includes both jobs. Cache entries retain activation logs,
models and traces. Assertion results keep their original formal status.

The Scala DSL emits `// rvw-source: FILE:LINE` at each statement. Its frontend
report and finite C1 rows retain `source = {file, line}`. The example generator
puts that location in each regression manifest row. C3 retains it on failures
and other outcomes. File names are source basenames. This identifies the DSL
call site. It is not a complete transitive source or input-closure certificate.
Helper functions can pass `sourceDepth` to skip their own Scala stack frames.

## Simple property defaults

Finite temporal lowering and named-property expansion accept module-local
`default clocking [NAME] @(EVENT); endclocking` with an empty body and
`default disable iff (EXPRESSION);`. They replace omitted controls with explicit
ones. Explicit controls take priority. A named alias inherits controls at its
resolved definition. Defaults stay inside the declaring module.

Only one inline clock declaration and one disable declaration are accepted per
module. Nested defaults, skews, clocking IO declarations and separate named
clocking selection remain unsupported. This normalization does not add an event
model or reset semantics to an engine that previously refused those controls.

## Compiled literal resource scenarios

`formal scenario-compile` writes `rvw.scenario-compiled/1` with `status`,
`actions`, `finisher` and `scope`. Status is `generated`, never executed or
accepted. Artifacts are `program.S`, `scenario_sequence.py`, `operations.json`,
`baremetal-plan.json` and `pyuvm-plan.json`. Both selected backend plans must
use cycles and the same action order. Operations are aligned literal RV32
`read32` and `write32`. Dynamic produced/consumed data is refused.

A project binds the generated virtual sequence's async `start`, `observe` and
`finish` port methods. `observe` returns the actual value and measured start/end
cycles. The sequence checks expected values and emits the existing
`rvw.scenario-observation/1`. The bare-metal adapter must produce separate
observations. The existing scenario checker validates outcomes, dependencies
and resource occupancy. The CPU-backed route is not an independent bus master.

## Nested eventual milestones

The existing liveness result schema records `operator: nested_eventually` and
`milestones`, the number of ordered Boolean milestones. Two to eight terms
are accepted. The acceptance predicate uses a separate set of old obligations.
It must hold infinitely often. These fields do not turn a finite observation
or bounded pass into an unbounded proof. Other nested temporal operators and
multi-clock proofs retain unsupported results.

## Trace property candidates

`rvw.trace-candidates/1` records the number of signal samples, trace boundaries,
retained `observed_candidate` rows, refuted count and inactive count. Each row
has a generated ID, kind, signal names, activation count and member hit counts.
Supported kinds are guarded next-sample stability, Boolean implication, mutex
pairs and declared one-hot-or-zero sets. Every supplied trace is checked.
No transition crosses a trace boundary. Unknown or missing values are errors.
Candidates with a refutation are omitted. Dead antecedents and insufficiently
activated set members are omitted. The result is finite observation evidence.
It is not a proof or a generated assumption. Review the emitted Scala DSL
before it is added to a core's property set.

## Finite core progress observations

The VexRiscv example's C1 assertion rows can record `pending`. This is the
number of eventual-release requests still open when simulation ends. Nonzero
pending counts give `inconclusive`, even if the program writes its passing
finisher value. `passed` counts completed requests. `activated` counts started
requests. These finite observations do not prove infinite-trace liveness.
## Machine-return MPP observation

`rvw.machine-checks/1` trap-return bindings now require `previous_mode_after`
with width two. The check asserts the MPP update as well as privilege, PC,
MIE and MPIE. `least_privileged_mode` is 0 by default. Set it to 3 for a
machine-only profile. Other values are rejected. This additional observation
is required on old manifests too; a missing observation is an error.

## Global-step two-clock proof

`formal cross-prove` prepares one C3 property job with `multiclock on` and a
separate bounded obligation cover. Both use global-step pre-update sampling.
The two scalar top-level property clock inputs start low. No fairness is added.
A pending request is checked at its nearest eligible target-clock event.
Simultaneous events follow overlapped or nonoverlapped implication semantics.
C3 retains the engine mode, depth, assumptions and separate activation result.
An unbounded engine result applies only to this discrete global-step model.
It does not prove that a target event will eventually occur or model transitions
between samples. Other SVA composition and full simulator scheduling remain
outside this subset.
Replay metadata for this subset also retains the Boolean `antecedent` and
`consequent` expressions. These fields describe the parsed operands. They do
not indicate that replay or proof ran.

## CSR slice contracts

`rvw.csr-slices/1` supplies implemented `addresses`, project `bindings` keyed
by catalog CSR name, and a base `machine` plan in `rvw.machine-checks/1` format.
The shared catalog resolves every address. Missing bindings stay unsupported.
Each binding uses the existing CSR consistency signal map and write mask.
Optional `cone_cuts` names local RTL nets. Yosys must find exactly one net for
each cut. It replaces the driver with an unconstrained symbolic value.
Project assumptions must state the boundary contract in the captured source.

`rvw.csr-slice-results/1` has one row per implemented address, the pinned
catalog revision, and native check and cover tokens. A passing cut job reports
`local_status: bounded`, `status: inconclusive`, and scope `local cone contract`.
This result requires separate pipeline composition evidence. A failing cut job
is a local contract counterexample. It does not by itself establish a core bug.
The API runs jobs in sequence. It does not grant whole-bank signoff.

`rvw formal isa --machine SLICES.json` accepts this slice manifest and prints
one `csr_consistency:NAME` row for each catalog entry. The aggregate CSR row
stays inconclusive while any binding or composition evidence is missing.

## Declared pulse request/response checks

`rvw.hdl-ports/1` accepts `req_rsp` for check generation. Its ports are
`request`, `response` and a nonempty `payload` list. The request is a
one-cycle issue pulse. Only one transaction can be outstanding. A response
must have an outstanding request or a request on the same edge. A new request
can replace a transaction that completes on that edge. Reset cancels tracking.
This monitor checks transaction counts. It does not check data or liveness.

`req_ack` uses the same port keys. The request and payload stay stable until
acknowledgment. An acknowledgment without a request is permitted. This is a
level handshake, so its monitor uses the existing ready/valid stability rule.
The project must choose the protocol from its interface specification.
VIP and UVM ready/valid agents still reject these two new protocol names.

## BOOM source disposition inventory

`SpinalChecks/boom/stream-dispositions.json` is a source review, not a native
check result. `source_dispositions` counts all named rows.
`historical_named_dispositions` excludes the IDs in `later_aliases`.
`unmapped_historical_checks` compares only those historical names with the
reported original total. A later alias cannot fill an original inventory gap.
`native_validation` remains `NOT RUN` until separate native evidence exists.
