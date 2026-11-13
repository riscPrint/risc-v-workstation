# Privilege campaigns

Build a project-owned RV64 control campaign:

```
rvw regress privilege build examples/privilege/controls.json --out rvw/out/controls
rvw regress privilege reference rvw/out/controls --timeout 2
```

The generator crosses TVM, TW and TSR with set/clear states and actual M/S/U
entry. It tests satp reads, satp writes, SFENCE.VMA, WFI and SRET. Each program
checks the trap cause and exception PC. It checks control retention on entry to
M-mode. It clears the bit and retries the operation in S-mode. SSIP is pending,
locally enabled and delegated. Global enables are clear. WFI has no minimum
sleep requirement. The expectations use the 20260120 privileged specification.

Use `modes` to select modes. The project supplies `isa`; the default is
`rv64im_zicsr_zifencei`. This first campaign requires S, U, PMP and RV64.
An unsupported configuration is not a passing disabled-feature test.

Merge the generated `suite.toml` section into the project's regression TOML.
Set its `dir` to the generated directory relative to that TOML. Run through the
project's existing C1 adapter:

```
rvw regress run --suite privilege --rvfi-trace --out rvw/out/controls-dut
rvw regress privilege check rvw/out/controls --results rvw/out/controls-dut --platform platform.json
```

`check` requires one conclusive passing C1 result per ELF and a complete strict
Spike match. A mismatch fails. Missing C1, missing traces, duplicate results,
incomplete comparison and synchronized comparison stay inconclusive. Functional
groups use all-member pass. Spike self-check results never earn DUT groups.
Two strict mismatch shapes are missing reference evidence, not core failures,
and stay inconclusive: a CSR read of `mip` that differs only in bits listed in
the platform's `irq_inputs`, and a load inside a platform `mmio` region that
differs only in the loaded value. Spike models neither the project's interrupt
pins nor its devices. Use `rvw cosim check` with irq/mmio synchronization as
separate, explicitly synchronized evidence for these programs.
`--results` may be a parent of several regression outputs. Each owned C1
member is read once (a regression keeps a sealed generation and a current view).
MCP tools expose build, reference and check with the same inputs.

## Decisions

Keep campaign generators separate from MMU and multi-hart modules. Reuse the
existing regression adapter and strict reference checker. Keep programs small.
Emit a new output directory for each build to prevent stale ELF discovery.

## Limits

This increment does not close #139. SUM, MXR and MPRV campaigns remain in the
existing MMU framework. Full disabled-feature combinations remain open. No RTL
run was made. The control programs do not test PLIC delivery, late WFI wake, reset,
Smrnmi, PMA, ePMP, AIA, CLIC, Sstc, state-enable, environment controls, CFI, RAS
or DVFS. These need separate campaigns and project interfaces.

## Timer and software WFI campaigns

Set `kind` to `wfi` and supply `timer.mtime`, `timer.mtimecmp`, `timer.msip`
and `timer.delta`. Addresses are integers. Delta is the future timer offset in
ticks. `examples/privilege/spike-wfi.json` declares the native Spike CLINT map.
Copy and change that data for the project's map. The generator does not choose
addresses for a core.

RV32 and machine-only cores: set `isa` to an `rv32` string and `priv` to `m`
(see `spike-wfi-rv32.json` and `scheduled-wfi-rv32.json`). The programs then
use word stores, a high/low/high `mtime` read, a high-word-first `mtimecmp`
write and bit 31 interrupt causes. The `m` preamble does not touch `satp`,
delegation or PMP CSRs, which an M-only core may not have. `priv = "m"` is
accepted only for `wfi` and `scheduled-wfi`. `rvw regress plan` selects
`wfi-clint-rv32` and `scheduled-wfi-rv32` for `xlen:32` features.

The four programs cross software/timer sources with global MIE clear/set.
They enable the local source. They drive the software event or program a future
timer compare. A masked case requires eventual pending and retained register
state without trap entry. An enabled case checks interrupt cause, exception PC
within the independent wait region, MIE clear on entry and retained state.
Legal early WFI return is allowed. The external C1 cycle bound limits waiting.
The programs restore the device interrupt state before reporting completion.
These cases do not test physical clock stop, delayed external input or reset.
They are a bounded increment for #149 and do not close that issue.

Builds also write `functional-groups.json` for `rvw cov functional --config`.
It describes CSR/mode, trap and interrupt observation domains. Observed bins
measure trace activity. Use `privilege check` for architectural pass groups.
An observed hit alone never establishes a correct outcome.

## Disabled features

`kind = "disabled"` selects two matrices. With `priv = "msu"`, declare F in
`isa`. The 36 programs keep FS Off and cross all six privilege controls with
M/S/U entry and both control values. Each floating-point operation must trap
with cause 2 at its exact PC. With `priv = "mu"`, 72 programs cross the same
controls with M/U entry and absent satp, SFENCE.VMA and SRET. Supervisor setup
CSRs are not accessed. The reference uses the configured privilege string.
See `examples/privilege/fs-off.json` and `no-supervisor.json`.

These programs check disabled state and absent supervisor operations. They do
not establish all possible disabled-extension combinations or DUT qualification.

## Scheduled WFI and clock observation

`kind = "scheduled-wfi"` generates six programs for MSIP, MTIP and MEIP with
global MIE clear/set. `wake.assert_cycle` and `wake.clear_cycle` select the
C1 input schedule. The generated suite has one section per program so each
source has its own `irq_schedule`. Set each section's `dir` for the project.
Programs allow early WFI return and check pending state or interrupt cause,
exception-PC interval and retained register state. The C1 checker requires the
exact requested input schedule. Spike CLI self-check is inconclusive because
it cannot apply this external-input schedule. No program timeout becomes pass.

RTL results on 2026-11-13 (strict `rvw regress cosim`, plus `--allow-sync irq`
for programs that read `mip` while a pin is asserted):

