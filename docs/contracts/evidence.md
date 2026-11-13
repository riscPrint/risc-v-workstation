# Cross-tool evidence contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Cross-tool evidence queries

`rvw.evidence-query/1` retains full recorded observations and their source path,
SHA-256, schema and validation scope. Queries recheck originals and explicit
`evidence_dependencies` path/hash links. Missing, changed or invalid evidence
has inconclusive integrity. Recorded status is never replaced with an inferred
accept. JSON-only validation is distinct from C1/C3/C4 schema validation.
