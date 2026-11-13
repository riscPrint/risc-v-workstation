# Evidence index

`rvw evidence index --root RESULTS --db evidence.sqlite` indexes C1, C3, C4,
C5, formal, coverage and lint JSON reports. `rvw evidence query --db
evidence.sqlite --text CLAIM --schema rvw.formal` finds the exact recorded
observations. MCP tools are `evidence_index` and `evidence_query`.

Each match includes its path, captured SHA-256, schema, full observations,
configuration and assumptions when recorded. Query rechecks the original hash.
Missing and changed files weaken integrity to inconclusive. Indexing never
rewrites source reports. Reindexing updates snapshots without deleting missing
records. C1/C3/C4 use the shared schema validators. Other reports have JSON-only
validation, which is explicit in each match. This is discovery, not admission to
a regression generation. Original tool verdicts remain recorded observations.

A report can declare `evidence_dependencies` as objects with `path` and `sha256`.
Relative paths start at the report directory. Query checks these explicit joins.
Absent or changed dependencies weaken the claim. A tool must supply dependency
links; the index cannot discover unstated assumptions. The index never infers
an accept, proof or closure result. No matches means no_checks.

## Decisions and limits

Use one small SQLite index and preserve the original JSON. Text search covers
all recorded fields. Configuration and scope remain in the observations.
There is no automatic dependency extraction or vendor adapter. Formal, coverage
and lint semantic validation remains with those tools. Large-campaign latency
has not been measured. Queries can expose captured project data to their caller.

A native-history sample indexed 583 reports: 564 C1, 13 C3, three C4 and three
C5. One local build took 0.668 seconds. One full query took 0.137 seconds and
rechecked all 583 hashes unchanged. Changing a separate copied C1 after its
indexing made its integrity inconclusive while retaining its recorded pass.
These are local discovery checks, not semantic validation or scale limits.
See `examples/regression-scale/management-rollup.json`.
