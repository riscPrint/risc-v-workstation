# Full suite run, 2026-11-13

The run is not green. The known remaining failures are listed below. No BOOM build or BOOM simulation was run.

## Scope and evidence

The first collection used main at `c29ad597`. Repairs and later collections used main at `f104f10a` plus the changes from this task. Other workers continued to merge changes during the run. These results span those revisions. They do not qualify a later main revision as a whole.

The suite ran in the private `uvm` worktree. Heavy jobs used nice level 10. Python used at most four workers across this task. Each batch had a 900-second cap. The initial per-test limit was 120 seconds. Later native batches used 600 seconds, or 840 seconds for the native build check. sbt used the private `sbt-uvm` lock. `SPINAL_BOOM` selected an empty directory.

The raw command records, JUnit files and logs are under `$RUN_ROOT`. The worktree-parent `FULLSUITE_LOG.md` records each batch. Counts below use the latest completed execution for each test ID at the `f104f10a` cutoff. A later unconfigured skip does not replace an earlier configured execution. Reruns do not add to the count. Deselected fast tests are not skips.

## First Python inventory

| Directory | Selected tests | Files |
|---|---:|---:|
| `rvw/tests` | 5169 | 360 |
| `rvw/tests/cosim` | 711 | 51 |
| `rvw/tests/cov` | 651 | 39 |
| `rvw/tests/devices` | 22 | 5 |
| `rvw/tests/formal` | 1625 | 146 |
| `rvw/tests/interrupts` | 4 | 2 |
| `rvw/tests/ordering` | 141 | 8 |
| Total | 8323 | 611 |

The first collection selected 8,323 of 10,379 tests. It deselected 2,056 fast tests. The later collection selected 8,028 slow tests from 10,551 tests. Added tests, changed parameter sets and fast promotions explain the difference. The file and test-ID audit found 33 IDs absent from completed results. The delta batch ran all 33. A union-schema probe failed in that batch and then passed after its repair.

## Slow Python results at the cutoff

| Directory | Pass | Fail | Skip | Timeout | Not run |
|---|---:|---:|---:|---:|---:|
| `rvw/tests` | 4722 | 1 | 135 | 0 | 0 |
| `rvw/tests/ci_native` | 4 | 0 | 0 | 0 | 0 |
| `rvw/tests/cosim` | 703 | 0 | 4 | 0 | 0 |
| `rvw/tests/cov` | 652 | 0 | 0 | 0 | 0 |
| `rvw/tests/devices` | 19 | 1 | 2 | 0 | 0 |
| `rvw/tests/formal` | 1570 | 45 | 25 | 0 | 0 |
| `rvw/tests/interrupts` | 2 | 0 | 2 | 0 | 0 |
| `rvw/tests/ordering` | 141 | 0 | 0 | 0 | 0 |
| Total | 7813 | 47 | 168 | 0 | 0 |

All 8,028 selected IDs have a completed result. The 47 failures are 45 cases against the installed slang plugin, one Spike PLIC oracle case and one UVM conformance case. The remaining skip reasons are listed below. Expected timeout and fault controls that pass their assertions are counted as passing tests.

## Fast order and timing

| Random seed | Pass | Skip | Wall seconds |
|---|---:|---:|---:|
| 111 | 2055 | 1 | 459.16 |
| 222 | 2080 | 1 | 503.46 |
| 333 | 2522 | 1 | 103.77 |
| 444 | 2522 | 1 | 88.30 |
| 555 | 2522 | 1 | 77.17 |
| 778, delivery main | 2821 | 1 | 94.19 |

The selections grew as main changed and modules gained fast markers. Seeds 333 and 444 used the same final cutoff selection. They each passed 2,522 tests with one expected command-reference skip. No order-dependent failure appeared in these runs.

The final delivery check used main `31a95be8`. Its first attempt had 2,814 passes and one collection error because the environment lacked the newly declared PyYAML dependency. After `uv pip install -e ".[dev,mcp]"`, seed 778 passed all 2,821 selected tests with one expected skip. The staged report also passed all 40 release-hygiene tests.

The task promoted 269 pure unit tests in 36 modules. Each observed call took less than one second. The largest promoted call in the serial validation was 0.46 seconds. The modules use `pytestmark = pytest.mark.fast`; no shared `FAST_MODULES` registry was edited. The doctor promotion added 25 more tests. The JSON argument-probe check added one more fast test.

