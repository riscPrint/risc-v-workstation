# Integrate a new core

Keep the core in its own repository. Install the workstation once. Set
`RVW_HOME` to its checkout. Do not copy tool sources into the core repository.
The commands below use project-owned files. Replace paths and ISA values with
reviewed values for the core. Run each stage only after its inputs exist.

## 1. Install a profile

From the workstation checkout:

```sh
scripts/install.sh --profile verification --dry-run
scripts/install.sh --profile verification
source env.sh
rvw doctor --features sim,riscv-gcc,cosim --json
```

Working means the selected executable checks pass. Doctor also needs a selected
project before it can report ready. Read every missing-tool row and its install
flag. `minimal` needs no native EDA tools. `formal` and `arch` add their own
backends. `all` includes manual setup entries and is not a qualified turnkey
installation. Sail and the IDE need separate setup. Linux recipes are untested.
See [tool versions](TOOL_VERSIONS.md) and [Linux recipes](LINUX_INSTALL.md).

## 2. Create project files

In the fresh core repository with an existing Spinal/sbt build:

```sh
rvw init --isa rv32im --dry-run --json
rvw init --isa rv32im
rvw doctor --json
```

Working means `rvw.toml`, the launcher and the adapter skeleton are created.
Build and run still refuse execution. This is expected. `init` does not create
CPU RTL, infer buses or certify the ISA. Review the generated `rvw/README.md`.
See [init](../rvw/src/rvw/init/README.md) for optional build wiring and linker
inputs. Its platform template requires review before cosim can use it.

For a non-Spinal core, select its HDL front end instead:

```sh
rvw init --hdl sv --top Core --isa rv32im --source rtl/Core.sv --dry-run --json
rvw init --hdl vhdl --top Core --isa rv32im --source rtl/Core.vhd --dry-run --json
rvw init --hdl chisel --top Core --isa rv64gc --fir out/Core.fir --dry-run --json
```

Choose one path. Supply sources in dependency order. SV needs `RVW_SLANG` and
Yosys. VHDL needs GHDL and its matching Yosys plugin. Chisel needs firtool and
an existing FIRRTL output. These scaffolds create a query build and a C++
harness skeleton. The harness does not map buses or completion. Its run still
refuses execution. HDL graph navigation is conservative; semantic diff remains
inconclusive. The tool does not infer a safe harness from the HDL.

For a Verilog core with a supported bus and RVFI ports, there is also a mapped
mode: `rvw init --verilog-top MODULE --verilog FILE ...`. Review the explicit
clock, reset polarity, reset address, parameters, memory map and bus bindings.
See [PicoRV32](../examples/picorv32/README.md). This mode uses the installed
Scala/sbt runtime. The `--hdl sv` C++ stub has no Scala dependency. Its project
still needs a complete C1 implementation and input audit before regression.


## 3. Bind the adapter

Implement `rvw/run.sh` and `rvw/src/main/scala/rvwcore/CoreAdapter.scala`.
For non-Spinal cores, implement the generated `rvw/sim/harness.cpp` instead.
Map clock, reset, memory transactions, completion and committed RVFI fields.
For RiscvSim, implement both `elaborate` and `generatedVerilog(model)`. The
latter must return the RTL files used by the compiled model. Omitting it leaves
C1 without the hash required to match the adapter identity.
Declare the real ISA, memory map, configs, test suites and identity inputs in
`rvw.toml`. Keep probes optional. Follow [C1](contracts/c1-run.md),
[C2](contracts/c2-rvfi-trace.md) and [project selection](contracts/project.md).

```sh
rvw/run.sh info --json
rvw/run.sh build --config default --json
```

Working means `info` identifies the actual core and build produces the selected
simulator. `info` alone cannot establish adapter conformance. The installed
RiscvSim path uses JDK 21, sbt, Verilator, make and a C++ compiler.

## 4. Run one ELF

Build a small bare-metal ELF with the project's reviewed linker script and
RISC-V GCC. Start with one instruction set and one config.

```sh
rvw/run.sh run --config default --elf tests/smoke.elf --out run/first --rvfi-trace --json
rvw doctor --smoke-elf tests/smoke.elf --smoke-options rvfi --json
```

Working means C1 reports `pass`, the end reason is known and the C2 stream is
complete. Check the ELF hash, config and ISA. A timeout or an empty trace is not
a pass. Doctor checks one config and ELF. It does not qualify all options.

## 5. Add regression and gate inputs

