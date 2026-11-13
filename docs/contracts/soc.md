# SoC project data contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## SoC project data

`rvw.soc/1` is an explicit input to `rvw soc generate MAP --out DIR`.
It does not change `rvw.project/1` selection. See the [SoC map contract](../rvw/src/rvw/soc/README.md)
for all fields and export limits. `rvw.sim-map/1` contains `address_bits`,
`regions` and `interrupts` from the validated map. The `schema` identifies the
consumer format. It does not imply that an adapter loaded the data.
Generation returns exit 0 with `status=generated`, or exit 2 with `status=error`.
No generation result is a design consistency verdict.

`rvw.soc-bindings/1` selects exact signal paths and decoder assignment keys from
SpinalDB `/20`, plus translation expectations for paired transaction samples.
`rvw soc check MAP --bindings FILE --db DB [--transactions JSONL] --json` writes
`rvw.soc-check/1`: `status`, `checks`, `gaps` and `transactions` (sample count).
Checks have `name`, `actual`, `expected`, and `status` (`consistent`, `mismatch`,
`unavailable`). Overall `mismatch` exits 1, `inconclusive` exits 3, and malformed
input exits 2 with `status=error`. No check result can grant C8 acceptance.
The [SoC tool README](../rvw/src/rvw/soc/README.md) defines the bounded evidence.

### C9 offline event fitting

`rvw arch fit PLAN --json` and MCP `arch_fit` consume `rvw.arch-fit-plan/1`.
The exact fields are `schema`, `rtl`, `candidates` (name to gem5 report path),
`train`, `held_out`, `events`, `scope`, `uncertainty`, and `unsupported`.
Paths resolve against PLAN. Each event has `name`, `rtl_metric`, `gem5_stat`,
`unit`, and `semantics`, plus optional `role` (`fit` or `consistency`). Events map raw C1 `metrics` to the first ROI stats
block in gem5 `stats.txt` beside `bare.json`. Event semantics are a project
assertion. All mapped values must be finite and nonnegative. Missing values
are errors. Existing C9 comparison evidence checks apply to every candidate.
Train and held-out IDs must be distinct, nonempty and cover all report IDs.
Their ELF hash sets must also be disjoint. Renamed ELF copies cannot be held out.

`rvw.arch-fit/1` records status `reported` or `inconclusive`, the selected candidate, training
scores, the winner's held-out score, winner event errors, split IDs, mappings,
scope, uncertainty, unsupported structures, plan/RTL/candidate report hashes,
and raw stats paths and hashes. Error is `abs(model-RTL)/max(1,RTL)`.
Instruction units, retired totals, instruction-class totals and commitStats
are consistency checks, even with role `fit`. They do not enter the objective.
Other events default to `fit`; role `consistency` excludes a project-owned fixed event.
The objective averages relative cycle error and eligible event errors per
workload, then averages workloads. `selected_errors` includes each event's
resolved role. `headline` includes `metric=cycle_relative_error`, per-workload
comparison rows (cycle gap and IPC ratio), and mean absolute cycle error per split.
Fewer than three training workloads, constant training cycle or eligible event targets, or equal
scores across multiple candidates give status `inconclusive` with a reason.
`event_fit` lists eligible events and constant targets. No eligible events or
insufficient target variation gives event-fit status `inconclusive`. Only training scores
select the winner. Lexical candidate names break ties. No acceptance or
confidence claim follows from this report. The caller must keep held-out
workloads separate when creating candidates. This offline command runs no parameter search.
Use the search extension below to generate parameter candidates.

### C9 static compatibility preflight

`rvw arch inspect --elf ELF --isa ISA --kind KIND --json` checks static ELF
layout independently of performance calibration. MCP exposes `arch_inspect`.
`rvw.arch-compatibility/1` records status, ELF path/hash, ISA, XLEN, CPU kind,
RAM base/bytes, required symbol addresses/sizes, blockers and limits.
Supported input labels are `rv32im`, `rv64gc`, `rv64gc_zba_zbb_zbs` and CPU
kinds `o3`, `minor`, `timing`. ELF class must match XLEN. Required runtime
symbols and the fixed RAM layout are checked in ELF32 and ELF64.
RV64 O3 and RV32IM Minor/TimingSimple return `compatible` (CLI exit 0).
Other known combinations return `unsupported` (CLI exit 2) with a CPU/ISA blocker. Unknown
labels or invalid files give the normal error object and exit 2.
Compatibility does not establish instruction behavior, ISA extensions,
ROI counter validity or model fidelity.
MCP returns the same status in the result of its background job.

