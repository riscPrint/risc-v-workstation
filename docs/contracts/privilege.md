# Privilege and interrupt suites contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Pointer-masking privilege matrices

`rvw.mmu/1` may contain `pointer_matrix` with `modes`, `extensions` and
`controllers`. Supported modes are sv39, sv48 and sv57. Extensions are smnpm,
ssnpm, smmpm, sspm and supm. Sspm/Supm require explicit controller declarations
in the project: `sspm = "smnpm"` and `supm = "ssnpm"` for this backend.
These capability names do not define separate CSRs. Scenarios may declare
`pointer_extension` and `pointer_controller`. Ssnpm selects senvcfg.PMM with
MPRV effective U privilege. Smmpm selects mseccfg.PMM for Bare M-mode data.
Smnpm selects menvcfg.PMM with effective S privilege. Tagged instruction fetch
under Ssnpm/Smnpm must fault even when data masking is enabled. The programs
check PMM readback, exact trap cause/tval/PC and successful data values.
The guest-pointer campaign below covers VS/VU HLV/HSV controls and HLVX
exemption. Debug interactions and nonstandard environment controls remain unsupported. The backend refuses inconsistent controller declarations.

## Split timer accesses and independent timer observations

`kind = "sstc-rv32"` selects RV32 low/high timer CSRs and ILP32. Timer-event
scenarios include `timer_contract`: source, ordered phases, ELF labels,
compare/delta values and optional reference-time precondition/latency bound.
Wide compare/delta values are hex strings. The `privilege_timer` C1 artifact
is a JSON sample list: integer tick/phase_start, phase name, independent
reference_time (integer or hex string), and Boolean pending. The checker binds
the artifact hash. It requires every phase witness, checks modulo-64-bit
virtual time and enforces a declared latency bound when present. Missing or
late-only evidence remains inconclusive. No architectural counter-read
synchronization is introduced, and sampled consistency is not a whole-core
or physical timing proof.

## Privilege campaign artifacts

IMSIC project data may select `file` as M, S or VS, `guest_index` for a VS
file and `identities` as 64*n-1. Programs bind their MSI destination page to
that selected file and check an uninjected peer. `kind = "aplic-msi"` selects
versioned edge/level-to-MSI programs. Mailbox payloads use `aplic-level`,
`controller_base`, `source` and Boolean `level`. Python reference reports bind
the gateway model source hash and retain their model-based scope.

`kind = "epmp-matrix"` selects the complete 16-encoding MML permission table.
Each scenario records `expected_allowed` and its pinned Smepmp specification
URL. Separate bins cross L/R/W/X with actual/effective privilege and access
kind. RLB is cleared before the access probe. Existing C1 and strict-reference
requirements still apply.

`kind = "disabled-matrix"` selects `disabled.feature` and all 64 requested
six-control masks. Profiles cover disabled FS/VS state and absent F/V/S
features. `requested_controls` in each scenario records the requested mstatus
word. Programs capture WARL readback and account for MRET clearing MPRV.
Requested-bin membership never asserts that an optional WARL bit latched.

Kinds `reri` and `dvfs` use the same model-based reference report and mailbox
stimulus contract. RERI pins its revision in project data and derives expected
record updates and signal requests from the versioned model. Its error payload
is a hardware-injection request, not proof that the error was handled.
`privilege_dvfs` is a C1 JSON sample-list artifact. Samples contain `tick`,
`step`, `phase`, `frequency_hz`, `voltage_uv`, `clock_ready`, `voltage_ready`.
The checker binds its hash and checks the complete ordered handshake against
project states. Digital sequencing never implies analog voltage or PLL proof.
Known C1 self-check failures remain failures when optional observations are
missing.

Kinds `sstc`, `stateen`, `envcfg`, `landing` and `shadow` select RV64
extension campaigns. Sstc requires Zicntr in the reference ISA. Optional
`sstc.virtualization` requires H and adds VS control cases. `envcfg` declares
`implemented_mask` and optional `henvcfg_mask`; these are implemented-bit
expectations, not permissive WARL guesses. The existing strict C1 check is
required before any architectural group passes.

