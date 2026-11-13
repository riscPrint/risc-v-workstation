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
