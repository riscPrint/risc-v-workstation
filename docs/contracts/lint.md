# Lint and CDC/RDC contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Lint and crossing inventory extension

`rvw lint` reads `rvw.lint-settings/1` from `--settings` or the project
`[lint] settings` path. Paths resolve against the settings file. See the
[lint guide](../rvw/src/rvw/lint/README.md) for fields and scope.
`rvw.lint/1` records settings and RTL hashes, native output, backend states,
structural inventory, exact waivers and match counts. Each finding has a SHA-256
`id` of its diagnostic data, backend, top and configuration. Waivers require
this value as `finding_id`, plus exact rule, endpoint, configuration and reason.
Structural diagnostic data includes `source_domain` and `destination_domain`
(the full domain records), `source_width` and `destination_width`. Changed clock
or reset records and changed widths invalidate the waiver.
A different source or message cannot reuse the waiver. Waived findings remain in
place. Missing backends remain `not_run`. Exit 0 means completed checks without
findings; 1 means active findings; 2 means input error; 3 means inconclusive.
Structural analysis cannot produce signoff. Its unrun rule inventory is mandatory.
No C4 gate acceptance is implied.
Structural reports also retain `reset_trees` (control cones with unknown-control
states) and `reset_crossings` (source and destination domain IDs). Different
reset signatures are candidates even when clock identity matches. Reset release
and reconvergence remain in the unrun rule inventory.
The structural backend also has `rdc`: `status` (`findings`, `protected`,
`inconclusive`, `no_crossings_found`; never `clean`), `domains` (reset
signatures with source, kind, clocks, register count and `release`) and
`crossings` (`source`, `destination`, reset domain IDs, `class`, `status`, and
`protected_by`/`reason` for declared protection). Settings `intent.isolation`
rows declare qualifiers with reasons. `waiver_findings` holds a
`lint.stale_waiver` error for each waiver that matched nothing in a backend that
ran; each waiver records `stale` (`true`, `false`, or `null` when its backend
did not run).
The structural backend also has `cdc`: `clocks` (per clock domain `kind`
`primary|divided|gated|generated|unknown`, `source`, `master`, `divide_by`,
`enables`), `obligations`, `memories`, `clock_groups` and `hierarchy`
(findings per component path). `crossings[]` rows gain `kind`,
`relationship` (`related`, `asynchronous`, `declared_*`, `unknown`), `stages`,
`library` and `width`. Settings `intent.clocks` rows declare clock groups with
reasons. `rvw lint --emit DIR` writes `rvw.cdc-obligations/1`
(`cdc_obligations.json`: `obligations` with `kind` `gray_code|data_stable|toggle_stable`,
`bind` or `unbound_reason`; `checks`; `checked_rtl`; `unbound`), plus
`cdc_checks.sv` and `checked/` RTL copies. Emitted obligations are not results.
Lint settings may also have `rules` (rule severities and parameters) and
select backend `rules`, whose `findings` use `lint.*` rule IDs and whose `fsm`
list records `checked` or `inconclusive` state registers. `rvw lint --sarif PATH`
writes the same findings as SARIF 2.1.0 with fingerprint `rvw/finding-id`.
Backend `sdc` (settings `sdc`: `clocks`, `generated`, `multicycle`, `check`,
`register_pattern`, `output_pin`) returns `sdc` (generated text), `clocks`,
`spinal_synchronous`, `excepted`, `unsafe`, `check` and `sdc.*` findings.
`--emit` also writes `constraints.sdc`. SpinalDB adds table
`clock_frequencies(clock_domain_id, hz)` without a schema bump; a missing table
means unknown frequencies.

## Waiver review metadata

`rvw.lint-settings/2` uses the version-1 settings fields. Each exact waiver also
requires a nonempty `owner` and `expires` in YYYY-MM-DD form. Expiry is the last
valid UTC date. Expired metadata is an error before backend execution. The
existing exact finding hash and stale-waiver errors still apply. Shared policy
code also validates generated check dispositions. Version 1 keeps its legacy
waiver format and makes no owner or expiry claim.

## Generated source-scope assignments

The database rule backend keeps a generated signal with one full-width,
conditional assignment in `unresolved` when only source-scope condition evidence
is available. Spinal can hoist an expression temporary into unconditional RTL.
The database condition alone does not prove that the emitted RTL infers a latch.
Each unresolved row has `rule`, `endpoint`, and `reason`. The backend remains
`inconclusive` while any such row exists. Named partial assignments retain the
`lint.latch` finding. This does not certify the unresolved temporary as latch-free.

## Counted structural findings

Structural diagnostics group paths with the same rule, severity, effective
source and destination clock/reset signatures, and recognised library class.
`count` gives the number of paths. `members` retains each path's endpoints and
source locations. The top-level endpoint is the first member. Crossings remain
in the detailed CDC/RDC inventories. Grouping does not establish protection.
Waiver IDs change because the full diagnostic content changes.

## Conditional declaration scope

SpinalDB signal `tags` can include `spinaldb:conditionalDeclaration`. This
records a declaration inside a conditional source scope. It is extraction
metadata, not a user waiver or a proof. The latch rule records incomplete
assignments on these expressions as unresolved until lowered RTL is checked.
Imported HDL assignments with source `$dlatch` or `$adlatch` identify actual
level-sensitive storage and produce `lint.latch` findings.


## Generated RTL source advice

Native source-style advice on exact `rtl_files` paths from a database with
`spinalhdl` metadata is counted per rule and file at info severity. Findings
use the existing `count` and `members` fields. Raw native output remains.
The advice whitelist does not include truncation, undriven signals, missing
switch defaults or errors. Files without that database provenance retain the
native severity and individual diagnostics. Backend completion status does
not change. Content-bound waiver IDs change when the diagnostic is regrouped.
