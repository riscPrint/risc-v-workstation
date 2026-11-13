# C3. Suite results (`rvw.results/1`)

New regress run sets publish through C8 `current` and `generations/<id>`. The root workspace
files are progress copies. Readers resolve one generation, validate all artifacts and read
claim-bearing JSON through that generation. Nested suite paths resolve through the owner.
Resume creates a new generation. `--fresh` clears the workspace and retains published generations.
Legacy complete run sets use one captured JSON set while holding the writer ownership lock.
An active writer, orphan adapter, incomplete set or missing generation pointer refuses the read.
Legacy caches are misses. New generation-bound caches store conclusive passes, and
conclusive failures with complete RTL identity as specified in C8.


A suite run (riscv-tests, ACT4, VM tests, benchmarks, random-timing stress, elaboration) is a
directory with `results.json`:

```json
{
  "schema": "rvw.results/1",
  "run_id": "2026-10-20T21-03-11Z-small-riscv-tests",
  "suite": "riscv-tests", "core": "boom", "config": "small",
  "created": "2026-10-20T21:03:11Z",
  "source": {"core_rev": "…", "core_dirty": false, "tools_rev": "…"},
  "tests": [
    {"id": "rv64ui-p-add", "status": "pass", "seed": 1, "cycles": 1234, "instret": 456,
     "elf_sha256": "…", "options": {"max_cycles": 200000}, "kind": "elf-dir",
     "wall_s": 2.1, "run": "tests/rv64ui-p-add/result.json", "signature": null,
     "metrics": {"ipc": 0.37}}
  ]
}
```

Runner C3 files carry `run_set`, the relative path to their owning run directory. Every C3
directory load checks its nearest ancestor `run.json`, even when the caller names only a nested
suite or its JSON file. The owner must be complete and list that directory. Run id, suite,
config, test count, core and overlapping source fields must agree. Missing source fields are
inherited from the manifest. Manifest paths must stay inside the run directory. The owner must
record a non-empty source identity object. Missing or malformed source data is an error.
A recorded `run_set` with a missing or different owner is an error. Older standalone C3 files without
`run_set` or an ancestor manifest remain readable; their former ownership cannot be recovered.
Older suites in the runner layout with `.rvw-job.json` records also require an owner.
Runner source fields `tools_key` and `adapter` require an owner even in a detached legacy C3 file.
An alias cannot bypass the run manifest above the requested path. The boundary check applies
to both directories and `results.json` file links, even when another run has matching metadata.

Each runner test entry records `elf_sha256`, `seed`, stimulus `options` and `kind`. Build entries
have `kind: "build"`, no ELF hash, and a `build_options` array. Options include C1 `max_cycles`,
`mem_latency` and reported option defaults. Compare requires the recorded
program and stimulus inputs to agree for each shared test and seed. Missing identity, a changed
ELF or changed options makes that test inconclusive, even when the failure signature agrees.
RiscvSim entries also retain `rtl_sha256` and the per-model `adapter_identity` digest.
Pooling requires one pair of these identities for each suite and config. The RTL digest identifies the tested design; different
RTL digests are expected when a gate compares design revisions. Each result must match its
own adapter identity claims. Equal design decisions use the RTL digest.
Such a test cannot be classified as still failing, fixed or known, or used for performance
comparison. Older entries without input identity need a rerun. A baseline failure can cover
only the same seed. Count and random seed modes still detect insufficient sample counts, but
different seed sets are inconclusive; equal counts alone do not establish comparable inputs.