Promoted modules:

- `test_arch_traffic.py`
- `test_arch_warmup.py`
- `test_ci_summary.py`
- `test_connectivity_tables.py`
- `test_csr_catalog.py`
- `test_device_events.py`
- `test_evidence_index.py`
- `test_farm_notifications.py`
- `test_farm_project_resources.py`
- `test_farm_selection.py`
- `test_farm_triage.py`
- `test_lint_depth.py`
- `test_lint_rdc.py`
- `test_lint_rules.py`
- `test_lint_sdc.py`
- `test_memory_axiomatic_pins.py`
- `test_memory_contract.py`
- `test_mmu_cov.py`
- `test_mmu_iommu.py`
- `test_mmu_memory_effects.py`
- `test_perf_events.py`
- `test_privilege_aia.py`
- `test_privilege_aplic_gateway.py`
- `test_privilege_controllers.py`
- `test_privilege_disabled_matrix.py`
- `test_privilege_dvfs.py`
- `test_privilege_epmp.py`
- `test_privilege_epmp_matrix.py`
- `test_privilege_events.py`
- `test_privilege_extensions.py`
- `test_privilege_plic.py`
- `test_privilege_pma.py`
- `test_privilege_pmp.py`
- `test_privilege_reri.py`
- `test_privilege_scheduled.py`
- `test_privilege_timer32.py`

## Scala suites

| Project | Pass | Fail | Cancel or skip | Result |
|---|---:|---:|---:|---|
| `SpinalWaves/spinalwaves` | 18 | 0 | 0 | full test suite |
| `SpinalTrace/spinaltrace` | 26 | 0 | 0 | full test suite |
| `SpinalDB/spinaldb` | 86 | 0 | 0 | full test suite |
| `SpinalChecks` | 145 | 0 | 0 | full test suite |
| `SpinalKonata` | 6 | 0 | 0 | full test suite |
| `SpinalKonata/inputs` | 7 | 0 | 0 | full test suite |
| `SpinalProbes` | 5 | 0 | 0 | full test suite |
| `SpinalBlocks/spinalblocks` | 6 | 0 | 0 | full test suite |
| `RiscvSim generic` | 180 | 0 | 0 | full test suite |
| `SpinalSoc` | 0 | 0 | 0 | compiled; no test cases |
| `SpinalSoc/db` | 0 | 0 | 0 | compiled; no test cases |
| Total executed tests | 479 | 0 | 0 | |

The generic RiscvSim run included the pinned official litmus plan. The observed fixture matched the herd reference. Its injected-fault comparison returned 1 as required. This fixture is not a core or memory-system qualification. SpinalWaves and SpinalTrace used the built Rust checker and CLI. SpinalDB used that checker too.

## Rust, JavaScript and example suites

| Suite | Pass | Fail | Skip | Scope |
|---|---:|---:|---:|---|
| SpinalTrace Rust workspace | 29 | 0 | 0 | backend, CLI and GUI library; doc tests also complete |
| Typed-wave Rust checker | 8 | 0 | 0 | checker integration tests |
| VS Code unit tests | 36 | 0 | 0 | typecheck and build also pass |
| SpinalBlocks engine | 16 | 0 | 0 | typecheck and build also pass |
| NaxRiscv example Python | 4 | 0 | 0 | project tests |
| VexRiscv example Python | 3 | 0 | 39 | private core or captured RTL inputs absent |
| VexRiscv formal example Python | 3 | 0 | 0 | generic environment tests |
| VexiiRiscv example Python | 5 | 0 | 6 | private core inputs absent |
| SMP example Python | 6 | 0 | 1 | private native timing input absent |
| ComponentSims | 99 | 0 | 0 | component and reference tests |
| SpinalChecks coherence | 5 | 0 | 0 | plus four passing subtests |

The VS Code debug browser script and extension integration script passed. The extension test used a prebuilt BOOM diagram, not a BOOM build. A rebuilt rerun verified screenshot output under the ignored test directory. No tracked screenshot changed. SpinalTrace GUI check/build and the SpinalBlocks web-host build passed; those packages declare no separate JavaScript test suite.

The example inventory also found PicoRV32 and the Vex cocotb/scenario folders. They require an external core or captured core RTL, so their native core flows were not run. PicoRV32 has no separate owned pytest folder in this checkout.

