# CSR and register maps contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## SpinalChecks normalized register map (version 1)

`SpinalChecks/scripts/import-map.py` writes Java properties. `version=1` is
required. `registers` lists unique comma-separated register names. Each name has
`address`, `width`, `reset`, `writeMask`, `w1cMask` and `readClearMask` properties.
Values are nonnegative decimal integers. Addresses use bytes. Masks and reset
must fit width. Ordinary-write and W1C masks must be disjoint. Register byte spans
must not overlap. Missing required fields fail loading. This format declares
register intent. It does not provide independent bus observations or a verdict.

### C1 native semantic requirements

## Project CSR generation

### Native event and device binding examples

The optional VexRiscv HPM binding observes real CSR storage and independent
clock/last-stage events. It declares masked RV32 counter-half writes. Generic
`HpmChecks.bind` applies increments before selected write-mask bits. Unselected
bits retain the increment result. The GPIO example selects actual library IP
APB direction accesses. Neither example grants full architectural, peripheral
or physical-device qualification.

#### Project check generation

`rvw.check-generation/1` selects relative input files for streams, buses, csrs,
queues and power. `rvw checks generate --all` writes
`rvw.check-generation-summary/1`, with per-kind status, reasons, instance rows
and output paths. Status `generated` means at least one bound generator result.
`complete` requires every kind and instance to be generated. Unbound emitted
sources do not count. This is generation evidence, not a proof verdict.
`rvw.micro-checks/1` declares a top target and rules with id, kind, width, entries,
ports and optional bounded arbiter fairness. `rvw.micro-generation/1` retains
per-rule generated/unsupported status. Port mappings remain project declarations.

#### CSR storage without a reset initializer

A CSR row can set `reset_known=false`. The default is true. Unknown reset
requires full-width ordinary M-mode RW fields. Partial writes, read-clear,
W1C and read-only registers are refused for this mode. State and read-data
checks start after the first accepted full write. Access checks remain active.
`reset` supplies the software initialization value in this mode. It does not
claim a DUT reset value. Generated safe assembly writes this value before its
first comparison. Scala `CsrModel.resetKnown` has the same restriction.

`rvw.csr/1` describes CSR addresses, project reset values, privilege, presence,
field ranges, per-privilege access, legal values, legalization tables and bounded
side effects. See `SpinalChecks/csr/README.md` for the exact transaction binding.
`rvw formal csr` and `formal_csr` emit `rvw.csr-generation/1` with status
`generated`. This status records artifact generation only. It is not C7 proof
or C1 execution evidence. `coverage.json` uses existing functional group data.

## Paired register hardware updates

Paired SoC register observations accept optional full-width expanded bit masks:
`write_mask`, `hw_clear`, and `hw_set`. Their defaults are all write bits, zero,
and zero. Hardware clear follows software effects; hardware set has final
priority. Failed bus accesses suppress software effects, but not hardware events.
These fields describe independently observed events over the transaction interval.

## Concurrent register event observations

`rvw.device-events/1` declares accepted-request linearization and a cycle-ordered
event array. Array order resolves events at the same cycle. Requests and responses
use `(master,id)` keys. Hardware increments, clear/set masks and state observations
are independent events. The SoC map supplies reset, access and side-effect rules.
`rvw.device-event-check/1` records comparisons and outstanding keys. Mismatch is
exit 1. Matching or incomplete observations remain inconclusive with exit 3.
This does not establish capture completeness or a real-device binding.

## Standard CSR catalog selection

`rvw.csr-catalog/1` stores pinned UDB definitions, source paths, source hashes
and notices. IDL expressions and extension conditions remain data.
`rvw.csr-selection/1` selects named CSRs and fields with project reset, access,
legalization and side-effect overrides. It resolves field positions to
`rvw.csr/1` before the existing generator runs. Unsupported alias, hypervisor
and debug execution models are errors. Selection is not compliance evidence.

## AIA field-layout supplement

`rvw.csr-catalog/1` retains the base UDB revision and can expose a `supplements`
list with independently pinned sources. Supplemental rows retain their own
revision, source hashes and license notices. The AIA supplement fills the
26 recorded layout gaps without changing the base UDB data. Definition flag
`requires_environment_model` prevents simple CSR selection from discarding
interrupt-controller side effects. Field availability does not establish
behavioral or privilege coverage.


