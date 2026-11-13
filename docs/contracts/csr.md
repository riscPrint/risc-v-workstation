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
