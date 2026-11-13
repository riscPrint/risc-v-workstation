# Measure your tests

`rvw cov mutate-core` runs a serial campaign on exported Verilog. The project
selects modules and line patterns. One operator changes on each selected line.
The runner spreads candidates across the declared scopes. Inspect `plan.json`
before a native campaign. This path complements MCY. It does not use MCY's
`FAIL` result as detection evidence.

```sh
rvw cov mutate-core --manifest /path/to/mutation-project.json \
  --work-dir /path/to/new-run --count 60 --prepare-only --json
rvw cov mutate-core --work-dir /path/to/new-run --resume --budget-s 120 --json
```

MCP tool: `cov_mutate_core`. Each call has a wall time budget. Child process
groups stop at the deadline. Cleanup can add time. One simulation runs at a time.
All commands use `nice -n 15`. Lock names are `vex-mutate` and `sbt-mutate`.
The project adapter must use those environment settings for its private core.

The JSON manifest uses `schema: "rvw.core-mutation-project/1"` and these fields:

| Field | Meaning |
|---|---|
| `rtl` | One exported Verilog file, relative to the manifest. |
| `inputs` | All adapter, ELF, platform and other dependency files. Each file is hashed. Include scripts used by commands. Tool installation identity remains a project obligation. |
| `scopes` | Ordered objects with `id`, exact Verilog `module`, and a `pattern` regular expression for selected lines. |
| `tests` | Ordered objects with unique `id`, `source`, cumulative `tier`, and `elf`. Every ELF must occur in `inputs`. |
| `build` | Argument array for build and elaboration. Exit zero only when the candidate model is ready. Reuse `{build}` for incremental Verilator output. |
| `test` | Argument array that runs the built model and strict Spike comparison. Write `{receipt}`. Never rebuild in this command. |
| `equivalence` | Argument array for `rvw formal equiv`, with `--gold {original} --gate {rtl} --out {proof}` and project top/reset settings. |

Commands also receive `{out}`, `{test}`, `{elf}` and `{rtl_sha256}` where
applicable. Paths are absolute. Commands run from the manifest directory.
Arguments use Python format fields, not a shell. Escape literal braces as `{{`.
Use stable pinned source revisions. The runner refuses changed inputs on resume.
Keep the complete run outside the repository. Retain logs and JSON only.

The original design must build and pass every declared test with strict Spike.
A failed control stops the campaign. Each mutant builds once per attempt.
A failed build or elaboration is `invalid`. A deadline is `timeout`.
The one build directory is removed on exit. Resume skips finished mutants and
retries timeouts. An interrupted mutant without a saved result runs again.

A test receipt uses `schema: "rvw.mutation-test/1"`, the exact `test` ID,
`rtl_sha256`, and `outcome`. A passing test needs `outcome: "pass"`, exit zero,
and `strict_spike_match: true`. A kill needs nonempty `evidence` and one of:

- `killed by self-check`
- `killed by reference mismatch`
- `killed by generated check or property`

The project adapter must extract evidence from the native run or comparator.
A generic nonzero exit, missing receipt, stale identity or plain `FAIL` is
`invalid`. The adapter is trusted code. The receipt is not an independent proof
of adapter soundness. Include event cycles in `evidence` to compare detection
times. Set `evidence.detection_cycle` and `evidence.reference_mismatch_cycle`
to measured integer cycles from the same run. Only a strict earlier cycle
increments `property_before_reference`. Other property kills increment
`property_timing_unmeasured`. `reference_first_kills` counts reference first
killers, not proof that every property monitor was active. This runner does not
infer detection times from an exit code.

Tests stop at the first killer. Source totals are first kills in the declared
order. They are incremental contributions, not independent source kill rates.
Invalid, timeout and proved-equivalent mutants stay visible and leave the kill
rate denominator. An empty denominator gives null. Survivors run the existing
formal equivalence flow. Only its unconditional `equivalent` result earns
`equivalent (proved)`. A bounded match cannot earn that result. `test_gap` is
true only with a `not_equivalent` result. Other survivors need further analysis.

## Study status

No native campaign has been measured through this interface yet. Fixture tests
validate orchestration only. They do not measure either core's detection power.

| Core | Native mutants run | Kill rate | Test gaps |
|---|---:|---|---|
| VexRiscv | 0 | NOT RUN | Not measured |
| ooo-mini | 0 | NOT RUN | Not measured |

The 60-mutant studies, directed tests from surviving mutants, and monitor timing
comparison remain open. Use a private pinned core copy and a short declared
test list. A complete campaign needs exported RTL build adapters for both
cores. The existing Scala launchers elaborate their own design and cannot be
used as mutant build adapters without an explicit RTL replacement path.