### C9 SoC description extension

`rvw.arch-core/1` accepts optional `soc` as documented in `Arch/README.md`.
Its exact keys are `levels`, `interconnect`, and `memory`. Levels are an ordered
array of zero to two scalar Cache parameter objects (L2, LLC). Interconnect
requires width and the four crossbar latency parameters. Memory selects
`simple` (latency, bandwidth) or `dram` (model, controller, interface).
DRAM models are DDR3_1600_8x8 and DDR4_2400_8x8. One classic memory path and
one controller are supported. The address window does not change.
SoC runs are model-only. C1 fixed-latency calibration refuses this extension.

### C9 memory interval reports

`rvw.memory-observations/1` and `rvw.memory-report/1` use the fields and units
in Arch/README.md, Memory observations. Reports preserve all input counters,
observation identities and evidence hashes. Missing metrics are null and listed
as unobserved. Status reported means arithmetic completed. It does not validate
the producer's mapping or establish the cause of contention.

### C9 bounded experiment extension

`rvw.arch-sweep/1` declares parameters (dotted paths to value arrays), max_points
and timeout_s. `rvw arch sweep` and MCP arch_sweep implement the limits and
identity rules in Arch/README.md, Small design-space sweeps. Unknown fields
are errors. `rvw.arch-dse/1` records the input hash, model-only point records,
objective and speed-only Pareto list. Its status is reported only when all
points produced reports; otherwise it is inconclusive (CLI exit 3).
SQLite points retain completed and incomplete trials. Null area and power
and unquantified uncertainty must not be interpreted as zero cost or confidence.

### Linux reference reports

`rvw arch linux firmware|build|prebuilt|prepare|boot` writes `rvw.linux/1` to
`OUT/manifest.json`. `OUT` must be new. The JSON stdout uses the same object on
success. Errors return exit 2; an initialized output keeps an inconclusive
manifest and command log. These reports do not produce a C4 verdict or claim
C8 completeness. `rtl_boot` is `not_run`; `equivalence` is `not_checked`.

`built` means files were constructed. `prepared_reference` means images and
QEMU tables were captured and the selected properties matched project data.
`reference_userspace_observed` additionally requires a clean QEMU exit, the
fixed userspace marker and power-down message, with no kernel panic.
Artifacts use absolute paths and SHA-256. The build report binds the source and
configuration. Reference runs bind kernel, initramfs, firmware, DTB, platform,
QEMU, command line and console. Selected table checks record expected and
actual values separately. They are not device-state or timing checks.

The `prebuilt` action takes `--source` (`rvw.linux-prebuilt/1`) and `--images`
(the native firmware directory). The source declares HTTPS URLs and SHA-256
for `Image` and `rootfs.cpio.gz`. `initramfs_selection` declares directories,
source-to-target regular files and symbolic links. The action selects these
bytes from the checked newc archive and adds `/rvw-init`. The report records
upstream hashes, source-lock hash, init-script hash and transformed artifacts.
It does not verify an upstream package signature. Device compositions and
bounded startup reports in `examples/qemu-linux` are project data. They do not
extend C1 or certify a connected RTL device bus.

The explicit `--platform` JSON uses `rvw.linux-platform/1`: `machine=virt`,
`harts=1`, `memory_mib=128`, `command_line`, and nonempty `dt_checks`. Each
check has `node`, `property`, `type` (fdtget format) and `expected` (exact text).
It is independent of the project's C1 selection. Network, storage devices and
console input are disabled. RTL loading and device replay remain unsupported.
See `Arch/README.md` for pinned sources, host limits and the close condition.

### Core-owned ISA declarations (optional)

`rvw.isa/1` JSON declares an expanded `isa` string, `extensions` keyed by
extension name with `version` (string or null) and optional `requires` list,
`options` object, and optional `consumers` mapping tool names to ISA strings.
Null means not verified. `rvw cov isa-check` validates these declarations.
This optional file does not change the project selection contract.

For generated functional bins, the ISA manifest can include `source` with
`url`, a full commit `revision`, and `files` (relative opcode paths to SHA-256).
`arg_lut.csv` defines the encoded operand fields. `unavailable` lists excluded
coverage scope. Optional `specifications` stores other spec pin declarations.
The functional report embeds the generated plan in `config.isa_plan`. Its
fingerprint includes all pins and generated bins. `sequences.distances` in a
functional plan enables retirement-order pair bins. These additions do not
change the C2 trace format. `rvw.isa-diff/1` reports proposal changes and an
explicit `adoption_required` flag. It does not adopt specifications.

