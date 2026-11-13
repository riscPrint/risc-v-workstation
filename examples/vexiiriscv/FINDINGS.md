# VexiiRiscv findings

Collected from the 2026-11-13 PR bodies and
[the status audit](../../docs/status/2026-11-13/FINDINGS.md). These are recorded
results. This collection adds no new RTL run. No upstream report was filed.

## VEXII-PTW-PMP-001

Confirmed core defect. Cacheless `rv32imasu` and `rv64imasu`, core
`9f70315deb3390b283995c5b8f1bd38215ecf52b`. The walker reads page tables that
PMP denies: 8 Sv32 and 11 Sv39 programs. They remain failures.

[Minimal load program, link script, Spike command and wave window](findings/ptw-pmp/README.md).
Spike raises load access fault 5 at `0x80000078`, tval `0x40000000`.
RTL completes the load and writes `tohost=3`.
The [PMP and paging rule](https://docs.riscv.org/reference/isa/v20260120/priv/machine.html#_physical_memory_protection_and_paging)
requires S-effective PMP checks for implicit page-table reads.
Sources: [#1121](https://github.com/riscPrint/risc-v-workstation/pull/1121),
[#1111](https://github.com/riscPrint/risc-v-workstation/pull/1111).
The exact 19 reviewed trace identities are in `known-findings.json`.

## VEXII-CHECK-PC-001

Open checker-contract finding, not a confirmed core defect. In the generated
checks runtime, `PcPlugin_logic_harts_0_output` valid-hold fires twice on the
absent-CSR program. One of two C1 runs fails. The rule requires a valid offer
to remain stable while stalled. Whether a legal cancellation explains these
drops is not yet established. No ISA deviation is established.

Reproduce with the generated absent-supervisor-CSR program and checked
runtime in [the example README](README.md#generated-csr-catalog-controls).
The exact failing inventory is in [checks-qualification.json](checks-qualification.json).
Sources: [#921](https://github.com/riscPrint/risc-v-workstation/pull/921),
[#940](https://github.com/riscPrint/risc-v-workstation/pull/940).
No minimal isolated core reproduction or specification violation is confirmed.

## Other tools

The collected formal, security and debug records do not establish another
VexiiRiscv core defect. Export limits, bounded passes and missing bindings
remain evidence limits. Reset stimulus was a harness gap in #1128, not a
core finding. Device and C2 capture bugs fixed in #1147 are tool defects.

## VEXII-ACT4-SM-CSR-001

The `rv32imasu` profile traps on `csrw mhpmevent3, zero` with cause 2.
The shared catalog defines CSR `0x323` under Sm. The profile declares
Sm 1.12. The upstream counter plugin supplies unused event selectors as
zero-valued CSRs, but this profile does not enable it.
This is one declared-profile compatibility finding, affecting 270 ACT4
cases before their bodies. A stable-checkout rerun has 270 C1 failures
and 270 strict Spike first differences. No full trace matches are earned.
No bootstrap access was removed. No core source was changed.
See [the decision and trace hashes](rvw/act4-supervisor/README.md#bootstrap-decision).

## VEXII-CSR-BOOT-001

Confirmed profile compatibility finding, not a confirmed hardware defect.
The selected RV32 supervisor scaffold writes `mhpmevent3` (CSR `0x323`).
The profile omits the counter plugin that supplies this event selector.
The core traps on `csrw mhpmevent3, zero`; Spike accepts it. All 270 ACT4
programs stop in this bootstrap. No test body earns a pass. The final
campaign checks all 270 first differences against Spike, with zero masks
and synchronizations. Earlier #1148 compared only 37 representative cases.

Minimal reproduction: [missing-boot-csr.S](rvw/act4/missing-boot-csr.S), built
with `-DCSR_ADDR=0x323`. The
[project CSR contract](rvw/act4-supervisor/csr-contract.json) declares it absent.
The shared CSR catalog assigns `mhpmevent3` to Sm. The remaining question is
whether this core profile and standard bootstrap claim the same CSR contract.
No mandatory access is removed to earn a pass. Sources:
[#1148](https://github.com/riscPrint/risc-v-workstation/pull/1148),
[#1178](https://github.com/riscPrint/risc-v-workstation/pull/1178).

## Reset harness follow-up

The reset gap recorded in #1128 is resolved for the one-hart RV64 main pin.
[#1188](https://github.com/riscPrint/risc-v-workstation/pull/1188) supplies
three fresh RTL passes and strict Spike matches across nine repeated pulses.
The initial timeout was a harness sampling defect. It is not a core finding.
Separate SoC reset domains, device reset and debug reset remain untested.
