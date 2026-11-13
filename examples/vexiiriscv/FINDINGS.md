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

Resolved checker-contract finding. The earlier PC payload and divider
valid-hold events lacked cancellation bindings. The cancellation-aware
51-program rerun has 51 passes and zero firings. This does not establish a
core defect. New backpressure runs retain other stream findings.

Reproduction and current counts: [generated checks](../../SpinalChecks/README.md).
Sources: [#1136](https://github.com/riscPrint/risc-v-workstation/pull/1136)
and [#1171](https://github.com/riscPrint/risc-v-workstation/pull/1171).

## Other tools

The collected security and debug records do not establish another
VexiiRiscv core defect. The optional divider finding is listed below. Export limits, bounded passes and missing bindings
remain evidence limits. Reset stimulus was a harness gap in #1128, not a
core finding. Device and C2 capture bugs fixed in #1147 are tool defects.

## VEXII-CSR-BOOT-001

Alias: VEXII-ACT4-SM-CSR-001. Both IDs refer to the same bootstrap finding.

Confirmed profile compatibility finding, not a confirmed hardware defect.
The selected RV32 and RV64 supervisor scaffolds write `mhpmevent3` (CSR `0x323`).
The profile omits the counter plugin that supplies this event selector.
The core traps on `csrw mhpmevent3, zero`; Spike accepts it. The RV32 campaign has 270 ACT4
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

## VEXII-DIVZERO-IPC-001

Confirmed core defect on the optional bitpasta IPC configuration.
DIV and DIVU return `0x808080ab` for division by zero. The M extension
requires an all-one quotient. The default and area configurations pass the
four measured division/remainder programs. No upstream patch was applied.

[Minimal assembly, runner and native receipts](findings/bitpasta-div-zero/README.md).
Source: [#1170](https://github.com/riscPrint/risc-v-workstation/pull/1170).

## RV64 follow-up to VEXII-CSR-BOOT-001

The RV64 standard-boot ACT4 campaign has 302 built and 302 run programs.
All 302 fail before their test bodies. Each first trap has cause 2 and
`mtval=0x32301073`. The encoding matches the ELF instruction at the fault PC.
This is the same selected-profile counter-plugin gap as the RV32 finding.
It is one compatibility cause across 302 cases. No failure is waived.

[The minimal event-CSR write](rvw/act4-64su/missing-event-csr.S) fails on RTL.
Spike accepts that write. [The menvcfg control](rvw/act4-64su/envcfg-control.S)
passes and matches Spike. The last retired instruction before the bootstrap
trap writes menvcfg. It is not the faulting instruction. The captured mtval
and ELF bytes identify the fault. See [all case identities](rvw/act4-64su/results.json)
and [the directed results](rvw/act4-64su/minimal-results.json).

## RV64 divider timing witness

The default RV64IMA divider has an operand-dependent timing witness.
The fixed-length setup gives `x6=7, x7=3` on one side and
`x6=9223372036854775807, x7=1` on the other. Both execute DIV then DIVU.
Both raw traces match Spike strictly, with zero masks and synchronization.
The declared case-window observations are 42 and 138 cycles. The security
contract reports a violation in `cycles` and `retire_cycles`.

This is not an ISA defect or a claim that the upstream divider promises
constant time. It is separate from VEXII-DIVZERO-IPC-001, which affects a
non-default RV32 bitpasta configuration. The [RV64 manifest](rvw/sec/constant-time64.json)
and [tool evidence](rvw/rv64/tool-results.json) retain the program and scope.

## RV64 tool assumptions removed

The [tool report](rvw/rv64/TOOLS.md) lists the formal observer's RV32 data,
mask and IXL constants, missing W-opcode operand mapping, the CSR runtime's
32-bit restriction, forced security ILP32 and truncated secret setup.
Each fix has targeted tests. RV32 defaults remain unchanged. The mapped RTL
security harness remains RV32-only; the generic C1 path runs the RV64 pair.
No incomplete formal result is promoted to a proof.
