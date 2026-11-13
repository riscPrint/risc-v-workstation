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
