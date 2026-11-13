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
are model tests. Programs currently cover machine interrupt files and one APLIC
context. Guest files, full virtualization, level-to-MSI conversion, vector
entry and asynchronous preemption need additional program campaigns. The model
rejects level-to-MSI requests rather than assume a gateway rule. Old CLIC drafts
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

Examples include `sstc-h.json` and `envcfg-h.json` for H profiles. These remain
RV64 campaigns. RV32 split timer accesses, all extension-state gates, complete
virtualization transitions, interrupted landing-pad sequences and guest shadow
stacks remain open. No C1 or DUT result is inferred from a native Spike pass.
