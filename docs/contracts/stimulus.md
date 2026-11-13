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

## Verification plan probe references

A `rvw.vplan/1` coverage reference can select event and sequence IDs from
`rvw.probe-coverage/1`. The reporter requires qualified C1/strict reference
execution, positive instruction count, complete trace, and zero masks and
synchronization. Probe and sampled RTL contexts stay distinct. Negative or
duplicate counts are invalid. Uncompleted sequences remain holes. These
references preserve the recorded model identity and do not grant C4 acceptance.

## Budgeted measured smoke suites

`rvw.coverage-smoke/1` pins the input database and native point universe. It
records full native points, observed signature targets, selected tests, covered
point count/hash, measured C1 costs, startup allowance, and minimisation scope.
Exact minimisation covers at most 20 measured tests. The time selector is greedy.
Missing cost excludes a test from budget selection. It does not imply zero cost.

Optional execution runs project C1 jobs with a process deadline. The deadline
covers lock acquisition and adapter execution. Termination cleanup can add time.
`timed_out` never becomes pass because output files exist. Passing execution
requires every selected C1 result, matching job identity/model flags and no
inconclusive C1 record. `new_execution_coverage_credit` stays false. These runs
do not repeat strict reference qualification or establish C4 acceptance.
Conclusive C1 fail/assert observations remain failures. A process error or
missing result remains inconclusive unless the deadline fired.

## Instruction feed and core-side port

`rvw.instruction-port/1` declares `config`, `word_bytes` (4 or 8), optional
`latency_cycles` (default 1), and `signals`. Required pin roles are `cmd_valid`,
`cmd_ready`, `address`, `rsp_valid`, and `rdata`. Optional roles are `rsp_ready`,
`error`, `cmd_id`, and `rsp_id`. IDs require both roles with equal widths. Pin
roles must name distinct top-level signals. Requests use byte addresses and
aligned bus words. The driver checks directions and widths. It allows one
outstanding request. A source with no ready word applies backpressure.

`rvw.instruction-feed/1` declares matching `word_bytes`, a reference ELF SHA-256,
and unique aligned `words`. Each word has `address`, `data`, and optional
boolean `error`. Hexadecimal strings preserve exact values. Missing addresses
return a fetch fault. A port without an error pin cannot represent that fault.
The reference hash binds the boot/comparison image, not equality of every feed
word. Deliberate instruction changes remain explicit input data.

C1 `--instruction-port` and `--instruction-feed` must appear together. An
adapter/config must opt in. C1 records the selected input paths in `options`,
captures parsed inputs as `instruction_port`/`instruction_feed` artifacts, and
writes `instruction_requests`. `details.instruction_injection` records input
hashes, attachment, requests, responses and fault responses. A software pass
becomes error if a requested hook did not attach or deliver a response.
Speculative responses do not establish retirement. The hook does not change
synthesis RTL or the normal path when disabled. It is not a live TestRIG
transport implementation.

## Project-derived pygen target

Optional random setting `target_profile` names `rvw.dv-target/1` JSON relative
to the settings file. `scripts/riscv-dv-project.py --csrs SELECTION` derives it
from the platform ISA, XLEN, privilege modes, RAM and alignment policy and the
shared-catalog CSR selection. The profile contains only present selected CSRs.
It preserves project reset metadata. This does not assert CSR completeness.
The launcher records its SHA-256 and replaces upstream architectural preset
values before configuration import. Legacy settings without the profile keep
the upstream preset. Neither path grants privilege or CSR coverage credit.
