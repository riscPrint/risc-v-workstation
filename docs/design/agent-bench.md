# Agent task benchmark

## Goal and scope

Measure an agent's bug-fix loop through a fixed rvw tool surface. Start with ten
seeded tasks and a scripted baseline. Keep task answers in the evaluator. Report
fixture results separately from native RTL results. This increment implements the
fixture track. Native Spinal and VexRiscv qualification remains a separate phase.
It does not close #27 or establish automatic root cause on a core.

## Research and prior art

[SWE-bench Verified](https://www.swebench.com/verified.html) uses reviewed tasks
and test patches. Adopt separate task descriptions and evaluator checks. Do not
adopt its container requirement. [VerilogEval](https://github.com/NVlabs/verilog-eval)
checks RTL generation and classifies simulator failures. Adopt functional checks,
not text equality with a gold patch. Neither supplies the rvw evidence-identity
challenge proposed here.

Existing code: `rvw/mcp/spec.py` defines tools; `registry.py` validates arguments;
`server.py` serves stdio. `bundle`, `query`, `wave`, `cosim` and `regress` already
implement the intended native loop. `examples/vexriscv/README.md` defines the
external RV32IM adapter. Issue #27 requires stable links from architectural effects
to transactions and Scala statements, reproduced failures, independent checking,
and incorrect-repair rejection. A fixture benchmark cannot earn those native claims.

## Architecture

Use a private task pack, one evaluator session per task, and an explicit allowlist
of benchmark tools in an rvw MCP registry. Do not discover normal tool plugins in
this server. An agent can inspect a task, inspect evidence, submit a cause with
stable statement IDs, propose a bounded source-expression replacement, and finish.
No shell, arbitrary file read, hidden test access or evaluator score tool is exposed.
The evaluator logs tool calls and monotonic elapsed time. The scorer alone reads
hidden vectors, expected causes and evidence defects. The scripted agent uses the
same registry calls. A second careless baseline exercises incorrect-fix detection.

Ten tasks cover add/sub, bitwise logic, shifts, comparisons and branch conditions.
Eight are synthetic component tasks; two reserve VexRiscv ALU decode scenarios.
The fixture track uses small integer semantics and Spinal source expressions.
VexRiscv fixtures model ALU behavior, not execution of the upstream core. Native
packs must pin a source revision and apply mutations in a disposable copy.

## Interfaces and contracts C1–C9

| Contract | Use |
|---|---|
| C1 | Native runner must retain run/config/seed, ELF and generated RTL identity; fixture reports are not C1. |
| C2 | Native cause records cite first wrong retirement order and architectural field. Fixture observations use stable local IDs only. |
| C3 | Native hidden workloads include fail-to-pass and pass-to-pass cases. Do not write fixture scores as suite passes. |
| C4 | Benchmark correctness is separate from gate accept. Human review remains required. |
| C5 | Native observations come from failure bundles with artifact identities. |
| C6 | Native statement IDs must resolve in the captured database and source. Fixture IDs are task-local. |
| C7 | Reuse ToolSpec, Registry and stdio server; strict schemas and a closed tool set. |
| C8 | Compare evidence identities before use; reject stale waves and wrong ELFs. No security sandbox is claimed. Use an agent account with no filesystem/network tools. |
| C9 | Architecture-model timing cannot certify RTL correctness. No C9 model is used here. |

Task packs use `rvw.agent-tasks/1`. Reports use `rvw.agent-bench/1` and contain a
track, task-pack digest, baseline name, per-task tool transcript and scores.
Write results into a new output directory; never overwrite a prior run.
A task has public requirements, source statements and artifact identity claims.
Private fields contain reference semantics, held-out vectors, cause IDs and decoy
reasons. The tool boundary must not return private fields or evaluation feedback.

## Scoring

Time-to-root-cause is elapsed wall time to the first submitted cause with the right
statement and only valid supporting evidence. Missing causes are censored, not zero.
Correct-fix rate is independently passing final fixes divided by all tasks.
False-fix rate is claimed final fixes that fail checking divided by claimed fixes;
report both counts and use null for an empty denominator. Missing checks are
inconclusive, not incorrect fixes. Misleading-evidence recall counts correct
artifact-and-reason rejections over injected defects. Also report false rejections.
Do not collapse these measures into one number. Keep failed and timed-out tasks.
The fixture oracle evaluates all hidden input vectors independently of the agent;
it does not compare the proposed text with a gold patch.

## Acceptance tests

- Ten unique tasks; every mutation fails at least one hidden vector before repair.
- A correct fixture repair passes all hidden vectors; constant and wrong repairs fail.
- Stale-wave and wrong-ELF evidence cannot support a scored root cause.
- Rejection credit requires both the artifact ID and the correct mismatch reason.
- Unknown tools, extra arguments and attempts to select private fields fail.
- A real MCP stdio client can complete a fixture session without an LLM.
- Results retain attempts, task-pack identity, elapsed times and score denominators.
- Native execution is NOT RUN until actual adapters and independent checks execute.

## Risks and phased plan

Fixture vectors can miss errors. Use width boundaries and held-out pseudorandom
vectors. Public packs can contaminate future agent training. Keep production packs
outside agent workspaces and rotate private seeds. Tool-only access is a capability
boundary, not an OS sandbox. Source-text parsing is deliberately limited to a fixed
expression grammar. This slice cannot check arbitrary Scala patches.

1. Implement fixture task pack, restricted MCP session, scoring and scripted dry run.
2. Qualify actual synthetic Spinal elaboration and two pinned VexRiscv mutations.
   Run native regression and Spike checks under resource locks. Bind stable IDs.
3. Add external agent clients, process isolation, time budgets and repeated trials.
   Retain failure logs and compare agents only on the same pack and machine profile.

Follow-up work:
- [#364: native Spinal and VexRiscv tasks](https://github.com/riscPrint/risc-v-workstation/issues/364).
- [#366: bounded external agent trials](https://github.com/riscPrint/risc-v-workstation/issues/366).
