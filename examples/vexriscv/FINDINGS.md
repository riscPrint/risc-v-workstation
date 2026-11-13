# VexRiscv findings

Collected from the 2026-11-13 PR bodies and
[the status audit](../../docs/status/2026-11-13/FINDINGS.md).
The external debug section below also records fresh RTL runs. No upstream
report was filed. Configurations differ below.

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

The historical interop script selected target+4 through GDB prologue skipping.
See "Breakpoint address selection" below. Execute-only triggers refuse watchpoints.
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

## Breakpoint address selection

The late breakpoint is an interop script bug. GDB 18.1 resolves `break target`
to `target + 4` for the interop ELF. It treats the first instruction as a
function prologue. This happens without a target connection. The instruction
is `addi s1,s1,1`. Both software and hardware function breakpoints use prologue
skipping. Use `break *target` and `hbreak *target` for the instruction address.

Minimal host-only reproduction after `rvw/debug/build.sh`:

```sh
riscv64-elf-gdb -nx -batch rvw/out/programs/debug-loop \
  -ex 'info address target' -ex 'break target' -ex 'info break' \
  -ex 'break *target' -ex 'info break'
```

| Command | Address |
|---|---|
| `info address target` | `0x80000014` |
| `break target` | `0x80000018` |
| `break *target` | `0x80000014` |

[Debug 0.13.2 DPC](https://five-embeddev.github.io/riscv-docs-html/riscv-debug-spec/v0.13-release/core_registers.html)
requires the ebreak address for an ebreak halt and the matching instruction
address for a timing-0 trigger. The reference checks `abs.dpc_resume` and
`trig.execute_matches` use those addresses. The latter also checks that the
matched instruction has not changed x8. The script must ask OpenOCD for that
same address. No DPC adjustment is needed in the harness.

Fresh DMI RTL run: `abs.dpc_resume` passes with cause 1, DPC
`0x80010004` and x8=6 after one increment from 5. `trig.execute_matches`
passes with cause 2 at `0x80010008` before the third increment. Both checks
match a fresh reference model. The complete run has 34 pass, 5 fail and
45 unsupported or skipped checks. The five failures are the recorded target
deviations above. The breakpoint-address fix changes no core RTL.

The installed OpenOCD reports `0.12.0+dev-00519-gb6ee13720-dirty`.
At its reported source revision,
[`riscv013_get_register`](https://github.com/openocd-org/openocd/blob/b6ee13720/src/target/riscv/riscv-013.c#L4077)
reads GDB PC from DPC without an offset. Its PC write path also writes DPC
without an offset. The version string reports a dirty build; the source check
is evidence for that reported revision, not an audit of local build changes.

The corrected RTL interop run passes seven checks. Software and hardware
breakpoints both stop at `0x80000014`. The execute-only profile reports the
watchpoint as unsupported. No PC offset is applied to the halt result.

The failed program-buffer reads in the earlier log were at `0x0`, `0x2`,
and subsequent low addresses through `0x62`. All are outside the example's
RAM (`0x80000000` through `0x80ffffff`). GDB attached with DPC at the suite's
scratch idle loop, `0x800103fc`, outside the interop ELF's code. The interop
setup now sets PC to the ELF entry after halting, before GDB attaches. The
repeat has no failed low-address reads. Load, memory write/readback and both
breakpoint checks pass. These observations do not indicate a failed access
to the valid RAM region. They are separate from function-prologue skipping.

Reproduce the supported interop checks with a running JTAG simulation:

```sh
rvw debug interop --profile rvw/debug/profile-jtag.toml --port "$port" \
  --elf rvw/out/programs/debug-loop --timeout 600 --out "$RUN_ROOT/interop"
```

## VEX-DEBUG-006

The new `dm.data_readback` check fails on `rv32im_dmi`: a direct write of
DATA0=0x13579bdf does not read back without an intervening abstract command.
This is a SpinalHDL Debug Module data-register deviation. DATA0 is R/W and
has reset value 0 in the
[Debug 0.13.2 register definition](https://github.com/riscv/riscv-debug-spec/blob/4e0bb0fc2d843473db2356623792c6b7603b94d4/xml/dm_registers.xml#L465).
The final 85-check DMI run has 34 pass, 6 fail and 45 unsupported or skipped
checks. Its other five failures are VEX-DEBUG-001 through VEX-DEBUG-005.
The reset check now establishes a nonzero read value through a completed
GPR read before clearing dmactive. It does not assume a direct write worked.

```sh
rvw debug suite --profile rvw/debug/profile-dmi.toml --check dm.data_readback \
  --out "$RUN_ROOT/data-readback"
```
