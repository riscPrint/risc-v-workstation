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
