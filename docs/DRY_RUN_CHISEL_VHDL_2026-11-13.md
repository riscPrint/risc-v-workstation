# Chisel and VHDL whole-core dry run, 2026-11-13

## Historical evidence availability

This document is a historical summary. Cleanup removed the external scratch
inputs, journals, raw logs and receipts. Their temporary recovery archives are
being deleted. Paths below identify the original locations, not available files.
The recorded runs cannot be replayed from this repository alone. Counts and
verdicts below describe the original runs, not fresh validation.


## Scope

Both cores live in independent Git repositories outside the workstation:
`wt/.dryrun3/chisel` and `wt/.dryrun3/vhdl`, relative to the saviour workspace.
Each repository uses a root `rvw.toml`. `RVW_HOME` selects the installed
`wt/deep` checkout, and its `rvw/.venv/bin` is on PATH. Core sources, native
outputs and the full command journal were stored outside the workstation.
`wt/.dryrun3/JOURNAL.md` records commands, exit codes, times and log names.

The source pins are:

- riscv-mini: `ucb-bar/riscv-mini`, revision
  `3eda724c437c73f3192fcbaaf76ae93b5eb870b0`.
- NEORV32: `stnolting/neorv32`, revision
  `7bd0858bed243e5e32521a8ffbeef8c68b68c653`.

The initial workstation revision was `c29ad597`. Runtime evidence below uses
`5ac7bdee`, which includes the simulation-launcher fix. The old untracked
`deep/out` directory was moved to the scratch parent before checkout.
No subagent, BOOM build, full Python suite, long formal campaign or hardware
run was used. Native commands use `nice -n 10`. Scala builds use `sbt-deep`.

## Build choices

Riscv-mini already uses Chisel 6.2.0. Its pinned sbt 1.8.2 failed on JDK 21.
The scratch build uses sbt 1.10.7. Scala 2.13.7 was older than the Chisel
runtime dependency; the scratch build uses Scala 2.13.12. A project main emits
Core FIRRTL and Verilog through the core's Chisel stage. The tested core has
no caches. It keeps the upstream instruction and data cache interfaces.

Project-only observation wiring exposes retirement and architectural register
snapshots. `rvw formal state-generate` produces the monitor from `state-map.json`.
A project wrapper connects that monitor to the exposed core state. Native
simulation enables its assertions. The C2 stream comes from this monitor.
Generation alone does not establish adapter conformance or ISA proof.

The state kit needs Yosys-compatible Verilog. Default Chisel output contains
procedural local variables that Yosys refuses. The scratch firtool step uses
`disallowLocalVariables,disallowPackedArrays` and disables random initialization.
The FIRRTL database front end already applies these lowering options.

NEORV32 uses its smallest CPU configuration. Optional ISA extension generics
stay false. A project VHDL wrapper selects boot address `0x80000000`, enables
the trace port and flattens the record ports. The trace port supplies retired
architectural effects. No ISA state-monitor proof is claimed for this core.

VHDL simulation uses standalone `ghdl --synth --out=verilog`, then Verilator.
This reuses the C1, C2, waveform and coverage path without another simulation
adapter. It also avoids the GHDL Yosys plugin ABI in simulation. Database
extraction still uses that plugin and the VHDL XML source map.

The bundled plugin failed Yosys memory-cell validation. The existing matching
plugin in the local tool cache worked after `RVW_GHDL_PLUGIN` was set.
Verilator 5.049 failed internally on GHDL memory output. Verilator 5.052
compiled the design. A same-cycle bus acknowledgment then caused zero
retirements. Returning a response one cycle after the single-shot request
fixed the project harness. The upstream CPU was not changed.

## Measured steps

