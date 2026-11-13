# Code correctness review

## Protocol VIP and UVM code review

The source pass used base `f3606ad0650861a3d8a3764c2ec0cbd8fecf182f`.
It covered protocol checks, active roles, scoreboards, coverage, bench generation,
RAL generation, and UVM report parsing. The inventory below gives file line counts
before integration. Later changes on main are outside this source pass.
F3 belongs to another worker. This review did not change zero-transaction rules.

Confirmed defects:

- AXI exclusive accesses could exceed 128 bytes on the 128-bit Python profile. Fixed by https://github.com/riscPrint/risc-v-workstation/pull/1358. The new rejection test failed before the fix. A valid 128-byte access remains legal. Arm IHI 0022 defines the limit in its exclusive-access restrictions: https://documentation-service.arm.com/static/5f915bbcf86e16515cdc3b23
- The pinned UVM runner accepted indented nonzero UVM_ERROR/UVM_FATAL summaries with a zero simulator exit and valid completion markers. Fixed by https://github.com/riscPrint/risc-v-workstation/pull/1377. Four regression cases failed before the fix. Zero-count summaries remain valid. The project C1 parser is checked by the same regression cases.

Unconfirmed items, not counted as fixed defects:

- Check whether the Python and SV AXI monitors reject mixed OKAY/EXOKAY read beats within one exclusive burst. No retained failing test establishes this gap in this review.
- Check the read strobe value in the reactive APB RTL manager under the full APB checker. The reactive qualification test does not start that passive monitor. No native reproduction was run.

Validation:

- Targeted AXI tests: 30 passed.
- Targeted UVM parser and flow tests: 52 passed.
- Assigned non-native tests: 428 passed, 4 skipped, 22 deselected. Command: `nice -n 15 rvw/.venv/bin/python -m pytest rvw/tests/test_vip_*.py rvw/tests/test_uvm*.py rvw/tests/test_soc_uvm_composed.py rvw/tests/test_sound3_vip.py -k 'not native' -q`.
- AXI fast set: 3294 passed, 4 skipped, 7724 deselected, 1 unrelated failure. `rvw/tests/test_mcp_workflow_coverage.py::test_each_tool_has_a_profile_and_workflow` found no workflow entry for `cov_mutate_core`.
- Parser fast set: 3306 passed, 4 skipped, 7724 deselected, 1 unrelated failure in the same MCP workflow coverage test; 59 temporary-directory cleanup warnings.
- Release hygiene: 40 passed.
- Report fast set: 3307 passed, 4 skipped, 7724 deselected; no failures.
- Verilator 5.052 interface/checker lint: all 20 protocols passed. Each interface had a temporary `top` wrapper with its interface instance and checker instance, where present. Command pattern: `nice -n 15 verilator --lint-only --timing --assert -Wno-fatal --top-module top Uvm/vip/PROTOCOL/PROTOCOL_if.sv WRAPPER.sv`.
- Full UVM package lint did not complete. The AHB package exceeded 60 seconds. The remaining package lint run was stopped. No UVM runtime build, core build, long simulation, or proof was run.

Read limits:

The inventory covers implementation and test source. Most README files, historical
qualification Markdown, historical result JSON, and remaining project metadata
were not audited. The scan does not qualify all protocol modes or any complete CPU.

Files read: 276. Line counts refer to this review checkout before integration. Repeated smoke runners were read as a common source plus each file difference.

| Directory | Files and line counts |
|---|---|
| `Uvm/base` | rvw_base_pkg.sv (101), rvw_ral_pkg.sv (59), rvw_soc_sequences.sv (71) |
| `Uvm/cpu` | rvw_cpu_if.sv (15), rvw_cpu_pkg.sv (194) |
| `Uvm/examples/adapter` | top.sv (23) |
| `Uvm/examples/composed` | scenario_test.py (95), smoke.py (37) |
| `Uvm/examples/composed/spinal/src/main/scala` | ScenarioSoc.scala (74) |
| `Uvm/examples/cpu` | cocotb_test.py (57), fixture.sv (36), python_top.sv (6), run.py (127), top.sv (68) |
| `Uvm/examples/custom_bus` | endpoint.sv (31), run.py (85), scenario.py (38) |
| `Uvm/examples/ral` | top.sv (82) |
| `Uvm/examples/soc` | connected_test.py (130), rvw_soc_env.py (21) |
| `Uvm/examples/soc/spinal/src/main/scala` | SeededSoc.scala (72) |
| `Uvm/examples/vexiiriscv` | replay_suite.py (37), replay_test.py (74), replay_top.sv (4) |
| `Uvm/examples/vexriscv` | csr-program.py (37), isa_suite.py (53), isa_test.py (17), live_test.py (186) |
| `Uvm/examples/vexriscv/sv` | check.py (27), prepare.py (78), top.sv (74) |
| `Uvm/probes` | randc.sv (16), run.py (46), transition.sv (14) |
| `Uvm/pyuvm` | constraint_test.py (45), cpu_env.py (53), parity.sv (10), parity_test.py (35), rvw_env.py (44), soc_sequences.py (14) |
| `Uvm` | spike_bridge.cpp (105) |
| `Uvm/tests` | controls.sv (100), cpu.sv (65), env.sv (246), tlul.sv (47) |
| `Uvm/tests/repro` | nested-task-local.sv (26) |
| `Uvm/vip/ahb` | ahb_if.sv (33), ahb_pkg.sv (263), cocotb_smoke.py (40), cocotb_test.py (47), cocotb_top.sv (17), fixture.sv (35), smoke.py (54), test.sv (38) |
| `Uvm/vip/apb` | apb_if.sv (48), apb_pkg.sv (208), cocotb_smoke.py (40), cocotb_test.py (30), cocotb_top.sv (16), fixture.sv (19), smoke.py (54), test.sv (57) |
| `Uvm/vip/axi` | axi_if.sv (26), axi_pkg.sv (335), fixture.sv (11), smoke.py (54), test.sv (39) |
| `Uvm/vip/axis` | axis_if.sv (14), axis_pkg.sv (189), cocotb_smoke.py (40), cocotb_test.py (38), cocotb_top.sv (44), fixture.sv (14), smoke.py (54), test.sv (47) |
| `Uvm/vip/clock_reset` | clock_reset_if.sv (3), clock_reset_pkg.sv (91), fixture.sv (4), smoke.py (53), test.sv (26) |
| `Uvm/vip/coherent` | coherent_if.sv (5), coherent_pkg.sv (101), fixture.sv (4), smoke.py (53), test.sv (27) |
| `Uvm/vip/dram` | dram_if.sv (8), dram_pkg.sv (49), fixture.sv (4), test.sv (4) |
| `Uvm/vip/ethernet` | ethernet_if.sv (4), ethernet_pkg.sv (40), fixture.sv (2), test.sv (1) |
| `Uvm/vip/gpio` | fixture.sv (12), gpio_if.sv (10), gpio_pkg.sv (99), smoke.py (53), test.sv (26) |
| `Uvm/vip/i2c` | fixture.sv (16), i2c_if.sv (11), i2c_pkg.sv (120), smoke.py (53), test.sv (30) |
| `Uvm/vip/interrupt` | fixture.sv (3), interrupt_if.sv (7), interrupt_pkg.sv (91), smoke.py (53), test.sv (27) |
| `Uvm/vip/jtag` | fixture.sv (3), jtag_if.sv (3), jtag_pkg.sv (100), smoke.py (53), test.sv (27) |
| `Uvm/vip/pcie` | fixture.sv (2), pcie_if.sv (5), pcie_pkg.sv (46), test.sv (1) |
| `Uvm/vip/qualification` | report.py (86), run.py (108) |
| `Uvm/vip/reactive` | ahb_manager.sv (38), apb_manager.sv (34), reactive_test.py (26), smoke.py (27) |
| `Uvm/vip/rnm` | fixture.sv (2), rnm_if.sv (5), rnm_pkg.sv (32), test.sv (1) |
| `Uvm/vip/rtl` | bus_test.py (24), bus_top.sv (82), contracts_smoke.py (41), contracts_test.py (107), contracts_top.sv (53), serial_test.py (42), serial_top.sv (43), smoke.py (33) |
| `Uvm/vip/spi` | fixture.sv (4), smoke.py (54), spi_if.sv (9), spi_pkg.sv (158), test.sv (38) |
| `Uvm/vip/sram` | fixture.sv (15), smoke.py (53), sram_if.sv (10), sram_pkg.sv (91), test.sv (27) |
| `Uvm/vip/stress` | fixture.sv (4), smoke.py (53), stress_if.sv (4), stress_pkg.sv (88), test.sv (27) |
| `Uvm/vip/tilelink` | fixture.sv (9), smoke.py (54), test.sv (39), tilelink_if.sv (20), tilelink_pkg.sv (315) |
| `Uvm/vip/uart` | fixture.sv (11), smoke.py (54), test.sv (38), uart_if.sv (12), uart_pkg.sv (175) |
| `Uvm/vip/wishbone` | fixture.sv (12), smoke.py (53), test.sv (27), wishbone_if.sv (14), wishbone_pkg.sv (92) |
| `rvw/src/rvw/sim` | ral.py (69), uvm.py (185), uvm_models.py (134) |
| `rvw/src/rvw/uvm` | __init__.py (0), capture_events.py (42), cli.py (63), cli_declarations.py (2), composed.py (141), constraints.py (73), cpu_events.py (34), csr_sequence.py (57), declared.py (31), features.py (41), flow.py (210), gate.py (119), gate_adapter.py (4), mcp_tools.py (22), native_inputs.py (19), profiles.py (168), qualification.py (51), scaffold.py (157), scaffold_cli.py (30), scenarios.py (61), soc.py (142) |
| `rvw/src/rvw/uvm/commands` | gate_config.py (24), qualification.py (18) |
| `rvw/src/rvw/vip` | __init__.py (1), ahb.py (320), apb.py (278), axi.py (401), axis.py (229), catalog.py (122), cli.py (28), cli_declarations.py (2), clock_reset.py (75), coherent.py (100), declared.py (46), dram.py (90), ethernet.py (64), gpio.py (104), i2c.py (207), interrupt.py (76), jtag.py (117), mapped.py (137), mcp_tools.py (13), pcie.py (86), ready_valid.py (37), rnm.py (53), spi.py (166), spi_flash.py (90), sram.py (98), stress.py (133), tilelink.py (280), uart.py (175), wishbone.py (128) |
| `rvw/tests` | test_soc_uvm_composed.py (90), test_sound3_vip.py (36), test_uvm.py (112), test_uvm_capture_events.py (61), test_uvm_constraints.py (31), test_uvm_cpu.py (155), test_uvm_cpu_events.py (35), test_uvm_cpu_native.py (50), test_uvm_csr_sequence.py (72), test_uvm_custom_bus.py (25), test_uvm_custom_bus_native.py (23), test_uvm_events_native.py (25), test_uvm_features.py (28), test_uvm_flow.py (166), test_uvm_gate.py (115), test_uvm_isa_suite.py (16), test_uvm_models.py (86), test_uvm_native.py (42), test_uvm_native_inputs.py (30), test_uvm_profiles.py (56), test_uvm_project_adapter.py (33), test_uvm_pyuvm_native.py (17), test_uvm_qualification.py (18), test_uvm_ral.py (58), test_uvm_ral_sequences_native.py (31), test_uvm_required_features.py (26), test_uvm_review_reports.py (17), test_uvm_scaffold.py (71), test_uvm_scenarios.py (61), test_uvm_soc.py (75), test_uvm_soc_native.py (19), test_uvm_vex_live.py (43), test_vip_ahb.py (101), test_vip_apb.py (92), test_vip_axi.py (134), test_vip_axis.py (63), test_vip_catalog.py (62), test_vip_clock_reset.py (21), test_vip_coherent.py (19), test_vip_contracts_native.py (24), test_vip_dram.py (22), test_vip_ethernet.py (23), test_vip_gpio.py (29), test_vip_i2c.py (75), test_vip_interrupt.py (27), test_vip_jtag.py (22), test_vip_pcie.py (24), test_vip_review_axi.py (15), test_vip_rnm.py (18), test_vip_spi.py (36), test_vip_sram.py (27), test_vip_stress.py (20), test_vip_sv_qualification.py (71), test_vip_tilelink.py (122), test_vip_uart.py (65), test_vip_wishbone.py (21) |

## SpinalSoc and rvw soc correctness review

Reviewed the assigned source, examples and tests from `f3606ad0`. Also reviewed the later lazy-import CLI changes from main.
Read 187 files and 12,974 lines after the fixes.
No assigned file remains unread. Referenced external CPU, SpinalHDL and consumer implementations are outside this inventory.

Confirmed defects:

- PLIC threshold blocked claim polling. PR https://github.com/riscPrint/risc-v-workstation/pull/1387.
- PLIC accepted completion from a disabled source. PR https://github.com/riscPrint/risc-v-workstation/pull/1387.
- Full UART device tree omitted its compatible string, register spacing and clock. PR https://github.com/riscPrint/risc-v-workstation/pull/1370.
- Audit used RV64 XLEN for the 32-bit APB data pins. PR https://github.com/riscPrint/risc-v-workstation/pull/1390.

