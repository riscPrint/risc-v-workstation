# Soundness review of verdict paths

Date: 2026-11-13. Base: `origin/main` at `652d57ca`.

## Scope and method

This is an independent review of the code that produces verdicts. The question
for each path is: can a normal setup get a pass, match, proof, accept or
exclusion without the evidence for it?

Method: read the code. For each candidate, make a minimal input (a small
fixture or a changed result file in a temporary directory) and run it on
current main. Each finding has one label:

- **realistic**: a normal user or agent can hit it by mistake. Fixed at once with
  a regression test that fails before the fix.
- **unusual**: needs an uncommon but honest setup, or the verdict is scoped
  correctly but easy to misread. Recorded, not fixed.
- **adversarial**: needs hostile or doctored inputs, or a race. Out of scope
  (contract C8). Recorded, not fixed.

The review did not trust the unit tests. It did not run native tools, BOOM
builds, simulations or proofs.

## Area 1: `rvw regress` run and gate, C1/C3/C4, farm intake

### Files read

| File | Lines |
|---|---|
| `rvw/src/rvw/regress/compare.py` | 551 |
| `rvw/src/rvw/regress/plan.py` | 236 |
| `rvw/src/rvw/regress/runner.py` (job, entry, provenance, cache, persistent batch parts) | 1359 |
| `rvw/src/rvw/regress/known.py` | 189 |
| `rvw/src/rvw/regress/findings.py` | 51 |
| `rvw/src/rvw/regress/commands/suite_cosim.py` | 161 |
| `rvw/src/rvw/regress/random_stream.py` | 188 |
| `rvw/src/rvw/results/schema.py` (statuses, conclusiveness rule) | 729 |
| `rvw/src/rvw/farm/selection.py` | 65 |
| `rvw/src/rvw/farm/gate_intake.py` | 72 |
| `rvw/src/rvw/farm/gate_job.py` | 42 |
| `rvw/src/rvw/farm/executor.py` | 230 |
| `rvw/src/rvw/farm/recorded_results.py` | 24 |

### What holds

- `compare` refuses pooled shards from different designs or sources, treats
  every inconclusive candidate entry (harness error, synthesized, wall-clock
  timeout, adapter mark, unattributed concurrent failure) as neither pass nor
  known nor still-failing, and gives `inconclusive` when no test ran on both
  sides.
- A dropped seed or test is `missing` and rejects, unless the caller sets
  `--allow-missing`. A base failure counts as fixed only when every failing seed
  has a conclusive pass.
- Known failures need an exact suite, id, config and signature. A wildcard or a
  missing config gives `inconclusive`, not a waiver.
- `rvw regress cosim` exits 0 only when every row is `match`. A
  `known_finding` row keeps exit 1. A match with an allowed synchronization
  still requires the complete strict rule (`trace_complete`, `end_status`
  `pass`, equal instruction count).
- The persistent batch path synthesizes `error` or `timeout` (both
  inconclusive) for every job without `result.json`, and each C1 result must
  match the requested job identity and options before it enters C3.
- The C3 status set has no `skip`. A test that is not run is absent, and the
  gate reports it as `missing`. Stored-plan checks make a stored side that
  does not cover the requested plan `inconclusive`.
- Farm impact selection is advisory (`gate_acceptance: false`). Farm shard
  status `complete` means collection only. The farm gate intake refuses
  inconclusive, dirty or unbound native C1 evidence before it calls the
  unchanged C4 gate.

### Findings

| ID | Finding | Label | Action |
|---|---|---|---|
| R1 | `python -m rvw.farm.gate_job` exits 0 with `status: complete` when the recorded C4 verdict is `reject` or `inconclusive`. The verdict is in `recorded_verdict`. A queue that reads only the exit code sees success. | unusual | Not fixed. The farm README states that exit 0 means "a C4 report was collected". The `rvw farm` CLI and MCP paths return the C4 document. |

No realistic false accept was found in this area.

## Area 2: `rvw cosim`

### Files read

| File | Lines |
|---|---|
| `rvw/src/rvw/cosim/checker.py` | 495 |
| `rvw/src/rvw/cosim/cli.py` | 171 |
| `rvw/src/rvw/cosim/adjudicate.py` | 85 |
| `rvw/src/rvw/cosim/multihart.py` | 114 |
| `rvw/src/rvw/cosim/trace.py` | 260 |
| `rvw/src/rvw/cosim/platform.py` | 276 |
| Consumers of `cosim check`: `regress/vector.py` (78), `regress/mmu.py` (826, check part), `privilege/campaign.py` (423, check part), `cov/campaign.py` (307), `cov/initial_coverage.py` (41), `cov/probe_goals.py` (99), `doctor/conformance.py` (64) | |

