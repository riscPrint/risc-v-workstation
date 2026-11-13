# Random stimulus contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Seeded random campaign report

`rvw regress random` and `regress_random` write `rvw.random-campaign/1` to
`campaign.json`. Settings are project-owned TOML, separate from `rvw.toml`.
Paths resolve from the settings file. The report records the settings hash,
upstream revision, selected core/configuration and ordered seed attempts.
Each attempt retains generator and compiler arguments, source and ELF hashes,
C1 result artifacts and the public `rvw.cosim/1` comparison where available.

Attempt statuses are `generator_error`, `compile_error`, `adapter_error`,
`trace_error`, `cosim_error`, `core_failure`, `mismatch`, or `pass`.
Errors never count as a pass. The aggregate status is `fail` for a core failure
or mismatch, `pass` only when every attempt passes, otherwise `inconclusive`.
CLI exit codes are 0, 1 and 3 for those statuses. Invalid requests exit 2.
Coverage is present only after a complete, nonempty Spike match with passing
termination and a C1 retired count equal to the comparison count. Coverage uses
the existing functional report and its input capture. It includes the complete
trace, including setup and termination. It does not establish payload closure.
Existing output directories are refused. The run has no resume or cache reuse.
Each C1 run retains the runner's source/native identity and ELF replay records.

The project schema accepts `[stimulus] random_settings = "random.toml"`.
This path resolves from `rvw.toml`. An explicit `--settings` overrides it.

## Native random campaign counts

`rvw.random-campaign/1` includes `counts` when execution finishes. The keys are
attempt status names. The values count attempts with each status. Missing keys
mean zero attempts with that status. `pass` requires a complete, nonempty strict
Spike comparison and passing C1 completion. A synchronized match earns no credit.
Generator and compiler errors remain separate from a core failure or mismatch.
