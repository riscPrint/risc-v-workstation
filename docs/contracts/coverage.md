# Coverage contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Coverage proof exclusions and test selection

Coverage proof exclusions use `rvw.coverage-exclusions/7`. The file records `config` and
`config_sha256`, `work_dir`, `timeout`, and an `elaboration` snapshot with `path` and `sha256`,
in addition to input resolution records and solver jobs. Apply binds every excluded point to
its reviewed plan mapping, generated property, SBY job and recomputed cone cover. It requires
a passing single-clock guard and synchronous state controls. Apply rechecks every module of the
saved raw netlist. Asynchronous reset/set/clear/load controls, latches and unsupported state
cells refuse exclusions. Memory asynchronous resets must be tied inactive. Older exclusion
schemas, including `/6`, require a proof rerun. `source_snapshot` records the path and hash of
one manifest captured before any front end runs. The manifest binds original source and include
resolution records, raw copies and frozen RTL with redirected literal includes. The guard and
every sanity, cover, proof and cone job read this snapshot. Each job and point records its
`snapshot_sha256`; each front end records `input_hashes`, including its actual RTL and harness
copies. Apply checks these copies against the snapshot and rebuilds generated job text from it.
Missing, changed or mixed snapshot evidence refuses exclusions. The files are local
evidence; they are not signed certificates. See `rvw/src/rvw/cov/README.md` for the proof limits.

Coverage test selection (`rvw.coverage-select/1`) keeps the requested range in `diff` and records
the full compared commit IDs in `base_revision` and `head_revision`. Each distinct ref is resolved
once. Both Git diffs use those IDs. Different refs are resolved in sequence; this does not claim
an atomic snapshot of all refs. Later branch moves do not change the recorded selection.

## Archived stimulus replay

`rvw cov campaign --replay N` and the `cov_campaign` replay argument verify
sealed campaign inputs and attempt evidence. They then run the archived ELF
through C1, strict Spike qualification and payload sampling in a fresh result
directory. `rvw.stimulus-replay/1` records the attempt, current and expected
execution identities, comparison/coverage evidence, costs and raw archive
generation. Old working output copies are not replay inputs.
`credited_new_hits` is always empty. Replay does not change the
campaign state or original hit set.

A qualified replay requires matching execution identity. Missing or changed
identity is inconclusive. Failed runs on a changed model do not prove failure
reproduction in the original context. Attempts without an ELF are unsupported.
Cross-host replay and complete cost qualification remain unverified.

## Code and RTL stimulus feedback

`rvw.stimulus-loop/1` accepts either `rtl_plan` or `code_plan`, paired with
`recipes`. `rvw.code-goals/1` binds generated RTL `design`, a `database` path,
and its `database_sha256`. Paths are relative to the code plan. The database is
an existing `rvw.coverage/1` native point template with resolved source hashes.
Optional `targets` selects unique template point IDs. Template counts earn no
feedback credit. The template is captured before initial state publication.

Code recipes use `rvw.event-recipes/1` with the exact code plan hash and design.
Accepted feedback requires complete C1/Spike qualification and a C1 `coverage`
artifact. `details.coverage_goals` must contain exactly `elf_sha256`,
`rvfi_sha256`, `samples_sha256`, `plan_id`, `rtl_sha256` and
`reset_at_start: true`. All hashes must match. Native point universe, keys,
fields and source hashes must match the template. Project adapters own counter
collection and reset. Unsupported adapters earn no credit.

`guidance_coverage` keeps `declared_bins`, `full_input_bins`, `observed`,
`unobserved` and `unsupported_targets` separate from ISA hit totals. RTL feedback
also retains `uncompleted_sequences` and `last_sample_pending`. A target subset
does not reduce the reported full input denominator. `generation_profile_bins`
counts potential generator goals. `generation_groups` records declared and
supported counts per ISA/sequence group. Generation support is the intersection
of the candidate profile and declared semantic plan. No native qualification or
comparative closure rate follows from these controller reports.

## GHDL source line navigation

The native-point mapper accepts a GHDL `/* path.vhd:line:column */` locator
immediately before an `assign`, `wire`, `reg` or `always` statement. A blank
line or unrelated statement breaks this pair. It does not search backward
for the nearest locator. `.vhdl` paths are also accepted.

The existing `scala` point field and `scala_line_metrics` report key retain
their names for compatibility. These source links can also name VHDL files.
Each line group retains the native metric and point denominator. A source
link does not establish that an individual original-language statement ran.
Stripped models need explicit maps. Missing locations remain unmapped.

## Functional run qualification

Functional reports use `qualification_policy: c1-pass-complete-c2-v1`.
Only a conclusive C1 pass with its bound, complete passing C2 trace earns
`groups` hits. The ELF identity and retirement count must agree.
The reader finds `result.json` beside the trace. Library callers can give
`run_results`, a map from absolute trace paths to C1 result paths.
Other observations appear in `unqualified` and never close bins.
Each trace records its qualification and end status. Merge refuses reports
without the qualification policy. Closure uses only qualified `groups`.


## Exported RTL mutation campaigns

`rvw.core-mutation/1` stores the hashed plan, baseline, mutant outcomes and first
killer. The project manifest and test receipts use
`rvw.core-mutation-project/1` and `rvw.mutation-test/1`.
See [the campaign contract](../../rvw/src/rvw/cov/CORE_MUTATION.md).
Build failures are invalid. They never earn kills. Strict passing controls are
required. Only unconditional formal equivalence earns proved equivalence.

## Mutation detection regression

`rvw.mutation-expectations/1` binds the exported RTL and exact mutation list by
`mutant_set_sha256`. Test inputs can change in a newly prepared plan.
`rvw.mutation-regression/1` reports each expected first killer as detected, lost,
changed or inconclusive. A passing unmutated control and every expected killer
are required. This is a slow execution tier. Saved detection results cannot
pass it without rerunning the campaign.

## Scalar FP crosses

`rvw cov fp` and MCP `cov_fp` write `rvw.fp-coverage/2`. They require C2/2
state on a complete passing DUT trace bound to a conclusive C1 pass. They
reuse the functional coverage qualifier. Reference-only traces get no hits.

A full bin is instruction mnemonic, RM, source position, operand class and
raised-flag mask. The report covers scalar F/D/C forms with the shared ISA
decoder. Each trace starts a fresh FP register history. Integer-to-FP source
class is `not_fp`. Loads classify loaded data. Unrounded forms use prior frm
as context. Computational S operands obey NaN boxing when FLEN is 64.

Prior nonzero fflags cannot establish all flags raised by the next operation.
Those operations get no full cross hit. Unknown inputs and RM also get no hit.
The class projection removes the flag dimension. All 32 flag masks remain in
the domain. No unreachable mask or operand tuple coverage is implied.
Bin hits establish execution, not arithmetic correctness or whole-FPU closure.
