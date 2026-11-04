# Coverage-closing stimulus

## Goal and scope

Design for [#30](https://github.com/riscPrint/risc-v-workstation/issues/30).
The owner has selected this idea for design. This selection does not complete
its execution acceptance list. This PR is the design sub-agent's handoff.
Implementation and runtime measurements are NOT RUN in this design change.

Build a loop that selects an unhit bin, generates a bounded program, runs the
program through C1, checks C2 with Spike lockstep, and measures new bins.
Report newly hit bins per CPU-hour against a random baseline on each core.
A solver model or proposed assembly program never earns a hit.

The first slice targets integer ISA semantic bins on the external RV32IM
VexRiscv adapter and BOOM `small`. Core names, presets, RAM, startup and
termination code stay in project data. Do not change either core's sources.
Sequence/hazard and typed RTL goals use the same loop in later phases.
This is the stimulus side of portable stimulus. It does not implement the
Accellera PSS language, scheduling semantics, or a PSS conformance claim.

## Existing code and prior art

Reuse these modules. Do not create a second coverage engine or a second runner.

| Source | Existing behavior | Change needed |
|---|---|---|
| `rvw/src/rvw/cov/closure.py:closure` | Reads functional, RTL and code holes. Attaches declared candidates. | Keep this suggestion-only interface stable. Add a separate execution command. |
| `rvw/src/rvw/cov/semantic.py:groups,Observer` | Observes seven operand classes, five imm12 classes, CSR access, exceptions and mode transitions. | Lower supported goals to constraints. Keep observers independent of generator code. |
| `rvw/src/rvw/cov/functional.py:functional` | Captures traces, binds plan hashes and counts observed bins. | Add a stable payload sampling policy and per-ELF region manifests. Apply them before semantic sampling. |
| `rvw/src/rvw/cov/isa.py:plan` | Uses a core-owned ISA manifest and pinned opcode files. | Reuse legal encodings and source hashes for generation. |
| `rvw/src/rvw/cov/sequence.py` | Measures retirement-order pairs. | Later synthesize bounded pairs. Do not call these measured pipeline hazards. |
| `rvw/src/rvw/cov/rtl.py` and `closure.py` | Typed RTL observations and uncompleted RTL sequences. | Later use project-owned stimulus recipes and matching sample identity. |
| `docs/TEST_SOURCES.md` | Native riscv-dv pyflow route; PyVSC/Boolector build can block it. | Preserve that limitation. Do not silently replace a selected generator. |
| `Cosim/README.md` | A prefix can return match and exit 0. | Require full completion and inspect synchronizations before credit. |

Research sources:

- [RISCV-CTG overview](https://riscv-ctg.readthedocs.io/en/latest/overview.html):
  turns CGF coverpoints into CSP constraints and emits tests. Its operand and
  instruction templates are useful prior art. Adapt goals rather than importing
  a second expected-result engine.
- [Kumar et al., CARRV 2022](https://carrv.github.io/2022/papers/CARRV2022_paper_2_Kumar.pdf):
  describes ISAC coverage extraction and CTG test generation. This supports a
  separation between coverage measurement and generation. It gives no evidence
  for closure performance on our cores.
- [CHIPS Alliance riscv-dv](https://github.com/chipsalliance/riscv-dv):
  supports directed streams, random streams and ISS comparison. It is a later
  backend and an external baseline when its native dependencies work.
- [Z3 bit-vector guide](https://microsoft.github.io/z3guide/docs/theories/Bitvectors/):
  fixed-width operations have separate signed and unsigned comparisons.
  Use XLEN bit vectors and explicit signedness in constraints.

Choose a small Z3 backend for the first slice. It avoids requiring UVM and
limits translation to existing semantic predicates. This is a design choice,
not a measured comparison with CTG, riscv-dv, or commercial tools.
Do not copy upstream code without a separate license review under #37.

## Architecture

Extend `rvw cov` with proposed `generate` and `campaign` commands. These names
and schemas are proposals until implementation updates PLATFORM_CONTRACTS.md.
Keep generation code in the existing coverage package. Place generator
protocol, goal lowering and campaign control in separate small modules.

1. Capture the project, plan, initial traces, opcode files and tool identities.
2. Recompute holes from validated initial evidence. Do not trust a saved holes
   array as proof that a bin is absent.
3. Classify every hole as supported, unsupported, or excluded by existing proof
   rules. An unsupported goal remains in the full plan denominator.
4. Select an uncovered supported goal in stable ID order. Use a seeded tie break
   only when explicitly requested. Limit retries per goal.
5. Solve instruction fields and source operands. Record SAT, UNSAT, unknown,
   timeout, or missing backend. UNSAT applies only to this template and bound.
6. Emit source and payload symbols through a project-owned runtime. Compile it.
   Decode the emitted payload to check the selected opcode and constraints.
7. Run the exact captured ELF through C1 with RVFI enabled and fixed run limits.
8. Compare the full trace with Spike. Check C1 and cosim evidence together.
9. Recompute payload coverage with the same plan. Credit the set difference.
   Update the working hit set only from qualified attempts. Select the next hole.
10. Publish a sealed campaign generation. Keep failed attempts and their costs.

An agent can submit source through the same candidate manifest later. The agent
cannot supply expected hits, reference values, or accepted result JSON. Source
still passes compilation, opcode validation, C1, Spike and coverage checks.

## First instruction domain

Use R-type `add, sub, xor, or, and, slt, sltu` and I-type
`addi, xori, ori, andi, slti, sltiu`. Run in M mode without interrupts.
This gives 170 supported bins per XLEN before initial hits: seven R-type
instructions times two source fields times seven classes, plus six I-type
instructions times seven source classes plus five immediate classes.
Generate the actual set from the pinned manifest. A missing instruction refuses
this profile. Full ISA reports retain all other declared goals as unsupported.

For a source value `v`, solve an XLEN bit vector for the existing seven classes.
Use exact equality for zero, one, all ones, signed minimum and signed maximum.
Use sign predicates plus exclusion of those values for the two remaining classes.
For imm12, use 12-bit values: zero=0, minimum=0x800, maximum=0x7ff;
positive=1..0x7fe, negative=0x801..0xfff. Encode then sign-extend as specified.

Constrain register indexes and pinned opcode mask/value fields. Reserve runtime
registers in project data. For the first profile use distinct writable operand
and destination registers. Never load a nonzero operand into x0. The assembler
must use `.option norvc` and `.option norelax`; validate the resulting bytes.
Use `.word` for the solved payload when needed. Operand setup can use `li`.

Mark each payload instruction with start/end symbols. Credit only those byte
ranges. Setup and termination can otherwise close visible `addi` bins without
exercising the requested operation. Bind the ELF-derived ranges to that ELF in
a captured region manifest. Include the stable sampling policy in plan identity;
keep per-ELF addresses in attempt evidence. Addresses can differ across programs
without changing the semantic bin universe. Do not merge these filtered reports
with ordinary full-trace coverage. Use full C2 for lockstep and filtered C2
observations only for campaign coverage. Initial evidence must use this same
policy and bound region manifests. Re-run legacy seed tests if these are absent.
Baseline and targeted programs use identical runtime and filtering rules.

CSR, exceptions, privilege transitions, memory, FP, compressed encodings and
unlisted instructions are unsupported for generation in this first profile.
Record a reason for each goal. Do not relabel it unreachable or remove it.

## Proposed interfaces and contracts

`rvw cov generate REPORT --campaign PLAN --goal ID --out DIR --json` emits
source, solver input/model and candidate manifest. It returns `generated`,
`unsupported`, `unsat`, or `inconclusive`. Generation never changes coverage.

`rvw cov campaign --project PATH --plan PLAN --out DIR --json` runs both arms
under fixed budgets. `cov_campaign` is the C7 job wrapper for the same API.
Keep existing `cov_closure` read-only. Do not turn a suggestion call into a run.

The proposed `rvw.stimulus-plan/1` has a pinned ISA/coverage plan, initial evidence,
backend, generator seed, instruction allowlist, project build command as argv,
runtime inputs, reserved registers, payload bound, attempt bound, solver timeout,
cycle/wall/CPU budgets and baseline distribution. Reject unknown fields.
Any project schema extension must be documented and validated in the same commit.

The proposed `rvw.coverage-campaign/1` records plan and initial-hit hashes,
project/config/XLEN, tools, input capture, arm, seed, attempt IDs, target IDs,
source/ELF/range hashes, C1 and cosim artifact hashes, before/after coverage,
new target and incidental bin IDs, reasons, cost and terminal campaign status.
Each attempt has a replay command. De-duplicate hits by plan-bound bin identity.
Keep existing human-readable group IDs; include plan hash in machine identity.

| Contract | Binding and limits |
|---|---|
| C1 run | Require conclusive `pass`, exact ELF hash, config, seed, cycle limit and requested options. Bind source, generated RTL, harness and native identities. A completion store alone does not check arithmetic. |
| C2 trace | Require nonempty trace, consistent header, continuous orders, final pass event and matching ELF. Compare full trace. Require Spike match, `trace_complete=true`, `end_status=pass`. No payload synchronization or DUT-derived operand/result substitution. Record runtime quirks and synchronization counts. |
| C3 suite | Keep attempt C1 results. Use the existing suite writer if exporting C3. A generated source is never a passed suite row. |
| C4 gate | A campaign report does not grant accept. A mismatch is a separate defect result. No coverage gain waives a failure or changes a gate. |
| C5 bundle | Bundle mismatches and crashes with source, solver input, ELF, plan, trace and replay. Failed attempts earn no accepted hits. |
| C6 database | No database dependency for ISA goals. Later RTL recipes bind exact elaboration, physical instance and sample plan. Structural paths do not prove event reachability. |
| C7 MCP | Use cancellable jobs and the same implementation as CLI. Cancellation stops the process group and preserves incomplete attempt records. |
| C8 capture | Use Capture and generation.publish/open_current. Capture runtime, linker script, solver, compiler, Spike/shim, adapters, environment and all result-changing inputs. Unknown dependencies refuse credit. Resume pins the prior generation and cannot reuse a changed plan. |
| C9 model | gem5 metrics are not RTL closure evidence. No C9 performance fit or timing claim follows from this campaign. |

Require each attempt's native/design identity to agree within an arm pair.
RV32 and RV64 reports stay separate. Do not merge XLEN, ISA, plan or RTL versions.
A mismatch stops that arm and keeps the issue unresolved. A passing attempt
that misses the goal records `miss`; qualified incidental hits still count once.

## Baseline and cost experiment

Pre-register the supported set, initial evidence, budgets and seeds. Both arms
start from the same initial hit set. The random arm never reads remaining holes.
Use the same instruction domain, payload count, runtime and run options.
The primary random baseline selects instructions uniformly, then samples each
operand class and immediate class uniformly and draws values within that class.
This boundary-aware baseline avoids an easy comparison with uniform XLEN data.
A uniform-bit baseline is optional and must be labeled separately.
Do not describe this small random backend as riscv-dv. Add a riscv-dv comparison
only when its pinned native backend runs with a matching domain and budget.

Run at least five paired seeds per core. Alternate arm order for each seed.
Use one worker. BOOM uses `small`, at most 16 payloads/program, 32 attempts/arm,
100000 cycles/run, 60 seconds/run, and 600 CPU-seconds/arm as initial limits.
Use the same limits for VexRiscv unless a preflight requires a documented change.
Do not tune budgets after seeing comparative results. Record overshoot by the
last bounded attempt. Stop at budget, saturation or attempt limit.

CPU time is user+system time for the controller and all descendants: solver,
compiler, simulation and Spike. Count failed attempts and retries in cost.
Implement per-attempt process-tree accounting on macOS; elapsed time is not a
substitute. If accounting cannot include descendants, the CPU-hour metric is
inconclusive. Record elapsed time and lock wait separately. Run arms sequentially
so child CPU deltas cannot include unrelated campaign workers.

Report cold build CPU and steady-state CPU separately. Charge the measured cold
build once to each arm for the end-to-end comparison, even when execution shares
a compiled model. Preserve the actual shared-build observation and allocation.
Never treat a prebuilt cache as zero-cost cold compilation.

Let H0 be the initial hit set and HA the union of qualified payload hits in an
arm. Gain is `|(HA - H0) intersect supported_bins|`. Rate is
`3600 * gain / cpu_seconds`. Count each new bin once per arm. Report gain,
supported denominator, full-plan unsupported count, costs, misses, reference
failures and saturation for each seed. Compare paired rates per core with a
seeded paired-bootstrap interval. A zero random rate gives no finite speedup;
report the rates and absolute difference. Show curves versus cumulative CPU
seconds when reporting measurements. No curve or numeric result exists yet.

## Acceptance tests

- [ ] Generate a currently unhit operand and imm12 goal. On each core, require
  full Spike match and a measured new payload hit. Re-run it: gain must be zero.
- [ ] Prove the second selection uses updated holes, not the original report.
- [ ] Check XLEN signed boundaries and all five immediate classes against fixed
  expected encodings and independent reference execution.
- [ ] Mutate an instruction, source register, immediate, result and target PC.
  Ensure misses or mismatches remove credit. Keep a separate held-out set of
  operand/result crosses and alias cases unknown to the selection policy.
- [ ] Reject empty/truncated trace, matching prefix, missing end, fail end,
  wrong ELF/plan/config/RTL, unexplained payload synchronization, stale files,
  missing tool and unknown dependencies. None can increase the accepted hit set.
- [ ] Kill a run and resume it. Preserve the old sealed generation. Charge the
  interrupted cost when measurable; otherwise mark the aggregate inconclusive.
- [ ] Verify unsupported sequence and RTL goals remain listed with zero generated
  hits. A solver UNSAT must not produce a proof exclusion.
- [ ] Run the fixed paired experiment on VexRiscv and bounded BOOM. Publish exact
  gains and CPU costs outside the repo. A negative result is still a valid result.
- [ ] Test CLI JSON success/error output and C7 parity. Run targeted coverage,
  cosim evidence and campaign tests only. Add failing tests before each fix.

## Risks and phased delivery

Z3 translation can duplicate a coverage bug. Keep lowering separate from
observation and use independent expected encodings, Spike and held-out mutations.
Sparse marginal bins can saturate quickly. Report saturation and later add
reviewed cross bins. Do not change the denominator mid-experiment.
Portable ISA actions cannot promise a microarchitectural event. RTL goals need
project recipes, actual samples and bounded exploration; speculative hazards
need separate event evidence. Core hooks remain outside this repository's scope.

1. Implement the ISA vertical slice, including the independent random backend,
   process CPU accounting, evidence qualification and two-core measurements.
   Update coverage README and PLATFORM_CONTRACTS.md with the implemented schema.
2. Add retirement-sequence constraints, branch/memory actions, a bounded action
   graph, resource constraints and seed replay. Distinguish ISA pairs from
   measured pipeline hazards. This is the next portable-stimulus slice.
3. Add project-owned RTL event recipes, exact sampling identity and guided
   mutations. Preserve unsupported and unproved goals. Compare to random again.
4. Add pinned riscv-dv/CTG backends and agent-proposed source through the same
   verifier. Propose CGF import/export upstream in the PR text; do not post it.

Implementation follow-ups:

- [#349: ISA loop and measured random comparison](https://github.com/riscPrint/risc-v-workstation/issues/349).
- [#352: bounded sequence actions](https://github.com/riscPrint/risc-v-workstation/issues/352).
- [#353: measured RTL event goals](https://github.com/riscPrint/risc-v-workstation/issues/353).
- [#33: shared external random generator](https://github.com/riscPrint/risc-v-workstation/issues/33)
  and [#48: suite integration](https://github.com/riscPrint/risc-v-workstation/issues/48)
  retain phase 4 ownership.

No core edits,
license decision, integration-model decision or complete #30 claim is authorized
by this design.