### Proof dependency report: `rvw.proof-cones/1`

`rvw cov prove` writes `proof-cones.json` beside `exclusions.json`. The latter also
embeds this report in `proof_cones`. This is informational evidence. Applying
exclusions does not validate this report as a certificate. It changes no coverage
counts and supplies no mutation results.

| Field | Meaning |
|---|---|
| `schema` | `rvw.proof-cones/1` |
| `source_snapshot` | The parent proof's frozen source snapshot reference |
| `top` | Flattened Yosys top module |
| `logic[]` | Cell `id`, elaborated `name`, Yosys `type`, optional `source` |
| `properties[]` | One row per reviewed plan point, in plan order |
| `outside_proven_cones[]` | Logic cell IDs outside all resolved, proven structural cones |
| `untested_assumptions[]` | Assumption cell ID, name, source and `status: not_tested` |
| `limits` | Explicit evidence limits |

Each property row has `property_id`, `point_id`, `requirement_ids`, `expression`,
`proof_status`, `proof_job`, `activation`, `proof_core` and `cone`.
`property_id` defaults to the stable plan `point_id`. Optional `requirement_ids`
are nonempty strings. Duplicate property IDs refuse the plan. Requirement IDs and
property IDs are join keys for external requirement obligations and activation
records. This report does not assert that an obligation is complete.

`proof_status` is `proven_conditional` only for an unbounded proof job with PASS,
exit 0 and no reported free wires. Otherwise it is `not_proven`. `proof_job`
retains the parent's local job paths and hashes, or is null. All proof assumptions
and all parent exclusion guards still apply. Activation is `{"status":"not_measured"}`
unless a separate declared activation cover runs, as specified below.
The solver does not export a proof core in this flow. `proof_core` has
`status: unavailable`, `cells: null` and a reason. Null is not an empty proof core.

`cone` has `status`, `cells` and `problems`. A resolved cone has status
`structural_overapproximation`. Missing names, netlists or unsupported cells give
`inconclusive`; such a cone contributes no reached logic to the union.
Fan-in traverses every input of each driver cell, including sequential feedback,
clock and reset. Whole buses are traced even for a selected bit. Constants end a
path. Constraints from assumption cells are not added to the cone.
Cell IDs are SHA-256 of snapshot hash, NUL, top, NUL and elaborated cell name.
They join rows within a frozen snapshot. They do not promise stability across
changed elaborations. Formal cells are excluded from the logic universe.

Logic outside these cones remains unverified by these expressions. It is not
proven irrelevant. The assumption list does not measure assumption activation,
necessity or adequacy. A cone is not a minimal solver proof core. Its size is not
functional coverage. Keep this evidence separate from MCY killed/survived results.

### Coverage mapping denominator fields

`rvw.coverage-report/1` adds `scala_mapping` with `mapped`, `denominator`
and `unit`. Each instrumented point counts once in that denominator.
`instance_scope` maps recorded hierarchy strings to `scope`,
`instrumented_points` and `exact_instance_denominator`. A wildcard gives
`scope: aggregate` and a null exact denominator. Missing hierarchy gives
`scope: unknown` and null. Literal hierarchy gives `scope: instance`.
No report expands aggregate counts into inferred physical instances.


### Typed RTL sampling coverage

`rvw.rtl-plan/1`, `rvw.rtl-samples/1` and `rvw.rtl-coverage/1` are the
project-defined RTL event sampling contract. See the coverage README for all
fields and refusal rules. Plan identity is SHA-256 over sorted compact JSON.
Every trace binds that identity and the design identity. Only unsigned integer
values sampled before a rising edge with disable-clear reset are supported.
Exact instance paths and an explicit bin universe define the denominator.
Incomplete traces give inconclusive results. Unobserved is not unreachable.
C2 retirement events and speculative RTL events remain separate domains.


The RTL plan can also declare bounded first-match `sequences`. Every later
step gives an inclusive sample-delay range. Reports separate activation,
completion, expiry, reset cancellation and trace-end pending attempts. Reset
clears all attempts. Each input starts fresh temporal history. Unsupported
clocks, reset rules or delay semantics refuse the calculation. See the
coverage README for the full sequence contract and native example.

