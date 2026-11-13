# Agent benchmark

Run a deterministic fixture benchmark without an LLM or native EDA tools:

```sh
rvw agent-bench dry-run --pack examples/agent-bench/tasks.json --out /tmp/agent-bench-good
rvw agent-bench dry-run --pack examples/agent-bench/tasks.json --agent careless --out /tmp/agent-bench-careless
```

Use a new output directory for each run. `results.json` contains the pack SHA-256,
agent name, fixture track, per-task transcripts, final candidates and scores.
Times are wall seconds from session creation. The median excludes censored cases;
use the reported root-cause and censored counts with it. Agent API latency and
native execution time are not measured by a scripted fixture run.

For an MCP client, start one task per stdio process:

```sh
rvw agent-bench serve --pack /evaluator/tasks.json --task task-03 --out /evaluator/run-03
```

The client gets only `bench_inspect`, `bench_diagnose`, `bench_reject`, `bench_patch`,
`bench_finish` and rvw's job status tools. This server constructs an explicit rvw
registry. It ignores plugin discovery. `bench_finish` ends the attempt; close the
stdio client to store its result. Disconnects retain an incomplete result.
There is a 32-call budget. A supervisor must enforce a wall-time limit for an
external client. No external LLM integration is included.

## Decisions

- Use the existing rvw ToolSpec, schema validation, registry and MCP stdio server.
- Store expected values and cause labels only in the evaluator pack. Do not return
  hidden tests or correctness feedback to an agent. The committed example pack is
  public test data. It is not suitable as a private production benchmark.
- Give the agent only a tool client. Do not grant shell, filesystem or network
  tools. The server is not an OS security sandbox. C8 excludes hostile inputs.
- Use a fixed expression grammar; never execute submitted code. The independent
  oracle compares results with stored vectors, not the expected patch text.
- Count only the final candidate as a fix. Keep each attempted patch in the log.
  A right cause requires a right statement and valid supporting artifact IDs.
  Evidence rejection requires the right artifact ID and mismatched identity field.
- Keep scores separate from C1 results and C4 acceptance. A fixture success is
  not a core repair result. Native validation is always `NOT RUN` in this track.

## Limits

The ten example tasks are eight synthetic Spinal expression models and two
VexRiscv ALU behavior models. They are not ten qualified native core mutations.
No Scala compiler, simulator, Spike checker, waveform parser or design database
runs here. Artifact identities and observations are fixture data. Source IDs are
local to each task. The scripted baseline maps the public operation requirement
to an expression. It tests the harness; it does not demonstrate agent reasoning.
Held-out vectors cover boundaries and seeded pseudorandom inputs, not all inputs.

See [the design](../../../../docs/design/agent-bench.md) for native qualification,
external clients and issue #27 acceptance. Tests: `rvw/tests/test_agent_bench.py`.

## Native seeded tasks

Build the benchmark ISA programs first:

```sh
nice -n 15 rvw/.venv/bin/python examples/agent-bench/build-native-tests.py \
  --source /path/to/pinned/riscv-tests --out examples/agent-bench/out/isa-control
```

The builder pins riscv-tests at `d7e86f701b929b5d801f8cda1a4871ab05f452bb`.
It adds `csrw mscratch, zero` as the first instruction. The core does not reset
this register. This write defines the first post-instruction CSR snapshot.
Strict comparison stays enabled. Unchanged ISA inputs passed C1 but first
mismatched Spike at PC `0x80000000` on the undefined `mscratch` snapshot.
These benchmark programs retain the named ISA test bodies and use an explicit
startup state. They are separate from the example's original ISA programs. Use the source revision in
`examples/agent-bench/native.json`. Keep the source checkout outside this repo.

```sh
rvw agent-bench native-qualify --pack examples/agent-bench/native.json \
  --source /path/to/pinned/core --out /tmp/native-tasks
```

Use `--task xor` to select one task. Each adapter call has a 110-second limit.
The example uses the private `vex-agentbench` and `sbt-agentbench` locks.
It limits native make jobs to two and uses nice level 15. The generic runner takes core
paths, mutations, config and workload names from the pack. It never edits the
source checkout. The runner first checks an unmutated copy, applies the seed, then reverses it
and checks the repaired copy. Each phase records its batch wall time.
Strict Spike checks must match baseline and repaired traces. Each failing seeded
trace must have a first mismatch. The report retains that instruction and the
reference check time. Missing Spike evidence cannot qualify a task. Each task needs a failing workload and passing
control workloads. C1 status, C2 completion and matching identities are required.
Both runs must use the same ELF, seed and config, and different RTL hashes.
Missing evidence is inconclusive. Reports retain every run path and identity.
MCP tool: `agent_bench_native_qualify`.

These ten tasks use the real VexRiscv example. The repair is evaluator supplied.
Qualification tests the task, not an agent. Dynamic Scala cause links, native
synthetic-core tasks and external agent repairs remain open in #364 and #27.
A native task result is not C4 acceptance.