Generic UVM native controls passed: one custom-bus positive/negative control test, four semantic-contract control tests, two connected SoC seeds and two composed SoC scenario seeds. The composed RTL was regenerated after its build dependency repair. The earlier pass against old RTL is excluded from this evidence. The native RAL sequence case passed. These Python tests are already included in the slow Python count where applicable. The composed scenario script is separate. Neither SoC fixture executes a CPU.

## Repairs

- Update restricted MCP benchmark fixtures for the job and metadata tools. Keep the restricted-catalog check.
- Update doctor result doubles for mapping access. Mark the pure doctor module as fast.
- Run native Python sbt fixtures under the private worktree lock.
- Update the command JSON probe for required subcommands, typed arguments and missing-input errors. Send the datapath input error to stderr.
- Update stale CLI/MCP equality checks for the C7 envelope. Keep payload, verdict and error checks.
- Compare stable CLI/MCP cosimulation data. Check that every shared captured source has the same byte hash. Each entry point can load a different module set.
- Keep portable ordering cases on the base ISA profile. Run the Zacas and cache-block cases with their required profiles in their own suites.
- Test the explicit refusal of multi-hart replay without the serialized-retirement profile.
- Isolate fake JVM and make settings from ambient options. Make each environment-mutation test start without the variable it changes.
- Copy the current Spinal axis helper and generic dependencies into the native cache fixture. Keep an exact allowlist of generic project references. Reject core references.
- Give RiscvSim Scala tests a private runtime cache under their own target directory.
- Add the shared SpinalChecks dependency required by the composed UVM SoC protocol monitors. Regenerate RTL before rerunning its scenario tests.
- Check process exit with the existing zombie-aware helper.
- Put eager configuration construction inside the expected-error context.
- Compare the regression watchdog's idle interval. Keep the exact pass/timeout counts. Exclude source capture, startup and serial retry from this interval.
- Give the native connectivity proof 60 seconds instead of 10 seconds. Keep its transfer, activation and semantic checks.
- Generate the temporal support-table expectation from all existing feature lists.
- Keep a newline after emitted Scala SVA source comments when the native test adds `endmodule`.
- Select temporary core paths in the fake example-project tests. Require explicit private core selection before native example tests can build a core.
- Keep the SoC example platform metadata in step with its canonical platform file.
- Let the RV32 native check select its external ISA sources with `RISCV_TESTS_SOURCE`.
- Make the MCP invalid-type probe handle union types.
- Write VS Code integration screenshots to ignored `.vscode-test/screenshots/spinalblocks/`.

No real check was removed. No failure was changed to an expected pass. The failed UVM workaround was reverted.

## Remaining failures and reproductions

### Accellera UVM conformance

`rvw/tests/test_uvm_native.py::test_accellera_subset_and_rvfi_fault` fails with `random data did not change` at time 825. The native wrapper returns 2. Its internal result has 24 error rows and six pass rows across seeds 1, 2 and 3.

The archive is the pinned Accellera UVM source at revision `78c06547a2a0a29b3dc9dcafae62b75b2ff61544`. Its SHA-256 is `9ee918499a92518f8f7c202c5f8a38b8a0c83d4eba3bedd7890bfa3ed023d1e4`. The simulator is Verilator 5.049 devel, `v5.048-26-g25d4827bd` with local modifications. The original SystemVerilog sets a data-change flag. The generated C++ appears to omit that update. A trial with an explicitly reset class member failed too. That trial was reverted. The cause remains unresolved. The check remains enabled.

Reproduce with the pinned archive and the installed native simulator:

```sh
RVW_UVM_ARCHIVE="$ARCHIVE" RVW_UVM_VERILATOR=verilator \
  nice -n 10 rvw/.venv/bin/python -m pytest \
  rvw/tests/test_uvm_native.py::test_accellera_subset_and_rvfi_fault \
  -p no:cacheprovider -q -ra --timeout=840
```

The separate native RAL sequence test passed. That pass does not clear the conformance failure.

### Installed slang plugin

Forty-four paired semantic cases and one direct frontend-boundary case fail with the OSS CAD Suite plugin. It loads, but reports `SVA unsupported`. It is not the patched source-built plugin required by these cases. The task did not build a replacement plugin. These are failed configured attempts, not proof passes.

A minimal source is:

```systemverilog
module top(input clk, a);
  assert property (@(posedge clk) a);
endmodule
```

Run `yosys -m "$SLANG_PLUGIN" -p 'read_slang --top top sva.sv'`. The installed plugin rejects this source. The generic finite temporal and Scala-emitted property suites have separate results above.

