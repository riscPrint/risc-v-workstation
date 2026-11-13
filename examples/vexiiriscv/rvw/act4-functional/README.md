# ACT4 and riscv-tests functional coverage

These reports use `rvw cov functional` on native C2 traces from 2026-11-13.
The coverage plan is the command's default plan. Coverage includes boot,
test code and signature checks. Failed prefixes remain in `merged.json`.
This is not a certification result or isolated test body coverage.

Each profile has these files:

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

## Profiles

`machine` merges 58 ACT4 traces with 49 riscv-tests traces: 107 observed
and 107 qualified. The ACT4 instruction profile uses a reduced boot and
does not qualify Sm compatibility.

`supervisor` merges 270 standard-bootstrap ACT4 traces with 49 riscv-tests
traces: 319 observed and 49 qualified. All 270 ACT4 cases fail on the
mhpmevent3 bootstrap write. None reaches `rvtest_code_begin` or retires an
instruction in the symbol-delimited test body. Coverage from those
prefixes does not qualify supervisor behavior. See `../act4-supervisor`
for the complete failures and strict first-difference comparisons.