| Core | Family | Generated | Run | C1 pass | Spike match | Finding |
|---|---|---|---|---|---|---|
| VexiiRiscv `rv64imasu` | controls | 30 | 30 | 30 | 30 | 0 |
| VexiiRiscv `rv64imasu` | PMP, 8 entries, 16-byte grain | 264 | 264 | 264 | 264 | 0 |
| VexiiRiscv `rv64imasu` | scheduled WFI | 6 | 6 | 6 | 6 | 0 |
| VexiiRiscv `rv32imasu` | scheduled WFI | 6 | 6 | 6 | 6 | 0 |
| VexRiscv `rv32im` (M only) | scheduled WFI | 6 | 6 | 6 | 3 | 3 |

The VexRiscv finding: an interrupt trap keeps the old `mtval`. See
[the reproduction](../../../../examples/vexriscv/findings/interrupt-mtval/README.md).
The per-core tables are in the
[VexiiRiscv](../../../../examples/vexiiriscv/README.md#generated-suites-on-rtl-2026-11-13)
and [VexRiscv](../../../../examples/vexriscv/README.md#generated-m-only-suites-on-rtl-2026-11-13)
READMEs. Other privilege families need extensions or devices these cores lack.

For a project clock-stop harness, set `wake.clock_state` to a map of retained
state names to positive bit masks. Record a `privilege_clock` C1 artifact as a
JSON list with `tick`, `clock_running`, `state`, `retired` and `pending` samples.
Tick is an independent reference-clock count. Retirement is a cumulative count.
Include a running sample before the pause, samples on every reference edge
while stopped, and resumed samples. The checker requires stable masked state,
no retirement while stopped, pending input during the pause and retirement after
restart. It binds the observation artifact hash in the report. Missing samples
remain inconclusive. The project harness must drive the clock pause itself.
This interface does not claim a clock-stop run or physical clock-gating proof.

## PLIC, reset and Smrnmi

Select `kind = "plic"` and supply a complete `PlicMap` as `plic`. Six programs
check priority, tie order, claim despite threshold, shared contexts, gateway
completion and enable changes. The existing independent PLIC model derives
expected claim IDs. The known native Spike threshold discrepancy remains a
failure; it is not used as a replacement rule.

Each source event uses RAM symbols `stimulus_step` and `stimulus_ack`. Generated
`rvw.stimulus/1` files carry the event payload. A project adapter must read the
request, apply the device event, then write the acknowledgement. `MailboxDriver`
in `events.py` provides this sequence for Python adapters. It does not contain
bus or signal names. The C1 result must record the generated stimulus SHA-256.
Unsupported adapters must reject the option. The source schedule requires a
fresh device state. It does not cover all simultaneous context races.

`kind = "reset"` requires `reset.pulses`, `state` with value/mask pairs and
`invalid_outputs`. `kinds` selects cold, warm or local reset. The program retains
a RAM restart count across actual pulses and requires every restart. The harness
must preserve this RAM region. It records `privilege_reset` as a JSON list of
pulses. Each pulse is a list of existing ResetSample records. The checker reuses
the independent reset contract checker. It requires all requested pulses. It
does not count simulator construction as a reset. In-flight bus, debug and trap
reset drivers remain project integrations.

`kind = "nmi"` requires Smrnmi in `isa`, `nmi.cause` and `nmi.vector`. It places
an NMI handler at that vector. The event waits for the exact `nmi_wait` PC. The
adapter supplies the PC and ELF symbol map to MailboxDriver. The program checks
MNCAUSE, NMIE clear, MNEPC, preservation across a nested ordinary ECALL trap,
MNRET recovery and a retained register. It does not test a second RNMI while
NMIE is clear, a vendor machine-error record or reset during RNMI.

The supplied examples declare fixture addresses and contracts. Replace them
with project data. Spike CLI cannot inject these mailbox events. Their reference
self-checks are inconclusive until a project reference adapter supplies them.
No DUT run, NMI injection or physical reset is claimed by a generated file.

`compiler_isa` can select a compiler ISA string separate from the reference
`isa`. The Smrnmi example uses numeric CSR and MNRET encodings because the
installed assembler does not recognize the Smrnmi ISA name. This does not
change the reference or DUT extension requirement.

## Physical memory protection

`kind = "pmp"` generates 394 RV64 base-PMP programs. The matrix covers TOR,
NA4, NAPOT, read/write/execute permission, M/S/U entry, MPRV effective S/U,
locked permission enforcement, locked address/config writes, TOR predecessor
locking and overlapping-entry priority. Stores also check the resulting data.
Denied accesses check cause, PC and mtval. The selected project must provide
at least eight PMP entries and four-byte granularity for this matrix.
An RV32 M/U core (no S-mode) uses `isa` `rv32...` and `priv = "mu"`; see
`examples/privilege/pmp-rv32.json`. It needs four entries: the allow-all TOR
fallback moves from entry 7 to entry 3 (the last entry in RV32 `pmpcfg0`).
The default modes are M, U and MPRV-U, 242 programs. `rvw regress plan`
selects `pmp-rv32` for `xlen:32`, `mode:U` and at least four PMP regions.

`kind = "epmp"` requires Smepmp. Four separate programs check MMWP unmatched
access denial, MML S/U-only and M-only rules, sticky security policy bits,
RLB changes to locked entries and failed RLB re-enable after locks take effect.
They follow Smepmp 1.0 in the 20260120 specification. They do not count as a
complete ePMP permission truth table or reset qualification. Base PMP programs
never count as ePMP coverage.

`kind = "pma"` uses project `pma.regions`. Each row declares name, base, size,
scalar widths, read/write permissions and expected value. `test_writes` must be
explicit. The generator probes the first and last aligned access for each width.
The project supplies `bus_count_allowed`, `bus_count_denied` and `device_state`.
C1 must provide `privilege_bus`: a JSON object with `complete`, `transfers`
(address/width/write) and independent `device_state`. Missing observation or
contract stays inconclusive. Spike CLI cannot implement arbitrary project PMA.
These initial boundary probes do not cover conflicting regions, atomic PMAs,
cache coherence or idempotency effects.

## Versioned interrupt controllers

The project pins `spec_version` and can record `spec_revision`. Models reject
unknown versions. A future version needs a separate implementation before its
results can count. Examples pin:

- AIA 1.0: `AIA-1.0`. IMSIC programs check MSI injection, enable, threshold,
  delivery and ordered claims. APLIC programs check detached software-pending
  sources, direct-delivery priority, threshold and claims.
- Fast interrupts: `riscv-fast-interrupt-v0.20`, commit
  `b623d1262ed40a255fd290333d8e0c6d0c44b2e8`. This is the latest published
  release found in the upstream release list. Its source says Stable. It uses
  ACLIC, Smidctrl and Smnip names. It does not use the old CLIC register layout.
  Four Smnip programs check threshold CSR values, synchronous-trap save and
  return restore. `fast_interrupts.config_csr` selects the implemented mireg4.
- ACLINT: `ACLINT-v1.0-rc4`, commit
  `4e570bfd3201f2c09e5afd290b5091526b0f099a`. MSWI and SSWI programs check
  setting and clearing pending state. SSWI zero writes must not clear SSIP.

Sources: [AIA 1.0](https://docs.riscv.org/reference/aia/v1.0/index.html),
[fast-interrupts v0.20](https://github.com/riscv/riscv-fast-interrupt/releases/tag/v0.20),
[ACLINT rc4](https://github.com/riscvarchive/riscv-aclint/releases/tag/v1.0-rc4).

Set `reference_backend = "python"` to run the small versioned reference models.
The report says `evidence = "model-based"` and binds model source hashes.
It never earns DUT groups. Set `reference_backend = "spike"`, or omit it, to
request native Spike self-checks. The generated ELF hash is checked in both
paths. An unavailable Spike device model is not a passing result.

The Python models cover IMSIC pending/enables/threshold/claims and file state,
APLIC source modes, priority, direct claims, source delegation and software/edge
MSI routing, ACLINT pending/timer state and nested priority groups. Unit tests
are model tests. Programs cover machine, supervisor and selected VS guest interrupt files,
one APLIC direct-delivery context and edge/level MSI gateways. Full guest
context switching, multiple harts, vector entry and asynchronous preemption
need additional program campaigns. The separate direct-delivery and MSI
models keep their different level-pending rules. Old CLIC drafts
are not silently mapped onto ACLIC. These limits keep #158, #165 and #186 open.

## RERI and digital DVFS

RERI project data pins `RERI-v1.0`, ratified 2024-05-24, source commit
`12eef3f549fe54f817185b1e084b85537f442999`. See the
[RERI v1.0 source](https://github.com/riscv-non-isa/riscv-ras-eri/tree/v1.0).
`reri.base`, supported `classes`, `priority_supported` and `control` describe
one implemented record. Programs first invalidate and initialize that record.
The specification does not define a universal reset value. Seven full-capability
cases check CE/UED/UEC logging, severity and priority overwrite, sticky history,
multiple occurrence and read/invalidate recovery. The model also implements
valid-write protection, RDIP/SINV races and corrected-error counting/overflow.

The project driver must inject an actual hardware error event, not silently
substitute a software status-register write. An optional `irq_routes` map from
RERI signal selection to interrupt cause adds an interrupt handler check. The
program requires observed delivery, the correct cause, a PC in the event region
and a valid error record. The example routes low and high RAS requests to MEIP.
That route is fixture data. It is not a RERI-mandated route. Python reference
reports cover record behavior and expected signal requests. They are model-based.
They do not establish physical poison propagation or successful DUT recovery.

`kind = "dvfs"` declares frequency/voltage states and a sequence of state names.
The program checks retained register state and completion across mailbox-driven
transitions. The Python reference lists expected digital handshake phases. It
requires voltage readiness before a frequency increase and a frequency decrease
before voltage reduction. A `privilege_dvfs` C1 artifact contains reference-tick
samples with step, phase, frequency_hz, voltage_uv, clock_ready and voltage_ready.
The checker requires every phase in order and ready target state before ack.
It checks the declared frequency/voltage-state limits. Missing samples stay
inconclusive. The report binds the observation hash. This is a digital sequencing
check. It does not qualify analog voltage, PLL behavior or physical timing.

The C1 checker gives a matching architectural self-check failure precedence over
missing optional device observations. A model-based report cannot override it.

## Timer, state-enable, environment and CFI controls

All these campaigns pin the 20260120 privileged specification.

- `sstc` crosses M/S/U access with STCE and counter-access enable. It also
  observes STIP assertion and clearing after compare writes. It requires
  `Zicntr` so the Spike reference has time support. The installed Spike crashes
  on some Sstc accesses without that extension. `sstc.virtualization = true`
  requires H and adds VS accesses across machine/hypervisor STCE and TM bits.
  It distinguishes illegal-instruction from virtual-instruction traps.
- `stateen` checks SSTATEEN access in M/S/U with MSTATEEN.SE0 clear/set.
- `envcfg` checks declared implemented bits in MENVCFG and SENVCFG. Set
  `envcfg.implemented_mask`. The example selects the Zicfilp LPE bit. An
  optional `henvcfg_mask` and H ISA add machine/HS/user HENVCFG access tests.
  Optional WARL bits must be declared from project support, not assumed.
- `landing` crosses M-mode setup with S/U entry, LPE clear/set, valid/absent
  landing pads and matching/mismatching nonzero labels. It checks software-check
  cause and the landing-pad fault code.
- `shadow` checks S/U push/pop, mismatched return values, read-only page recovery,
  ordinary-page rejection, Bare-mode rejection and normal-store rejection on
  shadow-stack pages. The small Sv39 fixture lives in this module. It does not
  edit or replace the MMU campaign. The independent Stack model checks pointer
  changes and mismatch atomicity. Programs check the architectural SSP and
  actual pushed values through SSPOPCHK.

Examples include `sstc-h.json` and `envcfg-h.json` for H profiles. These
profiles use RV64. The separate RV32 timer profiles are described below. All
extension-state gates, complete virtualization transitions, asynchronous
landing-pad interruption and guest shadow stacks remain open. No C1 or DUT result is inferred from a native Spike pass.

## Simultaneous disabled-feature combinations

`kind = "disabled-matrix"` crosses every requested combination of SUM, MXR,
MPRV, TVM, TW and TSR with M/S/U entry. `disabled.feature` selects `fs-off`,
`vs-off`, `no-float`, `no-vector` or `no-supervisor`. Absent supervisor uses
M/U entry and requires `priv = "mu"`. The first four profiles emit 192 programs
each. The absent-supervisor profile emits 384 across satp, SFENCE.VMA and SRET.
The five project examples use the `all-` prefix and emit 1152 programs in total.

Each program checks illegal-instruction cause and exact PC. It captures WARL
control readback before entry and checks retention on trap. It accounts for
MRET clearing MPRV on lower-mode entry. Group names say `requested` because an
unimplemented WARL bit need not retain the written value. Raw F/V encodings
permit absent-extension tests without requiring that extension in the compiler
or reference ISA. Only four masks per profile were selected for the short
native smoke run. Those samples do not establish results for all 1152 programs.

## Complete MML permission table

`kind = "epmp-matrix"` expands all 16 L/R/W/X encodings from the pinned
Smepmp 1.0 MML truth table. It checks reads, writes and instruction fetch in
M/S/U, plus MPRV effective S/U data accesses. The 208 programs include shared
code, shared data, inaccessible, mode-only and ordinary permission rules.
Stores check their data before changing privilege. The bootstrap uses shared
code and data rules so it does not mask target permissions. RLB is cleared
before each probe. No base-PMP result counts as an MML result.

All 208 programs pass short native Spike self-checks. This covers the MML
permission matrix in the reference model. It does not replace reset/lock
observation, all security-policy transition cases or DUT qualification.

The MML matrix bootstrap requires `epmp.rlb_supported = true`. RLB is optional
in Smepmp, so the generator does not treat its absence as a conformance failure.
Programs check MML set and RLB clear before each permission probe.


## IMSIC file isolation and APLIC MSI gateways

`imsic.file` selects M, S or VS. The VS profile requires H and a positive
`guest_index`. `identities` declares the file size as 64*n-1. Programs clear
that file's pending/enables, inject into its project-owned MSI page and check
the proper TOPEI CSR and pending IRQ bit. They also check that an uninjected
peer file stays empty. The examples select supervisor and guest-file pages
explicitly. They do not infer a project address map.

`kind = "aplic-msi"` combines project APLIC and IMSIC maps. Four programs
exercise Edge1, Edge0, Level1 and Level0 sources. Each drives an inactive
baseline before source configuration, asserts the source, holds it asserted,
deasserts it and rearms it. They check the delivered IMSIC identity and require
no repeated MSI merely from a held input. The model follows the pinned AIA 1.0
pending-bit rules. Level MSI pending clears on forwarding and rearms on a
rectified rising edge. Software can set it only while the input is active.
These rules differ from level direct-delivery pending, which follows the wire.

Programs wait for MSI arrival with a finite instruction bound. Source events
use the existing mailbox contract and include the controller base and source.
No RTL source driver or DUT result is implied by compilation. Reference output
is model-based. AIA profiles pin `AIA-1.0` and the revised 20250312 document
source `20318d1b03f0ac8253458b82f8244d0d0db074e9` in `spec_revision`.
The original ratified 2023 source revision remains supported for this subset.

Smnip has one previous-threshold field. Nested handlers must save and restore
that field in software. The Python model does not create an implicit hardware
stack. Its restore_previous method represents the explicit software restore.


## RV32 split timers and independent timer observations

`kind = "sstc-rv32"` selects the RV32 Sstc profile and ILP32 compiler ABI.
It checks both STIMECMP halves in M/S/U, safe split updates, full readback and
pending assertion/clearing. The H profile adds both halves of virtual accesses,
virtual-instruction traps and positive/negative HTIMEDELTA offsets. It verifies
offset-register readback and tests the resulting VSTIP changes against a nonzero
compare value. The RV64 H profile uses the same event program. H setup clears
MPV before entry and sets it explicitly for VS cases.

Virtual-time event programs require a fresh reference time below 2^39. They
use a compare of 2^39 and offsets of plus/minus 2^40. They do not read the time
counter. The negative offset tests unsigned 64-bit wrap. These are bounded
program scenarios, not all possible timer states.

Pending-event scenarios require a `privilege_timer` C1 artifact before their
architectural groups can pass. It is a JSON sample list with `tick`, `phase`,
`phase_start`, `reference_time` and Boolean `pending`. Reference time comes from
the independent device/clock model. It is not a synchronized architectural CSR
read. ELF symbols `timer_armed`, `timer_cleared`, or the virtual phase labels
identify the program phases. The build manifest records their expected compare
and delta values. Wide values use hex strings so JSON clients retain all bits.
The checker also accepts integer values in captured samples.

The checker needs a correct observed event for every phase. Missing samples or
witnesses remain inconclusive. An optional `sstc.max_latency_ticks` adds a
project timing bound measured from phase_start. Wrong state at the deadline
fails. A late-only witness stays inconclusive. Without that field, the report
makes no latency claim. The report binds the capture hash and still requires
the normal complete strict architectural reference match.


## CFI trap recovery and shadow stack boundaries

The ordinary `landing` profile covers M/S/U and `mseccfg.MLPE` as well as
lower-mode LPE controls. `kind = "landing-recovery"` first blocks fetch at an
indirect target with PMP. It checks the instruction access fault, saved MPELP
and exact target PC. The handler repairs PMP, restores x7 and returns. The
second trap checks the valid, missing or mismatching LPAD outcome. Half the
cases disable the target mode's LPE before MRET and check that ELP clears.
With C in the ISA, a two-byte-aligned LPAD also tests the four-byte requirement.
The example declares eight PMP entries through `landing.pmp_entries`.

These are synchronous fetch-fault recovery tests. They do not establish
asynchronous interrupt, Debug Mode or guest ELP preservation.

The `shadow` profile crosses S/U with x1 and x5. Its 48 programs cover stack
round trips, mismatch, read-only page repair, ordinary pages, Bare mode,
normal stores and loads, forbidden instruction fetch, misaligned pointers,
and guard pages at each end. Fault cases check the pointer stays unchanged. Misaligned-pointer cases use
CSR readback. They accept legal WARL alignment and check normal execution, or
require an access fault if the CSR retains a misaligned pointer.
Read-only recovery saves x5 before the handler uses it and restores it before
retry. Ordinary loads check the value stored by SSPUSH. Guest shadow stacks,
SSAMOSWAP and compressed shadow instructions remain open. Native Spike
self-checks do not establish DUT coverage.

## State-enable hierarchy and zeroing behavior

`kind = "stateen-hierarchy"` selects Smstateen 1.0 tests from the pinned
20260120 ISA. `stateen.probes` selects `stateen`, `envcfg` and `zfinx`.
`stateen.writable_bits` declares the selected gates as writable: bits 63, 62
and 1 respectively. The generator checks all four matching state-enable CSR
indices and actual M/S/U entry. With H, it adds VS/VU and independent machine,
hypervisor and supervisor gates. It distinguishes cause 2 from cause 22 and
checks the fault PC. Supervisor CSR access from U raises cause 2. VU access raises cause 22
when the same operation is permitted in HS. A denied machine gate retains
cause 2 priority. State-enable probes also check a different CSR index remains
accessible. Zfinx
FCSR tests require Zfinx in the selected ISA. Gates for other extension state
and Ssstateen-only implementations remain open.

`kind = "envcfg-zero"` checks CBO.ZERO with independent menvcfg, henvcfg and
senvcfg CBZE settings. It checks every doubleword of the selected block and
both neighbors after success. A denied operation must leave the block intact.
The operation uses an address inside the block. The example selects 64 bytes
through `envcfg.block_bytes`. Native Spike gets the same `--blocksz` value.
The project must configure its DUT with that block size. H adds real VS/VU
entry and virtual-instruction traps. This tests zeroing behavior. It does not
establish cache clean/flush/invalidate effects or timing.

## Reset during in-flight activity

`kind = "reset-inflight"` crosses cold/warm/local reset with project-selected
fetch, load, store, trap and debug phases. The example repeats each pulse three
times and emits 15 programs. A retained RAM cookie counts actual restarts.
No acknowledgement can make a waiting program pass without restarting it.

Each `reset.phases` entry declares a name, prepare/cleanup actions, a positive
`min_wait_ticks` and an independent masked `state` gate. `PhaseDriver.service`
first prepares the operation. On a later reference tick, it applies reset only
when all state gates match. It then releases held resources and acknowledges
the mailbox request. A failed reset still releases resources and gets no ack.
The project resolves action names and state names to its own adapter. Example
actions are declarations. They are not implemented RTL bindings. The plain
MailboxDriver rejects phased events so it cannot bypass the state gate.

Capture PhaseDriver receipts as `privilege_reset_phase`. The checker requires
one complete receipt per pulse, ordered preparation/reset ticks and the actual
in-flight state. It also requires the existing `privilege_reset` pulse/state
capture and strict architectural comparison. Missing observations remain
inconclusive. Native Spike CLI cannot drive these project reset phases, so
compilation and driver fixture checks do not establish reset qualification.

C1 matching uses ELF hash and requested input identity before checking result
uniqueness. A result from another stimulus cannot hide a matching failure.
Multiple results for the same input remain inconclusive.

## PMA crossing and atomic probes

`kind = "pma-access"` takes explicit `pma.probes`. Each probe supplies a name,
address, width, operation and expected cause. Cause 0 means success. Read/LR/SC
and AMO success also supply the returned `result`. `readback_value` can check a
write independently. Supported operations are read, write, amoadd, amoswap, lr
and sc. Write operations require `test_writes = true`. AMOs require A. Programs
check exact fault PC and mtval. Projects select misalignment and conflicting
attribute outcomes. The generator does not invent an overlap-priority rule.

`transfers` declares the complete ordered bus sequence within the single probe
window. This supports split accesses at different addresses and zero transfers
on denial. Capture from `pma_probe_start` until `pma_probe_end` or the operation's
trap. Exclude setup and later readback. The checker compares the whole sequence,
so an unexpected transfer at another address cannot disappear from the count.
Independent `device_state` remains required. Missing contracts stay inconclusive.

The Spike CLINT example selects `pma.spike_compatible = true`. It checks scalar
widths, misalignment and LR/SC versus AMO behavior in Spike's native map. This
flag requests execution. It cannot configure or change that map. Custom maps
omit the flag and remain inconclusive on native reference. The crossing example
is project data for two possible policies. It is not a universal RISC-V rule.
These tests do not qualify cacheability, idempotency or real device side effects.

Base PMP project data now declares `pmp.entries` and `granularity_bytes`.
The bootstrap requires at least eight entries. Granularity is a power of two
from 4 to 4096 bytes. NA4 is selected only at four-byte granularity. Optional
`address_modes` selects supported TOR/NA4/NAPOT modes. Larger regions use the
declared grain in alignment and address encoding. Spike smoke tests exercise
the programs; they do not prove the declared hardware grain. The fallback TOR
lower bound is initialized explicitly, so a stale pmpaddr6 cannot exclude the
program from the fallback region.

## PLIC interrupt delivery

`kind = "plic-delivery"` selects project `plic_delivery.targets`. Each target
supplies M/S mode and a context index in the existing `plic` register map.
Six example programs cross M/S delivery with global masking, local masking and
threshold blocking. Each establishes an inactive source baseline, asserts it,
checks pending state while blocked, then unmasks delivery. The handler checks
interrupt cause, exception-PC range, saved enable/privilege state and claim ID.
It deasserts the source before completion, disables local delivery and returns.
The main code checks retained registers and an empty claim. Supervisor success
returns through a checked ECALL to M-mode before writing tohost.

`settle_ticks` declares the adapter's source-settling delay before mailbox ack.
A project source callback must honor it. Python-only reference results describe
the controller expectations. They do not establish CPU execution.

For short native execution, set `reference_backend = "spike-python-plic"` and
`reference_shim` to a shim built by `Cosim/build.sh`. This backend runs the
actual ELF in Spike and supplies PLIC MMIO/IRQ from the Python model. A claim
read is previewed on a copy. Its side effect is committed only if the CPU
executes the load, so an interrupt before the load cannot consume the claim.
All requested mailbox events must complete before pass. Execution has time and
instruction bounds. The shim and linked library use the existing input-capture
contract. Reports bind native and Python source hashes. Their evidence remains
model-based. Source settling uses instruction steps here and makes no clock
latency claim. This backend does not qualify a native Spike PLIC or an RTL PLIC.
Concurrent context races and real-core delivery still need project tests.

## RERI status transactions and CE counters

`kind = "reri-transactions"` pins the same RERI v1.0 release. It requires
`reri.logging_writable = true` and CE reporting. Three programs test valid
status-write protection, the SRDP/SINV read race and disabled logging. Declaring
`reri.ce_counter_bits = 16` adds four programs for increment, rollover, disabled
counting and enable changes. Other counter widths are rejected by this profile.
Wide reference values use hex strings.

Programs first invalidate the record, then write their seed status. They do not
check a reset value. The first control action has no status assertion, so prior
valid, history and counter state cannot create a false initialization failure.
The model tests several starting values. `reri.reference_initial_status` can
select a nonzero native model state. It is a reference input, not a DUT reset
contract. The example uses a valid record with a full counter.

`reference_backend = "spike-python-reri"` and `reference_shim` run the actual
ELF with the Python RERI device through the same captured Spike execution path
as PLIC. The shared path commits MMIO effects only for executed instructions.
Error events call the model's hardware-error entry. They do not emulate hardware
injection by writing status. All seven self-checks pass with the example's
nonzero initial state. Reports remain model-based. They make no RAS signal-
delivery, poison-propagation, physical correction or DUT recovery claim.

## Smrnmi entry state and MNRET

`kind = "nmi-return"` pins `spec_version = "Smrnmi-1.0"` and runs six native
MNRET programs. They write a return PC and M/S/U mode, check that software cannot
clear NMIE, and execute MNRET with MPRV set. After a checked ECALL, they verify
NMIE set, exact return PC, retained registers and MPRV cleared for lower-mode
return. These test the return instruction. They do not inject an RNMI.

`kind = "nmi-matrix"` emits 12 project-driven entry programs with the full
example. It crosses M/S/U, ordinary exception nesting and an ordinary MSIP
pending during the RNMI. It checks saved MNPP, mnepc, mncause and NMIE. A PMP region that denies S/U access checks that NMIE=0 makes MPRV ineffective in the handler.
Ordinary pending interrupts must wait until MNRET returns. Their handler checks
that the exception PC lies in the resumed program. Nested exceptions preserve
the RNMI frame. The project declares the RNMI vector and either a distinct
`exception_vector` or `exception_uses_mtvec = true`. The generator does not
assume those implementation-defined vectors are the same.

The entry profile requires eight PMP entries and grain at most 16 bytes.
The example declares both. It follows Smrnmi without Smdbltrp. Double-trap,
guest and CFI RNMI frames need separate profiles. Native Spike does not model
external RNMI entry or these project exception vectors. Entry reference results
come from the small Python state model and remain model-based. Compilation,
model checks and native MNRET success do not establish DUT RNMI entry, reset
interaction or machine-error recovery.

## Fast-interrupt preemption and jump tables

`kind = "fast-preemption"` uses the existing fast-interrupt v0.20 pin. The
project declares at least two hart-local sources, eight priority bits and its
implemented `group_bits`. The example selects 0, 4 and 8 grouping bits. Twelve
programs test higher, lower, equal and same-group priorities. They configure
Smidctrl source, enable and priority CSRs, then request actual edge events.
The outer handler saves mistatus and mepc. The inner handler checks the current
threshold and saved previous threshold. Software restores the outer frame before
MRET. A deferred source must enter only after the outer handler returns. Zero
grouping bits disable nested preemption but permit delivery at threshold 256.

`kind = "fast-vector"` adds the Smijt interrupt jump table. Project data selects
`ijt_base`, `common_address`, `handler_address` and `table_shifts`. The example
crosses MSIP, MTIP and an external minor identity with two table strides and
VEN/address-bit values 0, 1 and 3. It checks signed negative major offsets,
positive minor offsets, common-dispatch fallback and IALIGN address masking.
The C profile uses a two-byte-aligned handler to distinguish the masks. The
program checks mode-3/mijt readback, exact interrupt PC, cause and saved threshold.

Input kinds `aclic-baseline`, `aclic-edge` and `fast-source` are project driver
contracts. The baseline deasserts the listed sources. Edge events pulse the
selected source. fast-source asserts/deasserts the selected major/minor input.
The first interrupt is gated at the named wait symbol. Adapters must drive
actual inputs. An ack without input activity cannot make these self-checks pass.
The fixed registers and encodings follow v0.20 Smidctrl/Smnip/Smijt. They do not
implement the old CLIC layout. Unknown version pins are rejected.

All 48 programs compile and have model-based expected outcomes. Installed Spike
has no model for these v0.20 extensions. The Python models supply grouping,
threshold-save/restore and jump-table expectations. They do not establish actual
nested entry, table memory permissions or DUT delivery. Supervisor variants,
interrupt table faults and interrupted trap entry remain open.

## Independent DVFS clock edges

The DVFS example now declares `dvfs.clock_measure`. It selects reference_hz,
minimum high/low pulse ticks, period tolerance and settling ticks. Optional
max_switch_ticks and max_edge_gap_ticks add project timing bounds. Generation
rejects invalid assumptions. The bounds are project data, not RISC-V requirements.

A C1 `privilege_clock_edges` artifact records reference_hz, complete,
start_tick, end_tick and an ordered `edges` list of tick/level pairs. Level is
the post-edge Boolean clock level. Reference ticks come from an independent
clock. `EdgeRecorder` can build this artifact from one sample per reference tick.
A missed tick or unknown level marks its capture incomplete. Do not sample it
from the core clock that can stop or change.

The checker requires complete edge capture when clock_measure is selected.
It checks pulse bounds across the switch and at least three rising edges in
each long stable window. It compares periods with reference_hz/frequency_hz
using exact fractions. Stable windows cover the initial state and every target
after acknowledgement plus settling. Short windows remain inconclusive. A
complete long window with missing edges fails. Handshake order and voltage-state
checks remain required, as does the strict C1 architectural gate. Reports bind
the edge-capture hash. This checks sampled digital behavior. It cannot detect
sub-tick pulses or qualify analog voltage, physical timing or PLL behavior.

## Model-based C2 observation groups

Fast-preemption, fast-vector and RERI transaction builds now name their model
observation sites in the ELF. `privilege check` can compare the C2 values at
those sites with the pinned Python model. It checks read type, address/CSR,
privilege mode, mask, count and ordered values. Vector cases also require the
selected handler address to execute. Each checked instruction must match the
ELF bytes. A complete C2 end status and matching ELF/core/config identity are
required. Reference traces are rejected for C1 observation groups.

Results put these checks in `model_subset`, `model_groups` and `model_counts`.
They say evidence=model-based and bind trace/model-source hashes. Every group
member must have a conclusive observation result. Missing reads or required PCs,
unknown versions, changed bindings and incomplete traces remain inconclusive.
A known value mismatch or failed C1 self-check fails. These groups cover the
listed reads and code addresses. They do not compare all instructions.

Architectural `groups`, `counts` and overall pass retain the complete strict
ISA-reference requirement. A passing model group leaves architectural status
inconclusive when that reference is unavailable. The checker does not run an
unsupported Spike extension model and mislabel its illegal CSR response as a
DUT architecture mismatch. Consumers must select the evidence scope they need.

Native Spike/Python-device runs also write `*.reference.jsonl` C2 traces with
explicit reference/model-based tags. They support oracle smoke tests. They
cannot earn C1 observation groups. Native backend registration is kept separate
from campaign-kind lists and has routing regression tests.


## Extension-state access probes

The state-enable hierarchy also selects `jvt`, `aia`, `csrind`, `imsic`,
`context` and `zfinx-op`. The gates are bits 2, 59, 60, 58, 57 and 1.
Projects must declare these gates writable and declare each required extension.
Context probes require `context_supported = true`. The Zfinx instruction probe
checks the FADD.S result in an integer register. Other probes check CSR access.
`guest_index` selects the VS IMSIC file. Zero requires a virtual-instruction
exception. A nonzero guest file has no native Spike CLI reference in this profile.

The extension examples pin Smstateen 1.0. The Python reference checks the access
and trap expectations. C2 model observations check the exact cause/PC, successful
instruction mode and virtual state, and absence of retirement for denied access.
A zero read mask checks CSR access only, with no claim about WARL data values.
These groups remain model-based. Native examples select the subset supported by
the installed Spike. Neither result establishes DUT coverage. Ssstateen-only
implementations and RV32 high-half state-enable access remain open.


## Seeded privilege transitions

`kind = "random-transitions"` uses project `random_transitions.seeds` and
`steps`. Each seed makes one RV64 program with up to 256 steps. The example
pins the 20260120 privileged ISA and uses four seeds with 32 steps each.
Each step selects M/S/U, an illegal instruction, EBREAK or ECALL, and legal
exception delegation to S. It checks cause, exact PC, saved privilege and a
retained register. The handler returns with MRET or SRET. A second checked
ECALL returns control to M before the next step. ECALL itself is not delegated.

The manifest records the complete transition plan. Functional groups distinguish
origin mode, operation and destination handler. Native Spike runs the actual
self-checking programs. DUT use follows the existing C1 suite and strict
reference path. This bounded generator does not cover interrupts, guest modes,
nested handlers, page translation or arbitrary CSR writes.

## RV32 state-enable banks

`kind = "stateen-rv32"` pins `Smstateen-1.0`. The two examples select RV32
with and without H. They generate 48 and 160 programs. Probes cover SE at
all four bank indices, ENVCFG, indirect CSR access and the Zfinx FCSR gate.
Project `stateen.writable_bits` declares the selected gates. Bit 1 and bit 63
must also be writable for split-bank retention checks. Zfinx must be present.

Programs write low and high halves separately. They check selected-bit readback
in M, the higher-level mask on H readback, the retained opposite half and an
independent SE bank. Guest entry uses `mstatush.MPV`. Access checks require the
expected cause and exact fault or ECALL PC. U and VU access restrictions remain
part of the matrix. RV32 uses a two-word tohost store.

The compiler ISA uses only the assembler features needed by these numeric CSR
instructions. The reference ISA retains Smstateen, Sscsrind, Zfinx and H where
selected. Native Spike checks actual programs. This suite does not establish
DUT coverage. Ssstateen-only implementations and other extension-state gates
remain open.

## Ssstateen without Smstateen

`kind = "ssstateen-only"` pins `Ssstateen-1.0`. The two examples select RV64
with and without H. They generate 24 and 80 programs. No program writes a
machine state-enable CSR. Probes cover the four supervisor state-enable banks,
SENVCFG, indirect CSR access and the Zfinx FCSR gate. Optional probes select
JVT and Zfinx arithmetic. Project data must declare their ISA extensions.

Without Smstateen, there is no machine gate to block S access. With H,
`hstateen` controls guest access. Supervisor user-state gates still control
U and VU access. `stateen.writable_bits` declares the selected H gates and
supervisor user-state gates. Without H, only the user-state gates need entries.

The installed Spike rejects the Ssstateen extension name. The examples therefore
select the Python reference backend. Expected causes, exact trap PCs, access
observations and denied instruction encodings use the existing named-observation
path. Results and subset groups are model-based. They cannot establish full ISA
comparison or DUT coverage. RV32 Ssstateen-only and other extension-state gates
remain open. The RV32 Smstateen suite above has separate native Spike evidence.

## WFI stop before wake input

`kind = "wfi-stop"` is an opt-in project clock-stop campaign. It pins the
20260120 privileged ISA. The example selects software, timer, external and
project interrupt 16. A project selects distinct implemented causes from
1/3/5/7/9/11 or 16..63 and supplies its source names. Each cause has global
MIE off/on cases, with the local enable set. These are RV64 M-mode programs.

`StopWakeDriver` takes the row's event and resolved ELF symbols. Call
`service(request, drive, acknowledge, tick=..., snapshot=...)` once per
independent reference tick. A snapshot has `clock_running`, `wfi_active`,
`wfi_pc`, selected-source `pending`, `retired` and project `state` values.
The driver waits for the exact WFI PC, a stopped clock and no selected pending
input. It then waits `min_stop_ticks` before asserting that input. It keeps the
input asserted until restart, `pulse_ticks` and the program's delivery witness
step 2. It then releases the input and acknowledges step 2. The program waits for this acknowledgment before reporting pass.
Call `close(drive)` in the adapter's finally block to release an input on error.
The generic `MailboxDriver` rejects these events.

Write `driver.capture()` as the C1 `privilege_wfi_stop` artifact. The checker
requires consecutive independent ticks, actual WFI and clock-stop observations,
retained masked state, no stopped retirement, observed pending input, restart
within `max_wake_ticks`, input release and resumed retirement. State names and
masks come from project data. Bind `retained_gpr` in the example to x8. Select
state that must remain stable during the stop and after wake.

Spike CLI does not model this external clock/input protocol. The examples use
a Python outcome model and named C2 cause/PC, pending-bit and retained-register
observations. All subset results are model-based. Complete architectural groups
remain inconclusive without a full reference. No physical clock-gating or DUT
result is claimed. The sampled pause is a project feature check. WFI may legally
return early. Without an observed stop, this campaign remains inconclusive and
does not drive the wake input. The ordinary WFI suites impose no minimum sleep.
NMI/reset wake and guest-mode stop scenarios remain open.


## AIA named claim observations

IMSIC M/S/VS and APLIC direct/MSI campaigns use named C2 observations.
IMSIC checks the two injected pending bits, the selected IRQ bit, an empty peer
file and three combined TOPEI read/write claims. APLIC direct delivery checks
the pending bitmap and claim loads. APLIC MSI checks five combined TOPEI claims
for each source-mode sequence. Expected values come from the pinned Python
controller models. Model bindings require the proper CSR instruction or MMIO
address, privilege, count and values. Read-only CSR instructions cannot stand
in for a claim operation.

MSI stores may reach an interrupt file later. Programs poll for all injected
pending bits before checking priority. They also poll the expected IRQ state.
`imsic.poll_iterations` selects the instruction bound. `peer_identities` declares
the peer file size; it defaults to `identities`. Programs initialize every
declared peer bank. APLIC direct programs poll their pending bitmap first.
`aplic.poll_iterations` selects direct/MSI wait bounds. These project bounds
do not assert an architectural maximum delivery delay. APLIC MSI currently
requires an M interrupt file and clears all its declared pending/enable banks.

The selected AIA document revisions are the 20250312 source above and the
original 2023 source `f24dd483d50e6a1448116dcf88b8b08e0863512c`. Other
revision strings fail closed. Model subset groups remain separate from full
architectural groups. Compilation and Python reference checks do not establish
DUT execution, full interrupt-file state, bus delivery or whole-ISA comparison.

## APLIC delegation and revocation

`kind = "aplic-delegation"` selects two direct-delivery domains. Project data
supplies parent/child bases, their contexts, the child's index, the implemented
source count and the selected source IDs. `direct_delivery` must be true.
The example selects sources 1 and 33, which use different pending/enable words.
It pins AIA 1.0 document revision 20250312.

Each program first makes all declared root sources inactive. It then delegates
one source, configures the child as Detached, and injects a software pending
bit. Parent pending/enable writes must be ignored. Only the child can claim the
source. The program next revokes delegation. Child state must read as zero,
and only the parent can claim. A final delegation checks that the child's
source configuration returns to zero before software enables the source again.
Every claim sequence must return the source once and then zero.

The Python model checks domain ownership and the transaction sequence. Named
C2 bindings check 24 MMIO observations per program, including masked pending
and enable bits, source configuration and claims. Results and subset groups
remain model-based. No native APLIC device, DUT execution or whole-ISA match
is claimed. The suite does not cover arbitrary child trees, MSI delegation,
wire-source transitions during reassignment or complete interrupt delivery.

## Native ISA execution with APLIC MMIO

`reference_backend = "spike-python-aplic"` runs actual `aplic`,
`aplic-delegation` and `aplic-priority` programs through the captured Spike library. Set
`reference_shim` to the project's built shim library. The existing capture
records the library and manifest hashes. The shared runner writes normalized
reference C2 traces, program status and instruction counts. Programs without
mailbox events need no artificial stimulus symbols.

Python supplies the APLIC registers. This model supports little-endian aligned
32-bit accesses, Inactive/Detached sources, direct delivery register state,
per-context priorities/thresholds, claims and one parent/child domain. It checks
target context, masks unowned state and resets new child configuration. It uses
project `priority_bits` from 1 to 8 for priority and threshold fields, with
a default of 8. It supports context indices 0..511 within
a 32-KiB control map per domain. Unsupported wire modes, MSI mode, access shapes,
child indices and uninitialized target fields fail closed. Claim preview does
not consume a source when a load has not executed.

Native results remain model-based. The IRQ input is held clear, so this backend
makes no IRQ-line delivery claim. A native pass checks ISA execution and the
Python register behavior. It is not a hardware APLIC or DUT pass. Reference-tagged
C2 traces cannot earn C1 model groups. The normal DUT checker still requires a
separate C1 result with matching input identity and actual DUT observations.


## APLIC implemented priority width

`aplic.priority_bits` selects IPRIOLEN from 1 to 8. It defaults to 8. The
normal direct-delivery cases select priorities and legal thresholds that fit
that width. With one bit, all source priorities are 1. The threshold case
therefore uses threshold 1, which suppresses all eligible source priorities.

`kind = "aplic-priority"` checks target-field conversion and readback. It writes
zero, normal values, high bits and the implemented limit. Zero low bits must
read back as priority 1. Unimplemented high bits must not remain in IPRIO.
The program also checks legal threshold equality, zero unmasking and claim
clearing at priority 1 and the maximum supported priority. Delivery controls
remain clear, since TOPI/claim state is independent of delivery enables.

The project supplies the base, context, implemented source count and selected
`source_id`. The example pins AIA 1.0 document revision 20250312. Programs
clear all declared root source configurations before using a Detached source.
Python and native Spike/Python-APLIC backends are available. Named MMIO
observations and all results remain model-based. Reserved WLRL threshold writes,
IRQ-line delivery, wired inputs and DUT qualification remain open.
