# Owner summary: 2026-11-13

Source cutoff: 846 merged PR bodies, 16:12:30 UTC. Results below are reported, not rerun. No whole-core qualification or commercial parity is claimed.

Start with [INTEGRATION_GUIDE.md](../../INTEGRATION_GUIDE.md). Read [CLEAN_ROOM_2026-11-13.md](../../CLEAN_ROOM_2026-11-13.md) for the new-core trial and informed second pass. The three [Spinal](../../DRY_RUN_2026-11-13.md), [Verilog](../../DRY_RUN_VERILOG_2026-11-13.md) and [Chisel/VHDL](../../DRY_RUN_CHISEL_VHDL_2026-11-13.md) dry runs show setup gaps. Use [ISSUES.md](ISSUES.md), [NEW_TOOLS.md](NEW_TOOLS.md), [FINDINGS.md](FINDINGS.md) and [RISKS.md](RISKS.md) for source links and limits.

| Area | What exists | Evidence level and next boundary |
|---|---|---|
| Architecture | Component models, probes, timing fit and paired capacity studies. | ran on real core RTL: VexRiscv, VexiiRiscv, NaxRiscv, BOOM small and OoO Mini. Structure prediction remains unqualified. |
| Core integration | Spinal, Verilog, Chisel and VHDL paths. Stepper passes and strictly matches 50 ISA programs. OoO Mini also matches 50. | ran on real core RTL: Stepper, PicoRV32, riscv-mini, NEORV32 and OoO Mini. Privileged boot and full interface acceptance remain open. |
| Simulation | Persistent servers, DPI, replay, device plugins, cacheless/cached SMP and finite checkpoint paths. | ran on real core RTL: VexRiscv, VexiiRiscv and BOOM small. Linux, portable live restore and general coherence remain open. |
| Verification | Strict Spike/Sail comparisons, ACT4, generated MMU/privilege/PMP suites and coverage reports. | ran on real core RTL: VexRiscv, VexiiRiscv, NaxRiscv and PicoRV32. Failed cases remain failures; no ISA certification. |
| Formal/checks | Generated monitors, bounded core checks, arithmetic certificates and small memory refinement. | ran on real core RTL: VexRiscv, VexiiRiscv, Nax helpers, PicoRV32 and OoO Mini. Whole-core ISA proofs and activation closure remain open. |
| SoC/UVM/VIP | Composer CPU/DMA, SMP host, imported UART, debug ports and live pyuvm/Spike benches. | ran on real core RTL: VexRiscv, VexiiRiscv and Stepper; other protocol work ran on seeded RTL fixture. CDC and complete protocol qualification remain open. |
| Debug/security/fault | DMI/JTAG, finite paired/flow checks, trace ingress and register injections. | ran on real core RTL: VexRiscv, VexiiRiscv, NaxRiscv and BOOM small in separate slices. No physical leakage, reliability or debug compliance claim. |
| Platform/IDE/farm | CLI/MCP, database imports, editor views, local queue, committed gates and report indexes. | Farm ran on real core RTL: VexRiscv. Much interface work has unit tests only. Cluster execution, independent newcomer repeat and accepted LLM repairs remain open. |
| Emulation | No new FPGA implementation evidence in this census. | no code for issue #23. Hardware acceptance remains open. |

The six main findings are: Vexii PMP-denied page walks; Vex interrupt mtval; Vex MRET/MPP and MEPC readback; optional Vexii IPC divide-by-zero; five unresolved Vex debug deviations; and the shared ACT4 bootstrap CSR blocker. These are third-party upstream cores. Nothing was filed upstream. [FINDINGS.md](FINDINGS.md) separates confirmed defects, compatibility findings and tool limits.

The six main negative results are:

1. Timing prediction meets the criterion for only 2 of 15 nonzero changes at #1218. At #1231 the result is 5 of 15; ten deltas still fail. Structure decisions still need RTL.
2. Eight-test impact selection misses the planted fault. Safe fallback runs all 49.
3. Deep-proof abstractions give no qualified capacity gain on real VexRiscv models.
4. Directed closure reaches 24 bins; random reaches 26 on the sampled campaigns.
5. Unbounded ISA portfolios add no closed proofs. Bounded newcomer ISA trials time out.
6. Nearly half the original ISA checks do not activate: 38 of 82. Later work leaves six current misses and retains stress failures.

[PR #1218](https://github.com/riscPrint/risc-v-workstation/pull/1218), [#1090](https://github.com/riscPrint/risc-v-workstation/pull/1090), [#810](https://github.com/riscPrint/risc-v-workstation/pull/810), [#994](https://github.com/riscPrint/risc-v-workstation/pull/994), [#1117](https://github.com/riscPrint/risc-v-workstation/pull/1117) and [#1171](https://github.com/riscPrint/risc-v-workstation/pull/1171) report these results. [RISKS.md](RISKS.md) gives the retired gaps and the limits that still stand.
