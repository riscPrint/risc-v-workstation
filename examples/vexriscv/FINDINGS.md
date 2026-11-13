# VexRiscv findings

Collected from the 2026-11-13 PR bodies and
[the status audit](../../docs/status/2026-11-13/FINDINGS.md). This collection
adds no RTL run. No upstream report was filed. Configurations differ below.

## VEX-MTVAL-IRQ-001

Confirmed core defect on `rv32im`, pinned core `baf7dc82`.
MSIP, MTIP and MEIP traps retain old nonzero `mtval`. Spike writes zero.
[Minimal programs, link script, schedules and evidence](findings/interrupt-mtval/README.md).
Each directed RTL run reads `0x55` and writes `tohost=3`.
The [Machine Trap Value rule](https://docs.riscv.org/reference/isa/v20260120/priv/machine.html#_machine_trap_value_mtval_register)
requires zero for traps outside the listed exception cases, including interrupts.
Source: [#1124](https://github.com/riscPrint/risc-v-workstation/pull/1124).
The three reviewed scheduled-WFI mismatch traces are in `known-findings.json`.
They do not count as Spike matches.

## VEX-MRET-MPP-001

Confirmed M-only configuration deviation. MRET clears MPP to 0 while privilege
stays M. Spike with `--priv=m` retains MPP=3. The privileged ISA xRET rule
sets xPP to the least privileged supported mode, which is M for this profile.
[Minimal assembly, native harness, RTL identity and measured comparison](formal/MACHINE_M.md#mret-decision-and-directed-reproduction).
The reproduction is `formal/findings/mret-mpp.S`. No core fix was applied.

## VEX-PC-CHAIN-001

Confirmed MEPC readback deviation and next-PC observation mismatch on the
captured M-only RTL. Write MEPC=`0x80000019`, read MEPC, then execute MRET.
RTL reads `0x80000019`; Spike reads `0x80000018`. Both retire at `0x80000018`.
The privileged ISA requires MEPC bit 0 to read as zero.
[Minimal assembly, native harness, RTL hash and directed comparison](formal/MACHINE_REMAINING.md#pc-chain-attribution-follow-up).
The original SRET formal witness remains inconclusive in Icarus because its
redirect has X values. It does not establish an MRET redirect defect.

[Six ACT4 decisions](rvw/act4/MEPC_DECISIONS.md) confirm the same readback
rule with writes 1, 2 and 3 and six CSR read forms. This profile has IALIGN=32.
Both MEPC bits 1:0 must read zero. All six fresh minimal programs fail C1 and
strict Spike comparison, with zero masks and synchronizations. Build
`rvw/act4/mepc-case.S` with `CASE=0..5`. The adjacent `mepc-review.json`
retains ELF and C2 hashes and each first difference. The original six full
ACT4 cases were not rerun in that review. Source:
[#1179](https://github.com/riscPrint/risc-v-workstation/pull/1179).


## VEX-DEBUG-001 through VEX-DEBUG-005

Five target deviations were observed on `rv32im_dmi` and `rv32im_jtag`
(core `a62c145a`). Source:
[#896](https://github.com/riscPrint/risc-v-workstation/pull/896).
Use `rvw debug suite` with `rvw/debug/profile-dmi.toml` or
`rvw/debug/profile-jtag.toml`. The cases are in the generic debug suite.
The relevant rules are in the
[RISC-V Debug Specification](https://docs.riscv.org/reference/debug-trace-ras/).
These recorded deviations still need isolated reproductions and clause-level
review before they can be promoted to confirmed specification defects.

| ID | Minimal transaction sequence | Observed difference | Rule to check |
|---|---|---|---|
| VEX-DEBUG-001 | Write data0; clear then set dmactive; read data0 | data0 survives | DM reset on dmactive=0 |
| VEX-DEBUG-002 | Select a nonexistent hart; read dmstatus | all-state bits stay 1 | Nonexistent-hart status |
| VEX-DEBUG-003 | Issue transfer=0 with invalid aarsize | cmderr=2 | Access-register transfer and size checks |
| VEX-DEBUG-004 | Write tdata1 action=1 with dmode=0 | action stays 1 | Trigger action restrictions |
| VEX-DEBUG-005 | Configure dmode trigger; attempt M-mode write | Trigger changes | Debug-only trigger protection |

Open interop observation: software and hardware breakpoints stop at target+4.
The stop position is unexplained. Execute-only triggers refuse watchpoints.
Physical JTAG and a hardware trace encoder were not tested.

## Resolved checker and harness findings

Eleven internal fetch valid-hold checks fired 8,768 times in #840.
[#893](https://github.com/riscPrint/risc-v-workstation/pull/893) tied each to
halt, flush or FIFO discard. With explicit cancellation bindings, 49 ISA
programs pass with all 57 checks active and zero firings. These are resolved
checker-contract defects, not confirmed core defects. #705 fixed missed C2
retirement capture before DPI yield. No reference value replaced RTL data.

## Security and formal limits

[#842](https://github.com/riscPrint/risc-v-workstation/pull/842) found two
undriven `CsrPlugin_stvec_mode` bits during security export. This is an
export/input limit. No demonstrated security leak follows from it.
The deliberately patched transient-load core is a positive control, not a
finding on the unmodified core. `rvw/sec/README.md` records those variants.
Formal portfolio timeouts and witness reconstruction failures remain
inconclusive. They do not establish core defects.

## VEX-CSR-BOOT-001

Open standard-bootstrap compatibility finding. The default RV32 profile traps
on `mstatush` (CSR `0x310`) in the standard ACT4 boot. The reduced bootstrap
results do not resolve that contract. Minimal reproduction:
[missing-boot-csr.S](rvw/act4/missing-boot-csr.S), built with `-DCSR_ADDR=0x310`.
See [the ACT4 record](rvw/act4/README.md). The selected scaffold expects this
access to complete. Resolve the declared machine CSR contract before calling
this a specification defect. No mask or waiver changes the observation.
