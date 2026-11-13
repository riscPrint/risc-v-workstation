# Coverage counter exchange

`rvw cov exchange report.json --destination coverage.xml --format ucis --json`
exports the declared UCIS counter profile. `cov_exchange` uses the same API.
Use `--format import-ucis` to read that profile into `rvw.coverage-exchange/1` JSON.
Use `dat` or `lcov` to export a code coverage database. LCOV needs the native
`verilator_coverage` tool. It uses that tool's `--write-info` conversion.
DAT retains exact native counter keys. Each output has a `.rvw.json` sidecar.
The sidecar retains source identity, native metric kinds and exclusions.

## Declared UCIS subset

The XML uses the UCIS 1.0 namespace and hierarchy from the
[Accellera FC4SC schema](https://github.com/accellera-official/fc4sc/blob/31b9339a34a40975fea0bb92a0ef876a6624b857/ucis/UCIS.xsd).
The logical profile is `rvw-counter-profile/1`. Every transported counter is a
coverpoint with one singleton ordinal bin. Original values and native metric
kinds remain in `rvw.counter` metadata. `rvw.context` retains source hashes,
plan identity and available native execution context. The logical source and
history elements describe export only. They do not identify a source statement
or a passing test. The fixed export date is not an execution timestamp.

Supported inputs are `rvw.coverage/1`, `rvw.functional-coverage/1`,
`rvw.assertion-counters/1` and `rvw.coverage-exchange/1`. Functional holes become
zero-count bins. Scalar crosses retain their original tuples and classifications.
Native code point keys, Scala links and exclusions remain exact metadata.
Assertion input has a `design_sha256` and `properties` list. Each property has
an `id`, optional source metadata and `counts`. Supported counter names are
`pass`, `fail`, `cover`, `vacuous`, `disabled`, `attempt`, `active` and `peak_active`.
These are reported counters. They do not establish proof or non-vacuity.

`merge_exchanges` requires equal source context, bin IDs, native kinds,
semantics and exclusions. It sums compatible event counts. Peak-active counters merge by maximum.
Active snapshots must agree and do not add. Imported exclusions remain
unverified. Import does not create a native code database or proof envelope.
No imported report grants C4 acceptance. Native UCIS metric tags, vendor databases,
arbitrary UCIS profiles and UCIS C API support remain outside this subset.
LCOV can lose metric distinctions. Use its metadata sidecar for those fields.
