# ACT4 and riscv-tests functional coverage

These reports use `rvw cov functional` on native C2 traces from 2026-11-13.
The coverage plan is the command's default plan. Coverage includes boot,
test code and signature checks. Failed prefixes remain in `merged.json`.
This is not a certification result or isolated test body coverage.

Regeneration produces these external files for each profile:

- `act4.json`: all ACT4 traces, including failed cases.
- `riscv-tests.json`: all 49 riscv-tests traces.
- `merged.json`: the command's merge of the two saved reports.
- `qualified.json`: only C1 passes with complete strict Spike matches.
- `corpus.json`: source pins, C1 status, ELF and raw C2 SHA-256 hashes.
- `holes.md`: all holes in the default finite domains for both streams.

Paths are rebased for publication. Raw source hashes are unchanged. The
merge captures the published source report hashes. The analysis checks
unique trace hashes, exact trace membership, summed instruction records
and all merged bin counts. Raw traces remain external build artifacts.

Run this procedure with the actual C2 paths from the C1 result records:

```sh
rvw cov functional ACT4_TRACE_PATHS --platform PLATFORM --json > act4.json
rvw cov functional ISA_TRACE_PATHS --platform PLATFORM --json > riscv-tests.json
rvw cov functional act4.json riscv-tests.json --platform PLATFORM --json > merged.json
```

Replace the uppercase terms with paths. Keep one XLEN/ISA context per
report. Use the project's platform to select the RVFI memory address
convention. Do not scan captured input fixtures or count both a sealed
result generation and its current view.

The qualified stream removes failed or incomplete reference checks from
qualification. It does not waive their failures. The observed stream and
corpus retain them. Groups without fixed bins measure observations and
have no completeness percentage. Default finite domains include modes,
classes and memory widths that a profile might not implement. Holes are
not automatically core defects. Unknown encodings remain visible.

## Machine profile

`machine` merges 58 ACT4 traces with 49 riscv-tests traces: 107 observed.
Only the 52 passing ACT4 tests qualify. Six ACT4 Zicsr cases fail on MEPC
alignment bits. All 49 riscv-tests C1 runs pass, but their stock reset stub
has a strict initial CSR snapshot difference. They do not qualify under
the stricter zero-synchronization policy used here. See the ACT4
observations and minimal reproductions in `../act4`.

Run-output JSON files with `summary_only` contain historical counts only.
They are not inputs to `rvw plan`, `rvw evidence`, or coverage merging.
Regenerate full records outside the repository before using those tools.

Historical `machine/corpus.json`: {"core":"vexriscv","date":"2026-11-13","observed_traces":107,"path_policy":"paths rebased for publication; source hashes identify original bytes","profile":"machine","qualified_traces":52,"raw_trace_hashes":true,"scope":"whole C2 execution including boot and signature checks; failed prefixes remain in merged.json; not test-body coverage","verification":"unique C2 content; exact SHA membership; summed retired records and all bin counts checked"}.
Raw records are no longer tracked. Regenerate outside the repository:
`rvw cov functional TRACE_PATHS --platform PLATFORM --json`. Use the pinned inputs and options from [PR #1153](https://github.com/riscPrint/risc-v-workstation/pull/1153).

Historical `machine/merged.json`: {"groups":{"entries":10},"notes":{"records":8},"retired":184292,"traces":{"entries":107},"unknown_encodings":{"entries":0}}.
Raw records are no longer tracked. Regenerate outside the repository:
`rvw cov functional TRACE_PATHS --platform PLATFORM --json`. Use the pinned inputs and options from [PR #1153](https://github.com/riscPrint/risc-v-workstation/pull/1153).

Historical `machine/qualified.json`: {"groups":{"entries":10},"notes":{"records":8},"retired":160420,"traces":{"entries":52},"unknown_encodings":{"entries":0}}.
Raw records are no longer tracked. Regenerate outside the repository:
`rvw cov functional TRACE_PATHS --platform PLATFORM --json`. Use the pinned inputs and options from [PR #1153](https://github.com/riscPrint/risc-v-workstation/pull/1153).