| Step | Chisel | VHDL |
| --- | --- | --- |
| Doctor and init | Existing `--hdl chisel` creates the stubs. Final doctor is ready with the smoke ELF and explicit reviewed platform. | Existing `--hdl vhdl` creates the stubs. Final doctor is ready with the restored smoke and explicit reviewed platform. |
| Core build and C1 | Core emits FIRRTL and Verilog. Monitor-enabled native smoke passes. | GHDL emits Verilog. Native smoke passes after the bus response fix. |
| C2 and smoke reference | Generated architectural monitor; 13 retirements match Spike. | Native trace port; 15 retirements in 49 cycles match Spike. |
| riscv-tests slice | add, beq, lw and sw: 4 pass, 0 inconclusive with the generated monitor. | Same four programs: 4 pass, 0 inconclusive. |
| Slice reference | All four captured ELF hashes checked. Spike matches 427, 253, 205 and 417 retirements respectively. | All four captured ELF hashes checked. Spike matches 428, 254, 230 and 453 retirements respectively. |
| Failure bundle | Planted instruction-response fault gives fail code 1 and bundle signature `fail:1`. | Planted instruction-response fault gives fail code 1 and bundle signature `fail:1`. |
| Query | FIRRTL whole-core database refresh succeeds: 9 components, 17,706 signals and 83,250 edges. PC drivers and loads return Scala lines. | Whole CPU plus trace wrapper: 11 components, 13,845 signals, 3 memories, 7,672 assignments and 58,998 edges. Trace-port queries return VHDL locations. |
| Diagram | Blocks export writes 129,262 bytes. Viewer rendering NOT RUN. | Blocks export writes 655,477 bytes. Viewer rendering NOT RUN. |
| Lint | 28,208 active findings across requested backends; native-only report has 62. No signoff. | 15,979 active findings across requested backends. No signoff. |
| Coverage | C1 merge/report: 6,089 of 19,738 points hit, 30.85 percent. Includes the wrapper and state monitor. | C1 merge/report: 15,469 of 57,336 points hit, 26.98 percent. |
| Declared checks | Request/response channels are unsupported by the declared ready/valid generator. No protocol relabelling is used to claim a check. | Same protocol limit. Use canonical lowercase GHDL module names in the map. |
| Gate | Committed good revision `63c4ef1` accepts against itself for one smoke test. Fault revision `3da7f8e` rejects with one new failure and no inconclusive evidence. The fault was reverted. | Committed good revision `adfaa10` accepts against itself for one smoke test. Fault revision `0031afb` rejects with one new failure and no inconclusive evidence. The fault was reverted. |

These are bounded tests of one configuration and a small software slice.
They do not qualify the full upstream ISA matrix, interrupts, CSR behavior,
misaligned transfers, memory wait states or a complete CPU proof.
The smoke coverage has no exclusions and does not establish closure.
The four programs use the riscv-tests copies retained by the preceding
PicoRV32 dry run, with an explicit tohost environment. They do not use the
full upstream privilege environment. The original test licenses are retained.
Coverage points refer to the emitted Verilog. Original-language statement
coverage is not established by these counts.

## Workstation fix and tests