### Spike PLIC oracle

`rvw/tests/devices/test_plic.py::test_spike_claim_ignores_threshold` fails against the installed Spike 1.1.1-dev library. With source 1 at priority 3, enabled, and threshold 3, the test expects claim 1 with no IRQ. The installed oracle returns claim 0. The ordinary PLIC oracle and timer cases pass. The PLIC model and the conformance check were not changed to hide this disagreement.

Reproduce with the installed Spike development headers and library:

```sh
RVW_DEVICE_SPIKE_PREFIX="$SPIKE_PREFIX" nice -n 10 \
  rvw/.venv/bin/python -m pytest \
  rvw/tests/devices/test_plic.py::test_spike_claim_ignores_threshold \
  -p no:cacheprovider -q -ra
```

## Skips and work not run

- BOOM builds, BOOM simulations and the BOOM Scala adapter suites were not run. BOOM runtime interrupt, WFI and launcher parity tests skipped.
- Private VexRiscv, VexiiRiscv, NaxRiscv and SMP core rebuilds were not run. Native example tests without explicit private inputs skipped. Their pure project and generator tests ran.
- CPU UVM replay, live Vex UVM and event UVM lacked the required completed C1 runs, captured RTL or ELF inputs. They were not run. Generic connected SoC and composed-SoC tests have separate results.
- Sail generated-model cases lacked the pinned source or generated models. DII and adjudication cases lacked their configured Sail inputs. No Sail compiler campaign was started.
- SoftFloat, E-Trace reference and profile-span cases lacked their pinned sources. The extracted-lint fixtures were generated and their tests ran.
- Native localhost SSH tests lacked the configured SSH connection. No SSH daemon or account settings were changed.
- rIC3, the optional cover-search tools, EBMC, Verible, the pinned CIRCT install, LLVM scheduling headers and tblgen, SystemC development libraries and the rebuilt GHDL memory plugin were absent from the required configured tool sets.
- The patched source-built slang plugin was not built. The installed plugin was tested and failed as stated above.
- The command-reference check stayed skipped under the parallel-push rule. This task did not edit that hot file.

A skip means that case supplied no runtime evidence. It does not qualify the missing tool, fixture or core.

## Execution corrections

The first root Python batch 8 was interrupted while a complete Scala job held the private sbt lock. Its replacement batches completed. The interrupted attempt is not counted as a measured 900-second timeout.

The first generic RiscvSim attempt reached the default shared runtime cache. It was stopped. The merged test setting now sends runtime output to this worktree's target directory. The replacement suite ran there. No shared cache files were removed.

The native Spike shim was rebuilt after rebases changed its captured source hash. The strict stimulus tests used a separate environment with `z3-solver==4.13.4.0`. They passed there. The primary environment's solver was not downgraded.

Disk space was low during the run. Completed scratch trees were removed after their logs, JUnit results and timings were retained. The native UVM failure files and other unresolved failure evidence were kept.

## Slow tests and directory cost

The table lists the 30 largest latest recorded pytest case durations, including setup and teardown. A later unconfigured skip does not replace an actual run. The latest Scala JUnit records were also checked. Their longest case was 13.46 seconds, so none enters this table. These timings came from a shared machine under changing load. They are observations, not a performance benchmark.

