# BOOM findings

## ACT4, 2026-11-13

The [bundled profile](../../rvw/configs/act4/boom/README.md) records the
610-program selection and counts. The following groups account for all
38 remaining execution failures. No core RTL, signature or waiver changed.

| Cases | Count | Classification | Observed result and retained action |
|---|---:|---|---|
| Zalrsc-sc.w, Zalrsc-sc.d | 2 | Core simulation assertion | Repeated unsuccessful SC triggers `dcache.scala:754`, even with LR and SC at different addresses. Keep the assertion failure. |
| PMPS/PMPU/PMPSm NA4 and TOR legal-lxwr; three PMPSm TOR configuration cases; six PMPZca NA4/TOR cases | 15 | Core execution difference | Narrow executable regions cause instruction access fault before the permitted instruction reaches its data access. |
| Sm_F | 1 | Core execution difference | FLW leaves FS Initial after it changes an FP register. |
| ZicntrSm, ZicntrS, ZicntrU | 3 | Core counter difference | The tested interval is 44 retired instructions against Sail's 43. The minimal ECALL interval is 6 against Spike's 5. |
| Sstvecd | 1 | Platform WARL mapping | Writing `0x4000000000` reads `0xffffffc000000000` on BOOM and the written value on Spike. The two WARL mappings differ. This alone does not prove an ISA defect. |
| Sm_mcsr_cntr | 1 | Platform timing assumption | The time CSR trap path returns 719 after the test writes mtime=42. Its delta bound is 100. The measured delta is 677. |
| ExceptionsSvZalrsc S/U; ExceptionsSvZalrscSm MPRV S; SvPMP on physical address S/U | 5 | Sail expectation/platform gap | The generated signature expects a low address such as `0x40000000`; BOOM and Spike report the full VA such as `0x140000000`. Do not truncate the observed VA. |
| ExceptionsSm/S/U/Zc; ExceptionsSv S/U; ExceptionsSvSm MPRV S/U | 8 | RVFI check binding | Trap records lose operands or access masks. A misaligned LH reproduces error 111. Keep the monitor active. |
| Sv canonical S/U | 2 | RVFI check binding | JALR reports next PC `0x8000000140009000`; the next trap record reports PC `0x140009000`. The shadow-PC check rejects this truncation. These runs do not establish an execution defect. |

The three extra PMPSm cases are `cfg_A_tor_zero`, `cfg_A_tor_bot` and
`cfg_tor_check-01`.
All case names have the ACT4 `-00` suffix. Full generated inventories stay
local. The eight RVFI cases are `ExceptionsSm`, `ExceptionsS`,
`ExceptionsU`, `ExceptionsZc`, `ExceptionsSv_sv39_exceptions_{S,U}mode`
and `ExceptionsSvSm_sv39_exceptions_mprv_{S,U}_Mmode`.

| Minimal source in findings/ | Variants | Spike | BOOM small | Rule or evidence boundary |
|---|---:|---|---|---|
| [sc-outside-reservation.S](findings/sc-outside-reservation.S) | W/D | pass | assertion after repeated failures | Different-address LR/SC is an unconstrained loop. The constrained-loop eventual-success rule does not apply. No forward-progress defect is claimed. |
| [pmp-narrow-exec.S](findings/pmp-narrow-exec.S) | NA4/TOR | pass, store fault 7 | fail, instruction fault 1 | PMP checks the bytes of the access. A four-byte instruction lies wholly inside its executable region. MIE and MIDELEG are cleared before S-mode entry. |
| [flw-fs-dirty.S](findings/flw-fs-dirty.S) | FLW changes f0 | pass, FS=3 | fail, FS=1 | A change to FP register state must mark FS Dirty. The core's dirty signal follows fflags validity and misses this load. |
| [minstret-ecall.S](findings/minstret-ecall.S) | ECALL, four handler instructions | pass, delta 5 | fail, delta 6 | ECALL raises an exception and does not retire. |
| [stvec-warl.S](findings/stvec-warl.S) | one write/read | written value | sign-extended value | STVEC is WARL. The reference needs the implementation's legal-value mapping. |
| [misaligned-rvfi.S](findings/misaligned-rvfi.S) | misaligned LH | pass, cause 4 | RVFI error 111 | The binding clears rs1 on traps and omits mem_fault for misalignment. This is not evidence that LH executed without its trap. |
| [word-remainder.S](findings/word-remainder.S) | REMW/REMUW | pass | pass after checker fix | Word division uses the low 32 operand bits and sign-extends the result. |