## Misleading and incomplete evidence

`examples/agent-bench/misleading.json` adds five fixture tasks: a stale RTL hash,
a wrong ELF hash, unsupported observation fields, incomplete coverage and a
missing run end. Run this pack with `dry-run` or an external MCP client.
The public observations identify the evidence limits. The evaluator records
whether the agent rejects each artifact for the correct reason and preserves
an inconclusive outcome. A correct arithmetic patch cannot earn a repair result
when required evidence is missing. A claimed fix counts as a false fix in that
case. The report retains the required and preserved inconclusive counts.
These are declared fixture defects. They do not validate real wave or ELF files.

## Bounded external client trials

```sh
rvw agent-bench trial --pack examples/agent-bench/tasks.json --task task-03 \
  --out /tmp/external-baseline --budget-s 30 --max-calls 32 --repeats 2 \
  --model 'scripted MCP baseline' -- python -m rvw.agent_bench.external_client
```

Replace the client argv after `--` with the external agent CLI. Configure that
client to use only the supplied MCP endpoint. Disable its other tools.
The runner passes `RVW_BENCH_MCP_URL` and `RVW_BENCH_MCP_TOKEN` in the child
environment. It does not pass a task pack path or hidden checks to the client.
The child starts in an empty trial directory. The evaluator serves only the
fixture tool allowlist. The runner does not grant shell or file tools over MCP.
It is not an OS sandbox. An independently configured CLI still has its host
permissions. Hostile clients are outside C8 scope.

The runner stops the process group at the wall-time limit. The evaluator owns
the session and retains partial transcripts on timeout, disconnect or a missing
client executable. Its call limit includes invalid and rejected requests.
Each repetition records the command, model label, machine, budget, wall time,
exit code, task pack digest, scores and denominators. The token is not stored.
`results.json` is updated after each repetition. Incomplete trials stay in the
denominator. Existing output directories are refused.

MCP tool: `agent_bench_trial`. The scripted client uses the same external MCP
path as other clients. `careless`, `disconnect` and `timeout` arguments exercise
negative paths. No LLM trial is implied by a scripted result. This command uses
the fixture track. It cannot earn native repair acceptance or replace review.

## Native repair loop

```sh
rvw agent-bench repair-prepare --pack examples/agent-bench/native.json --task xor \
  --source /path/to/pinned/core --out /tmp/repair-task
# The agent works in /tmp/repair-task/workspace.
rvw agent-bench repair-check --challenge /tmp/repair-task/challenge.json \
  --out /tmp/repair-check
```

Preparation copies the core and project files into a disposable workspace.
The public `TASK.md` names the symptom and failing program. The example includes
its adapter, ISA ELFs and private `vex-agent` lock. The original checkout stays
unchanged. Preparation runs the seeded failure and passing controls before the
agent starts. A missing reproduction is inconclusive. For a reproduced failure,
it runs `rvw bundle` without reruns and `rvw cosim check`. It retains both tool
outputs, errors and exit codes. A missing reference tool cannot earn a match.

The agent follows `rvw agent guide --workflow test-fails --json`. The checker
copies only candidate core source changes into a fresh seeded workspace. It
uses the evaluator's programs and adapter. Edits to project files or tests do
not change the checks. Each check keeps a candidate patch, its digest, source
file list, ignored edits and C1/C2 evidence. Results are `repair_verified`,
`repair_rejected` or `inconclusive`. A verified repair requires the reproduced
failure, repaired fail-to-pass programs and unchanged passing controls with
matching ELF/seed/config identities and different RTL hashes.

MCP tools: `agent_bench_repair_prepare`, `agent_bench_repair_check`.
This is a bounded benchmark repair check. C4 acceptance is not claimed. A human
must review the retained patch and results. Dynamic C6 statement joins and
cause ranking remain open in #27. The root cause stays unknown until such
observations exist. Fixture tests of this loop are not native repair evidence.

The checker also requires the same recorded harness revision in both runs.
A harness change between failure and repair leaves the check inconclusive.

## MCP evidence solver

`rvw agent-bench evidence-solve --plan PLAN.json --out NEW_DIRECTORY` drives
regression, cosim, bundle, query and wave tools over MCP stdio. It records
source locations in tool traversal order. See [the workflow](solver.md).
MCP tool: `agent_bench_evidence_solve`. Native localisation ranks are not yet
measured. The solver does not edit sources or earn repair acceptance.

## OoO Mini task inputs

[The second-core pack](../../../../examples/agent-bench/ooo-mini.md) declares ten
source mutations at a pinned example commit. They cover wakeup, rename,
free-list release, recovery, store forwarding and load/store ordering.
Source round trips are checked. Native detection and monitor activation are
not yet measured. A named workload in this pack is a proposed detector.