| Seconds | Result | Test ID |
|---:|---|---|
| 255.94 | fail | `rvw/tests/test_uvm_native.py::test_accellera_subset_and_rvfi_fault` |
| 120.68 | pass | `rvw/tests/cov/test_capture_mutation.py::test_real_mcy_legacy_unknown_dependencies` |
| 112.23 | pass | `rvw/tests/cov/test_capture_mutation.py::test_real_mcy_baseline_sed_expression` |
| 111.53 | pass | `rvw/tests/cov/test_capture_mutation.py::test_real_mcy_declared_external_header[False]` |
| 111.25 | pass | `rvw/tests/test_debug_dm_native.py::test_spike_debug_profile` |
| 109.64 | pass | `rvw/tests/test_query_capture.py::test_inline_fingerprint_is_the_emitted_text[True-False]` |
| 107.75 | pass | `rvw/tests/cov/test_capture_mutation.py::test_real_mcy_declared_external_header[None]` |
| 103.90 | pass | `rvw/tests/test_query_capture.py::test_scala_hdl_scan_binds_yosys_reads[root-True-False]` |
| 103.82 | pass | `rvw/tests/cov/test_capture_mutation.py::test_real_mcy_output_template_options_and_redirection` |
| 93.67 | pass | `rvw/tests/test_uvm_ral_sequences_native.py::test_generated_ral_builtin_sequences` |
| 77.43 | pass | `rvw/tests/test_riscvsim_scripts.py::test_real_native_flags_invalidate_cache_and_enter_c1_and_replay` |
| 71.93 | pass | `rvw/tests/cov/test_capture_mutation.py::test_real_mcy_declared_external_header[True]` |
| 71.06 | pass | `rvw/tests/test_privilege_rv32_interrupts_native.py::test_rv32_mu_pmp_matrix_passes_on_spike` |
| 70.11 | pass | `rvw/tests/formal/test_bit_crypto_models.py::test_symbolic_xperm_unit[64-8-True]` |
| 61.42 | pass | `rvw/tests/formal/test_bit_crypto_models.py::test_symbolic_xperm_unit[32-4-True]` |
| 60.40 | pass | `rvw/tests/test_debug_tools.py::test_reduce_symbol_is_exact_only_when_proven` |
| 57.96 | pass | `rvw/tests/cov/test_proof.py::test_hold_by_assumption_refuses_and_released_control_still_excludes` |
| 56.85 | pass | `rvw/tests/test_wave_array_names.py::test_simulator_array_queries_and_cuts[verilator-fst]` |
| 55.01 | pass | `rvw/tests/test_debug_tools.py::test_bisect_a_reduced_run` |
| 50.77 | pass | `rvw/tests/test_debug_tools.py::test_bisect_remove_clone_only_deletes_its_own` |
| 50.34 | pass | `rvw/tests/test_sec_isolation_native.py::test_private_state_boundary[True]` |
| 49.90 | pass | `rvw/tests/test_sec.py::test_native_pair_runner[True]` |
| 49.10 | pass | `rvw/tests/test_regress.py::test_gate` |
| 47.79 | pass | `rvw/tests/test_sec_isolation_native.py::test_private_state_boundary[False]` |
| 47.65 | pass | `rvw/tests/test_debug_tools.py::test_bisect_skips_wall_clock_timeouts_whatever_other_says` |
| 46.78 | pass | `rvw/tests/test_debug_tools.py::test_bisect_refuses_a_linked_or_foreign_workdir` |
| 46.52 | pass | `rvw/tests/test_regress.py::test_fingerprint_covers_dirty_submodule_contents` |
| 43.61 | pass | `rvw/tests/test_sec.py::test_native_pair_runner[False]` |
| 43.51 | pass | `rvw/tests/test_sec_fault_native.py::test_critical_register_upset[False]` |
| 40.96 | pass | `rvw/tests/cov/test_proof.py::test_cone_bits_held_by_assumption_or_tie_refuse` |

The initial directory batches used about 3,247 seconds for the root Python folder, 1,596 seconds for formal, 607 seconds for coverage and 215 seconds for cosim. Devices, ordering and interrupt folders each took less than three seconds in their initial batches. These are summed batch wall times, not CPU time. The root total substitutes the three completed reruns for interrupted batch 8 and excludes its interrupted duration. Later repairs and opt-in runs are separate.

Coverage is costly for its test count. Its MCY capture tests build and snapshot native inputs repeatedly. The formal directory is also costly because many cases run real solver jobs. Native capture, debug reduction and UVM compilation dominate the root folder. SpinalChecks took 498 seconds for 145 Scala tests on its final run. The first complete isolated generic RiscvSim run took 499 seconds; the final warm run took 107 seconds. These native tests remain outside the fast set.

## Merged changes

- [PR #1051](https://github.com/riscPrint/risc-v-workstation/pull/1051), head `146b081923cc1e594bd20d49fba240d8d56fb24c`, merged.
- [PR #1071](https://github.com/riscPrint/risc-v-workstation/pull/1071), head `9bd018a98f1346f2a4a3820613f617eb3cf72202`, merged.
- [PR #1160](https://github.com/riscPrint/risc-v-workstation/pull/1160), head `25119d997559fe132d75ac715d1c0dbfcfde5ee8`, merged.

The delivery rebase used later main code. Only the fast set and hygiene checks are rerun for the final report delivery. The complete native suites were not rerun after that rebase. No issue was closed by this task.