[PR #1032](https://github.com/riscPrint/risc-v-workstation/pull/1032), merged,
changes VHDL init simulation builds to standalone GHDL synthesis. A unit test
checks the command, source paths with spaces and the emitted RTL passed to
Verilator. Queries retain the matching-plugin requirement.

Targeted test: 1 passed. First fast set: 2,056 passed, 1 skipped.
Release hygiene: 40 passed. Later fast set: 2,098 passed, 1 skipped.
MCP discovery had no skipped-module error. No full Python suite was run.

## Friction retained in the journal

Initial attempts used a wrong cosim project key, omitted the query export
output argument, omitted the test-header include directory and omitted
`source_env`. These were corrected in the project files. The source identity
collector correctly refused shallow Git history. The scratch repositories
were initialized separately from the pinned upstream snapshots.

Two overlapping VHDL builds caused a precompiled-header mismatch. Those
attempts are invalid evidence. Later native builds run in sequence. Two
multi-step commands reached the journal wrapper's old 180-second limit.
The wrapper now allows 600 seconds for a full CLI sequence. An interrupted gate is not acceptance.

## Open edges, ranked

1. The bus-check generator supports declared ready/valid channels. These
   cores need request/response properties. Generated check support is
   explicitly unsupported for their current port maps.
2. Tool versions matter. VHDL memory import needs a matching GHDL Yosys
   plugin. This native design also needs a Verilator version that accepts
   the emitted memory RTL. Keep both identities with the results.
3. Default Chisel emission is not always Yosys-compatible. Keep the reviewed
   firtool lowering step and its source pin in the project build.
4. Whole-core query graphs are conservative lowered graphs. Navigation
   source links do not establish complete source semantics or semantic diff.
5. Four ISA programs and one smoke do not establish whole-core correctness.
   Full ISA, machine state, interrupts and whole-core formal remain open.

## Command path

Run each command from its separate core repository. The project adapter and
source maps are project-owned. The journal recorded the exact arguments,
failed attempts and native output directories.

```sh
rvw doctor --json
rvw init --hdl chisel --name mini --top Core --isa rv32i_zicsr --fir generated-src/Core.fir --source-root .
# VHDL alternative: rvw init --hdl vhdl --name neo --top neorv32_cpu --isa rv32i_zicsr_zifencei --library neorv32
# Emit RTL through the pinned core build, then bind the project harness.
rvw formal state-generate state-map.json --out rvw/out/state-monitor-lowered --json
rvw/run.sh run --elf rvw/out/programs/smoke --out rvw/out/smoke --rvfi-trace --max-cycles 10000
rvw regress run --tier isa --json
rvw cosim check --trace RUN/rvfi.jsonl --elf RUN/captured.elf --json
rvw bundle RUN --json
rvw query build --config default
rvw query drivers dpath.pc --json
rvw query loads dpath.pc --limit 8 --json
rvw query export blocks.json blocks-final.json
rvw lint --settings lint.json --json
rvw cov merge RUN/result.json --out rvw/out/coverage.json --json
rvw cov report rvw/out/coverage.json --json
rvw checks generate --all --out rvw/out/checks --json
rvw regress gate --base-rev GOOD --tier quick --json
```

The state-generation and `dpath.pc` commands are Chisel-specific project
selections. NEORV32 uses its native trace port and VHDL database paths.
The planted fault changes an instruction response in the harness. It tests
failure capture and gate rejection. It is not a discovered upstream CPU bug.

Doctor does not infer that a platform was independently reviewed. Its smoke
C2 mapping row remains inconclusive without `--smoke-platform`. The final
reference check supplies the project platform explicitly.

## Second pass

The second pass keeps both scratch repositories and source pins. Commands
use `nice -n 15`. At most two native simulations run together. No BOOM,
full Python suite, long formal campaign or hardware run was used.
The full scratch journal and native artifacts were stored outside this repository.

### Declared request and response checks

[PR #1080](https://github.com/riscPrint/risc-v-workstation/pull/1080) adds two
explicit protocols to the existing declared-port generator. `req_rsp` checks
one outstanding pulse request and an in-order response. `req_ack` checks a
request and payload held until acknowledgment. Idle acknowledgment is allowed.
Both use project-declared ports and database-checked widths. The ready/valid
VIP and UVM agents reject these new protocol names.

Both Chisel memory maps use `req_ack`. Both NEORV32 memory maps use
`req_rsp`. The public generation command emits all four monitors. Other
check families stay unbound because no project data was supplied.
Generated monitors pass replay of the add waveforms: 455 samples per Chisel
bus and 987 per VHDL bus. Chisel has 447 instruction requests and one data
request. VHDL has 462 instruction requests and one data request.
Yosys SAT passes at 24 steps for each of the four replay windows. Data-bus
windows include the first request, rather than idle samples only. This is bounded replay. Unconstrained whole-core proof remains NOT RUN.
The native bound models also pass the add program with assertions enabled:
427 retirements in 446 cycles for Chisel and 428 in 979 cycles for VHDL. No memory-data or liveness
property is claimed. The request/response pulse monitor has native positive,
orphan-response and overlapping-request tests.

### Lint triage

[PR #1085](https://github.com/riscPrint/risc-v-workstation/pull/1085) fixes
fan-out counting through imported net aliases. Alias-bit links are not loads.
The rule now follows those links to real loads. Exact-schema tests cover both
false positives and real loads behind aliases.

On the saved whole-core databases, Chisel rule findings fall from eight to
six. Two alias fan-out findings are removed. Two real fan-out findings remain,
with 992 loads each. VHDL rule findings rise from six to seven because the
rule now sees 1,073 real loads on `u.ctrl`. These counts are for the rules
backend. They do not replace the full lint totals above.

The native findings remain visible. Chisel has 61 unused-signal warnings and
one file/module-name warning. VHDL has 1,933 unused-signal, 58 case-overlap,
15 width-truncation, seven missing-pin, two undriven and one file/module-name
warning. Lowering alone does not justify waiving these findings. Case overlap
needs an exclusivity argument from the source. Width truncation needs a
bit-range review. Missing output pins can be intentional harness omissions.
Both projects lack an SDC clock period. This is a project setting gap.
Resetless state, reset release and asynchronous reset crossings remain
structural findings. No reset waiver or clean signoff is inferred.

A project waiver can select an exact finding. For example, select the saved
`verilator.PINMISSING` finding for the unused NEORV32 `sleep_o` harness output.
Copy its actual endpoint and ID from the lint report. Set `config` to
`default`. Give the reason that the harness does not consume the sleep
indication. Put that record in `waivers` and confirm `matches` is one.
This is an example for review. No such waiver was applied to these counts.

### Queries and source-line coverage

Drivers, loads and path queries on Chisel `dpath.pc` return Scala locations.
The path to `io_icache_req_bits_addr` is found. The same query family on
NEORV32 `u.trace_o[pc_rdata]` returns VHDL locations. Its path to `t_pc_rdata`
is found. No code fix was needed for these measured paths. Synthetic lowered
nodes can still have no original source location.

[PR #1095](https://github.com/riscPrint/risc-v-workstation/pull/1095) maps an
exact GHDL source locator to its immediately following lowered statement.
Blank lines and unrelated statements break the pair. The mapper does not
search backward for nearby comments. On the NEORV32 add run, 2,777 of 57,336
native points link to 343 VHDL source lines.

The existing inline Scala mapper works on original emitted Chisel RTL. A
separate native add run of `Core.sv` has 427 retirements in 446 cycles and
reports tohost 1. It hits 4,955 of 9,716 points. It links 6,562 points to 121
Scala lines. This run uses project observation ports without the generated
architectural monitor. The monitor model `observed.v` strips source comments
and maps zero points by the comment path. It needs an explicit map.

These source groups retain native metric counts and their denominator.
They do not establish individual original-language statement hits or full
source coverage. The compatibility keys still use `scala` for VHDL links.

### Validation and remaining limits

Generator tests: 23 passed. Later request/acknowledgment and release-hygiene
tests: 46 passed. Generator fast set: 2,254 passed, one skipped.
Lint targeted tests: six passed. Lint fast set: 2,284 passed, one skipped.
Coverage targeted tests and release hygiene: 59 passed. Coverage fast set:
2,300 passed, one skipped and one unrelated failure.
`test_mcp_workflow_coverage.py::test_each_tool_has_a_profile_and_workflow`
reported that `cov_probe_goals` had no workflow. The worker brief permits
this unrelated failure to remain. No CI wait was used.


### Full RV32UI campaign and trace mapping

Both selected configurations implement RV32I without M, A, C, F or D.
The campaign includes all 42 programs from the retained RV32UI Makefrag.
No UM or other optional arithmetic extension suite is claimed. The custom
tohost environment remains explicit. Privileged ISA qualification is NOT RUN.

The full suite found two project integration errors. The Chisel observer
combines an effective byte address with word-lane masks and full-word data.
Its old C2 records are not canonical aligned records. The strict full-word
reader correctly refuses subword loads with those addresses. It also finds
store address mismatches. [PR #1106](https://github.com/riscPrint/risc-v-workstation/pull/1106)
adds an explicit project-adapter helper that changes only the bus address to
the containing word. It preserves all data and mask bits. It rejects fault
effects. The co-simulation input checks are not relaxed. The project adapter
uses this helper before writing nontrapping C2 records. A new native lb run
passes and matches 191 instructions. Fourteen targeted tests pass.

Chisel implements FENCEI. The assembler and project ISA declaration now
include `zifencei`. This changes the declared instruction set, not comparison
masks. The NEORV32 trace port instead reports architectural, unshifted masks
and data. Its project platform now selects `aligned_mem=false` and
`memory_read_convention=architectural`. It does not use the word-bus helper.
Corrected replays of the prior captures match Spike on 41 programs for each
core. Chisel refuses ma_data. VHDL reports a mismatch on its fault record.
Those replay results do not replace a native regression campaign.

Initial full-suite runs executed 41 programs successfully and timed out on
ma_data for each core. The first journal budget was too short. Later runs
also exposed a process error: changing the installed checkout while a
campaign ran made 29 Chisel and 30 VHDL source identity claims inconclusive.
These are not qualification results. No identity check was disabled.
The final campaign uses a separate installed-tool copy frozen at
`cd42b67bd38d584c66e9921adfce910b3f58fce0`. Core project settings and adapters
are committed before it starts. The workstation worktree can then change
without changing the installed tool used by those runs.

The ma_data program expects misaligned loads and stores to complete. Both
selected cores trap on misaligned halfword loads. Their minimal tohost
environment has no emulation handler. Separate minimal native programs
confirm load-misaligned cause 4 and complete with tohost 1 when a handler is
supplied. VHDL uses a standard mtvec handler. Chisel uses its fixed 0x1c0
machine exception vector. Its older CSR interface does not permit a modern
mtvec write. The first Chisel handler attempt trapped on that write; the
fixed-vector reproduction succeeds with eight retirements in 14 cycles.
The VHDL reproduction succeeds with 13 retirements in 45 cycles.

This is a platform capability limit, not an earned pass or an ISA mask.
The full ma_data program stays in the test list. Its trap records also expose
an adapter limit: Chisel full-word fault reads are refused. NEORV32 reports
an attempted read and sequential pc_next rather than the reference trap
transition. Its current C2 fault mapping is not qualified. No field is waived
to turn those records into matches.

The helper fast set has 2,378 passes and one skip. After rebase, targeted
checks have 53 passes and one unrelated release-hygiene failure in main's
VexiiRiscv evidence files. The failing files are
`examples/vexiiriscv/formal/adapter-kit-results.json` and
`examples/vexiiriscv/formal/native-kit-results.json`. The worker brief permits
these unrelated failures to remain. Later main changes can alter that result.


### Emitted module binding and final counts

[PR #1126](https://github.com/riscPrint/risc-v-workstation/pull/1126) adds
optional `rtl_top` to the declared map. `top` still has to match the database.
GHDL's database uses `drytop`, while standalone synthesis emits `DryTop`.
The VHDL project now declares that emitted spelling. Port widths still come
from the database. Public check generation and native compilation confirm
the bindings for both instruction and data buses. Both complete core models
run add with generated assertions enabled and no assertion failure. This is
one program at the existing memory timing. It does not qualify stalled
traffic, response data or liveness. Seven targeted tests pass.

The final frozen campaigns give these results:

| Core | RV32UI regression | Inconclusive identity records | Spike comparison | Matched instructions |
| --- | --- | --- | --- | --- |
| Chisel riscv-mini | 41 pass, one ma_data timeout | 0 | 41 match, one ma_data error/refusal | 11,807 |
| VHDL NEORV32 | 41 pass, one ma_data timeout | 0 | 41 match, one ma_data fault-record mismatch | 12,090 |

All 42 captured ELF hashes are checked for each core. All comparisons have
zero applied masks and zero reference synchronizations. Both regression
summaries retain `ok=false`. The timeout and fault-trace limits are not
waived. No whole-ISA qualification or changed-core gate acceptance is claimed.

The recorded core project revisions are
`0803cdd19308ff62443942d539f858fe7ad170aa` for Chisel and
`be526a1266e2c106bc39c1fd4838655047a637b1` for VHDL. The immutable regression
generations are `87018bd4f39f45a58bed04273e547f9b` and
`edb770b6b95e49018008662099813460`. The VHDL emitted-name metadata was
committed afterward in `69e3051`. It does not change the RTL or trace adapter.
The native bind test uses that emitted-name declaration. Full C1 identities
remain those of the recorded campaign revisions.

The scratch journal contained commands, native logs, minimal misaligned-load
reproductions, lint reports, query results, coverage reports and the final
count audit. No core sources or native outputs are committed to the
workstation. Full Python suite, long formal runs and hardware tests remain
NOT RUN. Real lint findings, fault-access trace mapping, misaligned-access
emulation, privileged ISA tests and individual source-statement coverage
remain open.

Final documentation fast set: 2,435 passed, one skipped, two unrelated
failures and 8,327 deselected. The failures are
`test_agent_guide.py::test_agent_setup_embeds_the_generated_block` and
`test_release_hygiene.py::test_tracked_text_has_no_personal_paths`.
The latter still names the two VexiiRiscv evidence files above. Neither file
nor the generated agent setup block is changed in this work. The final docs
diff has no whitespace errors. MCP discovery has no skipped-module warning.