`signature` is a short normalized failure fingerprint (status + fail code or assertion location),
used to tell a known failure from a new one (`rvw.results.failure_signature`): e.g. `fail:3`,
`timeout` (max cycles), `timeout:wall-clock`, `assert:lsu.scala:1241`,
`assert:IllegalStateException@Mem.scala:42` (testbench exception), `rvfi_error:105`.
Assertions use the HDL file and line when there is no Scala location, for example `assert:core.sv:4`.
Without either location, `assert:sha256:<digest>` binds the full, unnormalized message.
Uncoded RVFI errors use `rvfi_error:sha256:<digest>` over the full message.
Runner C3 entries retain complete failure messages with `message_complete: true`.
Display limits must not truncate this evidence. Legacy 400-character messages without
this marker may be cut previews. Compare treats these entries as inconclusive and requires a rerun.
Compare derives assertion and RVFI signatures again from saved messages, including older C3 results.
C3 retains C1 `details.rvfi_errcode` when present. Compare uses this code before parsing
the message, as C1 signature generation does.
Old uncoded RVFI evidence without a saved message needs a rerun. Saved `fail_code` values
override saved fail signatures. An unchanged failure must also have the same status.
An assertion without a saved message or a complete location is inconclusive and needs a rerun.
Test entries and the top level may carry extra keys (e.g. `message`, `fail_code`, `cached`, `perf_metrics`);
readers ignore keys they do not know. An entry is *inconclusive* (`TestEntry.conclusive` is
false) when its status is `error`, it has `synthesized: true` (the runner wrote it because the
adapter did not), `wall_clock_timeout: true`, or `inconclusive` (the reason: `rvw regress` copies
`RunResult.why_inconclusive` of the C1 result, whatever its status, so every cause of the shared
rule reaches C3). Inconclusive results are not cached, not restored from the cache and not
resumed. `rvw regress` rechecks the core, `cache_paths`, adapter files, adapter identity and
ELF bytes after taking the execution lock, before reuse or execution, and again before result
publication under that lock. A detected input change makes every result in that suite
inconclusive in C1 and C3, clears cache keys, and prevents cache storage and resume. Later
suites in the invocation stay inconclusive. Explicit revision runs use a separate cached clone,
including for the current HEAD; live `WORKTREE` and `--source` runs use the checks above.
Job identities include `runner_identity_version: 5` so older unchecked cache and resume entries
are not reused.
Checks cannot detect an input changed and restored between checks, or an input not declared
in the identity. Each (`id`, `seed`) has its own run directory: `rvw regress` refuses a suite whose tests
would share one (same id after `strip_suffix`, ids that differ only in case, or one test's
directory inside another's). The top level may carry `seeds` (`{"mode":
"fixed" | "random", "base": 1}`) and `filter`. Shared code: `rvw/src/rvw/results/`. `rvw regress` also writes JUnit XML next to it.

A selected source checkout requires the core config's `source_env`; otherwise rvw refuses the
run before starting the adapter. C1 must name that source path and its Git revision when known.
`regress run` accepts at most one of `--source` and `--rev`. Shared validation refuses conflicting
selectors in CLI, Python and MCP calls before starting the adapter.
Recorded revision, dirty flag, fingerprint, link identity and identity coverage must agree with
the request. Conflicts make C1 and C3 inconclusive and prevent cache publication. Conflicting
cached or resumed results are discarded and rerun. A cached C1 may name a different checkout
only after rvw verifies that it has the same clean revision and link contents.

Suite `options` cannot replace runner fields: `config`, `elf`, `out`, `seed`, `max_cycles`,
`mem_latency`, `rvfi_trace` or `wall_timeout`, including dash spellings and a leading `--`.
C1 must agree with the
requested core, config, ELF SHA-256, seed and each requested stimulus option before C3 publication,
resume or cache reuse. Options may be reported as C1 fields or in a C1 `options` object. Missing
or conflicting evidence makes the result inconclusive and prevents cache publication. The runner's
wall timeout is a process budget, separate from the stimulus options checked in C1.
The observation flag `rvfi_trace` may instead be checked from one `--rvfi-trace` replay flag and
an existing C1 trace artifact inside that result directory. Both are required. An explicit
conflicting option field is never overridden by this evidence.

Source identity also checks raw tracked file bytes and executable bits, independent of index
flags, stat caching, `core.fileMode` and line-ending normalization. This applies to `cache_paths`
and cached revision checkouts. Private ignore files cannot hide untracked source files; use
repository `.gitignore` rules for build outputs. Sparse checkout, shallow history, replacement
refs, grafts, private attributes and active clean/smudge filters are refused.

## Reviewed suite findings

`rvw regress cosim --findings FILE` accepts project data with schema
`rvw.known-findings/1` and a `findings` array. Each entry has `finding_id`,
`core`, `test`, `trace_sha256`, `observed_status` and `reference` strings.
Only exact trace SHA-256, core, test and observed failure status matches apply.
The report uses `status: known_finding`, retains `observed_status` (`fail` or
`mismatch`), and adds `finding_id` and `finding_reference`. It retains the C1
status, mismatch and reason. The count is separate from `match`. The command
still exits 1. Changed evidence needs review. This catalog does not waive C1,
C3, gate, coverage or reference checks. It does not change a core or mask a
reference field.