## Shared CSR bank model

`rvw.csr-bank/1` declares canonical banks, static addressable views, supported
M/S/U modes, optional setup and directed sequences. Each view names a bank,
bit shift, readable mask and explicit writable mask. Catalog selections provide
address and minimum privilege only. They do not infer dynamic semantics.
Independent hardware clear/set inputs apply to canonical state every cycle.
The existing `formal csr` CLI/MCP emits `rvw.csr-generation/1`, canonical-bank
RTL, directed assembly, coverage groups and optional wrapper SBY files.
Conditional aliases, dynamic state enables and WARL/WLRL are outside this model.
Generation is not proof or architectural acceptance.


## Bound entries in project check generation

`rvw.check-generation/1` permits a `streams` object with database, report and
optional contracts paths. Channel ports, widths and clock/reset controls resolve
through the captured database. Streams need an explicit stable contract; Flows
need explicit value bounds. `rvw.stream-generation/1` records per-instance
bindings, failures and capture provenance. No stream policy is guessed.
A `power` object with source and bindings paths invokes literal UPF generation.
Legacy source-file entries retain unbound status without instance bindings.
The combined summary does not upgrade generation to proof or physical evidence.

## Generated AXI transaction bindings

`rvw.bus-checks/1` instance rows can set `coverage=transaction_safety`,
`tracker_depth`, `write_history_beats` and `check_groups`. These declare
independent pending transaction state, per-ID read order and write burst
pairing. AXI4 WSTRB history is checked against paired AW geometry.
Queue and history exhaustion are instrumentation bounds, not protocol
violations. Incomplete transaction fields leave `unbound_checks` reasons
and retain channel safety only. TileLink rows retain opcode safety only.
Memory data and exclusive reservation state are outside these trackers.
Project `buses` entries accept `database`, `depth` and `max_beats`. Both
limits are positive integers. Maximum values are 64 and 256 respectively.
Generation does not run a compiler or solver.

## Exact TileLink type inventory

`rvw.checks/1` can include `buses` rows with component `path`, local `object`,
qualified `class_name`, local RTL `signals` and integer library `options`.
TileLink options retain `size_max`, `data_width`, `source_width`, `sink_width`
and `with_bce`. These rows record elaborated library objects.
`formal buses --type-report` and the project bus entry `type_report` resolve
an ambiguous database `Bus` only when top, component path and the full live
signal-name set match exactly one inventory row. Missing or duplicate matches
remain unsupported. The type report does not establish capture equivalence
or protocol correctness.

## TileLink transaction safety profile

A generated bus row can set `protocol_profile=tilelink-uh-probe-c`,
`coverage=transaction_safety`, `probe_tracker_depth` and `check_groups`.
A/D source state is independent of DUT storage. Accepted beats start bursts.
Headers stay fixed inside a burst. A stalled beat inside a burst retains
valid and payload. Unaccepted first offers can change.
The profile checks Get, Put, ArithmeticData, LogicalData and Hint matching.
Coherent channels add Acquire/Grant, Release/ReleaseAck, GrantAck sinks and
Probe/ProbeAck pairs. Probe keys contain source and address. Capacity is
an instrumentation bound. Coherent B supports probes only. Negotiated
address regions, operation capabilities, cache permissions, data state and
forward progress are outside the profile. Zero-width source and sink fields
require exact library options from a matching type inventory.

## Native CSR example run reports

The VexRiscv optional CSR/HPM execution example uses `rvw.checks-run/1`.
It adds `elf`, `elf_sha256`, `observation_fault`, `cycles` and `retired` metadata.
`observation_fault` is `none`, `csr`, `hpm` or `hpm_read`. Seeded observation failures keep
run status `fail`. The fixture process can exit successfully only after the
expected firing is observed. This is test-fixture completion, not a core pass.

## Project resource bindings and incomplete summaries

