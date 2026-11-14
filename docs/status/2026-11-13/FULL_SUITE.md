# Full suite rerun, 2026-11-13

The rerun ran on 2026-11-13 and 2026-11-14 UTC. It is not green. The rerun uses main `f94b3a3b18a64f1bfd361115fc978c3848e12798`. The tracked source stayed fixed during the run. Earlier diagnostic runs and targeted repair tests are excluded from these totals. The previous mixed-revision run had 7,813 passes, 47 failures and 168 skips. Its skip table is retained below as historical data. A later main commit is not qualified by this run.

Python used at most three workers per batch and four across this task. Every batch had a 900-second cap. Heavy native files ran with one worker. Native jobs used `nice -n 10`. sbt used the private `sbt-uvm` lock. `SPINAL_BOOM` selected an empty directory. No BOOM build or simulation ran.

## Results

| Suite | Pass | Fail | Skip | Scope |
|---|---|---|---|---|
| Slow Python | 7964 | 1 | 203 | 0 setup errors; 0 missing IDs |
| SpinalTrace Rust | 31 | 0 | 0 | workspace and doc tests |
| Typed-wave Rust checker | 8 | 0 | 0 | native tests |
| VS Code JavaScript | 41 | 0 | 0 | typecheck and build also pass |
| SpinalBlocks JavaScript | 16 | 0 | 0 | typecheck and build also pass |
| `ComponentSims/tests` | 101 | 0 | 0 | pytest folder |
| `SpinalChecks/coherence` | 5 | 0 | 0 | pytest folder |
| `examples/naxriscv/rvw/tests` | 5 | 0 | 0 | pytest folder |
| `examples/smp/rvw/tests` | 11 | 0 | 1 | pytest folder |
| `examples/vexiiriscv/rvw/tests` | 10 | 0 | 13 | pytest folder |
| `examples/vexriscv/formal/tests` | 3 | 0 | 0 | pytest folder |
| `examples/vexriscv/rvw/tests` | 3 | 0 | 40 | pytest folder |
| Composed UVM scenarios | 2 | 0 | 0 | fresh RTL; outside Python totals |

VS Code UI and debug integration processes both exited 0. The native UVM, protocol and connected-SoC pytest cases are included in slow Python, not added again. The run selected 8168 slow Python test IDs.

Delivery checks passed: 3,669 fast tests passed with four skips. All 45 release-hygiene cases passed.

The Python audit matches collected test IDs to JUnit results. Each ID contributes once. All 54 batches completed. The largest batch took 112 seconds. No batch reached its 900-second cap. Fast deselections are not skips. Expected fault controls count as passes only when their rejection checks pass. Native crashes and Scala cancellations remain separate from passes.

| Scala project | Released: pass/fail/cancel/native | Old: pass/fail/cancel/native |
|---|---|---|
| SpinalWaves/spinalwaves | 18/0/0/0 | 16/0/1/1 |
| SpinalTrace/spinaltrace | 27/0/0/0 | 25/1/1/0 |
| SpinalDB/spinaldb | 89/0/0/0 | 86/0/3/0 |
| SpinalChecks | 149/0/0/0 | 148/1/0/0 |
| SpinalProbes | 5/0/0/0 | 5/0/0/0 |
| RiscvSim | 212/0/0/0 | 207/4/0/1 |
| SpinalKonata/inputs | 7/0/0/0 | not this axis |
| SpinalKonata | 6/0/0/0 | not this axis |
| SpinalBlocks/spinalblocks | 6/0/0/0 | not this axis |
| SpinalSoc/db | 0/0/0/0 | not this axis |
| SpinalSoc | 0/0/0/0 | not this axis |
| Total | 519/0/0/0 | 487/6/5/2 |

Native counts are crashes or aborts that prevented a Scala verdict. The Vex example has no Scala test cases. Its test sources compiled. Vexii has 32 passing Scala cases. SpinalSoc root and database have no Scala cases. The UVM SoC and composed-SoC Scala projects compiled and generated fresh RTL. Seven auxiliary builds also compiled with no Scala cases: bus binding, the small OoO check example, ooo-mini, coverage, Tiny Spinal, agent bring-up and the mapped adapter.

