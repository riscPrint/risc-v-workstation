# Platform contracts

### Shared C1 batch shard plans

`farm plan` copies ELF inputs by hash and writes one run-many manifest per shard.
Every expected cell binds its ELF hash, config, seed and declared options.
Additional identity claims cannot override manifest identities. Local and cluster
executors consume the same command/result plan. Shared PVC paths must match the
collector path. Collection never promotes process success to a DUT/gate verdict.

### Live farm views and checked crash cleanup

The owner-scoped live view reads validated C3 observations from owned job
folders. C5 reads stay within that job. Trends retain absent samples. Queue
attempt directories separate retry evidence. Explicit C1 DUT retries retain
all failures; identity-matched mixed outcomes can mark instability but cannot
waive a failure. SSH crash cleanup requires checked process start identities
and no live owned groups before releasing the dead worker's reservations.

### Authenticated remote MCP transport

MCP SSE requires bearer authentication on both session and message endpoints.
Each token has an explicit tool allowlist, fixed project and separate job store.
Clients can inspect and cancel only their own jobs. Remote calls use owned workers
and optional per-client per-run supervisor budgets. Disconnect does not cancel;
server shutdown does. Read-only roles are limited to the implemented query list.
No new verification verdict or hostile-input guarantee follows from transport.

### Persistent agent workflow plans

Farm workflow plans retain node IDs, command arrays and dependency IDs separately
from verification evidence. Queue jobs bind workflow/node IDs for resume. Only
completed dependencies admit a node. The SQLite event sequence supports SSE
replay by Last-Event-ID. HTTP event access is restricted to the token owner.
Workflow completion means execution complete, not a C4 acceptance or DUT pass.

### Cross-tool evidence queries

`rvw.evidence-query/1` retains full recorded observations and their source path,
SHA-256, schema and validation scope. Queries recheck originals and explicit
`evidence_dependencies` path/hash links. Missing, changed or invalid evidence
has inconclusive integrity. Recorded status is never replaced with an inferred
accept. JSON-only validation is distinct from C1/C3/C4 schema validation.

### Farm impact selection

`rvw.impact-selection/1` binds test observations to a design database hash.
It retains mandatory tests and unknown effects, reports deadline overruns and
uncovered signal paths, and ranks optional tests by marginal impact per second.
Existing coverage-selection fallback is preserved. Selection is advisory and
cannot earn gate acceptance. Recorded wall times are estimates, not guarantees.

### Farm failure clusters

`rvw.failure-clusters/1` retains original per-test evidence and source identities.
Clusters preserve core/configuration and infrastructure/DUT category boundaries.
Known-failure matches do not waive failures. C5 creation uses one representative
per cluster with reruns disabled. The optional diff uses existing C3/C4 identity
and seed checks; missing or changed evidence cannot establish a fix.

### Queue cumulative budgets

`rvw.queue-cost/1` records cumulative run, agent or project usage and configured
limits. Core-hours equal declared cores times attempt wall seconds divided by
3600. Attempts include retries, cancellation and cleanup. Active attempts reserve
their bounded maximum charge during admission. A worker timeout enforces the
smallest remaining scope limit; cleanup can exceed that limit and stays charged.
Execution states do not replace C4 verdicts. Monetary cost requires an explicit
rate; absent rates stay null.


The file formats and commands the phase 1 and 2 tools share. Every tool reads and writes these, so
they can be built in parallel and swapped out later. Change a contract only by editing its file
under `docs/contracts/` in the same commit as the code that needs it.

This file is the index. Each topic has its own file under `docs/contracts/`. To add a contract,
add a `##` section to your area's file. If your area has no file, create
`docs/contracts/<area>.md` and add one line for it to the list below. Do not put contract text
in this file.

Principles (from `ROADMAP.md`):

- Deterministic work is code with a command-line interface; every command has `--json` output.
  With `--json`, stdout is exactly one JSON document (on failure, the command's error document, as
  `rvw cov` and `rvw cosim` write, or nothing); progress and human messages go to stderr.
  The document is serialized in full before it is written; bundle, reduce, bisect, cov, regress,
  wave and perf also refuse NaN and Infinity (exit 2). `rvw/tests/test_json_stdout.py` runs every
  subcommand that has `--json` (error paths, and bundle/reduce/bisect on a fake-adapter failure).
  Agents reach the same commands through the MCP server (`rvw mcp`).