`rvw.micro-checks/1` rules also accept `allocation_pool`,
`freelist_conservation`, `rob`, `credit`, `freelist`, `cam_match` and
`counter_bounds`. Port names are listed in the checks README. Resource
ownership rules accept a literal `initial_live` bitmap.
`freelist_conservation` also accepts `usable`. The two bitmaps fit `entries`,
and initial ownership must be a subset of usable tags. Free and live bitmaps
partition usable tags. Independent accepted allocation and release events
update expected live ownership. Recovery events remain project declarations.
`rvw.check-generation-summary/1` includes an `unbound` list with kind, optional
instance/check and reason. Per-instance `unbound_checks` prevent `complete`,
even when the instance's channel monitor was generated. This is binding
completeness, not a verification verdict.

## Independent HPM read expectations

`HpmChecks.track` supplies the independent expected counter used by `bind`.
It returns that state for separate response checks. Existing `bind` calls
retain their Unit result. The optional Vex binding compares accepted machine
and user-alias half reads against this expected state. Read observations do
not initialize or update expected state. Native example clean runs require
nine inserted monitors. Seeded `hpm_read` runs retain fail status.

## AXI response precedence

AXI transaction checks require an earlier accepted AR before RVALID.
BVALID requires AW and the complete W packet to have been accepted on
earlier sampling edges. Current-edge request handshakes do not authorize
a current-edge response. This applies to AXI4 and AXI4-Lite. Internal
AW/W pairing can still use current accepted inputs. W can precede AW.
This follows the read and write dependency rules in Arm IHI 0022H.
TileLink's separate same-cycle response rules are unchanged.

## Queue flush and age-selected forwarding

Project microarchitecture kinds include `fifo_flush` and `store_forward_age`.
FIFO flush has priority over current-edge push/pop and clears expected queue
ownership. Data before the flush cannot be popped afterward.
Age-selected forwarding takes the existing eligibility masks and a packed
`older_than` matrix. Bit `i*entries+j` means `i` is older than `j`. A load
selects the unique eligible entry with no younger eligible peer. Nonempty
eligibility with no candidate or multiple candidates fails. The project
must supply actual age observations; slot indices do not define age.
Each data unit can be one byte. Projects can instantiate separate units for
byte merging. These rules do not infer speculation, fence or recovery state.

## Explicit bus clock declarations

`formal buses --clocks FILE` and the project `buses.clocks` entry accept
`rvw.bus-clocks/1`. Its `instances` object maps full captured bus paths to
objects with exactly `clock` and `reset` signal paths. Each pair must match
one captured clock domain. A declaration cannot replace a conflicting signal
clock domain. Unknown bus paths remain unsupported in the per-instance report.
The generator does not infer a clock from bus signal names.

Bus rows record `instance_path`, `clock_source`, `clock_domain_id`,
`target_instance` and `bind_scope`. A module used once in the captured design
uses a module bind. A repeated module uses an instance bind so each bus keeps
its own declared controls. These are generation results, not native test results.

## CDC generation inputs

The optional `cdc` entry of `rvw.check-generation/1` has a `report` path.
It selects structural lint CDC obligations with supported checker kinds and
signal bindings. The summary retains unsupported and unbound obligations.
Emission supplies no simulation or proof result.

## Connected check qualification summary

`rvw.check-qualification/1` records per-kind generated, bound, proven, bounded,
fired and unbound counts. `firing_count` sums runtime monitor observations.
Runtime checks reference the same inventory path and matching ELF hash as C1.
The C1 artifacts are `inventory` and `checks`. Missing execution evidence has
null counts. Distinct fired check IDs count once across programs. Unbound
entries retain their status and reason. Formal regress `requirements` hold
explicit bound check IDs. All properties associated with one check must succeed. All-proven groups
count as proven. Mixed proven and bounded-pass groups count as bounded.
The summary remains inconclusive without a runtime finding. It certifies
neither activation nor the closure of inputs.

## Optional VexiiRiscv CSR transaction binding

The VexiiRiscv example selects `mscratch` and absent `sscratch` in versioned
project data. Its native runtime validates a normalized RV32 machine scratch
model with unknown reset and a full-width writable field. It checks accepted
reads against independent last-write tracking. It does not model whole CSR RAM
state or all instruction decoding. Runtime reports use `rvw.checks-run/1` and
retain fail status for a seeded read-observation fault. The default adapter
keeps this instrumentation off.