### What holds

- Every synchronization changes only `rd_wdata` bits and is recorded in
  `synchronized`, `recent_synchronizations` and `applied_masks`. Structural
  fields (PC, instruction, trap, memory masks and address) are always compared.
- The IRQ mask takes only bits that the core reads as 1, the reference reads
  as 0, the platform declares as inputs, and the trace shows as high.
- `memory_read_convention = full_word` narrows the read mask to the bytes of
  the decoded load, and checks the raw address and strobes. It refuses MMIO and
  misaligned loads.
- Adjudication of Spike and Sail gives `match` only when both match, both
  traces are complete with no uncompared instructions, the instruction counts
  are equal, and the ELF, trace and platform hashes agree. A disagreement is
  never a pass.
- Multi-hart replay gives `match` only when every declared hart sends its
  `hart_end` and its checker returns `match`.
- Every in-tree consumer that turns a comparison into a pass (`regress cosim`,
  vector, MMU, privilege, coverage, probe goals, doctor conformance) checks
  `trace_complete`, `end_status` and, for strict uses, `synchronized == 0`.

### Findings

| ID | Finding | Label | Action |
|---|---|---|---|
| C1 | By code reading (the local Spike shim was too old to run): `rvw cosim check` on a trace without an end record (for example, a simulation that timed out) returns `status: match`, `scope: "trace prefix"`, `trace_complete: false` and exit 0. The claim is true for the prefix, and the text output names the scope. A user who reads only the exit code can take it as a whole-program match. | unusual | Not fixed. `docs/AGENT_SETUP.md` tells users to check `trace_complete` and `end_status`. All in-tree consumers check them. |
| C2 | A C2/1 trace (the RiscvSim default unless the header asks for `state`) carries no FP state. On an F/D core a `match` then compares FP effects only where they reach integer registers or memory. The result reports this in `state_coverage.fp: false`. | unusual | Not fixed. Contract C2 states that missing state is unavailable evidence, never a state match. |

No realistic false match was found in this area.

## Area 3: formal

### Files read

| File | Lines |
|---|---|
| `rvw/src/rvw/formal/regression.py` | 182 |
| `rvw/src/rvw/formal/regression_cache.py` | 105 |
| `rvw/src/rvw/formal/proof_cache.py` | 91 |
| `rvw/src/rvw/formal/portfolio.py` | 275 |
| `rvw/src/rvw/formal/cross_proof.py` | 108 |
| `rvw/src/rvw/formal/flows.py` (`_finish`, `_reachability`, header) | 1019 |
| `rvw/src/rvw/formal/common.py` (`final_status`, `count_asserts`) | part |
| `rvw/src/rvw/formal/autocheck.py` | 120 |
| `rvw/src/rvw/formal/apps.py` | 235 |
| `rvw/src/rvw/formal/automonitors.py` | 43 |
| `rvw/src/rvw/formal/equiv.py` (verdict and EQY run) | 428 |
| `rvw/src/rvw/formal/bus_environment.py` | 58 |

### What holds

- A pass needs matching SBY process and log exit codes and at least one
  `$assert` in the prepared model. Zero assertions give `no_checks`.
- Every flow pass (and every `PREUNSAT`) runs a separate cover job on the same
  prepared model with assertions removed. A pass stays a pass only when a legal
  path of the full depth exists. This catches assumptions that block all
  behaviour.
- `bmc` mode never gives `proven`: the portfolio maps it to `bounded_pass` and
  takes only `pass` or `fail` as a winner. A portfolio with any source
  assumption gives `inconclusive` (`activation_not_checked`). Two engines that
  disagree give `inconclusive`.
- `rvw formal regress` keeps every engine observation inconclusive at C3 level
  and reports overall status `unknown` with exit 1. An explicit `PREUNSAT`
  becomes `vacuous`.
