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

## Integer control and initial suite

`rvw.stimulus-loop/1` settings accept optional `strategy` (`directed`, the
default, or `random`) and `initial_results` (nonempty C1 result path list).
Random selection ignores holes and keeps the attempt budget. It supports only
the integer candidate profile. Initial runs must have complete strict Spike
matches and the selected core/config. Reports retain their hashes, comparisons,
coverage and common execution identity under `initial`. Initial hit credit is
restricted to the declared supported denominator. Candidate runs must retain
the initial execution identity. Settings and qualified initial evidence enter
resume identity. These fields do not grant C4 acceptance or a closure-rate claim.

Loop reports also record `initial_hits`, `strategy`, `attempt_budget` and
`pair_context`. The common context hash covers declared inputs, pinned plan,
control settings and implementation. The curve exporter requires equal common
context and qualified execution identity. Its `rvw.paired-curves/1` output
contains credited-bin histories by attempt wall time. It retains failed-attempt
cost and excludes initial-suite and publication cost.