The pass-to-pass control writes `mscratch`, forms the tohost address, then
stores a passing value. It does not use branch comparisons, bitwise ALU,
loads or shifts. ISA programs use these operations during startup and can
therefore fail as controls for a seed in those operations. The control is
separate from the failing ISA body. Native runs stop after 10,000 cycles.
A complete C2 cycle-limit run can detect a seeded fault only when strict Spike
comparison has an explicit architectural mismatch. A wall timeout, missing end
or matching prefix remains inconclusive. Raw C1 timeout status is retained.

## Actual native evidence admission

`rvw agent-bench audit-run --run-dir RUN --elf ELF --expected IDENTITY.json`
checks actual C1/C2 files against task-owned identities. MCP tool:
`agent_bench_audit_run`. Use `--require coverage.dat` to require that artifact.
Presence does not establish coverage completeness. A consistent old C1/C2 pair
needs the intended task identity to be rejected as stale. Admission cannot earn
repair credit. The independent repair checker still judges the candidate.

On 2026-11-13, replay from a real VexRiscv C1/C2 capture gave these results.
The original 527-retirement capture passed C1 and strictly matched Spike after
an explicit first-instruction `mscratch` write. The misleading cases edit copied
metadata or omit evidence. They do not execute a second core simulation.

| Input | Admission | Repair claimed |
|---|---|---|
| Consistent native pair | evidence_consistent | No |
| Old RTL pair against the seeded task hash | inconclusive | No |
| Different real ISA ELF | inconclusive | No |
| Unsupported C2 capability | inconclusive | No |
| Required coverage artifact missing | inconclusive | No |
| Native run end removed | inconclusive | No |

Regenerate these cases with a retained native capture:

```sh
nice -n 15 rvw/.venv/bin/python examples/agent-bench/audit-misleading.py \
  --run-dir BASELINE_RUN --elf MATCHING_ELF --wrong-elf OTHER_ELF \
  --stale-rtl SEEDED_RTL_SHA256 --out /path/outside/repository/new-audit
```

A controlled repair-runner test also checks a candidate that passes its named
program and fails a hidden independent program. It earns `repair_rejected`.
A native core run of that wrong-fix case remains NOT RUN.

## External trials on normal rvw tools

The scripted evidence solver can also use the external trial transport:

```sh
rvw agent-bench evidence-trial --plan PLAN.json --out NEW_DIRECTORY \
  --budget-s 110 --max-calls 32 --model 'scripted MCP evidence solver' -- \
  "$RVW_HOME/rvw/.venv/bin/python" -m rvw.agent_bench.solver_client
```

Use the same five-step plan as `evidence-solve`. The evaluator retains optional
truth. The client receives only public steps and budgets. It calls the actual
regression, cosim, bundle, drivers and wave tools over the bounded external MCP
endpoint. MCP entry: `agent_bench_evidence_trial`. The evaluator records responses
in the existing request log. It scores tool source-line rank and returned steps.
It records wall time, calls, missing observations and partial attempts.
The client cannot award its own successful workflow status.

This tool surface has no source-edit or independent repair-check tool. It gives
no repair credit. Any claimed fix is a false fix. Root-cause time stays censored;
a returned source line is not a causal proof. Use `repair-check` separately for
candidate sources. Supply qualified native inputs, a matching design database,
a waveform and project-owned signal bindings to measure native localisation.
A trial with missing inputs stays inconclusive. It does not become a native
repair result. See [the workflow inputs](solver.md).

The [fixture trial table](../../../../examples/agent-bench/external-trials.md)
records ten scripted fixture fixes and five preserved inconclusive cases with
zero false fixes. Those results test the fixture track, not native tools.

## Bounded cold-build retries

A cold Scala build can exhaust the adapter budget before simulation. Retain
its private workspace and retry without changing the source path:

```sh
rvw agent-bench native-qualify --pack PACK --source PINNED_SOURCE --out RUN
rvw agent-bench native-qualify --pack PACK --source PINNED_SOURCE --out RUN --reuse-workspace
```

Workspace reuse checks the source pin, tracked paths, clean state and every
source byte. It refuses a seeded or edited workspace. Each attempt reruns the
baseline and selected tasks. It archives the previous report and uses a fresh
output subdirectory. It reuses compilation state, not a passing verdict. A
changed pack gets a separate recorded digest. Keep each adapter budget short.

## Reproduce native tool measurements

`examples/agent-bench/measure-native-tools.py` verifies a clean private native
workspace before each campaign. It seeds one task at a time. It builds the
mutated design database through MCP, then starts the bounded external reference
client. The client runs the five-tool workflow through MCP. It selects the
observable mismatch field and finds its retirement order in the waveform.
The example supplies signal names. It supplies no mutated source line to the
client. Evaluator truth scores returned locations after the trial.

The helper retains the database build time outside the client budget. Each
client has 110 seconds and 32 calls. All source changes stay in the private
workspace. The helper restores the original source bytes on exit. Use the
measured result table for tool limits. Source-line rank does not grant repair
credit. The benchmark-owned OoO debug description supplies bundle metadata.
It does not change the pinned core.
