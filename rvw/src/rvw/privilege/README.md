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
is model-based. The AIA source revision is
`f24dd483d50e6a1448116dcf88b8b08e0863512c`.

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
