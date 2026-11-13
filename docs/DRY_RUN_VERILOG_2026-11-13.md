# Verilog core dry run, 2026-11-13

## Scope and evidence

The core lives in a separate Git repository at `wt/.dryrun2/core`, relative to
the saviour workspace. It is outside the workstation. `JOURNAL.md` in its parent
records commands, exit codes, times and log paths. Full logs and native outputs
remain there. No core source is added to the workstation.

PicoRV32 and its test copies come from revision
`ef203c2b0a3fb793280f5114941416c425c5b461`. The source license and test license
are retained. The initial workstation revision was `201b6ae2`. Later fixes
were tested as main advanced. The first Spinal dry-run journal was read first.
Its fixes were not repeated. No subagents were used.

Tool use starts from the core root. `RVW_HOME` selects the installed workstation.
Its `rvw/.venv/bin` is on PATH. A root `rvw.toml` selects the project.
The host has Verilator 5.049, Yosys, yosys-slang, Yices and RISC-V GCC.
Verilator is outside the documented tested version. This is one host result.

There are 46 native program completions with status pass: 45 PicoRV32 copies
of RV32IM riscv-tests and the smoke program. All C1 records retain an explicit
inconclusive marker because the temporary native adapter lacks complete native
identity capture. These observations are not a conformant C1 qualification,
C4 acceptance, full upstream ISA suite result or whole-core verification.

## Bring-up path

`rvw init --hdl sv --top picorv32 --source picorv32.v --isa rv32im`
creates a C++ harness stub. Its first build failed before the output directory
existed. PR #847 fixes this. The native scaffold then compiles. Its run still
refuses execution until the project maps its buses and completion rule.

The second attempt uses the shipped `--verilog-top` mapped mode. It recognizes
the memory bus and RVFI ports. This mode still needs the installed Scala/sbt
runtime. The shared sbt queue blocked the attempt. The queued processes were
stopped. This dry run does not claim a completed mapped-adapter build.

A project-owned C++ Verilator harness then provides ELF loading, low-active
reset, zero-latency memory, retired tohost completion, RVFI capture, VCD and
Verilator code coverage. A Python C1 launcher implements build, run and serial
run-many. It refuses unsupported faults, interrupts, Konata and SpinalTrace.
It does not implement reusable native identity. Its C1 results say so.

Regression first failed because this temporary launcher lacked run-many.
Adding serial run-many corrected that integration error. The mapped project
file's complete-input declaration was inherited during this experiment. It
must not be treated as a completed native input audit. The final temporary
native project declares incomplete inputs. Gate acceptance remains unavailable.

## Steps and results

