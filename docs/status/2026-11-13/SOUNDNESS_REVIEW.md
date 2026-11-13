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