Kinds `imsic`, `aplic`, `aclint` and `smnip` select versioned controller
programs. `spec_version` pins the implemented version; `spec_revision` records
an optional immutable source revision. `reference_backend = "python"` selects
small executable reference models. The reference report adds `evidence =
"model-based"` and `model_sha256`, mapping model source files to hashes.
Its scenario outcomes are model observations, not native Spike or DUT results.
The normal C1 plus complete strict-reference gate remains unchanged.

Kinds `pmp`, `epmp` and `pma` generate separate protection matrices. PMA
scenarios require a `privilege_bus` C1 artifact: `complete` is Boolean,
`transfers` hold address/width/write and `device_state` holds independent
project state. The configured counts, transfer shapes and state must agree.
Missing state or an incomplete capture remains inconclusive. Reports bind the
artifact hash. These observations do not replace the strict architectural check.

`compiler_isa` optionally selects compiler instruction parsing. `isa` still
selects the reference model architecture. Numeric encodings can therefore be
compiled with a base assembler without claiming extension model support.

Kinds `plic`, `reset` and `nmi` emit `rvw.stimulus/1` device events. Each
payload has a positive `step`, request/ack ELF symbols and project event data.
The adapter applies events in order and acknowledges each step after driving
it. Optional `when_pc` requires the resolved architectural PC. Build manifests
bind the stimulus hash; C1 must record `stimulus_sha256`. Reset campaigns also
require a `privilege_reset` artifact containing one list of ResetSample objects
per requested pulse. Samples use `cycle`, `asserted`, `state` and `valid`.
The report binds the observation hash and requires the existing independent
reset contract check. Missing evidence remains inconclusive.

`kind = "scheduled-wfi"` emits per-program suites with C1 `irq_schedule`.
`wake` declares assertion/clear cycles and optional retained-state masks in
`clock_state`. The optional C1 artifact `privilege_clock` holds a JSON sample
list: `tick` is the reference edge, `clock_running` is a Boolean, `state` maps
names to integers, `retired` is cumulative retirement and `pending` is Boolean.
Unknown values can be null. The checker requires a complete observed pause
and restart, stable masked state and a pending event during the pause. It binds
the artifact hash. A missing artifact is inconclusive. The artifact reports
project harness observations; Spike CLI cannot supply clock-stop evidence.

The optional `kind = "disabled"` selects FS-Off or absent-supervisor matrices.
`priv = "mu"` selects absent supervisor operations. Otherwise FS-Off requires
F in `isa`. The reference forwards `priv` to Spike. These cases use the same
build, reference and check schemas.

`rvw regress privilege build` reads `rvw.privilege/1`: `modes` selects distinct
M/S/U modes and `isa` selects an RV64 compiler and Spike ISA string. The current
control matrix requires `priv = "msu"` when given. It writes self-checking ELFs,
sources, a linker script, a suite fragment and `rvw.privilege-build/1` manifest.
The manifest records the description hash, specification URL, configuration,
scenario IDs, ELF/source hashes and functional group names in `bins`.

`reference` writes `rvw.privilege-reference/1` JSON to stdout. It records command,
return code, model hash and per-scenario self-check status. It is reference-only.
`check` writes `rvw.privilege-check/1`: it binds the build manifest and each C1
result by SHA-256. A group passes only if every member has a passing C1 result
and a complete strict Spike match with a passing end event, positive instruction
count and zero synchronizations. Missing or duplicate evidence is inconclusive.
These artifacts do not change C1, C2 or C3 and do not grant C4 acceptance.

The privilege description also accepts `kind = "wfi"` and a `timer` object with
integer `mtime`, `mtimecmp`, `msip` and `delta`. The generator programs the
project-owned timer/software device and crosses the two sources with MIE
clear/set. The delta is in timer ticks. C1 execution bounds the wait. It makes
no minimum sleep or physical clock-gating claim. Builds include
`functional-groups.json` for C2 observation coverage. Observation hits do not
grant the architectural pass groups from `privilege check`.


## CFI recovery project data

Privilege campaign kind `landing-recovery` selects the Zicfilp fetch-fault
recovery matrix. It requires RV64 Zicfilp and `landing.pmp_entries >= 8`.
A C-capable ISA also selects two-byte-aligned target cases. Project data uses
the existing `rvw.privilege/1` schema. Generated artifacts and C1 qualification
use the common privilege campaign contract. Model self-checks do not earn DUT
coverage. The shadow profile names its selected architectural register in each
scenario ID and functional bin.

