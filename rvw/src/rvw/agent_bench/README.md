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

Build the VexRiscv example ISA programs first. Use the source revision in
`examples/agent-bench/native.json`. Keep the source checkout outside this repo.

```sh
rvw agent-bench native-qualify --pack examples/agent-bench/native.json \
  --source /path/to/pinned/core --out /tmp/native-tasks
```

Use `--task xor` to select one task. Each adapter call has a 110-second limit.
The example uses the private `vex-agent` lock. The generic runner takes core
paths, mutations, config and workload names from the pack. It never edits the
source checkout. The runner checks a seeded copy, reverses the seeded change,
and checks the repaired copy. Each task needs a failing workload and passing
control workloads. C1 status, C2 completion and matching identities are required.
Both runs must use the same ELF, seed and config, and different RTL hashes.
Missing evidence is inconclusive. Reports retain every run path and identity.
MCP tool: `agent_bench_native_qualify`.

These ten tasks use the real VexRiscv example. The repair is evaluator supplied.
Qualification tests the task, not an agent. Dynamic Scala cause links, native
synthetic-core tasks and external agent repairs remain open in #364 and #27.
A native task result is not C4 acceptance.