## Generated stream cancellation metadata

In `rvw.checks/1`, stream check `detail` states whether cancellation was
recognised from the elaborated library assignments. `signals.cancel` is the
one-bit effective condition at the check sample. For a registered valid clear,
this is the previous sample's clear guard. For a combinational gate, this is
the current sample's gate condition. Unclassified streams retain strict checks
and a disposition hint. These optional metadata fields do not imply a waiver,
a successful simulation, or proof. The database port-binding generator still
requires its own reviewed stable contract.

`ChecksConfig.streamCancellations` supplies reviewed project bindings for custom
logic. A binding has an exact `path`, a local driven Bool `condition`, a Boolean
`previous` sample selector and a nonempty `reason`. The report identifies these
as reviewed bindings, separately from automatic recognition. Missing paths,
missing conditions and duplicate bindings are elaboration errors. No binding
removes a check or suppresses a failure when its condition is false.

## Connected example captures

The optional `RVW_CHECKS_ISA=1` paths in the VexRiscv and VexiiRiscv CSR runtimes
write C1 with `artifacts.inventory` and `artifacts.checks`. The SoC stub adapter
uses the same artifact roles. A firing retains a C1 failure. The SoC adapter
reports an error when requested check observations are missing. Formal capture
uses `RVW_CHECKS_FORMAL=1` and emits formal-mode RTL without simulation records.
A selected formal job names the exact generated check ID in `requirements`.
A depth-4 bounded pass does not imply activation or an unbounded proof. Native
and formal inventories are separate captures with matching requirement IDs.

## Generated check dispositions

`rvw.check-dispositions/1` has `inventory_sha256` and an `entries` list. Each
entry has an exact check `id`, a `disposition`, a nonempty `reason` and `owner`,
and `expires` as the last valid UTC date in YYYY-MM-DD form. Dispositions are
`waived`, `tool_false_positive`, `design_finding` and `needs_review`.

An expired entry, inventory hash change, absent or duplicate ID, or a check
that no longer fires in supplied C1 evidence is an error. Without run evidence,
`matched` and `stale` stay null. The optional `dispositions` and
`disposition_status` fields in `rvw.check-qualification/1` record the review.
Raw counts, C1 statuses and the findings verdict do not change. A needs_review
entry does not resolve an open finding. This metadata does not install native
waivers or certify source intent. The reason, owner, expiry and stale-state
policy is shared with lint settings version 2.

## Literal UPF command words

The existing UPF subset importer accepts literal quoted and flat braced words,
semicolon or newline command separators, backslash-newline continuation and
comments at command starts. Separators inside a grouped word stay literal.
Substitutions, nested braced lists and other backslash escapes remain errors.
Each tokenized command still passes the supported UPF command and option checks.
No Tcl interpreter runs. The normalized UPF schema and monitor bindings do not
change. Clock-gate import and physical power behavior are not implied.

## Recovery check bindings

`RecoveryChecks.bind` emits `recovery.*` rules in the existing check inventory.
Bindings declare up to 32 slots with equal-width generation tags on allocation,
release, retirement and accepted device-effect events. Kill and fence masks
must come from independent project intent. Missing bindings are elaboration
errors. A slot stays owned until release, including after cancellation.

Fence start captures selected pre-edge generations. Allocations at that edge
are younger. Current-edge release or kill can drain a predecessor. Slot reuse
does not add its new generation to a previous fence. The default device-effect
policy requires retirement before or at the same edge; the check detail records
an explicit project override. These are sampled template obligations. They do
not infer branch age, architectural fence classes, data values or a core binding.

## Vexii static-bank transaction binding

The project `CsrChecksRuntime` accepts `rvw.csr-bank/1` as an alternative to
`rvw.csr/1`. Its bank binding requires RV32, one present unshifted M-mode view
per bank, and declared static masks. It observes accepted CSR interface reads
and writes. Physical storage can be a register or RAM. Expected values come
from declared reset and software transactions, not from observed DUT storage.
Trap events invalidate the mepc and mtval reference values until a software
write. This does not establish trap-update correctness or denied-access checks.
The trap-free project harness leaves the general CSR generator's trap-control
restriction unchanged. Reference configuration differences remain failures.
