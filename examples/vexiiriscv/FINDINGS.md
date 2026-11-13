# VexiiRiscv findings

Collected from the 2026-11-13 PR bodies and
[the status audit](../../docs/status/2026-11-13/FINDINGS.md). These are recorded
results. The external debug section below records a fresh RTL run. No upstream
report was filed.

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
## VEXII-SEC-DIV-001

Confirmed leakage finding, not a functional defect. Cacheless `rv32im`, core
`9f70315deb3390b283995c5b8f1bd38215ecf52b`. The radix-2 divider (`DivRadix2`)
skips zero quotient bits, so divide and remainder latency depends on the
operands. `rvw sec contract --manifest rvw/sec/constant-time.json` reduced the
constant-time program to `remu x13, x6, x7`: 14 cycles for 7 % 3, 38 cycles for
0x7fffffff % 1, with equal architectural traces. The seed-11 campaign found the
same `remu` and `div` signatures. Do not divide secrets in constant-time code
on this configuration. Details: `rvw/src/rvw/sec/README.md`. The RV64 divider
witness above is the same mechanism on RV64IMA.

The `rv32imasu` TLB result in the same README (a secret-selected S-mode read of
a user page is visible to U-mode through page walks) is a true positive of the
channel but not a defect: RISC-V does not require a TLB flush on `sret`.

## External debug on the extra RV32 configurations

Fresh RTL runs on 2026-11-13 use VexiiRiscv `9f70315d`, SpinalHDL
`de72faf6`, two execute triggers with equality matching and chaining.
No upstream source was changed. The final 85-check DMI campaign has
35 pass, 6 fail and 44 unsupported or skipped checks. JTAG has 34 pass,
6 fail, 1 inconclusive and 44 unsupported or skipped checks.
The busy-collision check is inconclusive because a JTAG scan cannot observe
the short busy window. Every failing check passes on its fresh reference model.

| Check | Component | Minimal operation | Observed deviation |
|---|---|---|---|
| `dm.dmactive_reset` | SpinalHDL Debug Module | Seed nonzero DATA0 through a completed GPR read; clear and set dmactive | DATA0 keeps its value instead of reset 0 |
| `dm.data_readback` | SpinalHDL Debug Module | Write DATA0=0x13579bdf; read DATA0 without an abstract command | Reads 0 instead of the written value |
| `abs.transfer_none` | SpinalHDL Debug Module | Access Register with transfer=0 and invalid aarsize | cmderr=2; aarsize must be ignored without transfer |
| `dbg.debug_csr_hidden` | VexiiRiscv privileged unit | Clear mcause; execute M-mode csrr dpc, then ebreak | Stops at the following ebreak, mcause=0; DPC access must trap as illegal |
| `trig.warl_action` | VexiiRiscv trigger unit | Write mcontrol action=1 with dmode=0; read back | action=1 retained although it requires dmode=1 |
| `trig.dmode_protect` | VexiiRiscv trigger unit | Set dmode=1; execute an M-mode write to tdata1 | M-mode changes the debug-only trigger |

Minimal isolated session against a running JTAG simulation:

```sh
rvw debug suite --profile rvw/debug/profile-jtag.toml --port "$port" \
  --check dm.dmactive_reset --check dm.data_readback --check abs.transfer_none \
  --check dbg.debug_csr_hidden --check trig.warl_action --check trig.dmode_protect \
  --out "$RUN_ROOT/minimal-debug"
```

The DATA0 rules are its R/W access and reset value 0 in
[Debug 0.13.2 register definitions](https://github.com/riscv/riscv-debug-spec/blob/4e0bb0fc2d843473db2356623792c6b7603b94d4/xml/dm_registers.xml#L465).
The other rules are the Access Register aarsize rule, Debug Mode-only CSR
access, and mcontrol action/dmode restrictions in the same specification.

The initial 84-check DMI snapshot was superseded. Its reset check did not
establish a nonzero read value, and its debug-CSR check could accept a later
illegal word. The checks now verify their preconditions and bound the CSR
access with ebreak. A stale-read mirror and a model that leaks DPC are both
negative controls. A failed setup is never a reset pass.

The interop campaign passes all seven supported operations. Watchpoints are
unsupported in this execute-only profile. Sixteen single-step halts match
Spike for all 32 GPRs, DPC, misa and mscratch. Physical JTAG and other core
configurations are outside these results.