Compile with `riscv64-unknown-elf-gcc -nostdlib -nostartfiles
-march=rv64imafdc_zicsr_zifencei -mabi=lp64 -Wl,-Ttext=0x80000000,--no-relax
SOURCE -o ELF`. Use `-DWORD` for SC.W and `-DTOR` for TOR. Run with
`scripts/with-lock.sh boom nice -n 10 RiscvSim/boom/run.sh run --config small
--elf ELF --out RUN --rvfi-trace --max-cycles 30000 --json`.
The independent Spike runs use `spike --isa=rv64imafdc_zicsr_zifencei ELF`.
These directed checks are separate from the strict full-trace comparisons.

The imported riscv-formal REMW/REMUW models tested all 64 divisor bits for
zero. A divisor with low word zero therefore caused a false monitor error.
`RiscvFormalModel` copies and corrects the two word checks before elaboration.
The external source stays unchanged. Icarus unit vectors cover zero low
words, sign extension and nonzero divisors. Both ACT4 reruns pass.
The ECALL freshness guard compared an unsigned 40-bit PC to a signed
64-bit EPC. Generic `Hex.signExtend` and its tests retain the guard while
fixing that representation error. Both SvPMP-on-PTE reruns now pass.

All 610 strict comparisons stop at reset state, before the full test can
be compared. The reset veneer clears mscratch first. BOOM reports
FCSR=`0xff`; Spike starts with zero. Strict mode does not seed or mask
that state. This is a platform initialization
limitation. It is not 610 proven core defects. Later directed observations
do not turn those comparisons into complete matches.