| Step | Command or artifact | Result and limit |
|---|---|---|
| Doctor | `rvw doctor --features sim,riscv-gcc,cosim --json` | Reports absent project initially and absent local Spike shim. Building `Cosim/build.sh` supplies the shim. Final native adapter identity remains incomplete. |
| SV init | `rvw init --hdl sv ...` | Scaffold created. Native compile succeeds after #847. Run mapping is manual. |
| Mapped init | `rvw init --verilog-top picorv32 ...` | Bus and RVFI mapping generated. Native launch blocked by shared sbt queue. |
| C1/C2 | `native-adapter.py run ...` | Smoke passes in 55 cycles with 15 retirements. C1 retains an identity warning. C2 comes from real core RVFI. |
| Regression | `rvw regress run --tier full --rvfi-trace ...` | 46 program completions pass; all remain inconclusive through C1. One config, fixed memory latency. |
| Cosim doctor | `rvw cosim doctor --trace ... --json` | Inspects the scalar capture and platform. It makes no comparison claim. |
| Cosim | `rvw cosim check --elf ... --trace ... --json` | 40 of 46 traces match Spike. Six byte/halfword tests differ in memory masks/data. No checker masks were relaxed. |
| Planted bug | Instruction memory changes ADD to SUB at `0x80000008` | An explicit harness fault, not a discovered CPU bug. Smoke fails with code 1 after 35 cycles and 9 retirements. Cosim detects the changed instruction. |
| Bundle | `rvw bundle ... --core-config debug.toml --no-rerun --no-spinaltrace --json` | Bundle written with fail:1, C2, VCD and inputs. No identity-qualified rerun or causal reproduction claim. |
| Yosys query | `rvw query build-hdl --frontend yosys ...` | Database and path queries work. This frontend refuses defines/parameters. The plain default elaboration differs from the configured simulation. |
| Slang query | `rvw query build-hdl --frontend slang ...` | RVFI and MUL/DIV extraction works after #859 and #872. Reset parameter uses `32'h80000000`. Decimal 2147483648 is rejected by slang. |
| SpinalBlocks | `rvw query export blocks.json ...` | Stored SpinalBlocks JSON exported through CLI and MCP. Renderer, SVG layout and VS Code NOT RUN. |
| Lint | `rvw lint --settings lint.json --emit ... --json` | Verilator, rules, CDC/RDC inventory and SDC run. Initial report has 58 active findings. Reviewed settings emit a 10 ns clock constraint. Structural results do not establish signoff. |
| Code coverage | `rvw cov merge ...coverage.dat`; `rvw cov report ...` | Smoke hits 2773/10375 points, 26.73%. Raw .dat counts have no complete C1 provenance. No closure claim. |
| Functional coverage | `rvw cov functional ... --platform rvw/cosim.json` | Reports 15 retirements and no unknown encodings. Default bin domains are a plan, not an ISA completeness claim. |
| RVFI generation | `rvw formal rvfi-generate binding.json ...` | Generates project/wrapper from explicit ports. Project review must invert resetn and set core parameters. No inference of reset polarity. |
| riscv-formal | `rvw formal riscv ... --timeout 30` | Reviewed wrapper reaches retirement cover at depth 20. Add check times out. Overall inconclusive. |
| Autocheck | `rvw formal autocheck ... --kind dead_code` | Refuses a lowered latch in this elaboration under the single-clock model. No state conversion or waiver applied. |
| SVA | `rvw formal sva-lower ...`; `rvw formal regress suite-split.toml ...` | Three bus properties have bounded passes at depth 8. Reset is assumed initially active, then inactive. Memory is unconstrained. Activation is not measured. |
| Wave | `rvw wave info ...`; `rvw wave changes ...` | Reads the native VCD and RVFI PC changes. Typed wave/source semantics are not supplied. |
| Component model | `rvw csim run study.json ...` | Consumes 15 real retirements and 3 branches. BTFN is a hypothetical predictor; PicoRV32 has no predictor. No IPC fidelity claim. |
| Architecture model | `rvw arch inspect ...`; `rvw arch build --bench median` | Project RV32IM Minor description supplied. Build refuses absent gem5.opt. No model/RTL calibration. |
| UVM/VIP | `rvw uvm new ... --profile cpu`; `rvw vip buses/bench ...` | Automatic generation is unsupported without typed bus metadata. Plain port names require a project bench and explicit pin bindings. |
| Fault | `rvw fault sites/plan/run ...` | Sites and seeded plan work. Native adapter refuses --fault. One campaign outcome is inconclusive, zero injections. No detection claim. |
| Security | `rvw sec ift ...` | Initial transform refuses unsupported state/constants. After main #873, MCP completes 8 samples and reports potential mem_rdata to mem_wdata influence at cycle 7. X/Z values remain tainted. This is expected possible dataflow under the chosen policy, not a demonstrated security defect. |
| MCP | stdio ClientSession with `rvw mcp` | Real transport calls exercised query/export/build-hdl, regression, cosim/doctor, bundle, lint, coverage, formal, waves, csim/arch, UVM/VIP, fault and security. Worker completion preserves tool limits. |

SVA preprocessing required expansion with Verilator and removal of the remaining
timescale directive. Raw macro-bearing source now returns structured unsupported
through #866. Each regression task must contain exactly one assertion. The first
three-assertion task was an integration error. Splitting it produces three
bounded results. The initial unconstrained-reset counterexample was not a core
bug. Adding explicit reset assumptions changed the environment and is recorded.

Several initial invocations incorrectly added `--json` to commands that always
emit JSON. Other initial invocations used `-P` instead of `-G`, or named output
options instead of positional arguments. These are operator errors in the
journal. They are not missing-command defects. The first SoC map also had an
incorrect schema and duplicated RAM in its platform. The corrected map reaches
the actual typed-bus support limit.

## Fixes