Unwired scaffolds use `input_complete = false`. That setting prevents `regress run` from starting
simulations. Use the adapter's direct `run` command while developing the
integration. Audit its sources, build products, scripts, tools and environment.
Declare `cache_paths`, `input_env`, `input_tools` and the required command/toolchain
inputs before setting `input_complete = true`. Do not set the flag only to bypass
the refusal. See [input declarations](BRING_YOUR_OWN_CORE.md#declare-enough-inputs-for-a-gate).
Gate acceptance also needs clean committed revisions and complete identities.

```sh
rvw regress run --tier quick
rvw regress gate --base-rev HEAD~1
```

Working means all expected tests have C3 records. C4 acceptance needs complete
captured inputs and clean committed revisions. A passing dirty tree is not
accepted. Read [regress](../rvw/src/rvw/regress/README.md). Generated privilege
and MMU programs often have Spike-only evidence. Run them on the new RTL before
claiming DUT coverage. No optional generator is needed for an existing ELF suite.

## 6. Compare with an independent reference

Install `--with-cosim`. Review the project's Spike platform and capture scope.

```sh
rvw cosim check --trace run/first/rvfi.jsonl --elf tests/smoke.elf --json
```

Working means a complete reference match with a passing end event and no hidden
synchronization. Review which architectural fields were compared. Vector,
hypervisor, MMIO, faults and asynchronous inputs have separate capability limits.
See [cosim](../Cosim/README.md). Spike replay of a Spike trace is reference
validation. It does not establish RTL correctness. Sail is an optional second
reference, selected with `RVW_SAIL`.

## 7. Add probes

Add the [SpinalProbes API](../SpinalProbes/README.md) to the adapter. Build and
run with its probe option. Keep probes off by default.

```sh
rvw probes list --events run/probe-events.jsonl --json
rvw probes summary run/probe-events.jsonl
rvw probes convert run/probe-events.jsonl --to counts --c1 run/result.json --c2 run/rvfi.jsonl --out run/counts.json
```

Working means complete event totals and explicit consumer gaps. The converter
supports one hart. Per-slot CSR snapshots and grouped MMU walks are not generated.
The Python converters need no extra native tool. New signal mappings need RTL
validation. See [probes](../rvw/src/rvw/probes/README.md).

## 8. Collect coverage

```sh
rvw cov --help
rvw cov functional run/first/rvfi.jsonl --manifest isa.json --source-root riscv-opcodes --json
```

Working means the report identifies its denominator, source manifest and actual
observations. A model pass cannot fill DUT coverage holes. Use Verilator for
native structural coverage and the matching source revision for the ISA manifest.
Closure campaigns must retain raw attempts and complete native identities.
See [coverage](../rvw/src/rvw/cov/README.md). New closure orchestration has fixture
coverage; a native DUT closure campaign is not established by that test.

## 9. Start with a bounded formal property

Install `--profile formal`. Select the same HDL front end used by the design.

```sh
rvw formal bmc --verilog formal/counter.sv --top counter --depth 8 --out run/formal
```

Working means the selected property has a solver verdict, depth, assumptions,
engine and retained log. A bounded pass is not an unbounded proof. A small block
proof is not a core proof. A missing engine stays inconclusive. Portfolio engines,
CBMC and language front ends have separate inventory entries. Read
[formal](../rvw/src/rvw/formal/README.md) before using generated apps or cuts.

## 10. Check lint and CDC

Install `--with-lint` and the required query front end. Build a design database
with the project's extraction command. Write project-owned lint settings. Use the same clock/reset configuration for
database extraction and simulation. A no-argument top class passed to
`spinaldb.Main` uses the default SpinalConfig. If the adapter changes that
configuration, supply a project-owned extraction entry with the same settings.

```sh
rvw query build --config default
rvw lint --settings lint.json --json
```

Working means each requested backend reports its status and all waivers have
reviewed reasons. Structural CDC inventory is not metastability or timing signoff.
SDC checks test logical intent. They do not run STA. GHDL plugins must match Yosys.
See [lint](../rvw/src/rvw/lint/README.md) and [SpinalDB](../SpinalDB/README.md).

## 11. Inspect waves and debug

Enable waves in the project adapter and retain the exact ELF and source inputs.

```sh
rvw wave info run/wave.vcd
rvw wave changes run/wave.vcd '.*pc.*'
rvw debug suite --list --out run/debug-list
```

Working means signal names, values and times match the selected run. VCD queries
need no native viewer. FST can use `--with-wellen` or GTKWave converters. Typed
waves need `--with-typed-waves`. JTAG interoperability needs OpenOCD and RISC-V
GDB plus a real project debug bridge. Reference Debug Module fixtures do not
qualify physical debug hardware. See [waves](../rvw/src/rvw/wave/README.md) and
[debug](../rvw/src/rvw/debug/README.md).

## 12. Add architecture models

Install `--profile arch`. Set project-owned model parameters and workload paths.

```sh
rvw arch build --bench median,vvadd,memcpy --json
rvw arch calibrate --bench median,vvadd,memcpy --out run/calibration
```

Working means model and RTL results use the same workload, region and event
predicates. gem5 and native component models show trends. They do not replace
RTL. Native scheduler parity is not application accuracy. The committed-trace
model does not execute wrong-path instructions. Read [Arch](../Arch/README.md)
and [component simulations](../ComponentSims/README.md).

## 13. Add UVM and protocol VIP

Install `--with-sim`, `--with-cocotb` or `--with-pyuvm` for the chosen runner.
The constrained Verilator UVM example also needs Z3 from `--with-formal`.
Supply a design database, SoC map and exact pin bindings.

```sh
rvw uvm new --db design.db --soc map.json --out run/new-bench
rvw regress cocotb run/new-bench/bench.json --out run/new-bench-result
```

Working means independent monitors check accepted transactions and expected
negative cases fail for the intended reason. Accellera component fixtures are
real RTL but are not a CPU. Six VexRiscv ISA programs and bounded IRQ/mscratch sequences have native
evidence. Full imported VIP, native debug and HDL DPI/VPI backdoor support
remain unqualified. DRAM, PCIe and Ethernet optional model contracts have mock
callback tests; projects still supply their native models and bridges.
See [UVM](../Uvm/README.md) and [VIP](../rvw/src/rvw/vip/README.md).
Use `rvw vip list`, `rvw vip buses --db design.db` and
`rvw vip bench --db design.db --out bench.py`. MCP exposes `vip_list`,
`vip_buses` and `vip_bench`. The bench remains a skeleton until it has project
reset, stimulus and expected results. For a custom typed bus, use
`rvw uvm new --adapter adapter.json` with a project scenario and explicit pins.

## 14. Scale to a farm

Install matching tools on every worker. Configure SSH keys and trusted host
keys. Capture an exact adapter identity and a C1 run-many manifest first.

```sh
rvw farm run --help
rvw farm dashboard --root "$HOME/.cache/rvw/results" --out run/dashboard.html
```

Use the full command in [farm](../rvw/src/rvw/farm/README.md) with project-owned
hosts, manifest and identity command arrays. Working means every expected cell
has a collected result and matching identity. Collection exit 0 is not a DUT
pass. New cluster shard plans have fake-adapter tests. Native cluster/RTL parity
is not established. Missing hosts, acknowledgements or artifacts stay inconclusive.

## Evidence reviewed on 2026-11-13

This table reports recorded evidence, not tests run while writing this guide.
The initial source snapshot contained 268 merged PR bodies. The final refresh
reviewed 310 merged PR bodies from the requested date query.
Limits can differ within one tool. Read the linked README and PR before use.

| Tool or flow | Recorded scope | Evidence and remaining limit |
|---|---|---|
| init | Plain HDL identity capture; run mapping is project work | [Verilog second pass](DRY_RUN_VERILOG_2026-11-13.md#second-pass): native identity and good/bad smoke gates work with the project C++ adapter. The generated stub still refuses run until mapped. |
| sim / arcilator | Ran on RTL | [#654](https://github.com/riscPrint/risc-v-workstation/pull/654): bounded VexRiscv C1/C2 comparison; BOOM, checkpoints and broader engine options NOT RUN. |
| regress privilege extensions | Spike only | [#552](https://github.com/riscPrint/risc-v-workstation/pull/552): 81 programs; RTL and independent nested-pointer model remain open. The base privilege, PMP and WFI families now have RTL rows below. |
| generated MMU suites on RTL | Ran on RTL (VexiiRiscv Sv39/Sv32) | [VexiiRiscv README](../examples/vexiiriscv/README.md#generated-suites-on-rtl-2026-11-13): Sv39 matrix/fault/random 145/18/2 run, 154 Spike match, 11 finding; Sv32 140/12/2 run, 146 match, 8 finding. All findings: PTE reads ignore PMP. C2 walk check: 92 Sv39 and 89 Sv32 matrix scenarios consistent with the independent walker. Sv48/57, H, NAPOT, PBMT, pointer masking and shootdown have no RTL target. |
| generated privilege/interrupt suites on RTL | Ran on RTL (VexiiRiscv, VexRiscv M-only) | VexiiRiscv RV64: controls 30/30, PMP 264/264, scheduled WFI 6/6 Spike match; RV32 scheduled WFI 6/6. VexRiscv: scheduled WFI 3/6 match, 3 finding (interrupt keeps old `mtval`, [reproduction](../examples/vexriscv/findings/interrupt-mtval/README.md)). VexiiRiscv RV64 CLINT WFI 4/4 (device model drives the pins; `--allow-sync irq,mmio`). NMI, AIA, Sstc, state-enable and PLIC families NOT RUN (no target feature, or no stimulus mailbox yet). |
| generated ordering suites on RTL | Ran on RTL, single hart | VexiiRiscv RV64 and RV32: LR/SC, AMO, AMO fault, FENCE, FENCE.I 5/5 Spike match each; VexRiscv FENCE/FENCE.I 2/2. Zacas, cache-block, litmus and multi-hart NOT RUN. No concurrent ordering evidence. |
| cosim vector | Spike only | [#608](https://github.com/riscPrint/risc-v-workstation/pull/608): 1,333 instructions, replay match; no vector RTL. |
| probe collection | Ran on RTL fixture | [#612](https://github.com/riscPrint/risc-v-workstation/pull/612): Verilator collector tests; [#614](https://github.com/riscPrint/risc-v-workstation/pull/614) converters used fixture events. |
| coverage closure | Fixture only | [#643](https://github.com/riscPrint/risc-v-workstation/pull/643): identity/archive tests; native DUT/Spike closure campaign NOT RUN. |
| formal cell cores | Ran on RTL fixture | [#619](https://github.com/riscPrint/risc-v-workstation/pull/619): bounded native solver queries; full temporal vacuity and core proof remain open. |
| lint CDC | Ran on RTL fixture | [#548](https://github.com/riscPrint/risc-v-workstation/pull/548): native toggle checker holds/fails as expected. Physical CDC and STA are not qualified. |
| query SV / VHDL | Native elaboration only | [#601](https://github.com/riscPrint/risc-v-workstation/pull/601) Ibex and [#633](https://github.com/riscPrint/risc-v-workstation/pull/633) NEORV32; not behavioral RTL runs. Mixed-language and plugin compatibility limits remain. |
| waves | Ran on RTL fixture | [#566](https://github.com/riscPrint/risc-v-workstation/pull/566): Icarus/Verilator wave names; [#577](https://github.com/riscPrint/risc-v-workstation/pull/577) ELF profile used fixtures, not core workload waves. |
| debug | Reference/fixture only for new core | [README](../rvw/src/rvw/debug/README.md): requires project bridge; no new core or physical hardware qualification is transferred. |
| arch native scheduler | Native reference parity only | [#655](https://github.com/riscPrint/risc-v-workstation/pull/655): 250 seeded parity schedules; no RTL/application accuracy check. |
| UVM | Ran on RTL, bounded CPU and component cases | [UVM README](../Uvm/README.md): bounded Accellera RAM/pin tests; [#668](https://github.com/riscPrint/risc-v-workstation/pull/668) later passed six live VexRiscv programs; [#690](https://github.com/riscPrint/risc-v-workstation/pull/690) checked bounded IRQ/mscratch cases. Debug and C4 remain open. |
| VIP native model adapters | Fixture only | [#642](https://github.com/riscPrint/risc-v-workstation/pull/642), [#647](https://github.com/riscPrint/risc-v-workstation/pull/647), [#656](https://github.com/riscPrint/risc-v-workstation/pull/656): mock callbacks and lint; no native DRAM/PCIe/MAC qualification. Other bounded RTL VIP fixtures have separate evidence in the README. |
| farm shard plans | Fixture only | [#652](https://github.com/riscPrint/risc-v-workstation/pull/652): local fake adapter; native cluster and RTL NOT RUN. |

A later bounded scalar cosim run in [#692](https://github.com/riscPrint/risc-v-workstation/pull/692)
matched real VexRiscv RTL through the DPI path and detected its injected writeback
fault at the first affected retirement. This does not change the vector row's
Spike-only scope or qualify interrupts, extended CSR capture or a second core.

## Fresh Verilog project results

The [2026-11-13 second pass](DRY_RUN_VERILOG_2026-11-13.md#second-pass) records commands, fixes
and limits for an external PicoRV32 repository. These rows do not qualify
every non-Spinal core.

The current-main recheck at `25e761bf` confirms declared-port generation,
bounded formal execution, compiler-only architecture build and HDL doctor.
The fresh full regression has 46 conclusive passes. Its 46 sealed traces match
Spike after C1 ELF hash checks.
Rebuild the local Spike shim when the installed workstation changes its ABI.
A stale shim reports an error and must not be counted as a cosim mismatch.
See the report for the exact run revisions and remaining proof limits.

| Flow | Status | Recorded scope and limit |
|---|---|---|
| Pure C++ C1/C2 and regression | 46 passes, zero inconclusive C1 results in the final full regression. | PR #911 supplies plain HDL identity capture. A committed smoke gate accepts the good revision and rejects a planted instruction-response fault. The generated run stub still needs project bus mapping. |
| Scalar cosim | 46 native matches | PR #922 adds the declared full-word read convention. All 46 traces match Spike. Raw read address/strobes, accessed data, write strobes and destination values are checked. |
| Yosys/slang query and blocks | First-pass extraction and export | Both frontends ran. SpinalBlocks JSON exported. Rendering was not run. Include-bearing slang sources retain directory capture limits. |
| Declared plain HDL checks, UVM and VIP | Bound checks and generated skeletons | PR #927 accepts a project port map without Spinal types. Native ready/valid checks observe 3 stalls and 3 transfers. pyuvm stimulus and expected results remain project work. Other declared protocols and SV UVM remain outside this path. |
| Formal ISA kit | Overall inconclusive | Existing main reports add and cover bounded at depth 8 with the core RVFI wrapper. Machine-state bindings and adapter conformance remain open. No unbounded ISA proof. |
| Hand-written SVA | Three engine passes, all inconclusive | At depth 8. The rerun does not certify input closure, attribution or non-vacuity. |
| Fault injection through the temporary native adapter | First-pass unsupported | The adapter still refuses --fault. A project injection binding is required. |
| Security IFT | First-pass potential-flow observation | Not rerun in the second pass. The first run is not a security specification or whole-core proof. |
| Architecture without gem5 | Native ELF build and Python trace model | PR #933 permits compiler-only build. The OoO model consumes 15 real retirements. Its configuration is hypothetical. gem5 run/calibrate still need the supported binary. |
| HDL doctor | JVM probes not_applicable | PR #942 uses `[project] hdl = "sv"`. The final smoke check reports build/run, C2 mapping, wave and coverage ready. Only the workstation checkout gate remains inconclusive for the pre-existing untracked `out/`. Native version probes do not qualify a tool combination. |

For SV projects, keep `rvw/hdl.json` as the source of build arguments. Map the
native harness before running programs. Copy the saved build identity claims
into C1. Rebuild when the current identity differs. Review input declarations
when you add external dependencies.

Declare protocol meaning in a `rvw.hdl-ports/1` project file. Use `--port-map`
with `rvw vip buses`, `rvw vip bench`, or `rvw uvm new`. A checks generation
manifest can supply `database` and `port_map` in its `buses` entry. See the
[declared channel contract](contracts/vip.md#declared-plain-hdl-channels).
A port map does not define memory response behavior.

Use `memory_read_convention: "full_word"` only after reviewing the capture RTL.
The initial convention supports nontrapping aligned scalar loads outside MMIO.
It does not relax store strobes or destination register comparisons.

## Other tool boundaries

These rows cover the remaining packaged tool READMEs. Each label applies to
the cited scope. It does not erase older bounded evidence in that README.

| Tool | Recorded scope | Remaining limit |
|---|---|---|
| [memory](../rvw/src/rvw/memory/README.md) | Ran on multicore RTL, cacheless | [Native SMP suite counts](../examples/smp/README.md#measured-results): LR/SC 1060 cycles / 498 retirements; AMO 18630 / 8346; six litmus cases consistent with herd7; FENCE.I 191 / 62; IPI 247 / 74; HSM 1431 / 530; Spike 38 instructions match with zero masks/sync. Three generated executions allowed; one inconclusive at 100000 candidates. Coherent cache/home binding remains open. [#917](https://github.com/riscPrint/risc-v-workstation/pull/917). |
| [privilege](../rvw/src/rvw/privilege/README.md) | Spike only for recorded program slices | Generated cases and reference self-checks do not establish DUT privilege correctness. [#622](https://github.com/riscPrint/risc-v-workstation/pull/622). |
| [memory](../rvw/src/rvw/memory/README.md) | Ran on RTL fixture | Scripted coherence monitors have bounded native tests; real cache/home binding remains open. [#653](https://github.com/riscPrint/risc-v-workstation/pull/653). |
| [privilege](../rvw/src/rvw/privilege/README.md) | Ran on RTL for controls, PMP and scheduled WFI; Spike only for the other slices | VexiiRiscv and VexRiscv results are in the README. Other generated cases and reference self-checks do not establish DUT privilege correctness. [#622](https://github.com/riscPrint/risc-v-workstation/pull/622). |
| [evidence](../rvw/src/rvw/evidence/README.md) | Fixture only | Original JSON and declared hashes are checked; native semantic validation remains open. [#604](https://github.com/riscPrint/risc-v-workstation/pull/604). |
| [checks](../rvw/src/rvw/checks/README.md) | Fixture/source binding only | Queued HPM elaboration is not a completed RTL campaign. [#639](https://github.com/riscPrint/risc-v-workstation/pull/639). |
| [plan](../rvw/src/rvw/plan/README.md) | Fixture only | Status rollups do not run tests, prove properties or establish feature closure. [#567](https://github.com/riscPrint/risc-v-workstation/pull/567). |
| [soc](../rvw/src/rvw/soc/README.md) | Fixture only for new tagged pairing | Tagged pairing still needs fresh DUT capture. Separate connected APB/AXI-Lite/UART tests ran natively in #674, and bounded CLINT/PLIC tests ran in #694; no CPU boot was claimed. [#650](https://github.com/riscPrint/risc-v-workstation/pull/650). |
| [doctor](../rvw/src/rvw/doctor/README.md) | Presence and fixture checks | No complete native combination is qualified. |
| [bundle](../rvw/src/rvw/bundle/README.md) | Fixture oracles for new event replay | A reproduced symptom needs matching real-core identities; fixtures cannot establish a causal core defect. |
| [verification_plan](../rvw/src/rvw/verification_plan/README.md) | Fixture only | Generated extension/environment matrices need native custom-extension and control campaigns. |
| [agent](../rvw/src/rvw/agent/README.md) | Fixture/document checks | A generated playbook does not establish a scratch-core end-to-end run. [#649](https://github.com/riscPrint/risc-v-workstation/pull/649). |
| [mcp](../rvw/src/rvw/mcp/README.md) | Local service/process tests | External clients, TLS proxy and RTL were NOT RUN. [#623](https://github.com/riscPrint/risc-v-workstation/pull/623). |
| [agent_bench](../rvw/src/rvw/agent_bench/README.md) | Fixture only | Behaviour models are not qualified native core mutations. |
| [workloads](../rvw/src/rvw/workloads/README.md) | Spike only for recorded slices | Linux/SPEC hooks and broader RTL performance qualification remain open. [#501](https://github.com/riscPrint/risc-v-workstation/pull/501). |
| [results](../rvw/src/rvw/results/README.md) | Schema fixture tests | Compatibility parsing cannot qualify absent evidence. |
| [bugmem](../rvw/src/rvw/bugmem/README.md) | Fixture only | No held-out real defect accuracy result exists. [#484](https://github.com/riscPrint/risc-v-workstation/pull/484). |
| [sec](../rvw/src/rvw/sec/README.md) | Ran on RTL fixture | [#696](https://github.com/riscPrint/risc-v-workstation/pull/696) checked planted digital leaks. No whole-core, physical leakage or full dynamic provenance result follows. |
| [common](../rvw/src/rvw/common/README.md) | Local process/fixture checks | Process cancellation and resource limits do not establish DUT acceptance. |
| [fault](../rvw/src/rvw/fault/README.md) | Ran on RTL | A bounded VexRiscv campaign now confirms native register injection; BOOM, memories and FMEDA remain open. [#689](https://github.com/riscPrint/risc-v-workstation/pull/689). |
| [perf](../rvw/src/rvw/perf/README.md) | Recorded trace analysis | Predictor tags need project wiring; BOOM tag validation remains open. [#451](https://github.com/riscPrint/risc-v-workstation/pull/451). |
| [ooo](../rvw/src/rvw/ooo/README.md) | Native reference parity only | Committed-trace timing has no wrong-path execution; native gem5 comparison remains NOT RUN. [#655](https://github.com/riscPrint/risc-v-workstation/pull/655). |

## Shared library boundaries

| Library | Recorded scope | Limit |
|---|---|---|
| [ComponentSims](../ComponentSims/README.md) | Native reference model tests | RTL event agreement and model fidelity need project measurements. |
| [SpinalDB](../SpinalDB/README.md) | Native elaboration and fixture queries | Graph extraction is not behavioral RTL verification. |
| [SpinalWaves](../SpinalWaves/README.md) | Native checker evidence | Interactive Surfer rendering is separate; use the vendored limits. |
| [SpinalTrace](../SpinalTrace/README.md) | Bounded VCD/Verilator validation | FST and other simulators remain unqualified. Source paths need the original sources. |
| [SpinalBlocks](../SpinalBlocks/README.md) | Extraction/diagram tests | Native HDL diagram export in #688 did not run ELK/SVG rendering or VS Code. |
| [SpinalChecks](../SpinalChecks/README.md) | Ran on bounded RTL fixtures | One GPIO register or a generated app is not whole-core or physical qualification. |
| [SpinalKonata](../SpinalKonata/README.md) | Captured trace analysis | Standalone compiled-model capture is incomplete; retain its C1 error and null cache key. |
| [RiscvSim](../RiscvSim/README.md) | Ran on RTL, selected adapters | Fault, DPI and SystemC checks have different scopes. No all-option or BOOM qualification follows. |

Do not promote an issue closure, unit test, source pin or equal record count to
DUT qualification. Keep each new core's measured results and limits in its own
repository. See [the command reference](COMMAND_REFERENCE.md) for options and
[the contracts](PLATFORM_CONTRACTS.md) for required records.

## Machine-readable workflows

Use `rvw agent guide --json` or MCP `agent_guide` for ordered tool calls and
decision points. Select `bring-up`, `test-fails`, `add-coverage`,
`prove-property` or `performance-question`. The same data is available at
`rvw://agent/guide`. The playbook preserves the evidence limits in this guide.
A repair needs a reproduced failure, matching artifact identities, passing
repair workloads and an independent gate result. Missing evidence stays
inconclusive.

## Fresh-core dry-run evidence

[The independent RV32I dry run](DRY_RUN_2026-11-13.md) records native results,
refusals and open integration work. It does not transfer whole-core support.

| New-core flow | Measured status | Limit |
|---|---|---|
| Smoke and scalar cosim | Ran on independent RTL | Final smoke and Spike cosim passed, 19 instructions and 29 cycles, with a C1 RTL hash. |
| Query and diagrams | Database and export worked | A shared project config resolved the reset mismatch; viewer rendering was not checked. |
| Probes, perf, waves and coverage | Native capture and C1-based coverage worked | One short program; missing probe events remain explicit. No coverage closure. |
| Regression, formal, security | Four ISA passes; bounded formal; IFT blocked | Final four-test regression exited 0. One formal property passed to depth 6 with overall inconclusive. IFT refused X/Z constants. |
| UVM, VIP, SoC and architecture | Partial or unsupported | Historical first pass. The second pass adds a simple bus bridge, verifies the VIP CLI and accepts base-I model selections. |
| MCP | Twenty stdio calls exercised | Successful results and the architecture/UVM/security refusals are recorded in the report; job completion is not a DUT pass. |


## Development path vs gate path

Start with direct adapter runs while mapping the core. Build a smoke ELF.
Check C1 completion and the C2 stream. Then run a regression suite with
`--rvfi-trace` and compare each trace with the independent reference.
Exclude build side products such as `.dump` from the suite's ELF pattern.
A smoke match does not establish full ISA correctness.

`rvw init --wire-build --sbt-project ID --db-top PACKAGE.Top` now declares the
standard external launcher inputs. It supplies both `elaborate` and
`generatedVerilog(model)`. Extend `cache_paths` and `input_env` for custom
inputs. Keep the RTL mismatch check. An unwired stub still refuses execution.
The launcher caches its compiled classpath in `rvw/target/rvw-classpath.json`.
It rebuilds after source, build, environment or runtime file changes. Its sbt
lock is `sbt-<project-name>`. Use unique project names for private build trees.

Gate runs also need reviewed complete inputs, clean commits and exact identity
capture. A dirty development run can pass its tests without earning gate
acceptance. Do not turn an incomplete declaration on to bypass a refusal.

Use the generated `Elaboration.top()` and `Elaboration.config` for simulation
and SpinalDB. Formal and lint use the RTL recorded by that database. Rebuild
it after edits. This carries the selected clock/reset policy into each flow.
Default single-clock formal refuses ASYNC state. Constant-value ASYNC reset
FFs can use `--event-model --async-reset` with BMC, apps or autocheck.
IFT gives an early fix hint for unsupported state. A project that selects SYNC
must rebuild every flow from the shared entry. IFT treats X/Z as either Boolean
value with taint set. It does not model electrical high impedance.

Minor/Timing architecture descriptions and scheduling component models accept
RV32I and RV64I without M. RV64 O3 also accepts RV64I. Select actual core
resources. Static compatibility does not validate behavior. Gem5 execution
still needs its installed backend.

For a one-outstanding memory interface, bind a project `SimpleCoreWrapper` and
select `core.bus = "simple"` in the SoC composition. The APB3 bridge preserves
wait states, errors and write byte masks. The project must hold the CPU until
completion. Existing AXI4-Lite wrappers have their own ingress. An idle wrapper
is not evidence that the core executes a program. See [SpinalSoc](../SpinalSoc/README.md).

The init probe stub flushes both younger slots on redirect. Bind actual IDs
and measured stall causes. Check exact declarations after an instrumented run:

```sh
rvw probes check --events run/probe-events.jsonl --require flush/fetch --require flush/decode --require stall
```

Presence does not establish activation or correct wiring. A core that cannot
wait can declare inactive wait probes. Keep that limit in its report.
The [second pass](DRY_RUN_2026-11-13.md#second-pass) records native evidence and
remaining limits for the independent scratch core.
## Connected generated check captures

The 2026-11-13 captures compile generated checks into the selected simulation.
These are native simulation counts. The three retained formal captures contain
99 check IDs with depth-4 BMC results. The later 33-check capture has no formal run.
Each formal job selects one fail signal in the retained #921 RTL capture. Reset
is constrained for two samples. Activation was not measured. No unbounded proof
was obtained. The Vexii PC formal rule is the original strict rule before the
later cancellation binding. See the [formal record](../SpinalChecks/connected-depth4-results.json).

| Design | Generated | Bound | Proven | Bounded | Fired IDs / events | Unbound and reason |
|---|---:|---:|---:|---:|---:|---|
| VexRiscv | 57 | 57 | 0 | 57 | 0 / 0 | 0; native bindings present |
| VexiiRiscv | 25 | 25 | 0 | 25 | 0 / 0 | 0; native bindings present |
| VexiiRiscv, nine catalog CSR programs | 33 | 33 | NOT RUN | NOT RUN | 0 / 0 | 0; accepted CSR interface, including RAM |
| Composed RV32 stub SoC | 17 | 17 | 0 | 17 | 0 / 0 | 0; native bindings present |

The [nine-CSR Vexii record](../examples/vexiiriscv/csr-bank-native-results.json) has nine RTL passes,
eight Spike passes and one retained `marchid` configuration mismatch. The new
33-check binding has no formal run. Earlier 25-check formal evidence stays separate.

VexRiscv passed 49 aligned ISA programs with 49 C1 passes. VexiiRiscv ran two
CSR programs. Both have C1 passes after an exact PC hold cancellation binding.
The two original valid-hold firings are retained as tool false positives with
wave windows. The composed SoC passed hello with UART output checked.
Its core is a limited instruction stub. These results do not qualify whole cores,
all CSR addresses, all peripherals, or all protocol behavior.

See [SpinalChecks](../SpinalChecks/README.md#connected-captures-on-three-designs)
for selected check IDs, assumptions, capture records and reproduction commands.
Unknown cancellation semantics retain strict checks. Project cancellation
bindings require an exact stream path, condition, sample timing and review reason.

## Measured check models and templates

These 2026-11-13 tests are separate from connected core qualification.

| Capability | Evidence | Measured result | Remaining limit |
|---|---|---|---|
| Recovery and fence drain | Native Verilator template | 1 legal and 14 detected fault scenarios | No core event/age binding or recovery proof |
| HPM event selection and mode filters | Native Verilator template | 1 legal and 2 detected fault scenarios | No core HPM binding; OF remains separate |
| Coherent cache/reservation oracle | Scala model | 3 tests pass, including source-specific capability limits | No RTL cache binding or concurrent coherence model |
| Dynamic IMSIC indirect registers | Python model | 11 cases pass; unknown state remains inconclusive | No core binding, denial, arbitration or delay proof |
| Clock gates beside UPF domains | Generated monitors and native Icarus fixtures | 6 generation cases and 4 native cases pass | Explicit companion bindings; no Tcl gate command or physical proof |

The [validation record](../SpinalChecks/model-validation-results.json) gives
source hashes and test scope. The [check README](../SpinalChecks/README.md#measured-model-and-template-results)
keeps the core-binding limits. Core-specific integration must supply independent
observations and new execution evidence. Model tests do not transfer proof to a
core or peripheral.

## UVM and VIP integration

Select the project's actual bus, clock/reset domain, memory map and completion
condition. Supply a live binding or a declared capture-replay path. A generated
bench is a scaffold. Its unchanged scenario hook must fail. A build or empty
UVM phase cannot qualify the DUT. See [the UVM flow](../rvw/src/rvw/uvm/README.md)
and [the protocol agents](../rvw/src/rvw/vip/README.md).

For an SV bench, list sources in dependency order in `bench.json`. Add the
project's tests and required checks. Use a fresh build and run directory:

```sh
rvw uvm build bench.json --out /tmp/project-uvm-build --timeout 1800
rvw uvm regress --build /tmp/project-uvm-build --seeds 1 3 --out /tmp/project-uvm-runs
rvw uvm gate-config --build /tmp/project-uvm-build --source-repo "$PWD" --out /tmp/project-uvm-core.toml --seeds 1 3
rvw regress gate --core /tmp/project-uvm-core.toml --tier quick --base-rev COMMIT --cand-rev COMMIT --no-cache --json
```

Commit the source before the gate. Use that revision for COMMIT.
Rebuild after a source change. Keep project sources in the selected repository.
Declare external SV support sources as frozen dependencies. Declare
`native_dependencies` for DPI headers, runtime libraries, generated images
and other native inputs. The project must declare the complete native set.
The flow hashes those files and captures them with the executable and source.
It refuses changed declared inputs. `gate-config` stages a runtime bundle
beside its TOML. It omits compiler intermediates and keeps the capture limits.
A native dependency declaration alone does not qualify its ABI or behavior.

The following matrix records the measured profiles on 2026-11-13. It does
not transfer qualification to a new core, bus configuration or simulator.

| Profile | Measured result | Evidence boundary |
|---|---|---|
| SV protocol agents, Verilator 5.052 | 20 compiled. All 16 runnable fixtures passed their declared normal and fault cases at three seeds: 120 checked runs. | DRAM, Ethernet, PCIe and RNM have inert SV model stubs. AXI4-Lite has no separate SV runtime result. The reactive fixtures use one UVM phase invocation per component. |
| Live VexRiscv SV CPU environment | Seeds 1 and 3 each checked 13 retirements. Next-PC corruption was detected. Same-revision C4 returned `accept` at `b17abae9`. | Fixed generated CPU image and one arithmetic/load/store/branch program. Fifteen declared native files participate in identity. No changed-core or full-ISA acceptance. |
| Live VexRiscv pyuvm RV32IM ISA | 50 attempted, 49 passed, 1 failed. Passing programs checked 17,735 retirements and 196 traps. | `rv32ui-p-ma_data` failed with tohost 1337. This is the built RV32UI/RV32UM machine-mode set, not a complete upstream ISA matrix. |
| Native VexiiRiscv ISA captures through pyuvm | 50 native programs attempted. 49 complete passing captures checked 17,637 retirements and 245 traps. | Offline C2 replay. The native `ma_data` failure remains explicit. No live cocotb VexiiRiscv binding or full suite pass. |
| Composed SpinalSoc scenarios | Two pyuvm tests passed. Each checked 32 IRQ pulses, bus-error injection and reset during a stalled write. | Peripheral and fabric checks. Scenario seeds 1 and 7; simulator seed 1. CPU checks: zero. |
| Python PCIe, Ethernet, DRAM and coherent agents | Four native good/bad campaigns passed at seed 17 on Icarus 14.0 devel. | Seeded semantic RTL endpoints. No physical link, vendor model, JEDEC timing, MAC/PHY implementation or complete coherent protocol qualification. |
| Custom-bus project adapter | Verilator 5.049: 82 transfers and 83 positive checks passed at seed 17. Corrupt read data failed with `APB_DATA`. | Explicit APB4 semantics on custom pins. Declared database fixture and generated pyuvm bench. No automatic protocol discovery, CPU execution or C4 acceptance. |

Use the detailed records for exact checks and limits:

- [SV protocol matrix](../Uvm/vip/qualification/native-2026-11-13.md).
- [Live SV CPU and DPI/C4 result](../Uvm/examples/vexriscv/sv/README.md).
- [Live VexRiscv ISA campaign](../Uvm/examples/vexriscv/ISA.md).
- [VexiiRiscv native capture replay](../Uvm/examples/vexiiriscv/README.md).
- [Composed SoC scenario project](../Uvm/examples/composed/README.md).
- [Python semantic endpoint matrix](../Uvm/vip/rtl/CONTRACT_RESULTS.md).
- [Custom-bus adapter RTL result](../Uvm/examples/custom_bus/README.md).

The SV campaign uses pinned Accellera UVM 2020.3.1 with `UVM_NO_DPI`.
The CPU example links a separate matched ABI 6 Spike DPI bridge. This does
not enable or qualify Accellera HDL backdoors. Standalone C3 source identity
remains incomplete. Only the recorded committed CPU bench gate earns the
stated C4 acceptance. Keep failed, unsupported and unmeasured profiles open.

## Prove your core against the ISA

Start with the ISA and privilege modes of the elaborated RTL. Pin the core
revision. Keep the source outside the workstation repository. Use a private
source copy and a private lock for native runs.

1. Export retirement-aligned RVFI through project-owned elaboration code.
   Observe operands, writes, memory effects and next PC at the correct event.
   A later commit PC needs a model for intervening traps. A simulation callback
   cannot supply hardware inputs to a formal job.
2. For a core without RVFI, map architectural snapshots with
   `rvw formal state-generate MAP.json --out MONITOR`. The snapshots must span
   one instruction event. Include trapping instruction records when required. Compare the generated stream with an independent
   observation in simulation. Run bounded equivalence. Keep a mismatch as a
   failure until its cause is resolved.
3. For native RVFI, generate the project wrapper with
   `rvw formal rvfi-generate BINDING.json --out PROJECT`. The state generator
   already writes a project. Declare source files, signal maps, ISA, retirement
   channels, checks and cycle settings in project data. Declare bus service
   assumptions explicitly. Do not assume the property under test.
4. Run `rvw formal isa --project PROJECT --out OUT --timeout 150`. This runs the
   selected bounded instruction and consistency checks. It also runs an
   instruction-specific activation cover. It lists unselected instructions
   and missing retirement-channel checks as unsupported gaps. A general
   retirement cover cannot qualify an unreachable instruction check.
5. Add `--machine MACHINE.json` for the generated RV32 machine transition
   properties. Bind entry and return events, CSR before and after values,
   fetch responses, killed instruction state and trap redirects. The project
   must supply aligned observations. The current writeback flush flag alone
   does not prove that an earlier killed instruction cannot retire.
6. Select generated Sail models through `riscv_formal.instruction_models`.
   `rvw formal sail-m --model MODEL --compiler SAIL --out MODELS` generates
   RV32 M arithmetic slices. Keep `RISCV_FORMAL_ALTOPS` disabled for actual M
   arithmetic. Keep source, compiler, primitive-binding and final model hashes.
   Expression slices do not independently verify full machine state.
7. Add `--unbounded` to run the original instruction proof portfolio. Use
   `--abstraction MAP.json` for a separate conditional single-flight and RAM
   experiment. Keep the original result. An abstraction proof has its own
   scope. An abstract counterexample needs refinement. An unclosed activation
   obligation remains inconclusive.

The ISA and instruction-proof MCP tools accept `project` for call-level
selection. CLI commands and MCP tools retain the same result files.
Use a new output directory for each run. Keep native task trees, source hashes,
engine logs, assumptions and cover traces. Do not combine different
elaborations into one uniform campaign.

The result table distinguishes proven, bounded with a cycle bound, failed,
unsupported, not applicable and inconclusive. A timeout is inconclusive.
A reached cover is reachability evidence. It is not a proof of the property.
A not-applicable row needs an explicit project feature boundary. Check every
unsupported row before claiming signoff.

### Measured kit status

These results were measured on 2026-11-13. They apply to the named snapshots
and checks. Full core ISA signoff remains incomplete.

| Core and check | Result | Scope |
| --- | --- | --- |
| VexRiscv FormalSimple, 37 selected instruction checks | bounded PASS | Depth 20; earlier recorded campaign |
| VexRiscv FormalSimple, liveness with declared bus service | bounded PASS | Depth 30; finite-service assumptions |
| VexRiscv FormalSimple, RVFI x0 values | bounded PASS | Depth 20; trigger reached |
| VexRiscv FormalSimple, current writeback flush slot | bounded PASS | Depth 20; SMT retry; no instruction-ID kill history |
| VexRiscv FormalSimple, CSR and interrupt transitions | not applicable | This snapshot has no corresponding controllers |
| VexRiscv FormalSimple, instruction-memory pairing and trap PC chain | unsupported | Project observations are missing |
| VexRiscv RV32IM, exception and interrupt entry | bounded PASS | Depth 25; both controller triggers reached |
| VexRiscv RV32IM, machine return | FAIL | Step 15; second return has captured MPP zero and current privilege 3 |
| PicoRV32 architectural monitor, three simulation programs | matched sampled streams | 30 retirements per program |
| PicoRV32 base-RVFI bounded stream comparison | FAIL | Depth 35; misaligned JAL trap/write difference at step 10 |
| PicoRV32 fourth-retirement cover | reached | Step 18 |
| VexiiRiscv hardware observer | prototype; unsupported for signoff | Hardware elaboration passed; memory and trap alignment remain incomplete |
| VexiiRiscv ADD and LUI diagnostic checks | timeout | Depth 60; 150 seconds per job; retirement cover reached |
| Sail RV32 M model preparation | generated and Yosys checked | Eight arithmetic slices; 392 corner comparisons passed |
| VexRiscv RV32IM, eight Sail M assertion jobs | timeout | Depth 60; 90 seconds per job |
| VexRiscv RV32IM, four multiply retries | timeout | Depth 20; 120 seconds per job; all four target covers reached |
| VexRiscv RV32IM, Sail MUL and MULHU with Bitwuzla | timeout | Depth 20; 150 seconds per job; both target covers reached |
| VexRiscv LUI, all-word RAM abstraction and single-flight restriction | PDR PASS | Conditional unbounded model proof; 107.4 seconds; concrete cover reached |
| VexRiscv ADD and AND, all-word RAM abstraction | abstract counterexamples | SMT witnesses; not core failures |
| VexRiscv ADD, AND and LUI, word zero retained | timeout | 180 seconds per PDR job; concrete covers reached |

The older FormalSimple profile is RV32IC. The new M profile is RV32IM with a
CSR controller. Three controller checks were run. Full machine checks remain
incomplete. See [the controller results](../examples/vexriscv/formal/MACHINE_M.md).
The eight generated
machine transition rules have native Yosys preparation evidence. Their current
FormalSimple binding covers only x0 values and the writeback slot check.

The PicoRV32 comparison failure remains unresolved. The VexiiRiscv observer
needs completion, memory and trap alignment before qualification. The Sail M
assertion jobs did not close. The conditional LUI proof does not establish
unrestricted pipeline behavior, assumption activation or adapter conformance.
The ISA command retains these gaps in its table.

See [the VexRiscv records](../examples/vexriscv/formal/GENERATED_RESULTS.md),
[the PicoRV32 comparison](../examples/picorv32/formal/README.md),
[the VexiiRiscv observer](../examples/vexiiriscv/formal-observer.md),
[the Sail M campaign](../examples/vexriscv/formal/SAIL_M.md) and
[the conditional proof records](../examples/vexriscv/formal/ABSTRACT_RESULTS.md)
for source pins, measured variants, limits and reproduction commands.

## Give your core a SoC

Use the composer when the core needs a verification memory map, bus fabric
and peripherals. Keep the core wrapper and composition file in the core's
project. The wrapper selects a supported ingress and binds its interrupt vector
and debug-reset input. See [SpinalSoc](../SpinalSoc/README.md) for the exact
wrapper traits and [the Vex example](../SpinalSoc/examples/vex/README.md) for a
real CPU integration.

1. Create a `rvw.soc/1` map with aligned, disjoint windows and explicit registers.
2. Create a `rvw.soc-compose/1` composition with one binder per region.
3. Select the core wrapper and its bus in `core.class` and `core.bus`.
4. Set the clock frequency and reset kind.
5. Add explicit domains for peripherals which use a separate clock.
6. Generate the top with `rvw soc compose SPEC --out NEW_DIR`.
7. Compile the generated top with the wrapper and selected peripheral sources.
8. Run a directed program or independent bus-master test with assertions enabled.
9. Supply consumer bindings to `rvw soc verify MAP --manifest VERIFY --out NEW_DIR`.
10. Read every row and its detailed reasons in `result.json`.

`rvw soc peripheral watchdog` and `rvw soc peripheral block` export the new
register profiles. Their examples drive a composer-generated SoC through its
simple-bus ingress. They are peripheral/fabric tests and execute no CPU
instructions. Watchdog reset requests need an explicit project reset-controller
binding. The block device is volatile and implements no physical SD signalling.

The composed VexRiscv example was measured on 2026-11-13 at seed 31. Its real
CPU register program passed in 248 cycles and 36 retired instructions. The
combined verification command produced this table:

| kind | generated | ran | result |
|---|---|---|---|
| protocol | yes | yes | inconclusive |
| registers | yes | yes | inconclusive |
| vip | yes | yes | inconclusive |
| uvm | yes | yes | pass |
| connectivity | yes | yes | inconclusive |
| decode | yes | yes | proven |
| cdc_rdc | yes | yes | inconclusive |

The pyuvm bench checked 17 known-reset reads with an independent bus master.
The fabric proof covers map windows and unmapped completion. It excludes core
and peripheral state. Connectivity timed out during internal RTL binding.
Multi-domain lint ran on the composition with a 10 MHz CLINT domain. It found
2 clock sources, 293 registers, 9 CDC paths and 2,507 structural findings.
Those findings and unrun reset/protocol obligations remain open. Sampled
protocol/register/VIP matches do not qualify every behavior. Read the
[measured record](../SpinalSoc/examples/vex/VERIFICATION.md) before reusing the
profile. A new core, peripheral or clock configuration needs fresh evidence.

The UART profile is still a subset. Full 16550 behavior, boot-from-flash,
native AXI4/TileLink crossbars, AXI width conversion, composer-hosted SMP,
external-IP import and composed debug-module integration remain separate work.
The existing standalone SMP example is unchanged.
## Write properties for your core

Keep signal bindings beside your elaboration code. Do not put core signal names
in the generic formal library. The VexRiscv example uses
`examples/vexriscv/rvw/src/main/scala/rvwvex/CoreProperties.scala`.
It adds observation ports and writes the Scala DSL statements to a separate
file. It does not edit the upstream core.

Add the `SpinalChecks` project dependency to your build. Import
`spinalchecks.Sva._`. Use typed signals where possible:

```scala
import spinal.core._
import spinalchecks.Sva
import spinalchecks.Sva._
def observe(name: String, value: BaseType): Expr = {
  val port = out(cloneOf(value)).setName(name)
  port.assignFromBits(value.asBits)
  signal(port)
}
val fire = observe("check_fire", bus.fire)
val valid = observe("check_valid", bus.valid)
val payload = observe("check_payload", bus.payload.asBits)
val stalled = observe("check_stalled", bus.valid && !bus.ready)
val checks = Seq(
  fire.sequence.implies(valid.sequence).assertOn("fire_valid", signal("clk"), Some(signal("reset"))),
  stalled.sequence.implies(payload.equal(payload.past).sequence, overlap = false)
    .assertOn("stall_payload", signal("clk"), Some(signal("reset")))
Sva.write(outputPath, checks)
```

Place this code in the top component, as in the example. `outputPath` is a
`java.nio.file.Path`. The writer emits statements. It does not insert assertion
hardware in your design. Bind the emitted signal names to ports or names that
remain visible in the RTL. Add the monitor integration to your project harness.
The example's `core-properties-sim.py` shows the finite monitor integration.
Its `core-progress.py` shows eventual-response accounting.

A wrapper around `assertOn` can pass `sourceDepth = 1` to retain its caller's
DSL line. Check that the generated `rvw-source` annotation identifies that call.
C1 assertion rows and C3 property rows retain this location. A failed program
and a failed property are separate results. A passing finisher value must not
hide a failed assertion.

### Run simulation and formal checks

Use a private core copy. Keep build outputs in your worktree. Use the private
core and sbt locks named in your worker brief. The VexRiscv commands are in its
[Scala property campaign](../examples/vexriscv/README.md#scala-dsl-property-campaign).
Compile once. Run each ISA program in a fresh native process.

Read each property's `failed` and `activated` counts. Assertion pass counts
include false antecedents. Zero failures with zero activations gives no exercised
implication. Covers record reached conditions. Eventual-response checks also
need `pending`. A finite test with pending requests is inconclusive. Completion
of every observed request does not prove behavior on an infinite execution.

For formal checks, export one self-contained SBY job per property. Prepare a
`regress.toml` with `[[property]]` rows. Each row needs `id`, `sby` and `top`.
Record the assumptions and the DSL source location. Add `activation_sby` for a
separate antecedent-cover job. Use the same reset and environment assumptions
in both jobs. A cover not reached within N cycles is not an unreachability proof.

```sh
rvw formal regress regress.toml --jobs 3 --timeout 60 --proof-cache proof-cache --out proof-1 --json
rvw formal regress regress.toml --jobs 3 --timeout 60 --proof-cache proof-cache --out proof-2 --json
```

Keep C3, JUnit and the per-property logs. Read `formal_status` and the depth.
A `bounded-pass` result checks only its bound. A cache hit restores a prior
conditional engine observation. It is not a new proof. Changes to captured
sources, tools or relevant code invalidate an eligible cache entry. Missing
source closure can make a job ineligible for caching.

### Measured VexRiscv table

The safety rows below come from the earlier 49-program native campaign on
VexRiscv `a62c145a`, SpinalHDL 1.15.0 and Verilator 5.049. Formal used at most
three workers and two initial reset clocks. Other inputs were arbitrary. Each
safety assertion has a bounded result at depth 12. Six antecedents were not
exercised in simulation. The table records those gaps.

The final row is a separate native eventual-release campaign from this run.
It uses the same 49 aligned programs. Its formal lasso search uses one startup
reset clock and no progress fairness. It does not prove infinite-trace liveness.

| Property | Sim pass | Sim fail | Sim active | Sim cover | Formal | Antecedent cover |
|---|---:|---:|---:|---:|---|---|
| `stage0_fire_valid` | 42769 | 0 | 17931 | 0 | bounded 12 | reached |
| `stage0_fire_not_stuck` | 42769 | 0 | 17931 | 0 | bounded 12 | reached |
| `stage0_fire_not_removed` | 42769 | 0 | 17931 | 0 | bounded 12 | reached |
| `stage0_stall_pc` | 42720 | 0 | 1546 | 0 | bounded 12 | reached |
| `stage1_fire_valid` | 42769 | 0 | 17735 | 0 | bounded 12 | reached |
| `stage1_fire_not_stuck` | 42769 | 0 | 17735 | 0 | bounded 12 | reached |
| `stage1_fire_not_removed` | 42769 | 0 | 17735 | 0 | bounded 12 | reached |
| `stage1_stall_pc` | 42720 | 0 | 588 | 0 | bounded 12 | reached |
| `stage2_fire_valid` | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `stage2_fire_not_stuck` | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `stage2_fire_not_removed` | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `stage2_stall_pc` | 42720 | 0 | 1188 | 0 | bounded 12 | reached |
| `stage3_fire_valid` | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `stage3_fire_not_stuck` | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `stage3_fire_not_removed` | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `stage3_stall_pc` | 42720 | 0 | 0 | 0 | bounded 12 | not_reached_within_bound |
| `pc_chain_0` | 42720 | 0 | 17931 | 0 | bounded 12 | reached |
| `pc_chain_1` | 42720 | 0 | 17735 | 0 | bounded 12 | reached |
| `pc_chain_2` | 42720 | 0 | 17686 | 0 | bounded 12 | reached |
| `ibus_hold_valid` | 42720 | 0 | 19737 | 0 | bounded 12 | reached |
| `ibus_hold_pc` | 42720 | 0 | 19737 | 0 | bounded 12 | reached |
| `ibus_pc_aligned` | 42769 | 0 | 40196 | 0 | bounded 12 | reached |
| `dbus_hold_valid` | 42720 | 0 | 0 | 0 | bounded 12 | reached |
| `dbus_hold_address` | 42720 | 0 | 0 | 0 | bounded 12 | reached |
| `dbus_hold_data` | 42720 | 0 | 0 | 0 | bounded 12 | reached |
| `dbus_hold_write` | 42720 | 0 | 0 | 0 | bounded 12 | reached |
| `dbus_hold_size` | 42720 | 0 | 0 | 0 | bounded 12 | reached |
| `x0_write_zero` | 42769 | 0 | 4747 | 0 | bounded 12 | reached |
| `retire_machine` | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `retire_rv32` | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `retire_pc_aligned` | 42769 | 0 | 17686 | 0 | bounded 12 | reached |
| `trap_mie_clear` | 42769 | 0 | 196 | 0 | bounded 12 | reached |
| `trap_mpp_machine` | 42769 | 0 | 196 | 0 | bounded 12 | reached |
| `trap_mepc_aligned` | 42769 | 0 | 196 | 0 | bounded 12 | reached |
| `retirement_reached` | 0 | 0 | 0 | 17686 | NOT RUN: cover | NOT RUN |
| `trap_reached` | 0 | 0 | 0 | 196 | NOT RUN: cover | NOT RUN |
| `stage0_eventual_release` | 1742 | 0 | 1742 | 0 | bounded lasso 12 | reached |

See [the safety source table](../examples/vexriscv/property-results.md) for its
measurement limits. Register-file checks observe RVFI writes. They do not check
every physical storage write. The memory model does not exercise data-bus
backpressure. Instruction identity and eventual retirement remain open.

### Review mined candidates

`rvw formal trace-mine` emits Scala DSL candidates from pre-edge signal samples.
Supply a manifest with unsigned signal widths. Pass one `--trace` per program.
Trace boundaries prevent false transitions between independent runs. The tool
drops refuted candidates and candidates with too few active samples.

The [measured mining run](../examples/vexriscv/mining-results.md) used 42,769
samples from 49 aligned ISA programs. It retained 87 candidates and dropped
730 refuted candidates and 57 inactive candidates. The emitted source is
not enabled by default. Some relations depend on signals constant in this
suite. Review each candidate. Then run a fresh proof with explicit assumptions.
Do not use an observed candidate as an assumption.

### Current limits

The generated [SVA support table](../rvw/src/rvw/formal/TEMPORAL_SUPPORT.md)
identifies tested subsets. Default clocking and default disable conditions are
module-local subsets. Nested eventual milestones accept two to eight ordered
Boolean terms. General nested unbounded composition and formal reset
cancellation remain unsupported. `rvw formal cross-prove` checks a Boolean two-clock
implication in a discrete global-step model. It samples pre-update values and
adds no clock fairness. Positive native induction jobs and negative jobs cover
both implication forms. This does not qualify full multi-clock SVA or events
between global samples. Multi-clock native replay is finite simulation evidence.

The [scenario example](../examples/vexriscv/scenarios/README.md) compiles 12
literal MMIO actions to a bare-metal image and a CPU-backed pyuvm virtual
sequence. Both run on the real composed SoC. Their 24 observations match.
They use the same CPU image. Independent stimulus executors, dynamic produced
data, symbolic constraints, randomized schedules and PSS parsing remain open.
