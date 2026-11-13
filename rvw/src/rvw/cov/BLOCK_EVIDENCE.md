# Reusable block evidence

`rvw cov block-check --evidence evidence.json --integration integration.json --json`
checks declared reuse conditions. `cov_block_check` uses the same API.

An `rvw.block-evidence/1` file has a `sources` object. Each logical source name
maps to a `path` and `sha256`. Paths are relative to the evidence file.
`configurations` is a list of exact tested configurations. Each entry has
`parameters`, `assumptions` and `runs`. Parameters and assumptions are objects.
Each run has a `path` to its C1 result JSON and that file's `sha256`.

An `rvw.block-integration/1` file has `sources`, `parameters` and `environment`.
Its source object maps the same logical names to current source paths.
Each tested assumption must equal the integration's declared environment value.
Only exact tested parameters transfer. A parameter domain claim is insufficient.

Each conclusive passing C1 record must have a `details.block_evidence` receipt.
The receipt contains `source_id`, `parameters` and `assumptions`. Source ID is
SHA-256 of the compact sorted JSON mapping logical source names to their hashes.
The receipt must match the selected evidence configuration. A missing receipt,
changed result or inconclusive C1 record cannot authorize reuse.

Status is `eligible_for_reuse`, `incompatible` or `inconclusive`. Eligibility
applies only to the declared block inputs and recorded tests. Declared inputs
do not prove complete transitive dependency capture. Assumption comparison is
static. Runtime enforcement remains unverified. `new_wiring_covered` is always
false. Integration wiring and new behavior need separate checks. Formal evidence
and physical qualification are outside this first interface.