## Explicit project binders

`rvw.soc-compose/1` has `map` (relative to this file), `core` (`class` and
`bus`), positive `clock_hz`, `reset` (`sync_high` or `async_high`), and
`devices`. Devices map each region name to `type=ram|rom|project`. Project
binders also require a qualified Scala `class`. All profiles require
32 address bits and RV32. Bus and clock-domain extensions are specified below.

The generated `rvw.soc-composed/1` manifest records profile, memory dimensions,
clock/reset intent, bus paths, map/composition/ELF hashes and
`validation=generated_only`. This is generation metadata, not C1 evidence.

## Peripheral binders

Composition project binders can add `exports`, a list of IO member names to
export at the top, and `irq`, an interrupt-name to IO-member dictionary.
The default interrupt member is `irq`. `soc_peripheral` returns `region` in
the existing map format and `binder` for the composition file. This metadata
covers register addresses. It does not describe every dynamic device effect.

## RV32 stub example runner

The project under `SpinalSoc/examples/stub` supplies C1 build, identity, run
and serialized run-many. It supports fixed APB word latency only. C1 results
report the bounded instruction profile and the scheduled PLIC source event.
UART hello checks use actual TX pin samples. These fixture results do not
qualify an ISA or provide C2 retirement traces.

## Implementation handoff bundle

`rvw.soc-handoff/1` records the captured database hash, design metadata,
source-to-bundle file records with hashes, unresolved blackboxes, SDC findings
and validation scope. `files.f` uses bundle-relative RTL paths. JSON inventories
preserve database columns for clocks, frequencies, memories, ports, hierarchy
and blackbox generics. The existing lint SDC backend generates constraints.
Export does not establish constraint completeness or implementation readiness.

## Imported implementation feedback

`rvw.soc-feedback/1` binds an external tool, analysis scope, constraint list,
report paths and typed findings to an exact database hash. Output schema
`rvw.soc-feedback-links/1` retains report hashes, matched RTL/Scala links,
unmatched diagnostics and `status=imported_claims`. It never reports a
workstation timing, area, CDC or DFT pass from external claims.

## Memory BIST requirements

`rvw.soc-mbist/1` binds declared dimensions, one-bit test enable, functional
control value, repair signals and isolation declarations to database memories.
`rvw.soc-mbist-handoff/1` exports dimensions, ports, clock/reset records and
unrun isolation obligations. Status remains inconclusive. Dimension and
endpoint consistency do not establish functional isolation or BIST coverage.

## SoC audit

`rvw.soc-audit/1` records exact map decode intervals, unmapped error windows,
complete APB endpoint bindings, formal connectivity results and the lint
clock/reset inventory. Map interval arithmetic is separate from RTL decode
proof. Emitted APB/decode assertions and structural IRQ paths do not earn a
proof result. Missing fabric endpoints are errors. The audit remains inconclusive.

## Composition fragments

`rvw.soc-compose/1` can include `fragments`. Each file can set core, clock,
reset and region binders. Paths are relative to the composition file. Merge
order is the listed order, then the main file. Device binders replace by
region name. Nested fragments and fragment map changes are refused.
`rvw.soc-composed/1` adds fragment hashes and the effective configuration.

## Composed software exports and scaffold

Composition adds `board.dts`, a CPU/memory/peripheral description for known
profiles, and `link.ld` when executable and writable memory exist. The linker
script includes `memory.ld`. Startup code and driver policy remain project-owned.
`registers.ipxact.xml` uses the existing strict register memoryMap subset.
`registers.svd` retains the existing CMSIS-SVD subset. Neither is a lossless
full SoC interchange model. Scaffold output references the installed SpinalSoc
source path and contains an explicitly idle project core wrapper.

## Composition bus ingress and domains

`rvw.soc-compose/1` accepts `core.bus` values `apb3`, `axi4`, `axi4-lite`
and `tilelink`. Existing APB3 compositions retain word-only behavior.
The other ingress profiles preserve byte strobes for memory and reject
partial writes to legacy APB3 project peripherals before selection.
`domains` is an optional dictionary. Each entry has `clock_hz` and `reset`
with the same value rules as the root clock. A binder's optional `domain`
selects that domain. The generated top exports `<name>_clk` and
`<name>_reset`. Both source and destination resets must assert together.
The manifest records domains and names the ingress profile. A generated
manifest remains `generated_only`; it is not simulation or proof evidence.
