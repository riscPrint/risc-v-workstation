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

## Source coverage navigation

`rvw.source-bindings/1` declares `point_universe`,
`functional_config_sha256`, and `links`. Each link has `file`, `line`, and
`groups`. A link must name an existing native source line and fixed functional
groups. `rvw cov source-report` emits `rvw.source-coverage/1`. It retains native
metric counts and functional denominators separately. It lists unmapped points
and groups. `code_targets` names unhit native points for code-goal plans.
`functional_targets` names unhit generator goals. Source links are project
claims. They do not establish measured Scala statement coverage.

## Probe goals and controller feedback

`rvw.probe-goals/1` has `design`, nonempty `bins`, and optional `sequences`.
Bins declare unique `id`, probe `kind` and `name`, and optional `fields` value
lists. Sequences declare unique `id`, bin-ID `steps`, and positive `max_gap`.
Steps advance on increasing cycles. Pending monitor states with the same step
and last cycle collapse. Expired states do not count as pending or complete.

`rvw.probe-coverage/1` records C1, C2, probe and plan hashes, canonical `plan_id`,
`design`, event counts, completed/pending sequence counts, and holes. Its
`qualified` status means that C1 and complete strict Spike execution passed.
It does not prove probe wiring or architectural meaning. Event accounting,
cycle bounds, field widths, ELF, seed, core/config and RTL identities must match.

Campaign settings accept `probe_plan` with existing event recipes. Exactly one
of `rtl_plan`, `code_plan`, or `probe_plan` can be selected. Optional boolean
`coverage` retains the instrumented model used by the probe plan. Probe mode
enables C1 probe capture. Code mode enables native coverage capture. Archived
replay uses the same model options. Probe feedback validates its native stream
against C1 and full C2/Spike before UCB reward. Code and sampled RTL feedback
retain their existing exact receipt rules. Repeated streams earn no reward.

The generic C1 driver records selected model flags under `options`, including
coverage, probes and RVFI observation flags. This lets regression check the
requested model without inferring options from artifact names. Missing or
conflicting option receipts remain inconclusive. Native probe qualification
never bypasses that regression check.