The released axis used SpinalHDL 1.15.0 and Scala 2.13.14. The old axis used the clean Nax SpinalHDL source `c362657003fa178350d6955055867e9ab363c44a` and Scala 2.12.18 through `RVW_SPINAL_SOURCE`. Both axes tested all six affected libraries. The old axis used Verilator 5.049 devel, `v5.048-26-g25d4827bd (mod)`, with `-CFLAGS -DVL_TIME_CONTEXT --assert`. The released axis and Python used Verilator 5.052. FST compilation needed the installed LZ4 include and library paths. Those paths were set only for the FST formal batch. They were not passed to core adapters as opaque build inputs.

Other tools were JDK 21.0.13, RISC-V GCC 15.1.0, Spike 1.1.1-dev, Yosys 0.64+174 and the installed OSS CAD Suite slang plugin, and Z3 4.13.4. The gem5 test used the installed RISC-V gem5 25.1.0.1 binary. Tool presence does not establish a proof result.

## Real core flows

| Flow | Pass | Error | Inconclusive | Scope |
|---|---|---|---|---|
| vexriscv | 2 | 0 | 0 | rvw regress smoke |
| vexiiriscv | 2 | 0 | 0 | rvw regress smoke |
| naxriscv | 2 | 0 | 0 | rvw regress smoke |
| smp | 0 | 1 | 1 | rvw regress smoke |
| soc | 4 | 0 | 0 | rvw regress smoke |
| SMP direct | 1 | 0 | 0 | 23 retirements; separate from regress |

The SMP regression attempt is the main flow blocker. The adapter declares `input_complete=false` and lacks `cache_paths`, `input_env` and `input_tools`. Regression refuses conclusive execution with `input_not_captured:adapter_dependencies`. The report does not turn on `input_complete` without the missing declarations. A separate direct two-hart seed-17 run passed. It does not repair or qualify the regression path.

The three single-core runs used private pinned source checkouts with the adapters from the tested main commit. Their source heads were VexRiscv `a62c145aa042a5de874344e0a7683bd7c8c8c870`, VexiiRiscv `9b63f47fe559dbba7874af9196746412fa1294c1`, and NaxRiscv `9f452d50560d02fb391bc8039f5453c54e0911af`. The Nax launcher now compiles with Verilator 5.052 through the `WData=EData` alias. C1 smoke passes are bounded program results. They are not whole-core or strict Spike qualification. The copied adapters and untracked run output made the core and tools checkouts dirty. The base source heads and captured fingerprints identify those inputs. This prevents a release-accept claim.

The examples' own pytest folders ran without core rebuilds. Their native cases skipped when a private core or capture was required. The separate regress rows above supply native smoke evidence. The composed UVM SoC RTL was regenerated before its two cocotb scenarios ran. That fixture has no CPU.

## Repairs and remaining failures

The slang inventory pins frontend `4a77e391c2a66bf1caec5e076b7e29609123985b` and slang `42710c788ce76cd08ce2080773e0b8286c428a05`. The installed OSS CAD Suite plugin loads but rejects a clocked assertion. Capability probing now skips the affected tests with this exact reason:

> Installed yosys-slang lacks clocked SVA lowering (SVA unsupported); install the pinned source build with scripts/install.sh --with-formal

`rvw doctor --features formal --skip-adapter-info --json` reports the same inconclusive capability and install flag. The replacement plugin was not built. The probe skipped 49 current cases. The previous run had 45 failures in this area. These skips provide no SVA proof evidence.

The UVM random-data failure reproduced with the pinned Accellera archive at revision `78c06547a2a0a29b3dc9dcafae62b75b2ff61544`, SHA-256 `9ee918499a92518f8f7c202c5f8a38b8a0c83d4eba3bedd7890bfa3ed023d1e4`. The observed fault was a Verilator nested-task local accumulator update. The scoreboard now checks each observed item in a function. Seeds 1, 2 and 3 pass. A forced constant-data stream still fails. Seed selection was retained. No protocol-agent check was waived.