## State-enable and CBO.ZERO project profiles

`rvw.privilege/1` adds kinds `stateen-hierarchy` and `envcfg-zero`. The former
uses `stateen.probes` and `stateen.writable_bits` for the declared Smstateen
implementation. The latter uses `envcfg.block_bytes`, a power of two from 16
to 4096. The generated manifest records `reference_options` for the matching
native Spike cache-block size. This field configures the reference process.
It does not configure a DUT. Native results retain the Spike self-check scope.
DUT coverage still requires the existing C1 and strict-reference evidence.

## In-flight reset observations

Campaign kind `reset-inflight` uses `reset.phases`: name, prepare, cleanup,
min_wait_ticks and state. Each state entry has value/mask fields. Events carry
these as `phase`, `prepare`, `cleanup`, `min_wait_ticks` and `phase_gate`.
Adapters must use PhaseDriver or enforce the same preparation and observation
order. The driver invokes reset-prepare, the actual reset event and reset-cleanup.
It acknowledges only after successful reset and cleanup.

The `privilege_reset_phase` C1 artifact is a JSON list. Each receipt has step,
prepared_tick, reset_tick, state and complete. Ticks use an independent reference
clock. State is captured before the pulse. The checker binds the capture hash
and still requires reset pulse observations and architectural evidence. C1
selection matches ELF and requested stimulus/options before checking uniqueness.

## PMA access probes and PMP capabilities

`rvw.privilege/1` adds kind `pma-access`. Project `pma.probes` entries carry
name, address, width, operation, cause and optional result/value/readback_value.
Writes require test_writes. The existing PMA expectation gains optional
`transfers`: the full ordered address/width/write sequence in the probe window.
An empty list requires no bus transfers. Independent device_state and complete
capture remain required. The count-only form remains supported for old probes.
`pma.spike_compatible` requests native execution against the installed Spike
map. It does not change PMA attributes or waive a reference failure.

Base PMP data may select entries, granularity_bytes and address_modes under
`pmp`. The matrix requires at least eight entries. Unsupported NA4/granularity
combinations are rejected. Program generation uses the selected grain and
honors project mode selection for priority probes too.

## PLIC delivery reference execution

Campaign kind `plic-delivery` adds project `plic_delivery.targets`, each with
mode and context, and positive settle_ticks. Its source events retain the
mailbox protocol. `reference_backend = "spike-python-plic"` requires
reference_shim and runs the ELF through the captured native Spike shim with a
Python PLIC. The reference report records evidence=model-based, input capture,
source hashes, instruction count, traps and stimulus completion. Native self-
check success requires tohost=1 and all source events acknowledged. Bounds,
unsupported operations or incomplete input remain inconclusive. This reference
result does not earn DUT coverage or replace the C1 architectural gate.

## RERI transaction reference profiles

Campaign kind `reri-transactions` uses the RERI-v1.0 pin. Project data declares
logging_writable, supported classes and optional ce_counter_bits=16. Optional
reference_initial_status selects native model startup state and uses a hex
string for wide values. It is not a hardware reset expectation. Transaction
plans record kind/value/observe and hex status expectations. The initial
invalidation action is not observed before software writes a seed status.

`reference_backend = "spike-python-reri"` requires reference_shim. It executes
the ELF with a Python MMIO record. The report remains evidence=model-based and
binds the captured shim/library and Python sources. It records hardware-error
model events separately from software status/control writes. This profile has
no physical RAS signal route and makes no signal-delivery claim. Native PLIC
and RERI execution share a bounded ISA/MMIO runner; their models stay separate.

## Smrnmi project vectors and state profiles

`rvw.privilege/1` adds `nmi-return` and `nmi-matrix` with `Smrnmi-1.0` pinned
in spec_version. Entry data selects vector, cause, exception_vector or an
explicit exception_uses_mtvec flag, pmp_entries and pmp_granularity_bytes.
Optional ordinary_msip enables pending ordinary-interrupt cases. Entry events
are gated at rnmi_wait through the existing mailbox driver. Python expected
frames remain model-based. The native return profile tests MNRET only and does
not substitute a software CSR setup for hardware RNMI entry.

## Fast-interrupt runtime profiles

