# Cross-tool evidence contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Cross-tool evidence queries

`rvw.evidence-query/1` retains full recorded observations and their source path,
SHA-256, schema and validation scope. Queries recheck originals and explicit
`evidence_dependencies` path/hash links. Missing, changed or invalid evidence
has inconclusive integrity. Recorded status is never replaced with an inferred
accept. JSON-only validation is distinct from C1/C3/C4 schema validation.

## Verdict ownership across evidence layers

| Layer | Owned result | Verification boundary |
|---|---|---|
| Evidence producer | Scoped test, comparison or proof verdict | Keep its assumptions, configuration and evidence limits. |
| C4 gate | Acceptance of a committed revision | Only the gate grants `accept`. |
| `rvw evidence` | Report index, hashes and integrity | Preserve producer verdicts. Indexing does not verify a design. |
| `rvw plan` | Project links, holes, counts and verdict bound | Aggregate selected evidence. Do not grant C4 acceptance. |
| Farm workflow plan | Dependency order and execution state | `complete` means execution completion. Verification stays `inconclusive`. |
| `rvw agent guide` | Calls and decisions | Advice and workflow membership grant no verification verdict. |

## Conservative aggregation

`weakest_verdict` uses the C7 vocabulary. Only a nonempty set of `pass` inputs
can yield `pass`. Empty input yields `no_checks`. An unknown verdict yields
`inconclusive`. A conclusive failure stays `fail`. Other blockers have this
stable precedence: `error`, `not_installed`, `unsupported`, `inconclusive`,
`no_checks`. None counts as pass.

Plan entries, features and the overall report carry an additive `verdict` field.
Explicit producer blockers stop recorded closure. Invalid evidence, unresolved
holes and unassigned requirements cap the verdict at `inconclusive` unless a
conclusive failure is already known. C1 and C3 checks retain their typed
inconclusive rules. Formal summaries must agree with each selected child.
Coverage counts without a producer verdict do not create verification pass.
`reported_closed` remains a planning count. It does not grant verification or acceptance.
The evidence index keeps `recorded_status` and reports integrity separately.
Its query verdict remains `not_inferred`.
