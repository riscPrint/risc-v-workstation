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