- Proof caches key on the elaborated model bytes, the SBY script, captured
  files, tool hashes, environment and the formal and common Python code. A
  changed RTL or property changes the elaborated model and misses the cache.
  The regression cache refuses jobs with `` `include ``, `$readmem`, `$fopen`
  or other script commands, and refuses activation jobs it cannot identify.
  Only `pass` results with assertions, reachable paths and no capture problems
  are published.
- Equivalence needs every EQY partition `PASS` with no cut bits and no
  unmatched state. Black-box contracts and event models make the result
  `conditional`.
- App reports with any waived row, or any reachability-style target (FSM,
  dead code, toggle, counter wrap), cannot give `pass`.

### Findings

No realistic false proof was found. Not reviewed in depth: the ISA flows
(`isa.py`, `riscv_proof.py`, Sail subsets), datapath, security apps, IC3
lemma reuse, deep grids and liveness.

## Area 4: generated checks and dispositions

### Files read

| File | Lines |
|---|---|
| `rvw/src/rvw/checks/qualification.py` | 129 |
| `rvw/src/rvw/checks/dispositions.py` | 38 |
| `rvw/src/rvw/common/waivers.py` | 23 |
| `SpinalChecks/src/main/scala/spinalchecks/StreamCancellation.scala` | 74 |
| `SpinalChecks/src/main/scala/spinalchecks/SpinalChecks.scala` (stream checks) | part |

### What holds

- Qualification status is only `findings` or `inconclusive`. Proven and
  bounded counts need formal activation of every associated property.
- Dispositions need a reason, an owner and an unexpired date. A disposition
  for a check that did not fire in evaluated runs is refused as stale. Waived
  findings give `reviewed_findings`, never a pass.
- The automatic cancellation terms (`throwWhen`, `haltWhen`, `continueWhen`,
  `clearValidWhen`, `m2sPipe` register clears) all force `valid` low in the
  sample where `cancel` is true. The payload check is `stallPrev && !cancel &&
  valid && changed`, so a recognised cancel cannot hide a payload change while
  `valid` stays high. A reviewed project binding can hide one, by design, and
  the report names it as a reviewed binding.

### Findings

No realistic finding.

## Area 5: coverage, plans and evidence

### Files read

| File | Lines |
|---|---|
| `rvw/src/rvw/common/verdicts.py` | 20 |
| `rvw/src/rvw/plan/model.py` | 221 |
| `rvw/src/rvw/evidence/index.py` | 70 |
| `rvw/src/rvw/cov/code.py` (`merge`, `summary`) | 697 |
| `rvw/src/rvw/cov/proof.py` (`apply_exclusions`) | 1339 |
| `rvw/src/rvw/cov/campaign.py` | 307 |

### What holds

- `weakest_verdict` puts `fail` first and `pass` last. Plan features give
  `pass` only when every evidence entry is a pass and there is no hole. Coverage
  references keep the producer verdict, which is not `pass` for coverage
  reports, so they never raise a feature to `pass`.
- Formal plan evidence needs the child `rvw.formal/1` result with a pass,
  assertions, a reachable path and the required proof kind.
- Code coverage merge refuses different point universes and different C1
  provenance. Hit counts use `count > 0`, so a repeated input cannot raise
  the hit rate.
- A proof exclusion needs an unbounded `PASS`, no conflicting cover witness, a
  passing cone cover, a passing sanity cover, unchanged evidence hashes, an
  unhit point, and a plan rebuilt from hashed inputs.
- Stimulus closure credits bins only after a single C1 pass with a complete
  strict Spike match and exactly one retirement of each payload instruction.

### Findings

No realistic finding.

## Area 6: fault, security, debug, SoC, lint, UVM/VIP, ACT4

### Files read

| File | Lines |
|---|---|
| `rvw/src/rvw/fault/campaign.py`, `fault/cli.py` | 339, 106 |
| `rvw/src/rvw/sec/common.py`, `campaign.py`, `pairs.py`, `model_check.py`, `suite.py` | 35, 226, 156, 110, 38 |
| `rvw/src/rvw/debug/suite.py`, `api.py`, `profile.py`, `interop.py`, `campaign.py` | 533, 169, 183, 165, 34 |
| `rvw/src/rvw/soc/verify.py`, `connection_run.py`, `decode_proof.py` | 304, 79, 39 |
| `rvw/src/rvw/lint/cli.py`, `native.py`, `yosys.py`, `protocol.py` | 195, 52, 73, 182 |
| `rvw/src/rvw/uvm/cli.py`, `uvm/flow.py`, `vip/cli.py` | 63, 210, 28 |
| `rvw/src/rvw/sim/cocotb.py`, `sim/hdl.py` | 135, 152 |
| `rvw/src/rvw/regress/act4.py`, `act4_csr.py`, `sail_tests.py` | 126, 33, 116 |
| `rvw/src/rvw/workloads/core.py`, `formal/deep_grid.py`, `formal/initial_split.py`, `privilege/events.py` | 223, 30, 117, 62 |

A tree-wide search also looked for the empty-input pattern (`'pass' if
all(...)` over a list that can be empty, and verdicts that start as `pass`). Every
hit either guards against an empty list or cannot be empty.

### What holds

- Fault campaigns: an unconfirmed injection is `not_injected`. A passing run
  without a C2 trace or without a passing end is `inconclusive`. Any
  `not_injected`, `timeout` or `inconclusive` fault, or an empty campaign, makes
  the report `inconclusive` (exit 3). Silent corruption gives `fail`.
- Security: `no_leak_observed` needs complete evidence and no finding. Suite
  collection refuses a child verdict that conflicts with its technique status.
- SoC verify gives `pass` only when all seven check kinds ran and passed.
  Captured APB samples alone stay `inconclusive`.
- Lint: a backend that was not selected, not installed or did not complete
  makes the report `inconclusive`, never `clean`. A waiver binds to the hash
  of the complete finding and needs an unexpired review date. A waiver that
  matches nothing in a backend that ran is an error.
- UVM runs need exactly one `RVW_UVM_DONE <test> checks=N` marker with N ≥ 1
  and no UVM error or fatal. cocotb needs at least one test case. A skipped
  case is inconclusive. HDL runs need exactly one `RVW_PASS` marker.
- ACT4 build status `built` needs a zero `make` exit and at least one ELF. The
  checkout must be clean at the pinned revision.

### Findings

| ID | Finding | Label | Action |
|---|---|---|---|
| D1 | `rvw debug suite` with a profile file that has no `[transport]` section ran the campaign against the built-in reference model, because the transport defaults to `model`. It returned `status: pass`, exit 0, and wrote C3 with `core` set to the profile name. Reproduction: a profile with `name = "mycore"`, `xlen = 32` and no transport, then `rvw debug suite --profile p.toml --out out --group dm`, gave 11 passes and `transport: model`. The README lists `[transport]` with the optional keys, so a new user can miss it. | realistic | Fixed in [#1254](https://github.com/riscPrint/risc-v-workstation/pull/1254). The suite refuses a profile without a declared transport unless `--port` names the target. An explicit `kind = "model"` still runs the self-test. The regression test failed before the fix. |
| D2 | A security campaign reports `no_leak_observed` (C3 `pass`) when at least one pair was eligible, even if most other pairs were ineligible or errored. The counts are in `statuses` and `errors`. | unusual | Not fixed. `no_leak_observed` is documented as a finite observation, not a proof. |
| D3 | `rvw fault run --watchdog` counts a harness wall-clock timeout as `detected`. A loaded machine can then raise diagnostic coverage. | unusual | Not fixed. The flag is an explicit user declaration that a watchdog would catch hangs. |
| D4 | `rvw regress gate --filter REGEX` runs both sides on the filtered subset and can accept. C3 records the filter in `extra.filter`, but the C4 verdict's `gate` block records only the tier. A later reader of `verdict.json` (for example a plan `check` of kind `gate`) cannot see that tests were left out. | unusual | Not fixed. The user asked for the filter, and the base and candidate test counts are in the verdict. Recording the filter in the C4 `gate` block would be a small contract change for the owner to decide. |
| D5 | `rvw plan status` exits 0 for any rolled-up verdict, including `fail`. The verdict is in the JSON. | unusual | Not fixed. It is a report command. Its JSON carries the verdict. |

## Area 7: MCP result envelope and jobs

### Files read

| File | Lines |
|---|---|
| `rvw/src/rvw/mcp/envelope.py` | 29 |
| `rvw/src/rvw/mcp/worker.py` | 80 |
| `rvw/src/rvw/mcp/jobs.py` | 312 |
| `rvw/src/rvw/mcp/registry.py` (isolated calls, `call_json`, job tools) | 421 |
| `rvw/src/rvw/mcp/execution.py` | 32 |

### What holds

- The envelope sets `verdict` only from an explicit producer verdict or from a
  `status` in the common verdict set. Completion (`status: ok`, job `done`)
  never becomes a pass. An error result always gets verdict `error` (or
  `not_installed`).
- A job result is returned only when the job status is `done`. A worker that
  exits nonzero, writes no result or reports an error raises a tool error.
- The nested producer result is kept unchanged under the job result, with its
  own status and verdict.

### Findings

| ID | Finding | Label | Action |
|---|---|---|---|
| M1 | A C4 verdict returned through MCP (`regress_compare`, `regress_gate`) has no common-vocabulary verdict. The envelope moves `accept` or `reject` to `legacy_verdict` and sets `verdict: inconclusive` and `status: ok`. A `reject` therefore shows as `inconclusive` at the top level. | unusual | Not fixed. This is weaker than the evidence, never a false pass. Contract C7 documents the mapping. |

## Summary

| Label | Count | Findings |
|---|---|---|
| realistic | 1 | D1 (fixed in #1254) |
| unusual | 8 | R1, C1, C2, D2, D3, D4, D5, M1 |
| adversarial | 0 | (doctored C3 files and edited caches were not pursued: out of scope under C8) |

The core verdict paths (regress compare and gate, cosim comparison, formal
pass and reachability, proof exclusions, plan roll-ups) were already guarded
against every realistic false positive this review tried. Most of them carry
comments from earlier review rounds.

## Not reviewed

There was not enough time to review these areas in depth:

- Formal: ISA flows (`formal/isa.py`, `riscv_proof.py`, `riscv_abstract.py`,
  Sail subsets), datapath (`datapath.py`, `datapath_kit.py`), security apps
  (`formal/security/`), IC3 lemma and invariant reuse (`ic3_lemmas.py`,
  `lemma_cone.py`), deep grids and liveness (`liveness*.py`, `fair_live.py`),
  native SVA (`sva_*`), equivalence partitions and memory refinement.
- Cosim: the C++ Spike shim (including `scalar_split_ram`), Sail adapter
  (`cosim/sail.py`), online and lockstep transports, DII, external PLIC replay,
  device environment replay, QEMU observations.
- Regress: MMU suites (`regress/mmu_*.py`), random stream campaigns, the
  remote cache, run evidence ownership.
- Coverage: functional coverage bins (`cov/functional.py`), mutation
  (`cov/mutation.py`), exchange, the full proof-exclusion builder
  (`cov/proof.py` beyond `apply_exclusions`).
- Generated checks in Scala beyond stream cancellation (`SpinalChecks`), CDC
  and RDC structural analysis (`lint/cdc.py`, `lint/rdc.py`), the SDC backend.
- Privilege, memory-order, CSR, VexiiRiscv and arch-model areas.
- VIP protocol agents' own monitors (`vip/*.py`) and Uvm/ conformance runs.
- The VS Code extension, SpinalWaves, SpinalTrace and SpinalBlocks (no verdicts).

# Part 2

Date: 2026-11-13. Base: `origin/main` at `79488348` (after #1258). Same method and labels as
Part 1. Part 2 has two jobs: fix the cheap reporting defects that Part 1
recorded as unusual, and review the areas that Part 1 did not read.

## Part 2a: reporting defects from Part 1

| ID | Change | PR |
|---|---|---|
| D5 | `rvw plan status` exits 0 for `pass`, 1 for `fail`, 3 for any other verdict, 2 for input errors. Before the fix, a plan with a failing C1 test gave `verdict: fail` and exit 0. | [#1264](https://github.com/riscPrint/risc-v-workstation/pull/1264) |
| R1 | The farm contract already decides the exit code: `rvw.farm-gate/1` is collection state, so exit 0 means "a C4 report was collected", and the report names `recorded_verdict`. The exit code stays. The defect was in the in-tree caller that read exit 0 as accept: a farm workflow admitted dependents of a `complete` gate job. Reproduction: workflow `gate -> merge`, where `gate` collects `verdict: reject` and exits 0. After one worker step, `merge` was `queued`. Now a node whose last attempt collected `reject` shows `dut_failure`, and `inconclusive` shows `inconclusive`. Both block dependents. | [#1269](https://github.com/riscPrint/risc-v-workstation/pull/1269) |
| M1 | The MCP envelope maps a C4 report (`schema: rvw.verdict/*`) faithfully: `accept` to `pass`, `reject` to `fail`, `inconclusive` to `inconclusive`. `legacy_verdict` keeps the C4 word. An error result never maps to `pass`. Other legacy verdicts stay `inconclusive`. | [#1285](https://github.com/riscPrint/risc-v-workstation/pull/1285) |
| D3 | `rvw fault run --watchdog` counts a hang as `detected` only when the adapter stopped the run at the cycle limit (C1 `status: timeout` without `wall_clock_timeout`), the limit under which the golden run passed. A harness wall-clock timeout or a C1 `wall_clock_timeout` stays `timeout`, and the report stays `inconclusive`. | [#1286](https://github.com/riscPrint/risc-v-workstation/pull/1286) |
| D2 | A security campaign without a signature is `no_leak_observed` only when at least `min_eligible_pairs = max(1, ceil(min_eligible_fraction × pairs))` pairs were eligible. `min_eligible_fraction` is a manifest key with default 0.5. Below the minimum, the report and C3 entry are `inconclusive`. The report gives `eligible_pairs`, `min_eligible_pairs` and `pairs`. A found signature is still `violation`. | [#1287](https://github.com/riscPrint/risc-v-workstation/pull/1287) |
| C1 | The cosim contract did not define the offline result for a matching prefix of a trace without an end record. `rvw cosim live` and lockstep already make it `inconclusive`. `rvw cosim check` (CLI and MCP) now does the same: `status: inconclusive`, `cause: trace_incomplete`, exit 3. `scope: trace prefix` and `instructions` still describe the compared prefix. The library function `checker.check` keeps its prefix result, because every in-tree consumer checks `trace_complete` itself. | [#1288](https://github.com/riscPrint/risc-v-workstation/pull/1288) |

### Owner decisions (not changed)

**D4.** `rvw regress gate --filter REGEX` can accept on a subset. C3 records
the filter in `extra.filter`, but the C4 `gate` block (`regress/plan.py`)
records only `tier`, `base`, `candidate` and `known_failures_file`. Proposed
text for `docs/contracts/c4-verdict.md`:

> The C4 `gate` block records `filter`: the `--filter` regular expression, or
> null when all tests of the tier ran. A gate with a non-null filter is a
> subset gate. Its `accept` covers only the selected tests. A consumer that
> needs a tier acceptance (a plan `check` of kind `gate`, the farm gate intake)
> treats a subset `accept` as `inconclusive` with cause `filtered_gate`.

**C2.** A C2/1 trace has no FP state. On an F/D core, a `match` compares FP
effects only where they reach integer registers or memory. The result says so
in `state_coverage.fp: false`. Proposed text for
`docs/contracts/c2-rvfi-trace.md`, section "C2 version 2":

> When the platform ISA includes F or D and the trace does not declare the
> `state` capability, `rvw cosim check` returns `inconclusive` with cause
> `fp_state_not_observed` instead of `match`. `--allow-integer-scope` keeps the
> integer-only `match`, and the result records `scope: integer state only`.

## Part 2b: areas not read in Part 1

### Files read

| File | Lines |
|---|---|
| `Cosim/spike_shim.cc` (step, split and memory effects, policies) | 535 |
| `Cosim/spike_replay.cc` | 126 |
| `Cosim/lockstep_dpi.cc` | 52 |
| `rvw/src/rvw/cosim/checker.py` (synchronization, tval, mode and FCSR policies) | 495 |
| `rvw/src/rvw/cosim/platform.py` (policy parsing, normalization) | 276 |
| `rvw/src/rvw/cosim/spike.py` (policy application) | 424 |
| `rvw/src/rvw/cosim/sail.py` | 496 |
| `rvw/src/rvw/cosim/reset_fp.py` | 14 |
| `rvw/src/rvw/cosim/online.py`, `lockstep.py` (prefix rule) | 222, 58 |
| `rvw/src/rvw/cosim/cli.py` | 171 |
| `rvw/src/rvw/formal/datapath.py`, `operand_partition.py` | 220, 21 |
| `SpinalChecks/c2rtl/hardfloat.py` | 126 |
| `rvw/src/rvw/formal/ic3_lemmas.py`, `lemma_cone.py` (identity only) | 205, 102 |
| `rvw/src/rvw/formal/fair_live.py`, `liveness_app.py`, `liveness_safety.py` | 73, 116, 65 |
| `rvw/src/rvw/formal/isa.py`, `riscv_proof.py`, `riscv_abstract.py` (verdicts) | 134, 97, 134 |
| `rvw/src/rvw/formal/sail_zicond.py` | 229 |
| `rvw/src/rvw/formal/security/pair.py`, `policy.py` (binding and verdict) | 129, 199 |
| `rvw/src/rvw/cov/functional.py` | 343 |
| `rvw/src/rvw/cov/mutation.py` (classification) | 609 |
| `rvw/src/rvw/cov/exchange.py` (status only) | 209 |
| `rvw/src/rvw/lint/cdc.py`, `rdc.py` | 382, 213 |
| `rvw/src/rvw/regress/mmu.py` (reference and check) | 826 |
| `rvw/src/rvw/memory/axiomatic.py`, `multihart.py` | 383, 99 |
| `rvw/src/rvw/privilege/epmp_matrix.py` | 93 |
| `rvw/src/rvw/vip/` `axi`, `axis`, `tilelink`, `wishbone`, `uart`, `spi`, `sram`, `gpio`, `interrupt` (`finish`), `catalog`, `declared` | 396, 228, 278, 127, 175, 165, 98, 104, 76, 122, 46 |
| `rvw/src/rvw/csr/` | 173 |
| Part 2a fixes: `plan/cli.py`, `farm/workflows.py`, `farm/service.py`, `mcp/envelope.py`, `fault/campaign.py`, `sec/campaign.py` | 42, 65, 235, 29, 339, 226 |

### Findings

| ID | Finding | Label | Action |
|---|---|---|---|
| F1 | `rvw formal app-live` gave `pass`, `proof_kind: liveness_to_safety`, exit 0 for a unit that hangs forever, when the fairness predicate was a DUT output that the hang keeps false. Reproduction: `module hang` sets `stuck` on the first `req`, never drives `resp`, and outputs `busy = stuck`. Plan: `request: req`, `response: resp`, `fairness: ["!busy"]`, `--mode prove`. The hung loop never satisfies `!busy`, so the loop monitor never fires. The same design with `fairness: ["ready"]` (a free input) gave `fail`. The limits text said "Fairness feasibility is not established", but the status and exit code said proof. Fairness of the form "the unit is idle infinitely often" is a normal thing to write. | realistic | Fixed in [#1283](https://github.com/riscPrint/risc-v-workstation/pull/1283). `fairness_check` is now `no_fairness`, `free_inputs` or `not_checked`. A safety pass is a proof only for `no_fairness` or `free_inputs` (every fairness expression names only top-level inputs other than clock and reset, and the design has no assumptions). Otherwise it is `inconclusive`, exit 3. A `fail` stays `fail`. The native regression test failed before the fix. |
| F2 | `rvw cov functional` credits bins from every supplied C2 trace, including traces of failing runs and traces without an end record. The report does not record each trace's end status. A plan counts these bins toward `reported_closed`. | unusual | Not fixed. Coverage reports have no `pass` verdict, and the plan contract says `reported_closed` is a planning count. Recording each trace's end status, and leaving out traces that did not end with `pass`, is a small owner decision. |
| F3 | The AXI, AXI-Stream, TileLink-UL and Wishbone monitors accept `finish()` with zero sampled transactions. The GPIO, interrupt, UART and SRAM agents refuse it. A project bench that relies only on `finish()` passes with a monitor on the wrong clock. | unusual | Not fixed. The generated declared-bus bench asserts `monitor.transfers > 0` and a positive check count. The typed-bus skeleton raises `NotImplementedError` until the project writes its scoreboard. |
| F4 | A `--case` split or `--operand-prefix` partition of `rvw formal datapath` reports `status: proved` for its sub-domain. The operand partition adds "only the recorded operand b partition" to `scope`; an FP case split records only `case`. | unusual | Not fixed. No code composes partitions into a full-width claim. The HardFloat campaign ledger keeps one row per case, and the contract says a case pass applies only to its recorded case. |

| F5 | `rvw memory axiomatic` (`memory/axiomatic.py`) takes address, data and control dependencies from the core adapter's C2 events when the header says `memory_dependencies: complete`. It does not derive them from the RVFI register fields. An adapter that declares `complete` but leaves out an edge removes preserved-program-order edges, so a forbidden execution can be reported `allowed`. | unusual | Not fixed. The header is an explicit adapter declaration, and the check refuses traces without it. Deriving register dependencies from `rs1`/`rs2`/`rd` and checking them against the declared sets would be a small owner decision. |

### What holds

- Cosim Spike shim (`scalar_split_ram`): the policy aggregates a misaligned
  access only when misaligned emulation is on, the access is an ordinary
  scalar load or store to bare RAM (M-mode, or U-mode without S), PMP decides
  every byte the same way, no byte is in MMIO, the access stays in one page,
  and the logged byte effects cover the access exactly once. Anything else is
  a refusal, never a match. The record keeps the unaligned address, so a core
  that reports another address gives a mismatch, not a match.
- Cosim synchronization: `mmio` sync injects the core's bus data into the
  reference and then still compares `rd_wdata` on all bits. A fixture with an
  MMIO `lb` that the core zero-extends gave `mismatch` with every sync kind on.
  Only `counter` reads take the whole `rd` value, as the name says.
  `illegal_insn_tval=zero` accepts zero only for cause 2.
  `ecall_tval` takes one declared value, never the core's. `mode_after_change`
  accepts the core's mode only when it equals the reference's mode after the
  trap or xRET, and the next instruction's mode is still compared.
  `fcsr_reset=unspecified` seeds FCSR once, before a state-neutral first
  instruction from reset.
- Sail adapter: the core trace gives only the step count and the refusal of
  counter, MMIO and input-interrupt records. Expected values come from Sail's
  own trace. A Sail run that ends early is an error. Sail cannot synchronize.
- Spike replay shim: restore replays the action history in a fresh machine
  and checks every step's effect hash. A failed action poisons the session.
- Formal ISA: unbounded instruction checks give `proven` rows only from a
  portfolio pass, and the overall `rvw.riscv-proof/1` and
  `rvw.riscv-abstract/1` statuses are never `pass` (`fail` or
  `inconclusive`). Sail-generated Zicond, M and bitmanip modules
  are generation only. They refuse live exception logic and record every
  lowering.
- IC3 lemma reuse: cached lemmas need `fresh_unbounded` certification and an
  equal transition-cone hash. They enter the target only as extra
  assertions, never assumptions, and the target always needs a fresh native
  proof. A stale lemma after an RTL change can only fail or miss the cone.
- Finite-graph fair liveness (`fair_live`) is `inconclusive` when no fair
  infinite path exists. The AIGER liveness path keeps a fairness pass
  `inconclusive` without a separate feasibility result.
- Formal security pair: secrets must be inputs and observations outputs. DUT
  formal cells and nondeterministic cells are refused. The micro-observation
  assertion is conditional on equal architectural prefixes, as the
  `semantics` field states.
- Formal IFT secure path (`security/policy.py`): sources must be inputs and
  sinks outputs, DUT formal cells are refused, and the sink assertion is
  gated only by reset and an optional declassifier that is a free public
  input. Taint over-approximates (a tainted bit may take either value), so a
  pass is conservative.
- Mutation: a mutant is `killed` only on a test `FAIL`. The unmutated control
  must pass every detection and equivalence test, so a broken build
  environment makes the whole report `inconclusive`. Any result other than
  `PASS` or `FAIL` is `error`.
- CDC: Spinal library class names only annotate a crossing. The kind comes
  from structure (stage count, direct path, fanout, width, Gray source). A
  library match never makes a crossing safe.
- RDC: `protected` needs a declared isolation with a reason whose qualifier
  is structurally in the destination fan-in, or a declared reset order. A
  qualifier outside the fan-in is an error finding.
- MMU suites: a scenario passes only with one conclusive C1 pass for its ELF
  and a complete strict Spike or Sail trace match with no synchronization. The
  self-checking expectations come from the scenario declaration, and
  `mmu reference` runs them on Spike separately.
- Privilege: the Smepmp matrix takes its expectations from a hand-written
  specification table, not from the checker. The campaign check needs the
  C1 self-check and a strict reference match.
- Coverage exchange exports have status `reported` and
  `proof_exclusions_verified: false`. They carry no verdict.
- CSR checks never report a pass: a matching device-event check stays
  `inconclusive`.

### Summary of Part 2

| Label | Count | Findings |
|---|---|---|
| realistic | 1 | F1 (fixed in [#1283](https://github.com/riscPrint/risc-v-workstation/pull/1283)) |
| unusual, fixed | 6 | D5, R1, M1, D3, D2, C1 (from Part 1) |
| unusual, recorded | 4 | F2, F3, F4, F5 |
| owner decision | 2 | D4, C2 (contract text above) |

### Not reviewed

- Cosim: the online and lockstep transports beyond their prefix rule, DII,
  external PLIC replay, device environment replay, QEMU observations,
  `sail_config.py`, the vector and hypervisor paths of the shim.
- Formal: Sail state slices and bitmanip details, SVA liveness lowering (`liveness.py`,
  `nested_eventually.py`), deep grids, native SVA, the IFT
  cell transfer rules in `security/ift.py`, memory refinement, equivalence partitions, UF proofs.
- Coverage: the proof-exclusion builder beyond
  `apply_exclusions`, probe goals, semantic observers.
- Lint: SDC backend, `structural.py`, lint waivers beyond Part 1.
- Suites: MMU submodules (`mmu_*.py`), privilege device models
  (PLIC/APLIC/AIA, timers), the memory-order candidate search beyond its
  input rules, concurrent memory campaigns, VexiiRiscv
  and arch-model areas.
- VIP agents other than the monitors' `finish()` checks; Uvm/ conformance.