The native Spike PLIC disagreement remains a failing test: `devices/test_plic.py::test_spike_claim_ignores_threshold`. Minimal actions are priority[1]=3, context-0 enable=2, threshold=3, source-1 level=1, then claim and pending reads. Both paths mask IRQ. Python `Plic` returns claim=1 and pending=0. Native Spike `plic_t` returns claim=0 and pending=2. Lowering the native threshold to zero returns claim=1. This is a real difference between two reference paths. It is not cleared by [PR #1147](https://github.com/riscPrint/risc-v-workstation/pull/1147): that flow checks Vexii RTL against Spike instructions plus the Python external-PLIC replay. It does not call native Spike `plic_t` for this threshold case. The model and failing oracle assertion remain unchanged.

The old SpinalHDL axis has six failed cases, one native JVM crash and one native abort:

| Case | Observed limit |
|---|---|
| `ExamplesTraceSpec`, failing HDL assert | Expected assertion does not fire with HDL time fixed at zero. |
| `AxiReferenceSpec`, independent DMA memory | The old SDK AXI master produces strobe 16 for a four-bit port. Its middle-burst expression is `BigInt(1) << busConfig.bytePerWord`; the full mask needs the low four bits. |
| `CoherenceModelFixtureSpec`, ownership fault | The injected-fault negative control does not fire on the old time context. |
| `RiscvSimSpec`, HDL assert, concurrent failure and overlapped failure | Three assertion-negative controls do not report the expected failure. |
| Waves `SimGuardSpec`, repeated traced run | The JVM crashes with SIGSEGV in `VerilatedTrace::addModel` during repeated traced simulation. The runner stops the stuck sbt client after the native crash. |
| `TypedCacheBindSpec` | Native TL-C monitor aborts at HDL time zero: `rvw TL-C data message header changed`. The precise SDK/model interaction remains unresolved. |

The callback/context probe at `RiscvSim/tests/repro/verilator-context-time/` reports 17 through the old callback and 0 with `VL_TIME_CONTEXT`. The old wrapper does not advance context time. Assertions guarded by `noAssertAtTimeZero` can remain disabled. These failures were not changed to skips or expected passes. The five cancellations cover old waveform-path and `Mem.readAsyncWrite` capabilities, plus the `immutable.ArraySeq`, `immutable.VectorMap` and `immutable.LazyList` types absent from Scala 2.12. Six fresh litmus samples are consistent with the pinned herd allowed outcomes on each axis. All six injected-fault samples mismatch on each axis, with checker exit 1. This is bounded fixture evidence, not a core memory-model proof.

Other fixes retain the checks that exposed the faults:

- Detect the installed SystemC and LLVM development files, native Sail DII, Tiny Spinal, Vex runtime tools and gem5. Keep absent source or endpoint inputs separate from tool presence.
- Isolate the missing-tool installer fixture from an ambient `RVW_GEM5` setting. Keep its package-manager traps and no-write checks.
- Select an explicit integer ISA for integer Spike/Sail fixtures after scalar-FP generation changed. Preserve Sail full-state refusal. Keep the FP address-only fixture separate, with `no_fp_state` scope and a changed-address negative control.
- Isolate external-git fixtures and regression-resume tool metadata. The resume test still rejects changed tool fingerprints and platform bytes.
- Update the native CPU shim ABI guards. Preserve replay and state requirements.
- Use portable old-Spinal fixture APIs. Make the Round22 user phase change emitted RTL on both axes. Preserve its inequality check.
- Keep Vexii default RV32/RV64 configurations explicit when FPU configurations are added.
- Combine same-predicate assignment coverage per bit in latch analysis. Preserve missing-branch and missing-bit controls.
- Report unbounded cancellation and MCP command exit errors correctly. Keep unchecked fairness inconclusive.
- Keep unqualified coverage bins separate from qualified hits. Preserve capture-race and qualification controls. Check Sail termination separately from absent FP state.
- Count all eight DRAM transfers. Check legal stream cancellation with activation evidence. Exercise three supported Vex machine IRQs, reject the unsupported supervisor input, and retain timing and corrupted-event Spike controls.
- Disable GPU use in the VS Code integration launcher. Both final integration processes exited successfully. Earlier intermittent hangs mean this flag alone is not a complete stability proof.

## Original 168 skips

This table lists every distinct reason from the previous full run. Counts are historical. They are not added to the rerun totals.

| Prior skip reason | Count |
|---|---:|
| generated Sail bitmanip models and native tools required | 38 |
| generated Sail state models and native formal tools required | 36 |
| set RVW_TEST_SOFTFLOAT to the pinned external source tree | 13 |
| generated Sail Zicond models and native tools required | 8 |
| native tools and generated models required | 6 |
| VEXRISCV must select an external checkout; use a private copy for parallel runs | 5 |
| native localhost SSH required | 5 |
| set RVW_ETRACE_REFERENCE; Spike and RISC-V GCC are needed | 4 |
| pinned Sail model source required | 4 |
| set RVW_EXTERNAL_BOOM_LAUNCHER for BOOM launcher parity | 4 |
| optional native rIC3 missing | 3 |
| set RVW_TEST_SSH_OPTIONS for a native localhost SSH test | 3 |
| build IRQ and CSR ELFs and set RVW_VEX_EVENTS_DIR | 3 |
| set RVW_TEST_DII_SAIL to a native Sail with --rvfi-dii | 2 |
| set RVW_WFI_RUNTIME=1 for bounded core WFI runs | 2 |
| VEXIIRISCV must select a private pinned core with its SpinalHDL dependencies | 2 |
| set RVW_INTERRUPT_RUNTIME=1 for BOOM interrupt regression | 2 |
| native LLVM headers and tblgen absent | 2 |
| pinned GCC/LLVM source base files required | 2 |
| native riscv-formal and generated Zicond models required | 2 |
| set RVW_TEST_NATIVE_ADJUDICATE=1 for native Spike/Sail integration | 1 |
| set RVW_TEST_BENCHMARK_ELF to a built integer benchmark | 1 |
| optional native cover-search tools missing | 1 |
| optional native EBMC and Yosys missing | 1 |
| opt-in native gem5 FTQ test | 1 |
| set RVW_ETRACE_REFERENCE to the pinned native reference checkout | 1 |
| set RVW_TEST_TINY_SPINAL=1 with JDK, sbt, Verilator, GCC and Spike | 1 |
| verible is not installed | 1 |
| Verible is not installed | 1 |
| pinned CIRCT install required | 1 |
| pinned CIRCT required | 1 |
| pinned riscv-profiles source required for span verification | 1 |
| NEORV32 has memories; set RVW_GHDL_PLUGIN to a plugin built by scripts/build-ghdl-plugin.py | 1 |
| UART memories need the rebuilt GHDL plugin (RVW_GHDL_PLUGIN) | 1 |
| pinned Sail bitmanip source required | 1 |
| pinned Sail state sources required | 1 |
| generated Sail state models and Yosys required | 1 |
| native Sail compiler, pinned source and riscv-formal required | 1 |
| pinned Sail source required | 1 |
| SystemC development library required | 1 |
| set RVW_UVM_CPU_RUN to a completed scalar C1 run | 1 |
| set RVW_VEX_LIVE_ELF and RVW_CPU_SHIM; generate VexTop.v first | 1 |
| Total | 168 |

## Rerun skips

| Distinct rerun skip reason | Count |
|---|---|
| Installed yosys-slang lacks clocked SVA lowering (SVA unsupported); install the pinned source build with scripts/install.sh --with-formal | 49 |
| generated Sail bitmanip models and native tools required | 38 |
| generated Sail state models and native formal tools required | 36 |
| set RVW_TEST_SOFTFLOAT to the pinned external source tree | 13 |
| generated Sail Zicond models and native tools required | 8 |
| native tools and generated models required | 6 |
| native localhost SSH required | 5 |
| set RVW_ETRACE_REFERENCE; Spike and RISC-V GCC are needed | 4 |
| pinned Sail model source required | 4 |
| set RVW_EXTERNAL_BOOM_LAUNCHER for BOOM launcher parity | 4 |
| optional native rIC3 missing | 3 |
| set RVW_TEST_SSH_OPTIONS for a native localhost SSH test | 3 |
| build IRQ and CSR ELFs and set RVW_VEX_EVENTS_DIR | 3 |
| boom source checkout is unavailable; set SPINAL_BOOM | 2 |
| pinned GCC/LLVM source base files required | 2 |
| Verible is not installed | 2 |
| installed GHDL plugin has an incompatible Yosys memory ABI; rebuild with python3 scripts/build-ghdl-plugin.py and set RVW_GHDL_PLUGIN | 2 |
| native riscv-formal and generated Zicond models required | 2 |
| set RVW_TEST_BENCHMARK_ELF to a built integer benchmark | 1 |
| optional native cover-search tools missing | 1 |
| optional native EBMC and Yosys missing | 1 |
| set RVW_DEBUG_TEST_PORT to a disposable RTL remote_bitbang endpoint | 1 |
| set RVW_ETRACE_REFERENCE to the pinned native reference checkout | 1 |
| verible is not installed | 1 |
| set RVW_MAPPED_PROBE_PROJECT to a mapped smoke fixture with stage/retire probes | 1 |
| pinned CIRCT required | 1 |
| pinned CIRCT install required | 1 |
| pinned riscv-profiles source required for span verification | 1 |
| pinned Sail bitmanip source required | 1 |
| pinned Sail state sources required | 1 |
| generated Sail state models and Yosys required | 1 |
| native Sail compiler, pinned source and riscv-formal required | 1 |
| pinned Sail source required | 1 |
| set RVW_UVM_CPU_RUN to a completed scalar C1 run | 1 |
| set RVW_VEX_LIVE_ELF and RVW_CPU_SHIM; generate VexTop.v first | 1 |
| Total | 203 |

The remaining skips are explicit capability or input gaps. The Sail simulator is installed, but the Sail compiler and generated pinned models are absent. GHDL loads, but its memory-cell ABI is incompatible with the selected Yosys; the skip gives the rebuild command. SSH client and daemon binaries exist, but the native tests lack a working configured localhost endpoint. CPU UVM needs its supported C2/1 state capture; the new Vex capture is C2/2 with CSR state and cannot substitute for that input. Live/event UVM needs its own RTL and ELFs. The disposable RTL remote_bitbang endpoint is not configured. Sail still refuses full FP-state comparison. SoftFloat, E-Trace and compiler/profile cases need pinned external sources. rIC3, EBMC, Verible and the pinned CIRCT install were not found. No missing input was replaced by an invented pass.

## Reproduction and work not run

Use the tested commit and the development/MCP dependencies. Set private core paths and the pinned external input paths. Keep native build trees in the private worktree. Store raw command records, logs and JUnit outside version control under `$RUN_ROOT`.

```sh
(cd rvw && uv pip install -e '.[dev,mcp]')
export SPINAL_BOOM="$RUN_ROOT/empty-boom"
mkdir -p "$SPINAL_BOOM"
export RVW_HOME="$PWD" RVW_SBT_LOCK=sbt-uvm
export RVW_VEX_LOCK=vex-uvm RVW_VEX_CHECKS_LOCK=vex-uvm
export VEXRISCV="$PRIVATE_VEX" VEXIIRISCV="$PRIVATE_VEXII"
export NAXRISCV="$PRIVATE_NAX" RVW_NAX_SBT_LOCK=sbt-uvm
export RISCV_TESTS_SOURCE="$INPUT_ROOT/riscv-tests"
export RVW_TEST_RISCV_TESTS="$RISCV_TESTS_SOURCE/benchmarks"
export RVW_GEM5="$GEM5_BINARY"
export RVW_REMOTE_NATIVE_PROJECT="$PRIVATE_VEX/rvw.toml"
export RVW_UVM_ARCHIVE="$INPUT_ROOT/accellera.tar.gz"
export RVW_UVM_SOC_NATIVE=1 RVW_UVM_CUSTOM_NATIVE=1 RVW_UVM_CONTRACTS_NATIVE=1
```

Use the example READMEs to prepare the private adapter copies and programs. Use the pinned litmus plan and generated lint fixtures. Select the built wave checker, Trace CLI and release SpinalChecks test classpath. Keep the matching Yosys and plugin together. Build the Spike shim with `nice -n 10 bash Cosim/build.sh`.

Collect slow test IDs with `rvw/.venv/bin/python -m pytest rvw/tests -m 'not fast' --collect-only -q -p no:randomly`. Group at most 15 files. Put native formal, generated-core checks, Tiny Spinal, remote native, interrupt/WFI and UVM files in separate batches with one worker. For each batch, run:

```sh
timeout 900 nice -n 10 rvw/.venv/bin/python -m pytest $FILES \
  -m 'not fast' -n 3 -q -ra -p no:randomly -p no:cacheprovider \
  --timeout=840 --basetemp="$RUN_ROOT/$BATCH-tmp" \
  --junitxml="$RUN_ROOT/$BATCH.xml"
```

Use `-n 1` for the separate native files. Scope `CPATH="$LZ4_PREFIX/include"` and `LIBRARY_PATH="$LZ4_PREFIX/lib"` only to `formal/test_formal.py`. Do not export those opaque inputs to the core launchers.

Run Scala with `scripts/with-lock.sh sbt-uvm nice -n 10 sbt -batch test` from each project in the table. Use `show Test/definedTests` and `testOnly` groups of at most seven suites for SpinalChecks and old-axis RiscvSim. Run old `TypedCacheBindSpec` separately. Split old `SimGuardSpec` into its timeout, parsing and repeated-run cases. Stop the stuck sbt client after a confirmed native abort. For the old axis set `RVW_SPINAL_SOURCE="$NAXRISCV/ext/SpinalHDL"`, select the stated Verilator and flags, and add `'++2.12.18!'`. Clear both variables for the released axis.

Run `cargo test --locked --workspace -j 2` in SpinalTrace and the wave checker. Run `npm ci`, `npm run typecheck`, `npm run build` and `npm test` in VS Code and the block engine. Run `npm run test:integration:spinalblocks` and `npm run test:integration:debug` in VS Code and require process exit. Run the example pytest folders and ComponentSims with the same Python environment.

For each prepared single-core project run `scripts/with-lock.sh sbt-uvm nice -n 10 rvw --project "$PROJECT" regress run --suite smoke --rvfi-trace --source "$CORE_SOURCE" --out "$RUN_ROOT/$CORE" --no-index --no-cache --jobs 1 --json`. Configure the composed project with `SpinalSoc/examples/vex/configure.py` before its smoke. For SMP, generate `programs.py --suite smoke`, add a one-ELF smoke suite with its hart-images option to a copy of its project, and run the same regression command. Keep its incomplete-input declaration intact. Reproduce PLIC with `RVW_DEVICE_SPIKE_PREFIX="$SPIKE_PREFIX" nice -n 10 rvw/.venv/bin/python -m pytest rvw/tests/devices/test_plic.py::test_spike_claim_ignores_threshold -q`.

No BOOM adapter build, simulation, full architecture-test campaign, FPGA/hardware run, unconfigured SSH endpoint, missing Sail generated-model campaign, missing UVM CPU/live/event input, or source-built slang replacement ran. The examples' core-rebuild pytest cases are excluded from the pure-folder pass. Native core smoke coverage is limited to the rows above. The old SDK remains unqualified because of the failures and native crashes.

## Merged repairs

| PR | Head | State |
|---|---|---|
| [1176](https://github.com/riscPrint/risc-v-workstation/pull/1176) | `79325397e74f452e6220a8d26ceca94be3773200` | merged |
| [1183](https://github.com/riscPrint/risc-v-workstation/pull/1183) | `e6a8971202bff297a396e42634d0195b4b5c3ae6` | merged |
| [1233](https://github.com/riscPrint/risc-v-workstation/pull/1233) | `b7bac7c9dfada7e7fd51c2f63f88b6a82b40d24c` | merged |
| [1235](https://github.com/riscPrint/risc-v-workstation/pull/1235) | `81c1710a0060b382fb62f3da388d6ec73a830bcf` | merged |
| [1303](https://github.com/riscPrint/risc-v-workstation/pull/1303) | `5482e86d004d81e956d684babccda12818e16791` | merged |
| [1304](https://github.com/riscPrint/risc-v-workstation/pull/1304) | `c41da3199e45443e83736331b709013a59d70054` | merged |
| [1336](https://github.com/riscPrint/risc-v-workstation/pull/1336) | `1ff65ae804096efec5e5847107eeaef469c76bf6` | merged |
| [1427](https://github.com/riscPrint/risc-v-workstation/pull/1427) | `737d133a33b85d166ccbf566c739849de762b5ce` | merged |
| [1451](https://github.com/riscPrint/risc-v-workstation/pull/1451) | `c7cd3f07adf893cccab30f523affb554aa544ae2` | merged |
| [1485](https://github.com/riscPrint/risc-v-workstation/pull/1485) | `b0eb5b755de6bf3f5f3f59fd6c78c5bf2102a79e` | merged |
| [1489](https://github.com/riscPrint/risc-v-workstation/pull/1489) | `b09bb674393e3d4240d5e107929ee5bf8c103f9c` | merged |
| [1490](https://github.com/riscPrint/risc-v-workstation/pull/1490) | `103eb4df1f78e80a7a73460b7060850c6ce29e88` | merged |
| [1491](https://github.com/riscPrint/risc-v-workstation/pull/1491) | `9e0953f7423c1de865e1157b4662b3200545eb9f` | merged |
| [1492](https://github.com/riscPrint/risc-v-workstation/pull/1492) | `89c4cc4e95ecc330f4fc3f55a7cb950b31bd9c01` | merged |
| [1493](https://github.com/riscPrint/risc-v-workstation/pull/1493) | `7d3eb26bc08149f1f83ba77dd0d53bfc84f39341` | merged |
| [1495](https://github.com/riscPrint/risc-v-workstation/pull/1495) | `4bc779665e391361b6966e1235d448cd4b361599` | merged |
| [1496](https://github.com/riscPrint/risc-v-workstation/pull/1496) | `f8537acda0958532a499c8e552872c31c0caf8d1` | merged |
