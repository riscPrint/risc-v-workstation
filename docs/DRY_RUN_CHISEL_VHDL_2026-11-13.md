# Chisel and VHDL whole-core dry run, 2026-11-13

## Scope

Both cores live in independent Git repositories outside the workstation:
`wt/.dryrun3/chisel` and `wt/.dryrun3/vhdl`, relative to the saviour workspace.
Each repository uses a root `rvw.toml`. `RVW_HOME` selects the installed
`wt/deep` checkout, and its `rvw/.venv/bin` is on PATH. Core sources, native
outputs and the full command journal stay outside the workstation.
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
source maps are project-owned. See the journal for the exact arguments,
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