Suspected but unconfirmed defects: none retained.

Validation:

- All `rvw/tests/test_soc*.py` tests: 227 passed.
- UART, export and compose targeted set: 24 passed. Audit set: two passed.
- Release hygiene: 40 passed.
- `scripts/with-lock.sh sbt-rv-soc nice -n 15 sbt 'runMain rvwsoc.PeripheralSmoke'`, from `SpinalSoc`: passed at seed 17. Four CLINT and eight PLIC assertions ran. The printed PLIC count was corrected after that run.
- Threshold regression failed on the old RTL. A separate Icarus completion regression failed on the old generated RTL and passed on the fixed RTL.
- Two fresh required fast sets each passed: 3295 passed, 4 skipped, 7724 deselected. An earlier run had 3293 passed, 4 skipped and two failures: `test_mcp_workflow_coverage.py::test_each_tool_has_a_profile_and_workflow`, and the audit regression collected before its fix. Fresh SoC tests and both later fast sets passed.
- No CPU builds, full serial campaigns, native wide-fabric campaigns, long simulations or formal proofs ran. Static review does not qualify these profiles.

Review boundaries:

CLINT offsets and paired 32-bit words cover the single-hart 64-bit timer. This review does not establish atomic RV64 MMIO or multi-hart ACLINT behavior.
PLIC checks cover the declared seven-source, one-context, priority 0/1 profile.
The legacy MMIO bridge deliberately rejects partial writes before target selection.
The exporters use two address cells and two size cells. The map and IP-XACT round-trip tests passed.
Clock crossings still require the documented common-reset protocol.

Files read, with line counts:

| File | Lines |
|---|---:|
| `SpinalSoc/.gitignore` | 11 |
| `SpinalSoc/README.md` | 449 |
| `SpinalSoc/build.sbt` | 32 |
| `SpinalSoc/db/src/main/scala/rvwsoc/Database.scala` | 23 |
| `SpinalSoc/examples/MEASURED_RESULTS.json` | 332 |
| `SpinalSoc/examples/block/README.md` | 23 |
| `SpinalSoc/examples/block/Smoke.scala` | 59 |
| `SpinalSoc/examples/block/compose.json` | 22 |
| `SpinalSoc/examples/block/run.py` | 26 |
| `SpinalSoc/examples/block/soc.json` | 119 |
| `SpinalSoc/examples/compose.json` | 8 |
| `SpinalSoc/examples/debug/DebugCore.scala` | 14 |
| `SpinalSoc/examples/debug/README.md` | 62 |
| `SpinalSoc/examples/debug/build.py` | 48 |
| `SpinalSoc/examples/debug/loop.S` | 10 |
| `SpinalSoc/examples/debug/test_debug.py` | 106 |
| `SpinalSoc/examples/fabric/README.md` | 61 |
| `SpinalSoc/examples/fabric/VexDma.scala` | 79 |
| `SpinalSoc/examples/fabric/build-cpu.py` | 53 |
| `SpinalSoc/examples/fabric/configure.py` | 20 |
| `SpinalSoc/examples/fabric/cpu.S` | 27 |
| `SpinalSoc/examples/fabric/test_cpu.py` | 23 |
| `SpinalSoc/examples/fabric/test_fabric.py` | 201 |
| `SpinalSoc/examples/flash/README.md` | 71 |
| `SpinalSoc/examples/flash/boot.S` | 56 |
| `SpinalSoc/examples/flash/build.py` | 91 |
| `SpinalSoc/examples/flash/payload.S` | 9 |
| `SpinalSoc/examples/flash/test_boot.py` | 60 |
| `SpinalSoc/examples/import/README.md` | 40 |
| `SpinalSoc/examples/import/build.py` | 36 |
| `SpinalSoc/examples/import/test_import.py` | 52 |
| `SpinalSoc/examples/import/uart.toml` | 61 |
| `SpinalSoc/examples/smp/README.md` | 49 |
| `SpinalSoc/examples/smp/SmpHost.scala` | 93 |
| `SpinalSoc/examples/smp/build.py` | 60 |
| `SpinalSoc/examples/smp/test_host.py` | 72 |
| `SpinalSoc/examples/soc.json` | 48 |
| `SpinalSoc/examples/stub/README.md` | 61 |
| `SpinalSoc/examples/stub/Run.scala` | 65 |
| `SpinalSoc/examples/stub/Stub.scala` | 118 |
| `SpinalSoc/examples/stub/adapter.py` | 123 |
| `SpinalSoc/examples/stub/build-programs.sh` | 7 |
| `SpinalSoc/examples/stub/checks-qualification.json` | 78 |
| `SpinalSoc/examples/stub/checks.generate.json` | 6 |
| `SpinalSoc/examples/stub/compose.json` | 37 |
| `SpinalSoc/examples/stub/external.S` | 26 |
| `SpinalSoc/examples/stub/hello.S` | 22 |
| `SpinalSoc/examples/stub/interrupt.S` | 23 |
| `SpinalSoc/examples/stub/link.ld` | 2 |
| `SpinalSoc/examples/stub/run.sh` | 5 |
| `SpinalSoc/examples/stub/rvw.toml` | 56 |
| `SpinalSoc/examples/stub/soc.json` | 308 |
| `SpinalSoc/examples/uart16550/README.md` | 76 |
| `SpinalSoc/examples/uart16550/bench.json` | 7 |
| `SpinalSoc/examples/uart16550/configure.py` | 17 |
| `SpinalSoc/examples/uart16550/test_uart.py` | 186 |
| `SpinalSoc/examples/vex/README.md` | 86 |
| `SpinalSoc/examples/vex/Run.scala` | 82 |
| `SpinalSoc/examples/vex/VERIFICATION.md` | 154 |
| `SpinalSoc/examples/vex/VexCore.scala` | 57 |
| `SpinalSoc/examples/vex/adapter.py` | 120 |
| `SpinalSoc/examples/vex/build-programs.sh` | 14 |
| `SpinalSoc/examples/vex/build-verify.py` | 33 |
| `SpinalSoc/examples/vex/compose-multidomain.json` | 44 |
| `SpinalSoc/examples/vex/compose.json` | 37 |
| `SpinalSoc/examples/vex/configure.py` | 42 |
| `SpinalSoc/examples/vex/connections.json` | 28 |
| `SpinalSoc/examples/vex/prepare-verify.py` | 26 |
| `SpinalSoc/examples/vex/run.sh` | 6 |
| `SpinalSoc/examples/vex/rvw.template.toml` | 64 |
| `SpinalSoc/examples/vex/soc.json` | 314 |
| `SpinalSoc/examples/vex/uart_irq.S` | 36 |
| `SpinalSoc/examples/vex/verify-protocol.py` | 38 |
| `SpinalSoc/examples/vex/verify.S` | 48 |
| `SpinalSoc/examples/vex/verify.json` | 89 |
| `SpinalSoc/examples/vexii/.gitignore` | 6 |
| `SpinalSoc/examples/vexii/README.md` | 57 |
| `SpinalSoc/examples/vexii/Run.scala` | 53 |
| `SpinalSoc/examples/vexii/VexiiCore.scala` | 69 |
| `SpinalSoc/examples/vexii/build.sbt` | 28 |
| `SpinalSoc/examples/vexii/check-results.py` | 25 |
| `SpinalSoc/examples/vexii/compose.json` | 37 |
| `SpinalSoc/examples/vexii/prepare.py` | 36 |
| `SpinalSoc/examples/vexii/project/build.properties` | 1 |
| `SpinalSoc/examples/watchdog/README.md` | 26 |
| `SpinalSoc/examples/watchdog/Smoke.scala` | 53 |
| `SpinalSoc/examples/watchdog/compose.json` | 25 |
| `SpinalSoc/examples/watchdog/run.py` | 26 |
| `SpinalSoc/examples/watchdog/soc.json` | 110 |
| `SpinalSoc/project/build.properties` | 1 |
| `SpinalSoc/src/main/resources/rvwsoc/uart16550.sv` | 201 |
| `SpinalSoc/src/main/scala/rvwsoc/BlockDevice.scala` | 71 |
| `SpinalSoc/src/main/scala/rvwsoc/BusSmoke.scala` | 116 |
| `SpinalSoc/src/main/scala/rvwsoc/Buses.scala` | 169 |
| `SpinalSoc/src/main/scala/rvwsoc/FabricProof.scala` | 65 |
| `SpinalSoc/src/main/scala/rvwsoc/FullUart.scala` | 61 |
| `SpinalSoc/src/main/scala/rvwsoc/IdleCore.scala` | 21 |
| `SpinalSoc/src/main/scala/rvwsoc/LegacyErrorSmoke.scala` | 49 |
| `SpinalSoc/src/main/scala/rvwsoc/NativeFabrics.scala` | 165 |
| `SpinalSoc/src/main/scala/rvwsoc/PeripheralSmoke.scala` | 76 |
| `SpinalSoc/src/main/scala/rvwsoc/Peripherals.scala` | 131 |
| `SpinalSoc/src/main/scala/rvwsoc/ProtocolChecks.scala` | 35 |
| `SpinalSoc/src/main/scala/rvwsoc/ProtocolSmoke.scala` | 64 |
| `SpinalSoc/src/main/scala/rvwsoc/Serial.scala` | 105 |
| `SpinalSoc/src/main/scala/rvwsoc/SimpleBus.scala` | 62 |
| `SpinalSoc/src/main/scala/rvwsoc/SimpleBusSmoke.scala` | 35 |
| `SpinalSoc/src/main/scala/rvwsoc/Soc.scala` | 92 |
| `SpinalSoc/src/main/scala/rvwsoc/VerificationCore.scala` | 21 |
| `SpinalSoc/src/main/scala/rvwsoc/Watchdog.scala` | 40 |
| `rvw/src/rvw/soc/README.md` | 552 |
| `rvw/src/rvw/soc/__init__.py` | 0 |
| `rvw/src/rvw/soc/apb_capture.py` | 58 |
| `rvw/src/rvw/soc/audit.py` | 50 |
| `rvw/src/rvw/soc/binding_help.py` | 30 |
| `rvw/src/rvw/soc/bridge.py` | 74 |
| `rvw/src/rvw/soc/capture.py` | 59 |
| `rvw/src/rvw/soc/cdc_report.py` | 25 |
| `rvw/src/rvw/soc/check.py` | 113 |
| `rvw/src/rvw/soc/cli.py` | 64 |
| `rvw/src/rvw/soc/cli_declarations.py` | 2 |
| `rvw/src/rvw/soc/commands/__init__.py` | 1 |
| `rvw/src/rvw/soc/commands/audit.py` | 29 |
| `rvw/src/rvw/soc/commands/compose.py` | 35 |
| `rvw/src/rvw/soc/commands/exports.py` | 29 |
| `rvw/src/rvw/soc/commands/feedback.py` | 32 |
| `rvw/src/rvw/soc/commands/handoff.py` | 35 |
| `rvw/src/rvw/soc/commands/ip_import.py` | 25 |
| `rvw/src/rvw/soc/commands/mbist.py` | 32 |
| `rvw/src/rvw/soc/commands/new.py` | 29 |
| `rvw/src/rvw/soc/commands/observe.py` | 55 |
| `rvw/src/rvw/soc/commands/peripheral.py` | 36 |
| `rvw/src/rvw/soc/commands/verify.py` | 41 |
| `rvw/src/rvw/soc/compose.py` | 225 |
| `rvw/src/rvw/soc/configuration.py` | 29 |
| `rvw/src/rvw/soc/connection_cone.py` | 50 |
| `rvw/src/rvw/soc/connection_run.py` | 79 |
| `rvw/src/rvw/soc/connectivity.py` | 43 |
| `rvw/src/rvw/soc/decode_proof.py` | 39 |
| `rvw/src/rvw/soc/device_events.py` | 91 |
| `rvw/src/rvw/soc/exports.py` | 43 |
| `rvw/src/rvw/soc/feedback.py` | 42 |
| `rvw/src/rvw/soc/handoff.py` | 63 |
| `rvw/src/rvw/soc/importer.py` | 95 |
| `rvw/src/rvw/soc/ip_import.py` | 135 |
| `rvw/src/rvw/soc/mbist.py` | 46 |
| `rvw/src/rvw/soc/mcp_tools.py` | 2 |
| `rvw/src/rvw/soc/model.py` | 193 |
| `rvw/src/rvw/soc/observer.py` | 114 |
| `rvw/src/rvw/soc/pairing.py` | 182 |
| `rvw/src/rvw/soc/peripherals.py` | 72 |
| `rvw/src/rvw/soc/protocol_proof.py` | 29 |
| `rvw/src/rvw/soc/scaffold.py` | 59 |
| `rvw/src/rvw/soc/software.py` | 59 |
| `rvw/src/rvw/soc/uvm_run.py` | 58 |
| `rvw/src/rvw/soc/verification_bindings.py` | 42 |
| `rvw/src/rvw/soc/verify.py` | 304 |
| `rvw/src/rvw/soc/vip_bench.py` | 75 |
| `rvw/tests/test_device_events.py` | 69 |
| `rvw/tests/test_init_soc_scaffold.py` | 27 |
| `rvw/tests/test_soc.py` | 58 |
| `rvw/tests/test_soc_audit.py` | 52 |
| `rvw/tests/test_soc_binding_help.py` | 84 |
| `rvw/tests/test_soc_bridge.py` | 123 |
| `rvw/tests/test_soc_check.py` | 104 |
| `rvw/tests/test_soc_compose.py` | 148 |
| `rvw/tests/test_soc_configuration.py` | 38 |
| `rvw/tests/test_soc_connection_cone.py` | 118 |
| `rvw/tests/test_soc_connection_run.py` | 72 |
| `rvw/tests/test_soc_exports.py` | 51 |
| `rvw/tests/test_soc_feedback.py` | 19 |
| `rvw/tests/test_soc_handoff.py` | 43 |
| `rvw/tests/test_soc_ip_import.py` | 73 |
| `rvw/tests/test_soc_mbist.py` | 25 |
| `rvw/tests/test_soc_native_fabric.py` | 47 |
| `rvw/tests/test_soc_observer.py` | 154 |
| `rvw/tests/test_soc_pairing.py` | 99 |
| `rvw/tests/test_soc_peripherals.py` | 48 |
| `rvw/tests/test_soc_protocol_bindings.py` | 45 |
| `rvw/tests/test_soc_runtime.py` | 129 |
| `rvw/tests/test_soc_smp_host.py` | 38 |
| `rvw/tests/test_soc_spi_flash.py` | 53 |
| `rvw/tests/test_soc_stub.py` | 18 |
| `rvw/tests/test_soc_uart16550.py` | 48 |
| `rvw/tests/test_soc_uvm_composed.py` | 90 |
| `rvw/tests/test_soc_verification_bindings.py` | 35 |
| `rvw/tests/test_soc_verify.py` | 140 |
| `rvw/tests/test_soc_vex.py` | 72 |