| PR | Change | Validation |
|---|---|---|
| [#847](https://github.com/riscPrint/risc-v-workstation/pull/847) | Create SV scaffold build output before Verilator; use absolute harness path. | One targeted pass; fast set 1475 pass, 1 skip. |
| [#859](https://github.com/riscPrint/risc-v-workstation/pull/859) | Join slang parameter override arguments. | Native two-parameter test passes; fast set 1498 pass, 1 skip, 1 unrelated MCP audit failure. |
| [#866](https://github.com/riscPrint/risc-v-workstation/pull/866) | Return structured unsupported/error from SVA lowering. | Two targeted passes; fast set 1519 pass, 1 skip, 1 unrelated release-hygiene failure. |
| [#872](https://github.com/riscPrint/risc-v-workstation/pull/872) | Avoid parent-tree capture for self-contained SV files. | Capture-limit test passes; slang tests 6 pass, 2 skip; fast set 1536 pass, 1 skip, 1 unrelated release-hygiene failure. |
| [#879](https://github.com/riscPrint/risc-v-workstation/pull/879) | Return unsupported for automatic UVM/VIP generation on untyped databases. | Targeted tests 26 pass; fast set 1548 pass, 1 skip. |

All five fixes were merged before the final report.
No full Python suite, BOOM simulation, long formal proof or physical hardware
run was made. Fast-set failures outside these changes are retained in PR bodies.

## Open edges, in order of impact

1. The tested pure C++ adapter still needs a complete C1 input/identity audit.
   The mapped alternative adds sbt and a shared queue to a Verilog bring-up.
   Neither path earned C4 acceptance here.
2. Automatic UVM/VIP generation depends on Spinal typed bundles. A plain HDL
   database needs a project-owned protocol map and bench. Renaming ports cannot
   supply transaction semantics.
3. Six byte/halfword cosim cases differ in PicoRV32 RVFI memory representation.
   Resolve the core/platform semantics with independent evidence. Do not mask
   differences merely to obtain a match.
4. Slang sources with includes still capture whole source/include directories.
   Large build output in those directories can exceed snapshot limits.
   Self-contained sources no longer have this problem.
5. Whole-core formal capacity and automatic monitor applicability remain open.
   The short add check times out. Autocheck refuses lowered latch state. Three
   shallow bus properties and a retirement witness are not ISA proof.
6. Native fault injection needs project binding. IFT now runs, but the simple
   source/sink policy is not a security specification. Neither run establishes
   detection coverage or whole-core security.
7. gem5 is absent on this host. Architecture calibration is NOT RUN.
8. Diagram rendering, typed wave metadata, interrupts, extended CSR state and
   multi-config qualification are NOT RUN.

Final documentation fast check: 1560 passed, 1 skipped, 8048 deselected.
One unrelated test failed: `test_mcp_coherence.py::test_discovery_audit_baseline`.
The last code-fix fast check was clean at 1548 passed and 1 skipped.

## Second pass

The second worker used the same external scratch core. No core source was added
to the workstation. The pinned PicoRV32 RTL is unchanged. Scratch commit
`1350919` records the project changes. The planted fault was reverted.
`JOURNAL.md` records the native commands and log names.

| Area | Second-pass result | Remaining limit |
|---|---|---|
| Plain HDL identity | PR #911 adds a Verilator build manifest and C1 capture. PR #963 prevents stale native objects after compiler flag changes. A committed smoke gate accepts good revision `df68dcf`. A gate against planted revision `9bbaa3b` rejects `fail:1`, with no inconclusive evidence. | The scaffold still requires project bus and completion mapping. The planted change is an instruction-response harness fault, not a discovered core bug. |
| Native full regression | 46 passes, zero inconclusive C1 results in the final full regression. | One config and zero-latency memory only. This is not the full upstream ISA suite. |
| Scalar cosim | PR #922 adds a declared full-word read convention. All 46 original native traces match Spike. All 46 newly captured final-generation traces also match after their ELF hashes are checked against C1. | The RTL reports all read lanes for subword loads. The checker validates raw address/strobes before deriving instruction byte lanes. Stores and destination values remain strict. MMIO, misaligned, compressed and trapping loads are refused by this convention. |
| Declared protocol bindings | PR #927 generates checks, VIP and pyuvm skeletons from `port-map.json`, with no Spinal types. Native bound assertions run on the real core and observe 3 stalls and 3 transfers. | Initial declared protocol is ready_valid. The monitor checks stalled request stability. It does not check memory response contents. The UVM scenario remains project work. |
| Core RVFI ISA kit | Existing main runs `rvw formal isa` with the reviewed core wrapper. Add and cover rows report bounded results at depth 8. Overall result is inconclusive. | No unbounded ISA proof, machine-state bindings or adapter conformance certification. |
| Hand-written SVA | Three engine passes at depth 8. | The rerun marks all three inconclusive because input closure, attribution and non-vacuity are not certified. Do not count these as closed proofs. |
| Architecture without gem5 | PR #933 removes gem5 from benchmark compilation. The scratch median ELF builds. The Python OoO model consumes the real 15-retirement smoke trace. | The supplied model is hypothetical and uncalibrated. gem5 run/calibrate still require the supported binary. |
| HDL doctor | PR #942 adds `[project] hdl`. JVM probes are not_applicable for SV/VHDL. The final smoke check reports build/run, C2 mapping, wave and coverage ready. Only the workstation checkout gate remains inconclusive for the pre-existing untracked `out/`. | Applicable native checks remain active. Version probes are not qualification. |

The first full second-pass regression completed 46 programs but retained an
inconclusive marker because the temporary scratch adapter omitted the requested
`rvfi_trace` C1 field. That run is not conclusive evidence. The scratch adapter
now records that option and uses saved ELF bytes for symbol lookup.

Native logs in the scratch parent include `identity-good-gate2.log`,
`identity-bad-gate.log`, `second-pass-cosim.log`, `second-pass-bind-run.log`,
`second-pass-isa.log`, `second-pass-sva.log`, `second-pass-arch-build.log`, and
`second-pass-ooo.log`. Final rerun log names are recorded in the journal.
No full Python suite, BOOM run, long formal proof, native UVM scenario
qualification, gem5 calibration or physical hardware run was made.

A native compiler-flag check found that incremental make retained a binary built
with `ID_FLAG=1` after a requested rebuild with `ID_FLAG=2`. PR #963 forces
make to recompile before it saves new identity claims. The same fixture then
prints 2. The full 46-program regression and final 46 Spike matches above ran
at workstation `9fa90545`, with unchanged compiler flags. A later PicoRV32
smoke at `c6b7effc` checks the forced-rebuild path: one conclusive pass,
55 cycles and 15 retirements.
