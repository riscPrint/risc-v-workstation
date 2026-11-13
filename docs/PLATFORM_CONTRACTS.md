# Platform contracts

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

## Observed SoC transaction pairs

`rvw.soc-events/1` starts with `observation=rtl_request_response_retire_tags`,
`data_bytes`, `trace_sha256`, `source`, `rtl_sha256`, `elf_sha256`, `seed` and
`run_id`. The latter fields must match the selected C1 simulation identity.
Ordered `request` records contain cycle, unique tag, aligned address, Boolean
write, mask and data. `response` records contain cycle, tag, data and Boolean
error. `retire_link` records contain cycle, C2 order and a unique request-tag list.
Project probes must observe request-to-retirement tags independently.

`rvw.soc-pairing/1` reports pairs, comparisons, unpaired requests, gaps and input
hashes. Addresses and data use little-endian byte lanes. Contradictory observed
values report mismatch and exit 1. Matching or missing evidence remains
inconclusive and exits 3. Unknown/reused tags and identity errors exit 2.
Address-only pairing is not supported. Existing harness capture version 1 does
not supply these transaction identities. No full DUT/bridge proof is implied.

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

### Automatic component app bindings

Generated app plans can contain `fifo_stream`, `arbiter_transfer` and
`counter_wrap`. Typed channel maps use exact valid, ready and payload endpoints.
FIFO capacity comes from the selected component's memory structure. Counter wrap
failures are reached observations. CAM address bounds do not establish key-match
semantics. Public ports remain in the interface even when the database marks
instance use as pruned; native interface validation remains required.