Kinds `fast-preemption` and `fast-vector` use the pinned
riscv-fast-interrupt-v0.20 model. fast_interrupts declares sources,
priority_bits, group_bits and, for vectoring, ijt_base, common_address,
handler_address and table_shifts. This RV64 profile requires two sources and
eight priority bits. group_bits may be zero. Miconfig remains at the v0.20
mireg4 CSR number. The profile rejects incompatible register selection.

Mailbox payloads add aclic-baseline, aclic-edge and fast-source. They represent
actual source state, not a replacement software write of trap CSRs. Reference
plans record grouping decisions or hex jump-table addresses/targets. Reports
remain evidence=model-based. Compilation and reference-plan agreement do not
earn architectural DUT groups. Normal C1 stimulus binding and strict evidence
checks remain required.

## Independent DVFS clock measurements

Optional dvfs.clock_measure declares reference_hz, min_high_ticks,
min_low_ticks, period_tolerance_ticks, settle_ticks and optional max_switch_ticks
and max_edge_gap_ticks. A selected measurement contract requires the C1 artifact
privilege_clock_edges before the DVFS architectural group can pass.

The artifact has reference_hz, complete, start_tick, end_tick and edges. Each
edge has integer tick and Boolean level. Sampling uses independent reference
clock ticks. EdgeRecorder marks missed samples and unknown levels incomplete.
The observer checks sampled pulse bounds, complete stable-window periods and
selected timing bounds. It records the capture hash and retains missing or
short observations as inconclusive. A sampled digital pass is not analog or
PLL qualification. Existing handshake capture and strict architectural evidence
remain required.

## Model-based C2 observation scope

A scenario may declare reference_mode=model-observations, model_bindings and
model_required_pcs. The selected versioned model must reproduce those bindings.
Each binding supplies symbol, kind, expected values and optional mask/mode.
CSR bindings name csr. Load bindings name address and width. Wide values are
hex strings. Required PCs may be numeric hex strings or ELF symbol objects.

`rvw.privilege-check/1` adds per-scenario model_subset and aggregate model_groups
and model_counts. All group members must have evidence. This scope requires a
conclusive passing C1 result, matching input identity, a complete C2 trace,
matching ELF/core/config identity, exact ELF instructions at observation sites
and the model's read values/counts. It records evidence=model-based and hashes
of the trace and Python model sources. Reference-tagged traces cannot qualify.

Architectural groups and overall pass keep the strict full-reference gate.
Model subset pass leaves architecture inconclusive when no complete ISA model
exists. A known subset mismatch fails. Native device reference traces carry
config=reference and evidence=model-based and remain oracle evidence only.


## State-enable instruction observations

State-enable hierarchy rows can carry `reference_model.kind = "stateen-access"`
and `spec_version = "Smstateen-1.0"`. Their `model_bindings` include trap cause
and exception PC reads. Successful accesses also bind privilege and virtual mode.
An instruction-result binding uses `kind = "writeback"` and an exact `insn`.
`model_forbidden_pcs` names denied instruction symbols. A nontrapping retirement
at such a PC fails. Trap records do not count as successful retirement.
Missing required observations stay inconclusive. These checks earn only the
existing model-based subset groups, not complete architectural comparison.

Denied state-enable PCs also bind the expected instruction encoding. The ELF
must contain that encoding even when the instruction never retires. A changed
instruction gives an inconclusive model observation result.


## Seeded privilege-transition input

The `random-transitions` campaign requires `spec_version = "privileged-20260120"`.
`random_transitions.seeds` contains distinct nonnegative integers. `steps` is
an integer from 1 to 256. Each manifest row records `transition_plan` with the
selected mode, operation, cause, delegation and retained-register cookie.
The plan is reproducible from project inputs. It is not DUT evidence.
Existing strict architectural groups apply without a model-subset substitute.

## RV32 state-enable input

`kind = "stateen-rv32"` requires RV32 Smstateen, Zfinx and the pinned
`spec_version = "Smstateen-1.0"`. `stateen.probes` selects distinct entries
from `stateen`, `envcfg`, `csrind` and `zfinx`. `writable_bits` declares each
selected gate, plus bits 1 and 63 used for low/high retention checks. Indirect
CSR probes also require Sscsrind. H in the reference ISA adds VS/VU cases.
The compiler ISA may omit extension names when all instructions use numeric
CSR encodings. Functional CSR domains include the RV32 M/H high-half banks.