Rules: [RISC-V privileged specification, reset, PMP, FS, WARL and counters](https://docs.riscv.org/reference/isa/priv/machine.html),
[RISC-V unprivileged specification, M and A](https://docs.riscv.org/reference/isa/_attachments/riscv-unprivileged.pdf).
The high-VA rule requires the faulting virtual address when a nonzero trap
value is reported. The Sail expectation gap remains open. Full Sm_F and
Zicntr CLI runs hit earlier illegal-instruction tval policy differences;
only their isolated programs establish the Spike outcomes above.

## Generated families, 2026-11-13

The RV64 planner selection and family counts are in the
[adapter README](../../RiscvSim/boom/README.md#generated-rv64-families-2026-11-13).
All 15 native failures are `pmp-na4-*-execute` cases where execution is
permitted: five unlocked M-mode permission settings, locked M-mode X
settings, and S/U X settings with either lock value. They share the narrow
PMP execution finding above. The other 379 PMP programs pass.

The initial Sv39 matrix requested nonzero ASID in eight remap/root cases.
The exact SATP readback check rejected all eight because BOOM has
ASID_WIDTH=0. The corrected selection uses ASID 0 and keeps the readback
check. Two hardware A/D controls also fail because this profile implements
Svade, not Svadu. The selected fault-based A/D cases pass. These are
platform settings, not TLB or A/D core defects. All 145 selected Sv39 cases
pass. The first AMO fault run reached only 57 of 72 operations at the
30,000-cycle limit. The unchanged program passes at cycle 38,498 with its
200,000-cycle generator budget. No timeout or expectation was masked.

The harness has CLINT and interrupt-generator bindings. PLIC registers,
claim/complete and multiple-hart atomicity remain unmeasured. Every strict
comparison in the 588-program selection stops at reset FP state, often
with mscratch state too. These are execution results without complete
strict reference qualification.

## Generated checks, 2026-11-13

Private core revision `0cb0b69`, preset `small`, seed 1, randomized memory
latency. No core RTL or waiver file was changed. The quick tier selects
174 programs. All 174 instrumented runs fail because checks fire. This
is separate from their architectural tohost outcome. The run inserts
519 checks and leaves 101 existing checks waived or disabled.

| Firing group | Distinct IDs | Programs | First monitor cycle | Representative wave window |
|---|---:|---:|---:|---|
| TileLink A request legality | 2 | 174 | 3 | add, times 180 to 200 |
| TileLink D response legality | 6 | 2 | 878 | icache-alias, times 8930 to 8950 |
| Frontend TLB request valid hold | 1 | 2 | 446 | ae_ptw, times 4600 to 4640 |
| MSHR 0 replay queue valid hold | 1 | 1 | 1245 | ae_ptw, times 12550 to 12620 |

Wave times are raw FST timestamps. The clock period is 10. Separate wave
reruns reproduce all 10 IDs. Raw waves and build outputs remain local.
None of the 24 IDs in `SpinalChecks/boom/stream-dispositions.json` fires
in this run. The source review still records an incomplete mapping to
the original historical inventory. This does not close issue #5.

The two A IDs are `tilelink.request_legal:io_mem_a` and
`tilelink.request_legal:arbiter.io_down_a`. The first accepted reset fetch
at time 190 is Get, address `0x80000000`, size 6, mask `0x00`.
This is a core interface difference. A reset fetch alone reproduces it;
no particular retired instruction is needed. TileLink Get requires the
size-aligned mask, which is `0xff` on this eight-byte bus for size 6.
The monitor remains active. No CPU ISA or Spike conclusion follows from
this bus violation.

The six D IDs are `tilelink.response_legal:` at `io_mem_d`,
`tile.io_dmem_d`, `tile.dcache.io_mem_d`, `arbiter.io_down_d`,
`arbiter.io_ups_0_d` and `arbiter.ups_0_d`. The wave at time 8940
has an accepted ReleaseAck, size 6, source 2, param 1, denied 0 and
corrupt 0. TileLink requires ReleaseAck param 0. This is a simulation
platform defect, not a core response. SpinalHDL's `MemoryAgent.onC`
constructs `TransactionD(c)`, which copies the Release param, and changes
only the opcode before scheduling D. The private BOOM harness uses that
agent. Its external dependency still needs a generic fix and test.
No local response mask or replacement memory agent was added.

The frontend ID is `stream.valid_hold:tile.frontend.tlb.io_req`.
In ae_ptw, valid/ready is 1/0 at time 4610 and 0/0 at 4620.
`io_kill` is 0. `ifu/frontend.scala:95` forms valid from the current
stage-1 fetch, replay, clear and SFENCE conditions. This port does not
retain every offer until ready. This is a platform check-binding finding:
the strict Stream obligation does not describe this cancellable request.
A reviewed cancellation condition is still needed. The firing is retained.

The replay ID is `stream.valid_hold:tile.dcache.mshrs.mshrs_0.rpq.io_deq`.
In ae_ptw, valid/ready is 1/0 from time 12550, then 0/0 at 12610.
The branch-killable queue can remove speculative work without acceptance.
See `util.scala:377-436` and `lsu/mshrs.scala:135-142,273-299`.
This is a platform check-binding finding. The wave has flush=1 at time 12600 and valid=0 at 12610, with
branch mispredict mask zero. The cancellation follows the flush edge.
A binding must also retain the `uses_ldq` condition from `flush_fn`.
No broad flush exemption or waiver was added.

Rules: [TileLink 1.8.1, Get and ReleaseAck](https://starfivetech.com/uploads/tilelink_spec_1.8.1.pdf).
The two stream rules are the retained `stream.valid_hold` contract in
SpinalChecks. They are not RISC-V ISA rules. Spike has no internal stream
or TileLink response for comparison.
