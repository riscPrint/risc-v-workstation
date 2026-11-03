# rvw.results

Shared code for the result formats in `docs/PLATFORM_CONTRACTS.md`: rvw.run/1 (C1, one
simulation), rvw.results/1 (C3, one suite run) and rvw.verdict/2 (C4). Standard library only.
Other tools import it instead of parsing the JSON themselves.

```python
from rvw.results import (load_run, load_results, find_results, load_verdict, save_run, save_results,
                         RunResult, SuiteResults, TestEntry, Verdict, validate,
                         failure_signature, run_signature, write_junit)

run = load_run("out/rv64ui-p-add")           # DIR or DIR/result.json; SchemaError if invalid, FileNotFoundError if absent
run.status, run.cycles, run.metrics, run.extra   # unknown keys survive in .extra
sig = run_signature(run)                     # "fail:3", "assert:lsu.scala:1241", "timeout", ...
for res in find_results("~/.cache/rvw/results/runs/X"):   # a run set: the suites its run.json lists
                                                          # (SchemaError if unfinished or inconsistent, or if
                                                          # a results.json it does not list sits beside it);
                                                          # another tree: every results.json in it
    print(res.suite, res.config, res.counts())
validate(json_obj)                            # list of problems, by its "schema" key
write_junit(res, "junit.xml")
```

## Failure signatures

`failure_signature(status, fail_code, message)` identifies a failure by its code, source
location or message. Assertions without a source location bind the full message:

| Status | Signature |
|---|---|
| pass | `None` |
| fail | `fail:<code>` |
| timeout | `timeout` (max cycles), `timeout:wall-clock` (`wall_clock_timeout: true`) |
| assert | `assert:<File.scala>:<line>`; else `assert:<File.sv>:<line>` when an HDL location exists; else `assert:sha256:<full-message digest>` |
| assert, testbench exception | `assert:<ExceptionType>@<file>:<line>` with a source location; else `assert:sha256:<full-message digest>` |
| rvfi_error | `rvfi_error:<monitor error code>` (from `details.rvfi_errcode` or the message), else `rvfi_error:<normalized message>` |
| error | `error:<normalized message>` |

`TestEntry.conclusive` and `RunResult.why_inconclusive` use the same rule. Harness errors,
synthesized results, wall-clock timeouts, adapter marks and pending or unattributed concurrent
failures prove nothing about the core. Comparison reports them as inconclusive.
`load_run` is the one C1 loader: the result has `.dir`, `.failed`, `.details`, `.get(key)` and
`.artifact(name)` (path of `log`, `rvfi_trace`, `wave`, ... or None).

Normalization keeps the first line, drops `%Error:` prefixes and directories, replaces hex values
with `0x*`, numbers after `cycle`/`time`/`seed`/`pc`/`at` and any number of four or more digits
with `N`, and cuts to 120 characters. Small numbers (error codes, indices) are kept.

## Decisions

- Current run sets use C8 generations. `load_run_set` accepts a path or a pinned `Generation`.
  `load_results(..., generation=reader)` validates the suite through that reader's owner.
  `open_generation(store, id)` selects an old generation without reading `current`.
  `Generation.files` and `entry(name)` expose a read-only inventory.
- Readers resolve `current` once and verify the full generation. JSON reads check manifest
  membership and hashes. Returned suite paths remain inside the selected generation.
  Resume creates a new generation. C4 records the base and head generation IDs.
  Missing generations, missing pointers and stale root `results.json` files refuse the read.
- Legacy run sets need complete, consistent manifests. The reader takes the output ownership
  lock and captures JSON once. Active writers and unresolved adapters refuse that route.
  Standalone C3 files remain readable. Pre-C8 caches are misses.
- Direct suite paths retain run-set ownership. The nearest `run.json` must list the suite.
  Run ID, suite, config, test count, core and source fields must agree with the owner.
  Source identity must be non-empty. Missing suite source fields inherit the owner's fields.
  `run_set`, runner source fields and legacy job records require an owner. Aliases cannot
  change the owner. Parsed directories come from the same checked lookup as the JSON bytes.
- `load_results(..., capture=command_capture)` captures a legacy C3 input tree and validates
  ownership. Its returned path keeps the logical artifact base directory.
- Compare requires equal ELF hashes, seeds, stimulus options and job kinds. Build entries
  require equal build options. Missing inputs or unequal random/count seed sets are
  inconclusive, even when failure signatures agree. Live C1 paths cannot fill missing identity.
- C3 keeps full source identity. Compare refuses mixed identities, duplicate test/seed entries,
  and missing or unequal core names. Gate also requires the requested core name.
  Explicitly incomplete source evidence can show a failure but can never earn accept.
  Repeated paths reuse the first pinned generation. Private input and C1 cache stores stay
  outside C3 scans. Conflicting private-store markers refuse the scan.
- C3 records `perf_metrics`, `metric_keys` and each test's `metric_origins`. C4 requires equal,
  known origins for every metric sample, including fallback and derived IPC inputs.
  Samples must be positive and finite. Missing legacy origins are inconclusive.
- `write_json` serializes strict JSON before creating a temporary file or parent directory.
  Serialization errors leave existing files unchanged. `wall_s` must be finite and non-negative.
  Invalid regression thresholds cannot publish a verdict.

## Tests

```sh
rvw/.venv/bin/python -m pytest -q rvw/tests/test_results.py rvw/tests/test_generation.py rvw/tests/test_regress_round18_results.py
```

## Known limits

Legacy standalone C3 files copied away from their owner may have no origin markers.
Their run-set origin cannot be checked. Raw paths into a generation do not verify bytes;
use `Generation.read_bytes` for claim-bearing reads.

## Limit ownership

Retained limit: The documented schema and evidence restrictions remain required. Compatibility parsing does not qualify missing evidence. No separate issue is assigned for broader result formats.