- Reuse open-source tools (Verilator, Spike, Sail, SymbiYosys, Yosys, mcy, SpinalTrace, Surfer) and
  write only what they lack.
- Generic first. Anything specific to one core (signal names, configs, test lists, paths) lives in
  an adapter or a config file, never in the generic code. BOOM is the first adapter.
- Every result records how to reproduce it: source revision, config, seed, ELF hash, tool versions,
  and a replay command.

## Core contracts

- [Project configuration (`rvw.project/1`)](contracts/project.md)
- [C1. Run contract (core adapter)](contracts/c1-run.md)
- [C2. RVFI trace (`rvfi.jsonl`)](contracts/c2-rvfi-trace.md)
- [C3. Suite results (`rvw.results/1`)](contracts/c3-results.md)
- [C4. Verdict (`rvw regress compare`)](contracts/c4-verdict.md)
- [C5. Failure bundle (`rvw bundle`)](contracts/c5-bundle.md)
- [C6. Design database (`rvw query`)](contracts/c6-design-database.md)
- [C7. MCP tools (`rvw mcp`)](contracts/c7-mcp.md)
- [C8. Input capture and result generations](contracts/c8-capture.md)
- [C9. Native architecture models](contracts/c9-arch-models.md)
- [Resources](contracts/resources.md)

## Area contracts

- [Agent benchmark](contracts/agent-bench.md)
- [Architecture model extensions](contracts/arch.md)
- [Connectivity and riscv-formal bindings](contracts/connectivity.md)
- [Co-simulation transports and capture inspection](contracts/cosim.md)
- [Coverage](contracts/coverage.md)
- [Component simulations](contracts/csim.md)
- [CSR and register maps](contracts/csr.md)
- [Debug module and sessions](contracts/debug.md)
- [Equivalence and datapath checks](contracts/equiv.md)
- [Cross-tool evidence](contracts/evidence.md)
- [Farm and job queue](contracts/farm.md)
- [Proof cores and counterexamples](contracts/formal-cex.md)
- [Deep formal runs](contracts/formal-deep.md)
- [Formal checks and SVA](contracts/formal.md)
- [Hardware leakage](contracts/leakage.md)
- [Lint and CDC/RDC](contracts/lint.md)
- [Memory order and multi-hart](contracts/memory.md)
- [MMU suites](contracts/mmu.md)
- [Verification obligations](contracts/obligations.md)
- [Performance and pipeline events](contracts/perf.md)
- [Power intent](contracts/power.md)
- [Privilege and interrupt suites](contracts/privilege.md)
- [Design queries](contracts/query.md)
- [Setup and adapter selection](contracts/setup.md)
- [Simulation server and native ports](contracts/sim.md)
- [SoC project data](contracts/soc.md)
- [Random stimulus](contracts/stimulus.md)
- [UVM flow](contracts/uvm.md)
- [VexiiRiscv integration](contracts/vexii.md)
- [Protocol agents](contracts/vip.md)
- [Waveforms](contracts/wave.md)
- [Workloads](contracts/workloads.md)

## Layout

| Path | What | Language |
|---|---|---|
| `rvw/` | The `rvw` command: one Python package, a subpackage per tool (`rvw/src/rvw/<tool>/`, with `cli.py` defining `register(subparsers)`). Run with `rvw/.venv/bin/rvw` after `cd rvw && uv venv && uv pip install -e '.[dev]'`. Python ≥ 3.11, standard library first. | Python |
| `RiscvSim/` | Generic Spinal simulation pieces for any RISC-V core with RVFI (trace writer, tohost, ELF loading, the run contract's command line), and `RiscvSim/boom/`, BOOM's adapter. | Scala |
| `SpinalChecks/` | Assertions Spinal generates while elaborating, and the simulation-to-formal flow. | Scala, shell |
| `SpinalKonata/` | Generic Konata pipeline-trace library for Spinal designs. | Scala |
| `SpinalDB/` | One extraction pass over an elaborated Spinal design: the design database. | Scala |
| `scripts/with-lock.sh` | Machine-wide lock for heavy jobs (see Resources); a wrapper around `rvw/src/rvw/common/lock.py`. | shell |