## Architecture, OoO timing and component models

Review base: `f3606ad0`. The review covered 242 files and 25,745 lines at the recorded read snapshots. The table includes two supporting architecture study scripts. Later changes on main were not reviewed as a whole.

Confirmed defects:

- C2 conversion discarded shifted and sparse memory-mask byte lanes. Cache-line and page addresses could be wrong. Fixed in [PR #1376](https://github.com/riscPrint/risc-v-workstation/pull/1376).
- The component CLI used only the first byte of each data access. It omitted further cache lines and pages. Fixed in [PR #1399](https://github.com/riscPrint/risc-v-workstation/pull/1399). Cross-line OPT accesses now return an error because the next-use stream has one value per trace record.

Checks:

- Existing native and Python parity tests passed: 12 tests. They include seeded random small traces and exhaustive compressed instruction words. No new random parity test was needed.
- Converter tests passed: 19 tests. The shifted-mask regression failed before the fix.
- Component tests passed: 101 tests. The cross-line and cross-page regression failed before the fix.
- Assigned Python area tests passed: 921 tests, with 5 skipped.
- Accounting checks cover retired and squashed instructions, cache hits plus misses, and top-down commit slots. Top-down slots sum to cycles times commit width. They do not have a cycle unit.
- Read the counter updates, history folds, index and tag widths, replacement state, weighted CPI, absolute error and rank ties. Existing scalar references cover selected models. This review did not establish paper-equivalent behavior for every predictor.
- Initial fast run: 3,294 passed, 4 skipped and one failure in untouched `test_mcp_workflow_coverage.py::test_each_tool_has_a_profile_and_workflow` because `cov_mutate_core` lacked workflow coverage. Two later fast runs each passed 3,378 tests, with 4 skipped and 7,729 deselected. They emitted 14 and 46 temporary-directory cleanup warnings.
- NOT RUN: core builds, RTL simulation, proofs, external predictor qualification or the full Python test suite.

Commands for the test groups:

```sh
nice -n 15 rvw/.venv/bin/python -m pytest rvw/tests/test_arch*.py rvw/tests/test_ooo*.py rvw/tests/test_csim*.py rvw/tests/test_perf*.py rvw/tests/test_workload*.py -q
nice -n 15 rvw/.venv/bin/python -m pytest ComponentSims/tests -q
nice -n 15 rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q
```

Selected paper definitions checked against the source:

| Definition | Source comparison |
|---|---|
| [L-TAGE](https://jilp.org/vol9/v9paper6.pdf), sections 2 and 3 | Read the provider and alternate selection, bounded signed counters, weak-correct allocation, usefulness initialization and loop state. Hash and configuration choices are local model choices. This was not a bit-exact comparison. |
| [RRIP](https://jaleels.org/ajaleel/publications/isca2010-rrip.pdf), sections 3 and 4 | `Rrip` inserts SRRIP at maximum RRPV minus one, promotes hits to zero, ages until a maximum victim exists, and uses distant insertion for most BRRIP fills. The separate scalar SRRIP test passed. |
| [SHiP](https://www.istc-cc.cmu.edu/publications/papers/2011/SHiP.pdf), section 3.1 | `Rrip` retains each line's signature and reuse bit. Hits raise its stored signature counter. Eviction without reuse lowers it. A zero counter causes distant insertion. This was a source comparison. |
| [Store sets](https://www.princeton.edu/~rblee/ELE572Papers/MemoryDependencePredictionStoreSets_Emer.pdf), section 6 | `StoreSets` has SSIT and LFST state and chooses the smaller identifier when trained sets meet. Its unresolved-window model omits issue timing and store serialization. The code states this limit. |

Unconfirmed items: 2. No fix or correctness claim is made for these items.

- Translation reserves all missing pages at once. An access that needs more pages than walkers may never gain admission. A failing end-to-end test was not completed.
- Write-through stores may omit lower-level traffic. The intended traffic and timing scope needs a separate reference test.

Not read: no files were intentionally excluded from the assigned source directories or the associated test inventory below. Unrelated tests, external papers and external reference implementations were not reviewed in full.

Files read and line counts:

| File | Lines |
|---|---:|
| `ComponentSims/README.md` | 302 |
| `ComponentSims/branch_sim.cc` | 78 |
| `ComponentSims/capi.cc` | 171 |
| `ComponentSims/csim.cc` | 165 |
| `ComponentSims/examples/hashed-perceptron-64kb.json` | 82 |
| `ComponentSims/examples/tage-sc-l-64kb.json` | 117 |
| `ComponentSims/examples/tage-sc-l-8kb.json` | 63 |
| `ComponentSims/examples/wide-core.json` | 29 |
| `ComponentSims/include/csim/common.h` | 241 |
| `ComponentSims/include/csim/direction.h` | 574 |
| `ComponentSims/include/csim/memory.h` | 940 |
| `ComponentSims/include/csim/misc.h` | 227 |
| `ComponentSims/include/csim/study.h` | 458 |
| `ComponentSims/include/csim/target.h` | 273 |
| `ComponentSims/include/csim/trace.h` | 206 |
| `ComponentSims/qualify/ref_harness.cc` | 40 |
| `ComponentSims/qualify/shim/bt9.h` | 1 |
| `ComponentSims/qualify/shim/bt9_reader.h` | 1 |
| `ComponentSims/qualify/shim/utils.h` | 21 |
| `ComponentSims/spike.py` | 157 |
| `ComponentSims/tests/conftest.py` | 23 |
| `ComponentSims/tests/test_branch.py` | 79 |
| `ComponentSims/tests/test_csim_engine.py` | 514 |
| `ComponentSims/tests/test_csim_reference.py` | 139 |
| `ComponentSims/tests/test_spike.py` | 88 |
| `rvw/src/rvw/arch/__init__.py` | 1 |
| `rvw/src/rvw/arch/cli.py` | 178 |
| `rvw/src/rvw/arch/cli_declarations.py` | 2 |
| `rvw/src/rvw/arch/commands/__init__.py` | 1 |
| `rvw/src/rvw/arch/commands/compiler_export.py` | 34 |
| `rvw/src/rvw/arch/commands/custom_tradeoff.py` | 23 |
| `rvw/src/rvw/arch/commands/gem5_export.py` | 24 |
| `rvw/src/rvw/arch/commands/ooo_delta.py` | 31 |
| `rvw/src/rvw/arch/commands/ooo_designer.py` | 27 |
| `rvw/src/rvw/arch/commands/ooo_fit.py` | 23 |
| `rvw/src/rvw/arch/commands/ooo_profile.py` | 50 |
| `rvw/src/rvw/arch/commands/ooo_sampled.py` | 29 |
| `rvw/src/rvw/arch/commands/ooo_sensitivity.py` | 27 |
| `rvw/src/rvw/arch/commands/ooo_whatif.py` | 32 |
| `rvw/src/rvw/arch/commands/ooo_wrongpath.py` | 32 |
| `rvw/src/rvw/arch/commands/system_energy.py` | 23 |
| `rvw/src/rvw/arch/compiler_export.py` | 79 |
| `rvw/src/rvw/arch/core.py` | 379 |
| `rvw/src/rvw/arch/custom_tradeoff.py` | 60 |
| `rvw/src/rvw/arch/dse.py` | 208 |
| `rvw/src/rvw/arch/energy.py` | 56 |
| `rvw/src/rvw/arch/fitting.py` | 167 |
| `rvw/src/rvw/arch/gem5_export.py` | 30 |
| `rvw/src/rvw/arch/ledger.py` | 50 |
| `rvw/src/rvw/arch/linux.py` | 287 |
| `rvw/src/rvw/arch/mcp_tools.py` | 77 |
| `rvw/src/rvw/arch/measure.py` | 36 |
| `rvw/src/rvw/arch/memory.py` | 181 |
| `rvw/src/rvw/arch/sampling.py` | 131 |
| `rvw/src/rvw/arch/sched.py` | 278 |
| `rvw/src/rvw/arch/sched_study.py` | 71 |
| `rvw/src/rvw/arch/search.py` | 162 |
| `rvw/src/rvw/arch/statistics.py` | 30 |
| `rvw/src/rvw/arch/traffic.py` | 141 |
| `rvw/src/rvw/arch/warmup.py` | 90 |
| `rvw/src/rvw/csim/__init__.py` | 2 |
| `rvw/src/rvw/csim/cli.py` | 283 |
| `rvw/src/rvw/csim/cli_declarations.py` | 2 |
| `rvw/src/rvw/csim/config.py` | 123 |
| `rvw/src/rvw/csim/engine.py` | 70 |
| `rvw/src/rvw/csim/lib.py` | 157 |
| `rvw/src/rvw/csim/mcp_tools.py` | 124 |
| `rvw/src/rvw/csim/models.py` | 71 |
| `rvw/src/rvw/csim/qualify.py` | 199 |
| `rvw/src/rvw/csim/rtl.py` | 267 |
| `rvw/src/rvw/csim/rtl_cache.py` | 183 |
| `rvw/src/rvw/csim/simpoint.py` | 181 |
| `rvw/src/rvw/csim/study.py` | 229 |
| `rvw/src/rvw/csim/target_status.py` | 13 |
| `rvw/src/rvw/csim/traces.py` | 351 |
| `rvw/src/rvw/ooo/README.md` | 1456 |
| `rvw/src/rvw/ooo/__init__.py` | 1 |
| `rvw/src/rvw/ooo/attribution.py` | 19 |
| `rvw/src/rvw/ooo/cli.py` | 23 |
| `rvw/src/rvw/ooo/cli_declarations.py` | 2 |
| `rvw/src/rvw/ooo/component_events.py` | 23 |
| `rvw/src/rvw/ooo/components.py` | 100 |
| `rvw/src/rvw/ooo/control.py` | 6 |
| `rvw/src/rvw/ooo/core.py` | 874 |
| `rvw/src/rvw/ooo/custom.py` | 44 |
| `rvw/src/rvw/ooo/delta.py` | 127 |
| `rvw/src/rvw/ooo/dependence.py` | 27 |
| `rvw/src/rvw/ooo/designer.py` | 85 |
| `rvw/src/rvw/ooo/evidence.py` | 190 |
| `rvw/src/rvw/ooo/execution.py` | 46 |
| `rvw/src/rvw/ooo/fit.py` | 70 |
| `rvw/src/rvw/ooo/floating.py` | 16 |
| `rvw/src/rvw/ooo/frontend.py` | 175 |
| `rvw/src/rvw/ooo/issue_window.py` | 28 |
| `rvw/src/rvw/ooo/mcp_tools.py` | 29 |
| `rvw/src/rvw/ooo/memory_rename.py` | 36 |
| `rvw/src/rvw/ooo/native.c` | 111 |
| `rvw/src/rvw/ooo/native.py` | 196 |
| `rvw/src/rvw/ooo/native_c2.c` | 117 |
| `rvw/src/rvw/ooo/native_decode.c` | 96 |
| `rvw/src/rvw/ooo/project.py` | 58 |
| `rvw/src/rvw/ooo/regions.py` | 111 |
| `rvw/src/rvw/ooo/rename.py` | 32 |
| `rvw/src/rvw/ooo/sampled.py` | 101 |
| `rvw/src/rvw/ooo/search.py` | 117 |
| `rvw/src/rvw/ooo/sensitivity.py` | 82 |
| `rvw/src/rvw/ooo/speculative.py` | 28 |
| `rvw/src/rvw/ooo/spike_replay.py` | 131 |
| `rvw/src/rvw/ooo/structures.py` | 70 |
| `rvw/src/rvw/ooo/translation.py` | 41 |
| `rvw/src/rvw/ooo/whatif.py` | 60 |
| `rvw/src/rvw/ooo/windows.py` | 43 |
| `rvw/src/rvw/ooo/wrongpath.py` | 129 |
| `rvw/src/rvw/perf/README.md` | 184 |
| `rvw/src/rvw/perf/__init__.py` | 1 |
| `rvw/src/rvw/perf/analysis.py` | 310 |
| `rvw/src/rvw/perf/classify.py` | 63 |
| `rvw/src/rvw/perf/cli.py` | 110 |
| `rvw/src/rvw/perf/cli_declarations.py` | 2 |
| `rvw/src/rvw/perf/events.py` | 61 |
| `rvw/src/rvw/perf/function_topdown.py` | 91 |
| `rvw/src/rvw/perf/inputs.py` | 46 |
| `rvw/src/rvw/perf/kanata.py` | 153 |
| `rvw/src/rvw/perf/mcp_tools.py` | 46 |
| `rvw/src/rvw/perf/prediction.py` | 107 |
| `rvw/src/rvw/perf/topdown.py` | 75 |
| `rvw/src/rvw/workloads/README.md` | 261 |
| `rvw/src/rvw/workloads/__init__.py` | 1 |
| `rvw/src/rvw/workloads/assets/build_coremark.py` | 24 |
| `rvw/src/rvw/workloads/assets/build_riscv_tests.py` | 30 |
| `rvw/src/rvw/workloads/assets/build_zstd.py` | 16 |
| `rvw/src/rvw/workloads/assets/coremark.json` | 25 |
| `rvw/src/rvw/workloads/assets/coremark_smoke.c` | 20 |
| `rvw/src/rvw/workloads/assets/default.json` | 237 |
| `rvw/src/rvw/workloads/assets/evaluation-platform.json` | 11 |
| `rvw/src/rvw/workloads/assets/evaluation.json` | 35 |
| `rvw/src/rvw/workloads/assets/link.ld` | 18 |
| `rvw/src/rvw/workloads/assets/main.c` | 7 |
| `rvw/src/rvw/workloads/assets/riscv-tests.json` | 169 |
| `rvw/src/rvw/workloads/assets/rtl_recipe.py` | 80 |
| `rvw/src/rvw/workloads/assets/start.S` | 36 |
| `rvw/src/rvw/workloads/assets/zstd.json` | 25 |
| `rvw/src/rvw/workloads/assets/zstd_smoke.c` | 18 |
| `rvw/src/rvw/workloads/cli.py` | 45 |
| `rvw/src/rvw/workloads/cli_declarations.py` | 2 |
| `rvw/src/rvw/workloads/commands/compare.py` | 30 |
| `rvw/src/rvw/workloads/commands/evaluate.py` | 45 |
| `rvw/src/rvw/workloads/commands/run.py` | 37 |
| `rvw/src/rvw/workloads/comparison.py` | 69 |
| `rvw/src/rvw/workloads/core.py` | 229 |
| `rvw/src/rvw/workloads/evaluation.py` | 96 |
| `rvw/src/rvw/workloads/mcp_tools.py` | 30 |
| `rvw/src/rvw/workloads/profile.py` | 52 |
| `rvw/src/rvw/workloads/rtl.py` | 162 |
| `rvw/tests/test_arch.py` | 521 |
| `rvw/tests/test_arch_base_i.py` | 37 |
| `rvw/tests/test_arch_build_independent.py` | 20 |
| `rvw/tests/test_arch_compatibility.py` | 74 |
| `rvw/tests/test_arch_compiler_export.py` | 15 |
| `rvw/tests/test_arch_custom_tradeoff.py` | 43 |
| `rvw/tests/test_arch_dse.py` | 131 |
| `rvw/tests/test_arch_fitting.py` | 169 |
| `rvw/tests/test_arch_ftq.py` | 91 |
| `rvw/tests/test_arch_gem5_export.py` | 22 |
| `rvw/tests/test_arch_injection.py` | 76 |
| `rvw/tests/test_arch_lifecycle.py` | 91 |
| `rvw/tests/test_arch_linux.py` | 246 |
| `rvw/tests/test_arch_memory.py` | 120 |
| `rvw/tests/test_arch_micro.py` | 27 |
| `rvw/tests/test_arch_model.py` | 306 |
| `rvw/tests/test_arch_rv32.py` | 64 |
| `rvw/tests/test_arch_sampling.py` | 66 |
| `rvw/tests/test_arch_sched.py` | 197 |
| `rvw/tests/test_arch_sched_study.py` | 50 |
| `rvw/tests/test_arch_search.py` | 173 |
| `rvw/tests/test_arch_soc.py` | 116 |
| `rvw/tests/test_arch_system_energy.py` | 19 |
| `rvw/tests/test_arch_traffic.py` | 47 |
| `rvw/tests/test_arch_warmup.py` | 64 |
| `rvw/tests/test_csim.py` | 250 |
| `rvw/tests/test_csim_cache.py` | 113 |
| `rvw/tests/test_csim_formats.py` | 206 |
| `rvw/tests/test_ooo.py` | 152 |
| `rvw/tests/test_ooo_attribution.py` | 12 |
| `rvw/tests/test_ooo_branch_speculation.py` | 32 |
| `rvw/tests/test_ooo_checks.py` | 126 |
| `rvw/tests/test_ooo_component_events.py` | 10 |
| `rvw/tests/test_ooo_components.py` | 70 |
| `rvw/tests/test_ooo_control.py` | 41 |
| `rvw/tests/test_ooo_custom.py` | 52 |
| `rvw/tests/test_ooo_delta.py` | 75 |
| `rvw/tests/test_ooo_delta_rank.py` | 23 |
| `rvw/tests/test_ooo_dependence.py` | 63 |
| `rvw/tests/test_ooo_designer.py` | 27 |
| `rvw/tests/test_ooo_evidence.py` | 108 |
| `rvw/tests/test_ooo_execution.py` | 27 |
| `rvw/tests/test_ooo_fdip.py` | 66 |
| `rvw/tests/test_ooo_fetch_blocks.py` | 31 |
| `rvw/tests/test_ooo_fit.py` | 63 |
| `rvw/tests/test_ooo_fixture_followup.py` | 26 |
| `rvw/tests/test_ooo_floating.py` | 46 |
| `rvw/tests/test_ooo_frontend.py` | 46 |
| `rvw/tests/test_ooo_inorder.py` | 60 |
| `rvw/tests/test_ooo_issue_window.py` | 54 |
| `rvw/tests/test_ooo_memory_rename.py` | 54 |
| `rvw/tests/test_ooo_mini_example.py` | 38 |
| `rvw/tests/test_ooo_native.py` | 100 |
| `rvw/tests/test_ooo_native_c2.py` | 98 |
| `rvw/tests/test_ooo_native_decode.py` | 79 |
| `rvw/tests/test_ooo_pipeline.py` | 57 |
| `rvw/tests/test_ooo_pressure.py` | 307 |
| `rvw/tests/test_ooo_project.py` | 55 |
| `rvw/tests/test_ooo_references.py` | 16 |
| `rvw/tests/test_ooo_regions.py` | 77 |
| `rvw/tests/test_ooo_rename.py` | 56 |
| `rvw/tests/test_ooo_resource_study.py` | 25 |
| `rvw/tests/test_ooo_sampled.py` | 63 |
| `rvw/tests/test_ooo_sampled_many.py` | 78 |
| `rvw/tests/test_ooo_search.py` | 33 |
| `rvw/tests/test_ooo_sensitivity.py` | 37 |
| `rvw/tests/test_ooo_static_prediction.py` | 43 |
| `rvw/tests/test_ooo_store_policy.py` | 62 |
| `rvw/tests/test_ooo_structures.py` | 104 |
| `rvw/tests/test_ooo_translation.py` | 30 |
| `rvw/tests/test_ooo_whatif.py` | 42 |
| `rvw/tests/test_ooo_wrongpath.py` | 66 |
| `rvw/tests/test_ooo_zero_irq.py` | 35 |
| `rvw/tests/test_perf.py` | 246 |
| `rvw/tests/test_perf_capture.py` | 147 |
| `rvw/tests/test_perf_conclusive.py` | 62 |
| `rvw/tests/test_perf_events.py` | 172 |
| `rvw/tests/test_perf_function_topdown.py` | 41 |
| `rvw/tests/test_perf_topdown.py` | 75 |
| `rvw/tests/test_workload_evaluation.py` | 65 |
| `rvw/tests/test_workload_recipes.py` | 41 |
| `rvw/tests/test_workloads.py` | 195 |
| `rvw/tests/test_workloads_comparison.py` | 43 |
| `rvw/tests/test_workloads_native.py` | 35 |
| `rvw/tests/test_workloads_rtl.py` | 78 |
| `rvw/tests/test_workloads_sizing.py` | 56 |
| `examples/naxriscv/rvw/arch/rank.py` | 44 |
| `examples/naxriscv/rvw/arch/resource-study.py` | 73 |


## Generic simulation harness and Python simulation services

Read 210 files. This includes every tracked source and documentation file under `RiscvSim/src/`, `RiscvSim/scripts/`, and `rvw/src/rvw/sim/`, the listed Python tests, and the shared device and Spinal axis sources. The table gives the line counts at report publication. Confirmed defects: 7. Fix PRs: 5. Unconfirmed findings retained: 0.

### Confirmed defects

- Mapped completion stores shifted data twice on nonzero byte lanes, which could lose or change tohost results. PR [#1404](https://github.com/riscPrint/risc-v-workstation/pull/1404), merged.
- The socket server could block past its request deadline after a partial native JSONL reply. PR [#1405](https://github.com/riscPrint/risc-v-workstation/pull/1405), merged.
- Generated header lookup split build paths at spaces and missed required Verilator member-name repairs. PR [#1407](https://github.com/riscPrint/risc-v-workstation/pull/1407), merged.
- PLIC claim polling incorrectly applied the notification threshold. PR [#1408](https://github.com/riscPrint/risc-v-workstation/pull/1408), merged.
- The PLIC lost a pending request when its source went low before claim. PR [#1408](https://github.com/riscPrint/risc-v-workstation/pull/1408), merged.
- UART IIR reads did not acknowledge a pending THRE interrupt. PR [#1408](https://github.com/riscPrint/risc-v-workstation/pull/1408), merged.
- External adapter classpath reuse ignored the selected Spinal source SDK, its files, and the shared axis script. PR [#1409](https://github.com/riscPrint/risc-v-workstation/pull/1409), merged.

PLIC claim behavior was checked against the [ratified claim specification](https://docs.riscv.org/reference/plic/plic-claims.html). UART acknowledgement behavior was checked against Table IV of the [manufacturer PC16550D data sheet](https://media.digikey.com/pdf/Data%20Sheets/Texas%20Instruments%20PDFs/PC16550D.pdf).

### Validation and limits

Each defect has a regression that failed with the original behavior. The mapped store check compiled production ToHost with the extracted completion helper and passed 12 RV32/RV64 lane cases after the fix. The generic sbt `testOnly riscvsim.MappedAdapterSpec` attempt used the private `sbt-rv-sim` lock and `nice -n 15`. It was canceled during project setup on the loaded machine. The full project regression is NOT RUN.

Direct Scala checks compiled production LiveDevices, SimMap and Hex with small RunJob and RunContext type stubs. All 12 tests in LiveDevicesSpec passed. This includes snapshot and reset checks. Five pure writer suites passed 8 tests. That check used the production writer source with the hardware RvfiProbe class omitted. It checked pending late traps, C2/2 CSR and environment records, external-interrupt ordering, flushing and writer checkpoints. These checks do not compile the full Spinal harness or exercise its native bridge.

Python server tests passed 10 tests. Script-name and coverage-writer tests passed 7 tests. Classpath tests passed 2 tests. A separate group of checkpoint, injection, profile, CPU-service, native-identity and capability tests passed 114 tests and skipped one optional test. The affected post-rebase Python set, including release hygiene, passed 55 tests. `bash -n RiscvSim/scripts/make-jobs.sh` passed. `rvw mcp --list` completed without skipped tools.

The required command `nice -n 15 rvw/.venv/bin/python -m pytest rvw/tests -m fast --strict-markers -q` completed with 3294 passed, 4 skipped, 1 failed and 7724 deselected. The failure was in the untouched `test_mcp_workflow_coverage.py::test_each_tool_has_a_profile_and_workflow`: `cov_mutate_core` had no workflow entry. The brief permits publication with an unrelated failure. The later classpath regression passed its targeted run. No raw test output is committed.

No BOOM build or simulation ran. Native whole-core, debug DMI/JTAG, fault-injection, coverage, cache and multi-hart simulation suites are NOT RUN. The direct checks are unit evidence. They do not establish whole-core qualification or complete device specification compliance.

### Read boundary

No source file remains unread in the three assigned directory trees. Files outside the inventory were not reviewed, including the BOOM adapter, external core adapters, and further integration tests and fixtures. Shared reference files in the inventory were read only. No unconfirmed defect is counted as a finding.

### Files read

| File read | Lines |
|---|---:|
| `RiscvSim/scripts/build-devices.py` | 65 |
| `RiscvSim/scripts/classpath.py` | 74 |
| `RiscvSim/scripts/make-jobs.sh` | 55 |
| `RiscvSim/scripts/native-identity.py` | 284 |
| `RiscvSim/scripts/replay-checkpoint.py` | 105 |
| `RiscvSim/scripts/source-identity.py` | 16 |
| `RiscvSim/scripts/supervise.py` | 47 |
| `RiscvSim/src/main/cpp/Checkpoint.h` | 37 |
| `RiscvSim/src/main/cpp/DEVICES.md` | 127 |
| `RiscvSim/src/main/cpp/DeviceDpi.cpp` | 29 |
| `RiscvSim/src/main/cpp/DevicePlugin.h` | 82 |
| `RiscvSim/src/main/cpp/PythonDevices.cpp` | 98 |
| `RiscvSim/src/main/cpp/TlmMemory.h` | 54 |
| `RiscvSim/src/main/scala/riscvsim/AssertIndex.scala` | 45 |
| `RiscvSim/src/main/scala/riscvsim/AtomicMemoryObserver.scala` | 94 |
| `RiscvSim/src/main/scala/riscvsim/BootImage.scala` | 54 |
| `RiscvSim/src/main/scala/riscvsim/BridgeState.scala` | 102 |
| `RiscvSim/src/main/scala/riscvsim/BusObservationWriter.scala` | 27 |
| `RiscvSim/src/main/scala/riscvsim/ByteMemory.scala` | 21 |
| `RiscvSim/src/main/scala/riscvsim/CacheEventObserver.scala` | 69 |
| `RiscvSim/src/main/scala/riscvsim/CacheScoreboard.scala` | 90 |
| `RiscvSim/src/main/scala/riscvsim/Cli.scala` | 177 |
| `RiscvSim/src/main/scala/riscvsim/CoherenceMonitor.scala` | 35 |
| `RiscvSim/src/main/scala/riscvsim/DebugPort.scala` | 206 |
| `RiscvSim/src/main/scala/riscvsim/DmaAgent.scala` | 64 |
| `RiscvSim/src/main/scala/riscvsim/DmaTransport.scala` | 10 |
| `RiscvSim/src/main/scala/riscvsim/Driver.scala` | 859 |
| `RiscvSim/src/main/scala/riscvsim/ElfFile.scala` | 129 |
| `RiscvSim/src/main/scala/riscvsim/FairnessMonitor.scala` | 39 |
| `RiscvSim/src/main/scala/riscvsim/FaultInjector.scala` | 197 |
| `RiscvSim/src/main/scala/riscvsim/HartImages.scala` | 73 |
| `RiscvSim/src/main/scala/riscvsim/HartLifecycleObserver.scala` | 78 |
| `RiscvSim/src/main/scala/riscvsim/Hex.scala` | 22 |
| `RiscvSim/src/main/scala/riscvsim/InstructionPort.scala` | 152 |
| `RiscvSim/src/main/scala/riscvsim/InstructionVisibility.scala` | 39 |
| `RiscvSim/src/main/scala/riscvsim/InterruptSchedule.scala` | 24 |
| `RiscvSim/src/main/scala/riscvsim/LiveDevices.scala` | 260 |
| `RiscvSim/src/main/scala/riscvsim/Lockstep.scala` | 22 |
| `RiscvSim/src/main/scala/riscvsim/LockstepDpi.scala` | 69 |
| `RiscvSim/src/main/scala/riscvsim/MappedAdapter.scala` | 380 |
| `RiscvSim/src/main/scala/riscvsim/Model.scala` | 147 |
| `RiscvSim/src/main/scala/riscvsim/MultiHart.scala` | 120 |
| `RiscvSim/src/main/scala/riscvsim/MultiHartExecutor.scala` | 66 |
| `RiscvSim/src/main/scala/riscvsim/NativeBuild.scala` | 110 |
| `RiscvSim/src/main/scala/riscvsim/NativeOutput.scala` | 147 |
| `RiscvSim/src/main/scala/riscvsim/PluginDevice.scala` | 58 |
| `RiscvSim/src/main/scala/riscvsim/ProbeCollector.scala` | 98 |
| `RiscvSim/src/main/scala/riscvsim/ProgressMonitor.scala` | 33 |
| `RiscvSim/src/main/scala/riscvsim/ResetSchedule.scala` | 57 |
| `RiscvSim/src/main/scala/riscvsim/ResourceWaitMonitor.scala` | 17 |
| `RiscvSim/src/main/scala/riscvsim/RtlCoverage.scala` | 76 |
| `RiscvSim/src/main/scala/riscvsim/Rvfi.scala` | 304 |
| `RiscvSim/src/main/scala/riscvsim/SimEncoding.scala` | 13 |
| `RiscvSim/src/main/scala/riscvsim/SimMap.scala` | 88 |
| `RiscvSim/src/main/scala/riscvsim/SimSession.scala` | 238 |
| `RiscvSim/src/main/scala/riscvsim/SpeedMetrics.scala` | 10 |
| `RiscvSim/src/main/scala/riscvsim/SpinalCompat.scala` | 9 |
| `RiscvSim/src/main/scala/riscvsim/StimulusMailbox.scala` | 55 |
| `RiscvSim/src/main/scala/riscvsim/TileLinkDmaTransport.scala` | 39 |
| `RiscvSim/src/main/scala/riscvsim/TileLinkProgressObserver.scala` | 121 |
| `RiscvSim/src/main/scala/riscvsim/ToHost.scala` | 69 |
| `RiscvSim/src/main/scala/riscvsim/TraceIngress.scala` | 82 |
| `RiscvSim/src/test/scala/riscvsim/AtomicFixture.scala` | 86 |
| `RiscvSim/src/test/scala/riscvsim/AtomicFixtureSpec.scala` | 229 |
| `RiscvSim/src/test/scala/riscvsim/AtomicMemoryObserverSpec.scala` | 43 |
| `RiscvSim/src/test/scala/riscvsim/BootImageSpec.scala` | 128 |
| `RiscvSim/src/test/scala/riscvsim/BridgeStateSpec.scala` | 44 |
| `RiscvSim/src/test/scala/riscvsim/BusObservationWriterSpec.scala` | 27 |
| `RiscvSim/src/test/scala/riscvsim/ByteMemorySnapshotSpec.scala` | 22 |
| `RiscvSim/src/test/scala/riscvsim/ByteMemorySpec.scala` | 19 |
| `RiscvSim/src/test/scala/riscvsim/CacheEventObserverSpec.scala` | 48 |
| `RiscvSim/src/test/scala/riscvsim/CacheScoreboardSpec.scala` | 78 |
| `RiscvSim/src/test/scala/riscvsim/CoherenceModelFixtureSpec.scala` | 68 |
| `RiscvSim/src/test/scala/riscvsim/CoherenceMonitorSpec.scala` | 23 |
| `RiscvSim/src/test/scala/riscvsim/CoherentCacheNativeSpec.scala` | 158 |
| `RiscvSim/src/test/scala/riscvsim/CoverageLocationsSpec.scala` | 33 |
| `RiscvSim/src/test/scala/riscvsim/CoverageVersionSpec.scala` | 22 |
| `RiscvSim/src/test/scala/riscvsim/CsrSnapshotSpec.scala` | 44 |
| `RiscvSim/src/test/scala/riscvsim/DmaAgentSpec.scala` | 79 |
| `RiscvSim/src/test/scala/riscvsim/EnvironmentTraceSpec.scala` | 26 |
| `RiscvSim/src/test/scala/riscvsim/ExternalInterruptSpec.scala` | 28 |
| `RiscvSim/src/test/scala/riscvsim/FairnessMonitorSpec.scala` | 32 |
| `RiscvSim/src/test/scala/riscvsim/FaultInjectorNativeSpec.scala` | 50 |
| `RiscvSim/src/test/scala/riscvsim/GenericAdapterSpec.scala` | 94 |
| `RiscvSim/src/test/scala/riscvsim/HartImagesSpec.scala` | 74 |
| `RiscvSim/src/test/scala/riscvsim/HartLifecycleObserverSpec.scala` | 39 |
| `RiscvSim/src/test/scala/riscvsim/InstructionPortSpec.scala` | 37 |
| `RiscvSim/src/test/scala/riscvsim/InstructionVisibilitySpec.scala` | 34 |
| `RiscvSim/src/test/scala/riscvsim/InterruptScheduleSpec.scala` | 28 |
| `RiscvSim/src/test/scala/riscvsim/LiveDevicesSpec.scala` | 193 |
| `RiscvSim/src/test/scala/riscvsim/LiveTraceSpec.scala` | 55 |
| `RiscvSim/src/test/scala/riscvsim/MappedAdapterSpec.scala` | 64 |
| `RiscvSim/src/test/scala/riscvsim/MultiHartExecutorNativeSpec.scala` | 146 |
| `RiscvSim/src/test/scala/riscvsim/MultiHartExecutorSpec.scala` | 107 |
| `RiscvSim/src/test/scala/riscvsim/MultiHartSpec.scala` | 102 |
| `RiscvSim/src/test/scala/riscvsim/NativeFlagsProbe.scala` | 56 |
| `RiscvSim/src/test/scala/riscvsim/PersistentNativeSpec.scala` | 60 |
| `RiscvSim/src/test/scala/riscvsim/PluginDeviceSpec.scala` | 41 |
| `RiscvSim/src/test/scala/riscvsim/ProbeCollectorSpec.scala` | 60 |
| `RiscvSim/src/test/scala/riscvsim/ProgressMonitorSpec.scala` | 27 |
| `RiscvSim/src/test/scala/riscvsim/ResetScheduleSpec.scala` | 31 |
| `RiscvSim/src/test/scala/riscvsim/RiscvSimSpec.scala` | 633 |
| `RiscvSim/src/test/scala/riscvsim/RtlCoverageSpec.scala` | 43 |
| `RiscvSim/src/test/scala/riscvsim/RtlIdentitySpec.scala` | 56 |
| `RiscvSim/src/test/scala/riscvsim/Rv64AtomicFixtureSpec.scala` | 162 |
| `RiscvSim/src/test/scala/riscvsim/SerializedMemorySpec.scala` | 25 |
| `RiscvSim/src/test/scala/riscvsim/ServerSpec.scala` | 183 |
| `RiscvSim/src/test/scala/riscvsim/SimEncodingSpec.scala` | 41 |
| `RiscvSim/src/test/scala/riscvsim/SimMapSpec.scala` | 30 |
| `RiscvSim/src/test/scala/riscvsim/SimThreadsSpec.scala` | 44 |
| `RiscvSim/src/test/scala/riscvsim/SpeedMetricsSpec.scala` | 17 |
| `RiscvSim/src/test/scala/riscvsim/SpinalTraceFlagSpec.scala` | 72 |
| `RiscvSim/src/test/scala/riscvsim/TileLinkProgressObserverSpec.scala` | 87 |
| `RiscvSim/src/test/scala/riscvsim/TileLinkSdkCompat.scala` | 36 |
| `RiscvSim/src/test/scala/riscvsim/TwoHartNativeSpec.scala` | 169 |
| `RiscvSim/src/test/scala/riscvsim/TypedCacheBindSpec.scala` | 182 |
| `RiscvSim/src/test/scala/riscvsim/WriterCheckpointSpec.scala` | 33 |
| `rvw/src/rvw/cosim/devices.py` | 261 |
| `rvw/src/rvw/sim/INJECTION.md` | 61 |
| `rvw/src/rvw/sim/README.md` | 470 |
| `rvw/src/rvw/sim/REVERSE.md` | 39 |
| `rvw/src/rvw/sim/__init__.py` | 1 |
| `rvw/src/rvw/sim/arcilator_install.py` | 49 |
| `rvw/src/rvw/sim/backends.py` | 67 |
| `rvw/src/rvw/sim/bench.py` | 28 |
| `rvw/src/rvw/sim/checkpoint.py` | 113 |
| `rvw/src/rvw/sim/cli.py` | 105 |
| `rvw/src/rvw/sim/cli_declarations.py` | 2 |
| `rvw/src/rvw/sim/cocotb.py` | 135 |
| `rvw/src/rvw/sim/commands/__init__.py` | 1 |
| `rvw/src/rvw/sim/commands/server.py` | 41 |
| `rvw/src/rvw/sim/cpu_env.py` | 197 |
| `rvw/src/rvw/sim/devices.py` | 175 |
| `rvw/src/rvw/sim/hdl.py` | 152 |
| `rvw/src/rvw/sim/injection.py` | 110 |
| `rvw/src/rvw/sim/live.py` | 147 |
| `rvw/src/rvw/sim/mcp_tools.py` | 59 |
| `rvw/src/rvw/sim/native_models.py` | 195 |
| `rvw/src/rvw/sim/native_profiles.py` | 96 |
| `rvw/src/rvw/sim/native_wave.py` | 24 |
| `rvw/src/rvw/sim/persistent.py` | 34 |
| `rvw/src/rvw/sim/profile.py` | 69 |
| `rvw/src/rvw/sim/ral.py` | 69 |
| `rvw/src/rvw/sim/reverse.py` | 39 |
| `rvw/src/rvw/sim/server.py` | 110 |
| `rvw/src/rvw/sim/speed.py` | 230 |
| `rvw/src/rvw/sim/spike_bootstrap.py` | 36 |
| `rvw/src/rvw/sim/timing.py` | 90 |
| `rvw/src/rvw/sim/uvm.py` | 191 |
| `rvw/src/rvw/sim/uvm_cpu.py` | 237 |
| `rvw/src/rvw/sim/uvm_features.py` | 41 |
| `rvw/src/rvw/sim/uvm_models.py` | 134 |
| `rvw/src/rvw/sim/worker.py` | 38 |
| `rvw/tests/devices/test_plic.py` | 94 |
| `rvw/tests/devices/test_reset.py` | 53 |
| `rvw/tests/devices/test_timer.py` | 81 |
| `rvw/tests/fixtures/cocotb/semantic_bench.py` | 71 |
| `rvw/tests/test_arch_injection.py` | 76 |
| `rvw/tests/test_backend_capabilities.py` | 20 |
| `rvw/tests/test_c1_capabilities.py` | 62 |
| `rvw/tests/test_cocotb.py` | 84 |
| `rvw/tests/test_cocotb_data_files.py` | 15 |
| `rvw/tests/test_cocotb_native.py` | 24 |
| `rvw/tests/test_coverage_writer.py` | 39 |
| `rvw/tests/test_cpu_controls.py` | 59 |
| `rvw/tests/test_cpu_env.py` | 97 |
| `rvw/tests/test_device_build_library.py` | 43 |
| `rvw/tests/test_device_events.py` | 69 |
| `rvw/tests/test_device_plugin.py` | 125 |
| `rvw/tests/test_external_classpath.py` | 67 |
| `rvw/tests/test_hdl_declared_ports.py` | 102 |
| `rvw/tests/test_hdl_identity.py` | 40 |
| `rvw/tests/test_hdl_semantics.py` | 131 |
| `rvw/tests/test_live_checkpoint.py` | 51 |
| `rvw/tests/test_make_jobs_names.py` | 44 |
| `rvw/tests/test_native_checkpoint.py` | 90 |
| `rvw/tests/test_native_checkpoint_verilator.py` | 107 |
| `rvw/tests/test_native_identity.py` | 172 |
| `rvw/tests/test_native_port_wave.py` | 19 |
| `rvw/tests/test_native_profiles.py` | 50 |
| `rvw/tests/test_native_scalar_models.py` | 45 |
| `rvw/tests/test_native_wide_models.py` | 60 |
| `rvw/tests/test_regress_persistent.py` | 148 |
| `rvw/tests/test_replay_checkpoint.py` | 69 |
| `rvw/tests/test_reverse_checkpoint.py` | 40 |
| `rvw/tests/test_riscvsim_scripts.py` | 615 |
| `rvw/tests/test_sim_accel_launcher.py` | 48 |
| `rvw/tests/test_sim_linux_recipe.py` | 19 |
| `rvw/tests/test_sim_profile.py` | 34 |
| `rvw/tests/test_sim_socket_server.py` | 123 |
| `rvw/tests/test_sim_speed.py` | 242 |
| `rvw/tests/test_spike_bootstrap.py` | 32 |
| `rvw/tests/test_standard_devices.py` | 164 |
| `rvw/tests/test_timing_handoff.py` | 39 |
| `rvw/tests/test_uvm.py` | 112 |
| `rvw/tests/test_uvm_cpu.py` | 155 |
| `rvw/tests/test_uvm_cpu_native.py` | 50 |
| `rvw/tests/test_uvm_events_native.py` | 25 |
| `rvw/tests/test_uvm_features.py` | 28 |
| `rvw/tests/test_uvm_flow.py` | 166 |
| `rvw/tests/test_uvm_gate.py` | 115 |
| `rvw/tests/test_uvm_models.py` | 86 |
| `rvw/tests/test_uvm_native.py` | 42 |
| `rvw/tests/test_uvm_profiles.py` | 56 |
| `rvw/tests/test_uvm_pyuvm_native.py` | 17 |
| `rvw/tests/test_uvm_ral.py` | 58 |
| `rvw/tests/test_uvm_ral_sequences_native.py` | 31 |
| `rvw/tests/test_uvm_soc_native.py` | 19 |
| `rvw/tests/test_uvm_vex_live.py` | 43 |
| `scripts/sbt/SpinalAxis.scala` | 56 |
## Python formal package review

Read all 204 Python source files and all 214 assigned Python test files. Also read two related Sail tests and 13 package documentation, example and license files. The total is 433 files and 44025 lines. Counts describe commit 90f456ca583f8657f766320d22c47f708b5aaefe with the seven review fixes. Changes to the formal command adapters on main during the review were also read.

Review order: property and SBY generation, engine result parsing, cache identities, remaining source, tests and documentation. No unread Python source or assigned Python test remains.

### Confirmed defects

| Defect | Fix | PR |
| --- | --- | --- |
| Sail temporary-concatenation slices lost their braces and emitted invalid SystemVerilog. | Keep the concatenation inside the sized cast in both lowering paths. | [#1361](https://github.com/riscPrint/risc-v-workstation/pull/1361) |
| Datapath C uncertainty masks started at zero for unreset registers. | Mark every initial state bit unknown until RTL defines it. | [#1364](https://github.com/riscPrint/risc-v-workstation/pull/1364) |
| Liveness snapshots ignored declared net offsets and ascending ranges. | Select the actual RTL indices in Yosys bit order. | [#1368](https://github.com/riscPrint/risc-v-workstation/pull/1368) |
| MCP Boolean options produced extra True arguments that argparse rejected. | Emit confirm, unbounded and run as flags. | [#1371](https://github.com/riscPrint/risc-v-workstation/pull/1371) |
| The shared MCP reader rejected valid command-specific success states. | Check the declared success states while retaining exit/status consistency. | [#1374](https://github.com/riscPrint/risc-v-workstation/pull/1374) |
| The datapath kit MCP reader looked in the wrong output path for both modes. | Read proposal.json or proof/result.json and keep their success states separate. | [#1400](https://github.com/riscPrint/risc-v-workstation/pull/1400) |
| A completed cross-clock attempt hid a later pending request in event simulation. | Report all pending cross-clock counts to the existing assertion and assumption checks. | [#1402](https://github.com/riscPrint/risc-v-workstation/pull/1402) |

Each defect has a regression that failed before the change. The fixes remain separate PRs. No CLI name or result schema changed. No missing evidence was promoted to success. The Sail syntax fix also updates one existing test outside the assigned test-name pattern.

### Validation

Targeted checks: Sail lowering and existing M tests, 10 passed; generated concatenation, one tiny native Yosys SAT check passed; uncertainty initialization, two native C cases passed; liveness ranges and existing app tests, five passed with OSS CAD Suite; MCP flags and outcomes with error tests, 13 passed; datapath kit with existing tests, 19 passed; post-rebase MCP kit checks, 11 passed. Cross-clock native checks had 15 passing cases, then one old diagnostic expectation failed. After that expectation was updated, the two new cases and four unknown/pending cases passed. These are fixture results, not whole-core qualification.

First fast set: 3294 passed, 4 skipped, 7724 deselected, one unrelated failure in test_mcp_workflow_coverage.py::test_each_tool_has_a_profile_and_workflow because cov_mutate_core had no workflow entry. A later fast set passed: 3392 passed, 4 skipped, 7729 deselected. Final pre-push fast set: 3471 passed, 4 skipped, 7740 deselected.

Release hygiene: 40 passed. CLI import and MCP discovery passed with no skipped modules. No core build, long simulation, long proof, full Python suite or Scala build was run. The Homebrew yosys-witness launcher lacked click. The liveness tests passed with the existing OSS CAD Suite installation. No system package was changed.

### Unconfirmed items and limits

No suspected code defect remains unconfirmed. The two CSR reference catalogues were parsed for structure and entry counts, but were not read entry by entry or checked against their source standards: csr_catalog.json has 416 entries and 27211 lines; csr_aia_catalog.json has 26 entries and 3455 lines. Their text and semantic tables remain outside this review's assurance. No other package file remains unread. External core implementations, third-party models, tools and test fixtures outside the named area were not comprehensively reviewed.

### Files read

| File | Lines |
| --- | ---: |
| `rvw/src/rvw/formal/AIA_CATALOG_LICENSE.txt` | 395 |
| `rvw/src/rvw/formal/CSR_CATALOG_LICENSE.txt` | 26 |
| `rvw/src/rvw/formal/README-apps.md` | 417 |
| `rvw/src/rvw/formal/README-datapath-kit.md` | 45 |
| `rvw/src/rvw/formal/README-equiv-partitions.md` | 38 |
| `rvw/src/rvw/formal/README.md` | 3570 |
| `rvw/src/rvw/formal/SCENARIOS.md` | 82 |
| `rvw/src/rvw/formal/TEMPORAL_SUPPORT.md` | 45 |
| `rvw/src/rvw/formal/__init__.py` | 0 |
| `rvw/src/rvw/formal/activation.py` | 33 |
| `rvw/src/rvw/formal/aiger_input.py` | 100 |
| `rvw/src/rvw/formal/aiger_live.py` | 97 |
| `rvw/src/rvw/formal/aiger_live_model.py` | 183 |
| `rvw/src/rvw/formal/antecedent_cover.py` | 50 |
| `rvw/src/rvw/formal/app_monitors.py` | 66 |
| `rvw/src/rvw/formal/apps.py` | 235 |
| `rvw/src/rvw/formal/apps_cli.py` | 114 |
| `rvw/src/rvw/formal/apps_mcp.py` | 52 |
| `rvw/src/rvw/formal/architectural_state.py` | 165 |
| `rvw/src/rvw/formal/autocheck.py` | 119 |
| `rvw/src/rvw/formal/automonitors.py` | 43 |
| `rvw/src/rvw/formal/axi_strobes.py` | 51 |
| `rvw/src/rvw/formal/axi_transactions.py` | 167 |
| `rvw/src/rvw/formal/bench.py` | 222 |
| `rvw/src/rvw/formal/bindings.py` | 47 |
| `rvw/src/rvw/formal/bitc.py` | 151 |
| `rvw/src/rvw/formal/blackbox_models.py` | 24 |
| `rvw/src/rvw/formal/bug_hunt.py` | 62 |
| `rvw/src/rvw/formal/bus_bindings.py` | 202 |
| `rvw/src/rvw/formal/bus_environment.py` | 58 |
| `rvw/src/rvw/formal/bus_types.py` | 21 |
| `rvw/src/rvw/formal/campaign.py` | 170 |
| `rvw/src/rvw/formal/cell_model.py` | 142 |
| `rvw/src/rvw/formal/cex.py` | 299 |
| `rvw/src/rvw/formal/cex_reduce.py` | 105 |
| `rvw/src/rvw/formal/channel_bindings.py` | 69 |
| `rvw/src/rvw/formal/cli.py` | 378 |
| `rvw/src/rvw/formal/cli_declarations.py` | 2 |
| `rvw/src/rvw/formal/commands/__init__.py` | 2 |
| `rvw/src/rvw/formal/commands/aiger_live.py` | 37 |
| `rvw/src/rvw/formal/commands/counter_quotient.py` | 24 |
| `rvw/src/rvw/formal/commands/cover_hunt.py` | 34 |
| `rvw/src/rvw/formal/commands/cross_prove.py` | 31 |
| `rvw/src/rvw/formal/commands/datapath_kit.py` | 16 |
| `rvw/src/rvw/formal/commands/equiv_partitions.py` | 28 |
| `rvw/src/rvw/formal/commands/ic3_lemmas.py` | 34 |
| `rvw/src/rvw/formal/commands/initial_split.py` | 31 |
| `rvw/src/rvw/formal/commands/isa.py` | 64 |
| `rvw/src/rvw/formal/commands/lazy_ram.py` | 33 |
| `rvw/src/rvw/formal/commands/machine_checks.py` | 43 |
| `rvw/src/rvw/formal/commands/reset_audit.py` | 33 |
| `rvw/src/rvw/formal/commands/revision_bench.py` | 39 |
| `rvw/src/rvw/formal/commands/riscv_abstract.py` | 55 |
| `rvw/src/rvw/formal/commands/riscv_proof.py` | 54 |
| `rvw/src/rvw/formal/commands/sail_m.py` | 37 |
| `rvw/src/rvw/formal/commands/sail_state.py` | 35 |
| `rvw/src/rvw/formal/commands/scenario_compile.py` | 32 |
| `rvw/src/rvw/formal/commands/strategy.py` | 47 |
| `rvw/src/rvw/formal/commands/sva_inspect.py` | 29 |
| `rvw/src/rvw/formal/commands/trace_mine.py` | 37 |
| `rvw/src/rvw/formal/commands/uf_prove.py` | 35 |
| `rvw/src/rvw/formal/common.py` | 794 |
| `rvw/src/rvw/formal/compiled_variants.py` | 35 |
| `rvw/src/rvw/formal/connection_binding.py` | 142 |
| `rvw/src/rvw/formal/connectivity.py` | 358 |
| `rvw/src/rvw/formal/contracts.py` | 187 |
| `rvw/src/rvw/formal/core_model.py` | 76 |
| `rvw/src/rvw/formal/cores.py` | 201 |
| `rvw/src/rvw/formal/counter_quotient.py` | 109 |
| `rvw/src/rvw/formal/cover_hunt.py` | 121 |
| `rvw/src/rvw/formal/cross_clock.py` | 107 |
| `rvw/src/rvw/formal/cross_proof.py` | 108 |
| `rvw/src/rvw/formal/csr.py` | 237 |
| `rvw/src/rvw/formal/csr_aia_indirect.py` | 86 |
| `rvw/src/rvw/formal/csr_bank.py` | 185 |
| `rvw/src/rvw/formal/csr_catalog.py` | 4 |
| `rvw/src/rvw/formal/csr_slices.py` | 93 |
| `rvw/src/rvw/formal/custom_backends.py` | 157 |
| `rvw/src/rvw/formal/custom_effects.py` | 225 |
| `rvw/src/rvw/formal/custom_isa.py` | 203 |
| `rvw/src/rvw/formal/cuts.py` | 60 |
| `rvw/src/rvw/formal/database_autocheck.py` | 94 |
| `rvw/src/rvw/formal/datapath.py` | 251 |
| `rvw/src/rvw/formal/datapath_binding.py` | 78 |
| `rvw/src/rvw/formal/datapath_kit.py` | 142 |
| `rvw/src/rvw/formal/deadlock_app.py` | 49 |
| `rvw/src/rvw/formal/deep_cli.py` | 145 |
| `rvw/src/rvw/formal/deep_grid.py` | 30 |
| `rvw/src/rvw/formal/deep_model.py` | 153 |
| `rvw/src/rvw/formal/engine_bench.py` | 42 |
| `rvw/src/rvw/formal/engine_doctor.py` | 23 |
| `rvw/src/rvw/formal/engine_limits.py` | 31 |
| `rvw/src/rvw/formal/equiv.py` | 428 |
| `rvw/src/rvw/formal/equiv_cex.py` | 15 |
| `rvw/src/rvw/formal/equiv_memory.py` | 51 |
| `rvw/src/rvw/formal/equiv_partitions.py` | 90 |
| `rvw/src/rvw/formal/event_equiv.py` | 16 |
| `rvw/src/rvw/formal/event_sim.py` | 268 |
| `rvw/src/rvw/formal/examples/AutocheckFifo.scala` | 23 |
| `rvw/src/rvw/formal/examples/cross-proof-results.json` | 25 |
| `rvw/src/rvw/formal/explain.py` | 21 |
| `rvw/src/rvw/formal/export.py` | 99 |
| `rvw/src/rvw/formal/fair_live.py` | 73 |
| `rvw/src/rvw/formal/flows.py` | 1019 |
| `rvw/src/rvw/formal/generated_checks.py` | 61 |
| `rvw/src/rvw/formal/grid_adapter.py` | 52 |
| `rvw/src/rvw/formal/grid_farm.py` | 103 |
| `rvw/src/rvw/formal/ic3_lemmas.py` | 205 |
| `rvw/src/rvw/formal/initial_split.py` | 117 |
| `rvw/src/rvw/formal/input_identity.py` | 38 |
| `rvw/src/rvw/formal/instruction_attempts.py` | 12 |
| `rvw/src/rvw/formal/internal_exposure.py` | 30 |
| `rvw/src/rvw/formal/internal_paths.py` | 136 |
| `rvw/src/rvw/formal/invariants.py` | 71 |
| `rvw/src/rvw/formal/isa.py` | 174 |
| `rvw/src/rvw/formal/isa_activation.py` | 61 |
| `rvw/src/rvw/formal/isa_latency.py` | 36 |
| `rvw/src/rvw/formal/isa_memory.py` | 68 |
| `rvw/src/rvw/formal/lazy_ram.py` | 157 |
| `rvw/src/rvw/formal/lemma_cone.py` | 102 |
| `rvw/src/rvw/formal/literal_tcl.py` | 46 |
| `rvw/src/rvw/formal/live_sim.py` | 151 |
| `rvw/src/rvw/formal/liveness.py` | 136 |
| `rvw/src/rvw/formal/liveness_app.py` | 128 |
| `rvw/src/rvw/formal/liveness_safety.py` | 65 |
| `rvw/src/rvw/formal/local_capture.py` | 98 |
| `rvw/src/rvw/formal/machine_checks.py` | 168 |
| `rvw/src/rvw/formal/mcp_tools.py` | 431 |
| `rvw/src/rvw/formal/memory_refinement.py` | 76 |
| `rvw/src/rvw/formal/micro_checks.py` | 174 |
| `rvw/src/rvw/formal/mining.py` | 84 |
| `rvw/src/rvw/formal/nested_eventually.py` | 45 |
| `rvw/src/rvw/formal/ooo_checks.py` | 116 |
| `rvw/src/rvw/formal/operand_partition.py` | 21 |
| `rvw/src/rvw/formal/portfolio.py` | 287 |
| `rvw/src/rvw/formal/power_checks.py` | 71 |
| `rvw/src/rvw/formal/power_intent.py` | 112 |
| `rvw/src/rvw/formal/profile_clauses.py` | 150 |
| `rvw/src/rvw/formal/profiles.py` | 179 |
| `rvw/src/rvw/formal/progress.py` | 61 |
| `rvw/src/rvw/formal/proof_cache.py` | 91 |
| `rvw/src/rvw/formal/proof_conditions.py` | 21 |
| `rvw/src/rvw/formal/property_library.py` | 183 |
| `rvw/src/rvw/formal/property_names.py` | 38 |
| `rvw/src/rvw/formal/psl.py` | 118 |
| `rvw/src/rvw/formal/raw_events.py` | 110 |
| `rvw/src/rvw/formal/recheck.py` | 116 |
| `rvw/src/rvw/formal/register_match.py` | 20 |
| `rvw/src/rvw/formal/regression.py` | 182 |
| `rvw/src/rvw/formal/regression_cache.py` | 105 |
| `rvw/src/rvw/formal/relations.py` | 26 |
| `rvw/src/rvw/formal/reset_audit.py` | 172 |
| `rvw/src/rvw/formal/resource_checks.py` | 59 |
| `rvw/src/rvw/formal/revision_bench.py` | 44 |
| `rvw/src/rvw/formal/ric3_compat.py` | 29 |
| `rvw/src/rvw/formal/riscv-abstract-options.md` | 76 |
| `rvw/src/rvw/formal/riscv.py` | 272 |
| `rvw/src/rvw/formal/riscv_abstract.py` | 154 |
| `rvw/src/rvw/formal/riscv_proof.py` | 97 |
| `rvw/src/rvw/formal/role_bindings.py` | 21 |
| `rvw/src/rvw/formal/role_discovery.py` | 52 |
| `rvw/src/rvw/formal/role_monitors.py` | 45 |
| `rvw/src/rvw/formal/rtl_grid.py` | 64 |
| `rvw/src/rvw/formal/rtl_refine.py` | 125 |
| `rvw/src/rvw/formal/runtime.py` | 21 |
| `rvw/src/rvw/formal/rvfi_binding.py` | 94 |
| `rvw/src/rvw/formal/sail_bitmanip.py` | 128 |
| `rvw/src/rvw/formal/sail_m.py` | 67 |
| `rvw/src/rvw/formal/sail_state_slices.py` | 159 |
| `rvw/src/rvw/formal/sail_subset.py` | 147 |
| `rvw/src/rvw/formal/sail_zicond.py` | 233 |
| `rvw/src/rvw/formal/sampled.py` | 71 |
| `rvw/src/rvw/formal/scenario.py` | 216 |
| `rvw/src/rvw/formal/scenario_compile.py` | 92 |
| `rvw/src/rvw/formal/schedule.py` | 33 |
| `rvw/src/rvw/formal/search.py` | 60 |
| `rvw/src/rvw/formal/security/README.md` | 299 |
| `rvw/src/rvw/formal/security/__init__.py` | 1 |
| `rvw/src/rvw/formal/security/cli.py` | 106 |
| `rvw/src/rvw/formal/security/contracts.py` | 95 |
| `rvw/src/rvw/formal/security/entropy.py` | 26 |
| `rvw/src/rvw/formal/security/ift.py` | 117 |
| `rvw/src/rvw/formal/security/pair.py` | 129 |
| `rvw/src/rvw/formal/security/pmp.py` | 67 |
| `rvw/src/rvw/formal/security/policy.py` | 199 |
| `rvw/src/rvw/formal/security/unsupported.py` | 26 |
| `rvw/src/rvw/formal/shortest.py` | 122 |
| `rvw/src/rvw/formal/simple_bus_checks.py` | 78 |
| `rvw/src/rvw/formal/slang_capability.py` | 29 |
| `rvw/src/rvw/formal/smt_uf.py` | 178 |
| `rvw/src/rvw/formal/snapshot.py` | 187 |
| `rvw/src/rvw/formal/state_encoding.py` | 102 |
| `rvw/src/rvw/formal/state_overlay.py` | 120 |
| `rvw/src/rvw/formal/state_selection.py` | 34 |
| `rvw/src/rvw/formal/strategy.py` | 56 |
| `rvw/src/rvw/formal/sva.py` | 84 |
| `rvw/src/rvw/formal/sva_ast.py` | 124 |
| `rvw/src/rvw/formal/sva_defaults.py` | 66 |
| `rvw/src/rvw/formal/swarm.py` | 84 |
| `rvw/src/rvw/formal/temporal.py` | 384 |
| `rvw/src/rvw/formal/testplan.py` | 172 |
| `rvw/src/rvw/formal/tilelink_coherent.py` | 95 |
| `rvw/src/rvw/formal/tilelink_transactions.py` | 149 |
| `rvw/src/rvw/formal/timeout-rerun.md` | 93 |
| `rvw/src/rvw/formal/timeout_rerun.py` | 244 |
| `rvw/src/rvw/formal/tools.py` | 205 |
| `rvw/src/rvw/formal/trace_candidates.py` | 87 |
| `rvw/src/rvw/formal/typed_bus_checks.py` | 87 |
| `rvw/src/rvw/formal/uf_prove.py` | 71 |
| `rvw/src/rvw/formal/unbounded.py` | 229 |
| `rvw/src/rvw/formal/upf_clock_gates.py` | 29 |
| `rvw/src/rvw/formal/upf_subset.py` | 205 |
| `rvw/src/rvw/formal/upf_switches.py` | 58 |
| `rvw/src/rvw/formal/vcdsnap.py` | 326 |
| `rvw/src/rvw/formal/xcontext.py` | 90 |
| `rvw/src/rvw/formal/xreplay.py` | 131 |
| `rvw/src/rvw/formal/xsweep.py` | 80 |
| `rvw/tests/formal/conftest.py` | 15 |
| `rvw/tests/formal/test_activation.py` | 61 |
| `rvw/tests/formal/test_activation_native.py` | 45 |
| `rvw/tests/formal/test_aiger_input.py` | 27 |
| `rvw/tests/formal/test_aiger_live.py` | 62 |
| `rvw/tests/formal/test_aiger_live_model.py` | 125 |
| `rvw/tests/formal/test_aiger_live_native.py` | 32 |
| `rvw/tests/formal/test_app_monitors.py` | 114 |
| `rvw/tests/formal/test_apps.py` | 169 |
| `rvw/tests/formal/test_apps_entrypoints.py` | 14 |
| `rvw/tests/formal/test_arithmetic_lemma_bindings.py` | 65 |
| `rvw/tests/formal/test_autocheck.py` | 90 |
| `rvw/tests/formal/test_autocheck_input_errors.py` | 21 |
| `rvw/tests/formal/test_axi_transactions.py` | 114 |
| `rvw/tests/formal/test_bench.py` | 149 |
| `rvw/tests/formal/test_bench_fetch.py` | 26 |
| `rvw/tests/formal/test_bit_crypto_models.py` | 137 |
| `rvw/tests/formal/test_blackbox_contracts.py` | 59 |
| `rvw/tests/formal/test_boom_replay_shell.py` | 50 |
| `rvw/tests/formal/test_bounded_datapath.py` | 47 |
| `rvw/tests/formal/test_bug_hunt.py` | 40 |
| `rvw/tests/formal/test_bus_bindings.py` | 210 |
| `rvw/tests/formal/test_bus_types.py` | 73 |
| `rvw/tests/formal/test_cell_model.py` | 67 |
| `rvw/tests/formal/test_cex.py` | 154 |
| `rvw/tests/formal/test_cex_reduce.py` | 69 |
| `rvw/tests/formal/test_channel_bindings.py` | 73 |
| `rvw/tests/formal/test_compiled_variants.py` | 28 |
| `rvw/tests/formal/test_contracts.py` | 181 |
| `rvw/tests/formal/test_core_model.py` | 73 |
| `rvw/tests/formal/test_core_progress_native.py` | 31 |
| `rvw/tests/formal/test_counter_quotient.py` | 46 |
| `rvw/tests/formal/test_cover_hunt.py` | 36 |
| `rvw/tests/formal/test_cover_hunt_native.py` | 34 |
| `rvw/tests/formal/test_cross_clock.py` | 69 |
| `rvw/tests/formal/test_cross_clock_native.py` | 115 |
| `rvw/tests/formal/test_cross_proof.py` | 27 |
| `rvw/tests/formal/test_cross_proof_native.py` | 75 |
| `rvw/tests/formal/test_csr_bank_sby.py` | 45 |
| `rvw/tests/formal/test_csr_spike.py` | 32 |
| `rvw/tests/formal/test_database_autocheck.py` | 115 |
| `rvw/tests/formal/test_datapath.py` | 88 |
| `rvw/tests/formal/test_datapath_definedness.py` | 85 |
| `rvw/tests/formal/test_datapath_kit.py` | 124 |
| `rvw/tests/formal/test_datapath_public_reset.py` | 25 |
| `rvw/tests/formal/test_deadlock_app.py` | 40 |
| `rvw/tests/formal/test_deep_abstraction_commands.py` | 13 |
| `rvw/tests/formal/test_deep_grid_farm.py` | 32 |
| `rvw/tests/formal/test_deep_model.py` | 65 |
| `rvw/tests/formal/test_dynamic_pmp.py` | 73 |
| `rvw/tests/formal/test_engine_bench_qualification.py` | 20 |
| `rvw/tests/formal/test_engine_doctor.py` | 27 |
| `rvw/tests/formal/test_engine_install.py` | 45 |
| `rvw/tests/formal/test_engine_limits.py` | 19 |
| `rvw/tests/formal/test_engine_portfolio.py` | 118 |
| `rvw/tests/formal/test_entropy_protocol.py` | 39 |
| `rvw/tests/formal/test_equiv.py` | 192 |
| `rvw/tests/formal/test_equiv_export.py` | 98 |
| `rvw/tests/formal/test_equiv_memory.py` | 44 |
| `rvw/tests/formal/test_equiv_partitions.py` | 78 |
| `rvw/tests/formal/test_equiv_replay.py` | 36 |
| `rvw/tests/formal/test_event_equiv.py` | 45 |
| `rvw/tests/formal/test_event_sim.py` | 76 |
| `rvw/tests/formal/test_explain.py` | 28 |
| `rvw/tests/formal/test_fair_live.py` | 51 |
| `rvw/tests/formal/test_formal.py` | 382 |
| `rvw/tests/formal/test_formal_abc.py` | 67 |
| `rvw/tests/formal/test_formal_async.py` | 141 |
| `rvw/tests/formal/test_formal_capture.py` | 199 |
| `rvw/tests/formal/test_formal_clocks.py` | 223 |
| `rvw/tests/formal/test_formal_elaboration.py` | 143 |
| `rvw/tests/formal/test_formal_events.py` | 84 |
| `rvw/tests/formal/test_formal_filter.py` | 46 |
| `rvw/tests/formal/test_formal_mapping.py` | 169 |
| `rvw/tests/formal/test_formal_out_lock.py` | 153 |
| `rvw/tests/formal/test_formal_safety.py` | 502 |
| `rvw/tests/formal/test_formal_snapshot.py` | 236 |
| `rvw/tests/formal/test_formal_suite_install.py` | 65 |
| `rvw/tests/formal/test_formal_undriven.py` | 117 |
| `rvw/tests/formal/test_freelist_proofs.py` | 41 |
| `rvw/tests/formal/test_generated_checks.py` | 40 |
| `rvw/tests/formal/test_generated_sby.py` | 112 |
| `rvw/tests/formal/test_hardfloat_wrappers.py` | 46 |
| `rvw/tests/formal/test_hier_state_native.py` | 88 |
| `rvw/tests/formal/test_ic3_lemmas.py` | 35 |
| `rvw/tests/formal/test_ic3_lemmas_native.py` | 33 |
| `rvw/tests/formal/test_initial_split.py` | 35 |
| `rvw/tests/formal/test_integration_options.py` | 9 |
| `rvw/tests/formal/test_internal_exposure.py` | 17 |
| `rvw/tests/formal/test_invariant_native.py` | 93 |
| `rvw/tests/formal/test_lazy_ram.py` | 72 |
| `rvw/tests/formal/test_lemma_cone.py` | 58 |
| `rvw/tests/formal/test_live_cancel.py` | 45 |
| `rvw/tests/formal/test_live_cancel_native.py` | 81 |
| `rvw/tests/formal/test_live_sampled.py` | 36 |
| `rvw/tests/formal/test_live_sampled_native.py` | 51 |
| `rvw/tests/formal/test_live_sim.py` | 47 |
| `rvw/tests/formal/test_live_sim_native.py` | 149 |
| `rvw/tests/formal/test_liveness_app.py` | 47 |
| `rvw/tests/formal/test_liveness_frontend.py` | 99 |
| `rvw/tests/formal/test_liveness_safety_frontend.py` | 92 |
| `rvw/tests/formal/test_local_assignment.py` | 34 |
| `rvw/tests/formal/test_local_capture.py` | 112 |
| `rvw/tests/formal/test_local_flow_sim.py` | 34 |
| `rvw/tests/formal/test_memory_model.py` | 47 |
| `rvw/tests/formal/test_memory_refinement.py` | 52 |
| `rvw/tests/formal/test_micro_checks.py` | 77 |
| `rvw/tests/formal/test_mixed_datapath.py` | 79 |
| `rvw/tests/formal/test_named_temporal_native.py` | 57 |
| `rvw/tests/formal/test_native_bus_binding.py` | 41 |
| `rvw/tests/formal/test_native_engines.py` | 51 |
| `rvw/tests/formal/test_nax_units.py` | 25 |
| `rvw/tests/formal/test_nested_eventually.py` | 49 |
| `rvw/tests/formal/test_nested_eventually_native.py` | 73 |
| `rvw/tests/formal/test_power_checks.py` | 93 |
| `rvw/tests/formal/test_progress.py` | 27 |
| `rvw/tests/formal/test_proof_cache.py` | 69 |
| `rvw/tests/formal/test_proof_conditions.py` | 20 |
| `rvw/tests/formal/test_proof_engines.py` | 116 |
| `rvw/tests/formal/test_property_library.py` | 82 |
| `rvw/tests/formal/test_property_names.py` | 59 |
| `rvw/tests/formal/test_psl.py` | 58 |
| `rvw/tests/formal/test_raw_event_native.py` | 100 |
| `rvw/tests/formal/test_raw_event_semantics.py` | 64 |
| `rvw/tests/formal/test_real_div_extract.py` | 27 |
| `rvw/tests/formal/test_real_fifo_configs.py` | 55 |
| `rvw/tests/formal/test_real_mul_configs.py` | 56 |
| `rvw/tests/formal/test_real_mul_extract.py` | 46 |
| `rvw/tests/formal/test_real_revision_examples.py` | 70 |
| `rvw/tests/formal/test_recheck.py` | 42 |
| `rvw/tests/formal/test_register_match.py` | 42 |
| `rvw/tests/formal/test_regression.py` | 109 |
| `rvw/tests/formal/test_repetition_ranges.py` | 26 |
| `rvw/tests/formal/test_repetition_ranges_native.py` | 102 |
| `rvw/tests/formal/test_replay_safety.py` | 134 |
| `rvw/tests/formal/test_replay_vcd.py` | 140 |
| `rvw/tests/formal/test_reset_assert_events.py` | 49 |
| `rvw/tests/formal/test_reset_audit.py` | 72 |
| `rvw/tests/formal/test_resource_bindings.py` | 27 |
| `rvw/tests/formal/test_resource_checks.py` | 47 |
| `rvw/tests/formal/test_review_cross_clock_pending.py` | 34 |
| `rvw/tests/formal/test_review_liveness_ranges.py` | 16 |
| `rvw/tests/formal/test_review_mcp_datapath_kit.py` | 49 |
| `rvw/tests/formal/test_review_mcp_flags.py` | 16 |
| `rvw/tests/formal/test_review_mcp_outcomes.py` | 34 |
| `rvw/tests/formal/test_review_sail_concat.py` | 15 |
| `rvw/tests/formal/test_review_unreset_definedness.py` | 34 |
| `rvw/tests/formal/test_revision_bench.py` | 31 |
| `rvw/tests/formal/test_ric3_compat.py` | 20 |
| `rvw/tests/formal/test_role_bindings.py` | 44 |
| `rvw/tests/formal/test_rtl_grid.py` | 23 |
| `rvw/tests/formal/test_rtl_refine.py` | 47 |
| `rvw/tests/formal/test_rtlil_names.py` | 23 |
| `rvw/tests/formal/test_sampled_history.py` | 50 |
| `rvw/tests/formal/test_sby_campaign.py` | 69 |
| `rvw/tests/formal/test_scalar_cipher_models.py` | 181 |
| `rvw/tests/formal/test_scenario.py` | 98 |
| `rvw/tests/formal/test_schedule.py` | 54 |
| `rvw/tests/formal/test_secure_path.py` | 79 |
| `rvw/tests/formal/test_security_observed_isolation.py` | 46 |
| `rvw/tests/formal/test_security_pair.py` | 87 |
| `rvw/tests/formal/test_security_pair_bounds.py` | 33 |
| `rvw/tests/formal/test_security_seeded_fixtures.py` | 25 |
| `rvw/tests/formal/test_security_state_sources.py` | 84 |
| `rvw/tests/formal/test_security_unsupported_reset.py` | 25 |
| `rvw/tests/formal/test_shortest.py` | 75 |
| `rvw/tests/formal/test_simple_bus_checks.py` | 83 |
| `rvw/tests/formal/test_slang_capability.py` | 30 |
| `rvw/tests/formal/test_smt_uf.py` | 78 |
| `rvw/tests/formal/test_softfloat_compare_models.py` | 66 |
| `rvw/tests/formal/test_solver_cores.py` | 54 |
| `rvw/tests/formal/test_spinal_sva_api.py` | 52 |
| `rvw/tests/formal/test_spinal_sva_unbounded_api.py` | 96 |
| `rvw/tests/formal/test_state_encoding.py` | 50 |
| `rvw/tests/formal/test_state_event_native.py` | 121 |
| `rvw/tests/formal/test_state_overlay.py` | 130 |
| `rvw/tests/formal/test_state_selection.py` | 29 |
| `rvw/tests/formal/test_strategy.py` | 43 |
| `rvw/tests/formal/test_sva.py` | 152 |
| `rvw/tests/formal/test_sva_ast.py` | 38 |
| `rvw/tests/formal/test_sva_ast_native.py` | 88 |
| `rvw/tests/formal/test_sva_defaults_native.py` | 29 |
| `rvw/tests/formal/test_swarm.py` | 154 |
| `rvw/tests/formal/test_temporal.py` | 189 |
| `rvw/tests/formal/test_temporal_bindings.py` | 100 |
| `rvw/tests/formal/test_temporal_composition.py` | 150 |
| `rvw/tests/formal/test_temporal_events.py` | 50 |
| `rvw/tests/formal/test_testplan.py` | 78 |
| `rvw/tests/formal/test_tilelink_transactions.py` | 140 |
| `rvw/tests/formal/test_timeout_rerun_native.py` | 25 |
| `rvw/tests/formal/test_trace_candidates.py` | 49 |
| `rvw/tests/formal/test_typed_bus_checks.py` | 60 |
| `rvw/tests/formal/test_uf_prove_native.py` | 23 |
| `rvw/tests/formal/test_unbounded_native.py` | 89 |
| `rvw/tests/formal/test_unbounded_parentheses.py` | 13 |
| `rvw/tests/formal/test_unbounded_semantics.py` | 102 |
| `rvw/tests/formal/test_unbounded_throughout.py` | 31 |
| `rvw/tests/formal/test_unbounded_throughout_native.py` | 47 |
| `rvw/tests/formal/test_upf_retention.py` | 99 |
| `rvw/tests/formal/test_upf_subset.py` | 65 |
| `rvw/tests/formal/test_upf_switches.py` | 64 |
| `rvw/tests/formal/test_vex_generated_checks.py` | 93 |
| `rvw/tests/formal/test_vex_x_candidates.py` | 18 |
| `rvw/tests/formal/test_vexii_div_unit.py` | 63 |
| `rvw/tests/formal/test_vexii_generated_checks.py` | 53 |
| `rvw/tests/formal/test_vexii_mul_unit.py` | 64 |
| `rvw/tests/formal/test_xcampaign.py` | 159 |
| `rvw/tests/formal/test_xcontext.py` | 62 |
| `rvw/tests/test_formal_input_identity.py` | 35 |
| `rvw/tests/test_formal_isa.py` | 66 |
| `rvw/tests/test_formal_isa_conditions.py` | 70 |
| `rvw/tests/test_formal_mcp_smoke_errors.py` | 44 |
| `rvw/tests/test_formal_runtime.py` | 120 |
| `rvw/tests/test_formal_timeout_rerun.py` | 99 |
| `rvw/tests/test_sail_m.py` | 68 |
| `rvw/tests/test_sail_zicond.py` | 124 |
