# C2. RVFI trace (`rvfi.jsonl`)

First line is a header, then one object per retired instruction in `order`:

```json
{"schema": "rvw.rvfi/1", "xlen": 64, "isa": "rv64imafdc_zicsr_zifencei", "core": "boom", "config": "small", "elf": "…"}
{"order": 0, "cycle": 52, "pc": "0x80000000", "pc_next": "0x80000004", "insn": "0x00000297",
 "mode": 3, "trap": false, "intr": false, "halt": false,
 "rs1": 0, "rs1_rdata": "0x0", "rs2": 0, "rs2_rdata": "0x0", "rd": 5, "rd_wdata": "0x80000000",
 "mem_addr": "0x0", "mem_rmask": 0, "mem_wmask": 0, "mem_rdata": "0x0", "mem_wdata": "0x0",
 "mem_fault": false}
```

Field meanings follow riscv-formal's RVFI spec (`rd` 0 means no write; `insn` for compressed
instructions holds the 16-bit encoding). Values are `"0x…"` lowercase hex strings. Optional extra
records, distinguished by an `"event"` key:
`{"event": "trap", "cycle": N, "cause": "0x…", "tval": "0x…", "intr": bool}` and
`{"event": "end", "cycle": N, "status": "pass"}`.
A trap event's `cause` and `tval` are the values the core writes to `xcause`/`xtval` (BOOM
writes 0 for illegal instructions, as the spec allows; Spike writes the instruction bits). An
adapter reads them from the core, not from its own decoding (BOOM's adapter reads the CSR
file for ECALL/EBREAK). `cycle` never decreases from one line to the next, events included: a
trap event whose `tval` arrives late is written before the next cycle's records.
`{"event": "irq", "cycle": N, "levels": "0x…"}` (optional) gives the levels of the interrupt
inputs the harness drives, in their `mip` bit positions (MSIP 3, MTIP 7, SEIP 9, MEIP 11), from
cycle `N` on. An adapter that writes these events writes one with the first sampled cycle and one
at every change; records of cycle `N` may come before it. `rvw cosim` takes an interrupt bit of a
`mip`/`sip` read from the core only with such evidence (see `rvw/src/rvw/cosim/README.md`).
Tools that report C2 values (for example `rvw cosim` mismatch JSON) use the same hex strings.

### Cosim platform policy audit

Cosim platform JSON permits the optional schema `rvw.cosim-platform/1`.
Unknown top-level settings and other schema values are errors. The existing
schema-free platform format remains supported. `rvw.cosim/1` results include
`platform_policy` with the selected privilege, misaligned, endian, absent-PMP
and ECALL choices. `applied_masks` contains objects with `reason`, `csr` and
`mask`. The CSR and mask are hex strings. Each entry is the union of masks
actually used for that reason and CSR across the compared trace. This list
is independent of the bounded recent synchronization history.

The cosim platform JSON declares `privilege_modes`, `misaligned` outcomes,
`endianness`, `absent_pmp_csrs` and `ecall_tval`. Missing keys retain the legacy
MSU, alignment-trap, little-endian, absent-PMP-trap and ECALL-zero defaults.
Unsupported policies must be refused. These settings do not permit arbitrary
trace values or broad CSR masks. See the exact settings and the
[C2/Spike/Sail comparison matrix](../Cosim/README.md#architectural-comparison-coverage).
### C2 version 2 (`rvw.rvfi/2`)

One schema supports `state`, `multihart`, `csr` and `fault` capabilities. A capability
can be used alone. `multihart` requires the `harts` header and the per-hart
records below. `state` requires the FP fields below on each retirement and
supports CSR snapshots and fault fields. The optional `csr` capability requires
C2/2 and a nonempty `csr_snapshot` set. It compares declared CSR state without
claiming FP observations. It retains all scalar instruction fields. It does
not permit FP fields unless `state` is also declared. Capabilities can combine.
For existing v2 producers, omitted capabilities mean `multihart` when `harts`
is present, and `state` otherwise. V1 keeps its existing scope. Missing state
in v1 or multi-hart-only traces is unavailable evidence, never a state match.
Single-hart Spike/Sail comparison refuses multi-hart traces before comparison.

#### State fields

The state capability retains version 1 instruction fields and adds:
`fd_valid` (boolean), `fd` (0..31), `fd_wdata` (64-bit hex), `fflags` (5-bit hex),
and `fcsr` (8-bit hex). `fd_valid` distinguishes no write from a write to f0.
`fd_wdata` contains the raw architectural FLEN=64 bits, including NaN boxing.
Do not canonicalize NaNs or change payload bits. When `fd_valid` is false,
`fd` and `fd_wdata` are not observations. `fflags` and `fcsr` are full state
immediately after this instruction, including synchronous trap entry.
The low five bits of `fcsr` must equal `fflags`. `fcsr` includes `frm`.
The checker compares these fields exactly. A backend without these observations
must refuse version 2 comparison. Version 1 keeps its integer-only scope.
Version 2 does not imply that a DUT adapter exports these fields.
FLEN above 64 remains unsupported. Multi-hart reference comparison is unsupported.

PMP platform settings: `pmp_granularity` is the minimum region size in bytes.
It defaults to 4 and must be a power of two. Spike applies it through
`cfg.pmpgranularity`. PMP entry priority follows the ISA: the lowest matching
entry wins. This priority is fixed and cannot be changed by a platform setting.
Sail refuses non-default grain until its configuration mapping is implemented.

The C2/2 `fault` capability allows scalar fault-access comparison without FP
fields. Missing FP state makes no FP claim.

Sail scalar fault observations use its independent instruction operands and
memory log. Within one virtual page, logged physical fragment offsets map to
attempted bytes. Completed masks and data include only logged fragments.
Overlapping fragments and split-page effects are refused. This does not add
partial-effect observation to Spike. A missing backend observation remains
an error. Synthetic fragments validate the adapter, not native partial faults.

C2 version 2 can declare `"csr_snapshot": ["0x300", "0x341"]` in its header.
Each instruction must then carry `"csr_state": {"0x300": "0x…", "0x341": "0x…"}`.
The key set must equal the declared set. Values are full XLEN state after the
instruction and synchronous trap entry, before the next reference step.
These snapshots check effects even if software never reads the CSR. They do
not assert that every changed CSR was captured. No CSR snapshot uses read
synchronization or a platform mask. Counters and external pending state can
differ with timing; include them only when the adapter can supply the same
architectural observation point. An unavailable backend CSR is an error.

Version 2 trap instructions can include `fault_access` with exactly these fields:
`addr` (XLEN hex virtual start address, access-relative), `rmask`, `wmask`,
`completed_rmask`, `completed_wmask` (integer byte masks), `rdata`, `wdata`.
Attempted masks describe bytes requested by the instruction, not successful
transfers. Completed masks must be subsets of the respective attempted masks.
Data is XLEN hex with valid bytes only in completed lanes. With no completed
lanes, data must be JSON null. Unknown data must never come from the reference.
Legacy `mem_*` fields still describe completed effects. A missing fault record
makes no claim about attempted accesses. This extension describes data accesses;
instruction fetch faults still use trap cause/tval.

Spike checks zero-completion scalar load/store attempts, compressed accesses
and LR/SC/AMOs. It computes address and width from its own instruction and
pre-step registers, then checks the synchronous cause. Reserved encodings,
partial effects on either side and Sail fault-attempt observations are refused. Such a refusal is not a match.
Partial records define validity but do not establish checker support.
The Spike shim refuses any trap with logged memory effects. It does not
discard those logs and infer zero completion. `state_coverage` includes
`csr_snapshot_steps` and `fault_access_steps`, the number of reference
observations checked. These counts include a mismatching observation.
A header declaration alone does not increase either count.


The cosim result's `state_coverage` gives the input `trace_schema`, whether FP
fields were compared (`fp`), and the declared `csr_snapshot` address list.
The optional live integration API uses the same C2 fields and synchronization
rules as offline checking. Its result adds `mode: online`,
`consumed_trace_prefix_sha256` and `consumed_trace_lines`. This digest covers
only consumed UTF-8 JSONL lines, including one-cycle lookahead. It is not a
full trace identity. Input/reference identities stay in `reproduction`.
An incomplete live stream returns `inconclusive`, with cause
`live_trace_incomplete`. The API stops the producer on a checked divergence.


### C1 debug transport (optional)

A core adapter can expose its simulated Debug Module in one of two ways.
The debug profile (`rvw.debug-profile/1`, see `rvw/src/rvw/debug/README.md`)
names the way in `[transport]`.

- `remote_bitbang`: the simulation contains a JTAG DTM and serves OpenOCD's
  remote_bitbang protocol on a TCP port. rvw drives TCK/TMS/TDI and reads TDO.
- `dmi_process`: the profile gives a command. rvw starts it and speaks a line
  protocol on its standard input and output. The adapter prints `ready ABITS`
  first. rvw then writes `r ADDR`, `w ADDR DATA`, `t CYCLES` or `q`. The adapter
  answers each `r` or `w` with `ok DATA`, `busy` or `fail`, and each `t` with
  `ok 0x0` after it advances the simulation by that many cycles. Values are
  hexadecimal with a `0x` prefix. `busy` means the request did not start; rvw
  sends it again. `fail` is a DMI failure (status 2). Diagnostics go to stderr.

`rvw debug serve` wraps a `dmi_process` bus in the reference JTAG DTM, so
OpenOCD can attach to a core that has only a DMI bus. A transport response is
not evidence that a debug operation worked. The campaigns check effects through
a separate path, for example memory read back by another access method.

The debug compliance suite writes C3 with `suite: "debug-compliance"`, `core`
set to the profile name and `config` set to `debug-<version>`. Each test entry
has `group`, `observations` and `dmi_accesses`. Against a non-model target it
also has `reference_status` and `reference_diff`, the result of the same check
on the reference model. A check the reference model cannot pass makes the entry
inconclusive. Different observations make it fail. Checks for options the
profile does not declare, or that the profile skips with a reason, are listed in
the top-level `unsupported` array and are not tests. An entry that could not
exercise its rule has status `error`, signature `inconclusive` and an
`inconclusive` reason. `rvw debug tap` writes the same layout with
`suite: "jtag-dtm"`. Exit codes: 0 all pass, 1 any fail, 3 inconclusive or no
checks.

### E-Trace flow results

`rvw debug etrace-check` writes `result.json` with `status` (`flow_match`,
`partial_match`, `mismatch`, `leak`, `no_checks`, `inconclusive`), `scope`,
`decoder_rev`, `retired`, `qualified`, `expected_packets`, `rvfi_sha256`,
`complete`, and with a capture also `packets_sha256`, `packets` (field
comparison), `windows` (each `observed`, `unknown` or `mismatch` with `start`
and `count` in C2 retirement order), `losses` and `skipped_packets`. A `leak`
result lists `leaked_pcs` and `leaked_addresses`. `partial_match` is not a
match of the whole run. `rvw debug etrace-loss` writes C3 with
`suite: "etrace-loss"`; each test records `windows` and `unknown_instructions`.

### N-Trace results and trace adapters

`rvw debug ntrace-check` writes `result.json` with the E-Trace flow statuses and
`codec` (`rvw-ntrace/1`), `mode`, `expected_messages`, `messages` (message
comparison), `trailing_bytes`, `windows` and an optional `adapter` (name, SHA-256).
It writes the expected stream as `expected.ntrace`. `rvw debug ntrace-loss` writes C3
with `suite: "ntrace-loss"`. A trace adapter file (`rvw.trace-adapter/1`, TOML) has
`name`, `vendor`, `codec`, `specification`, `license`, an `[ntrace]` table of codec
parameters and one or more `[[vectors]]` with `bytes` (hexadecimal) and `messages`.
An adapter with a failing or missing vector is refused.

### C1 fault injection (optional)

`<adapter> run ... --fault FILE` applies the faults in `FILE` (`rvw.fault/1`:
`{"schema": "rvw.fault/1", "faults": [{"id", "kind", "site", "bit", "cycle",
"duration"}]}`). `kind` is `stuck0`, `stuck1` or `flip`. `site` is a design
database register path. `cycle` is the first faulty cycle. Without `duration`, a
stuck-at fault holds to the end; a flip lasts one cycle. C1 `details.fault` must
be `{"applied": true, "site", "bit", "cycle"}` after the bit was forced, or
`{"applied": false, "reason"}`. `details.detections` lists the names of detection
mechanisms that fired. An adapter without `--fault` support must not claim it.
`rvw fault run` writes `plan.json` (`rvw.fault-plan/1`), `outcomes.json`,
`report.json` (`rvw.fault-report/1`) and C3 `results.json` with
`suite: "fault-campaign"` (see `rvw/src/rvw/fault/README.md`).

### RiscvSim harness hooks

The generic RiscvSim driver implements these optional C1 options for any adapter that runs
its simulation through `SimSession`. No adapter code names a signal.

- `--fault FILE` builds a separate `_fault` model: every register is `simPublic`
  and Verilator gets `--public-flat-rw`. The injector resolves `site` as the
  design database path (instance names below the toplevel, then the signal name).
  It writes the bit after each clock edge in the fault window and reads the
  register back one time unit later. `details.fault` adds `applied_cycle`,
  `before`, `after` (hex) and `writes`. Missing sites, enumeration registers,
  bits outside the register, runs that end first and read-back mismatches give
  `applied: false` with a reason. A file with several faults gives `applied` for
  all of them and a `faults` list.
- `--debug dmi --debug-binding FILE` serves the C1 debug transport line protocol
  on stdin and stdout. `--debug jtag:PORT` serves remote_bitbang on 127.0.0.1
  (`0` picks a port; the run directory gets `debug-port`). `FILE` is
  `rvw.debug-binding/1`: `dmi` maps `cmd_valid`, `cmd_ready` (optional),
  `cmd_write`, `cmd_address`, `cmd_data`, `rsp_valid`, `rsp_error` (optional) and
  `rsp_data` to top-level ports, with `abits` (7) and `timeout_cycles` (10000);
  `jtag` maps `tck`, `tms`, `tdi`, `tdo`, `trst` (optional, active high) with
  `cycles_per_byte` (1) and `idle_timeout_s` (300). Simulation time advances only
  inside requests. A DMI client ends the run with `q` or by closing stdin. JTAG
  clients connect one at a time; `Q` or a closed connection ends a client, and the
  run ends when no client connects within `idle_timeout_s`. The run ends with status
  `timeout` and message `debug session ended: ...`; it is never a pass.
  `details.debug` has `mode`, `requests`, `clients`, `ended` and `port`.

### Optional multi-hart extension (C1 and C2)

C1 stays `rvw.run/1`. An adapter can opt in with `details.multihart`.
It lists `harts`: objects with unique non-negative `hart`, reset `epoch`, and
`status`. Each hart starts in reset. Each reset starts a new epoch and restarts
that hart's retirement order at zero. Shared memory survives a hart reset.
The adapter must drain or cancel that hart's outstanding transactions before reset.
Completion applies to one hart. A run can pass only after every declared hart
completes with pass. An unfinished hart at the cycle bound gives timeout.
Harness errors must stay errors. Record each hart's reset PC and input ELF hash
in project metadata. The current single-ELF CLI does not select multiple images.

Multi-hart traces use **`rvw.rvfi/2`**, never `rvw.rvfi/1`. The header adds
`harts: [0, 1]`. Each retirement adds `hart` and `epoch`; `order` is a decimal
string with full 64-bit precision. Order is contiguous within one hart and epoch.
Equal retirement orders on different harts are valid. Reset and completion are
`event: reset` and `event: hart_end` with `hart`, `epoch`, `cycle` and, for
completion, `status`. A missing reset or an order gap is an input error.
All records add `capture_seq`, a contiguous decimal string from zero, and share
one nondecreasing sampled `cycle` in 0..9007199254740991. These describe capture order only. They do
not impose a global retirement order or implement RVWMO.

Shared memory initialization is captured once before reset release. Project
inputs declare its address ranges, bytes, byte order, hashes, arbitration and
memory type. Capture accepted external transactions as `event: external` with
unique transaction `id`, `action` (read, write, atomic, irq or maintenance),
`source`, hex `address`, hex `data`, hex byte `mask`, cycle and capture sequence.
Retried requests keep their logical transaction ID. Capture interrupt targets,
DMA coherence mode, read-from/write serialization IDs and maintenance completion
in the payload when applicable. Request presentation is not acceptance. Record
all nondeterministic input and arbitration decisions required for replay.

A reference adapter must use per-hart architectural state and an explicitly
captured memory interleaving or a memory-model checker. It must not feed the
reference values read from DUT retirement. Ambiguous read-from relations or
missing external inputs give inconclusive. Current Spike/Sail single-hart
commands do not implement this extension. Do not split `/2` into `/1` files and
claim a shared-memory match. `MultiHartTrace` in RiscvSim supplies the writer and
completion aggregation. It does not supply a multi-hart reference backend.

A serialized project boundary can use `SerializedMemoryReference` for byte data
and read-from checks. The project assigns contiguous `serialization` IDs only
when memory actions are accepted. This order is separate from `capture_seq`
and each hart's `order`. An event names its `boundary`. Reads add `read_from`,
one write ID per observed byte; `initial` names the captured initial image.
External writes consume serialization IDs too. Initialize the reference from
captured input bytes. Derive expected writes from stimulus or independent
architectural state. Compare observed writes before updating the reference.
This stricter serialized model is valid only for a declared serialized boundary.
It must not reject legal weak-memory core behavior by imposing retirement order.
The native two-hart subset fixture uses this model. Production multi-image
loading and a full multi-hart architectural reference remain unavailable.


### C2 online launch

`rvw cosim live --elf ELF --core CORE --out DIR --simulator COMMAND ...`
launches a C1 adapter. DIR must be new. COMMAND must contain `{elf}` and `{out}`
placeholders. The command receives the captured ELF and writes C2 to
`DIR/rvfi.jsonl`. `RVW_RVFI_FLUSH=1` requests line flushes in RiscvSim.
The existing offline comparison and synchronization rules apply. The wall
timeout covers the whole launch, including builds and lock waits. A checked
mismatch stops the process group and returns exit 1. A timeout, incomplete
stream or nonzero exit cannot produce a match; it returns exit 3 when usable
trace evidence exists. A timeout before any C2 output is also inconclusive.
Other input and trace errors return exit 2. `simulator` records command,
returncode, timed_out and trace path. The consumed prefix digest is not a
complete file identity. Launch metadata captures the executable identity and
argument list; adapter build dependencies still require C1 provenance.


### Unspecified mscratch reset bits in C2 comparison

For a declared trace from reset, CSR synchronization can resolve the unknown
reset bits of `mscratch` (0x340) from its first read or C2 CSR snapshot.
`rvw.cosim/1.recent_synchronizations` records `reason: csr_reset_unknown`,
`csr`, `mask`, `reference`, `core`, `order` and `source` (`rd_wdata|csr_state`).
The reference takes only unknown bits. Full writes clear the unknown mask;
set/clear writes clear their written bits from that mask. Subsequent observations
remain strict. The rule is disabled by strict CSR synchronization or by
`trace_from_reset=false`. Unsupported reference synchronization is an error.
No other CSR reset state is inferred by this rule. C1/C2 formats do not change.

### Multi-image preparation and serialized byte checking

`rvw memory images` emits `rvw.hart-images/1` with a `harts` array.
Each entry has a unique non-negative integer `hart`, absolute `elf` path,
and `elf_sha256`. At least two harts are required. This is input preparation,
not adapter execution. The project still owns image placement, overlap policy,
reset PCs and shared-memory initialization.

`rvw memory check` consumes C2/2 plus `rvw.serialized-memory/1`. The latter
has `boundary`, `initial` regions with hex `address` and hex byte-string `bytes`,
and `writes` keyed by accepted transaction ID. Each expected write declares
hex `address`, `data` and byte `mask`. Read-from entries correspond to selected
byte lanes in increasing order. Capture order does not define memory order.
The report is `rvw.memory-check/1`, with `status`, `checks`, `scope` and
`exhaustive_proof:false`. Status is `consistent`, `mismatch` or `inconclusive`.
Consistency applies only to the sampled declared serialized boundary.


### C2 blocking co-simulation transport

`rvw cosim live --lockstep` supplies a localhost TCP port in `RVW_COSIM_PORT`.
The producer sends a C2 header and records as UTF-8 JSON lines. It waits for one
JSON reply after each line. `status: continue` permits the next observation.
Any other reply is the final `rvw.cosim/1` report. The producer must stop.
The end event receives the final report. Missing end evidence cannot earn match.
Events precede affected retirements, including events in the same cycle. This
transport does not reorder cycles or read ahead. Taken interrupt traps inject
only platform-declared interrupt inputs. Declared debug halt events also synchronize at that boundary.

### C2 observation exchange

`rvw cosim exchange` writes a new output only. C2 export to RVVI-TEXT 0.5
uses RET/TRAP, ORDER, MODE, X and NET elements. A vendor STATE string named
`rvw.c2` retains the complete C2 header and each original record. This includes
asynchronous events, extension snapshots and synchronization inputs. Imports
check retirement PC, instruction and register writes against the vendor state.
The format source is RVVI commit `04dc469012f718ffe104c1c1d0cd8cea66f96724`.
This is a bounded subset, not a complete RVVI implementation.

Spike commit-log export retains C2 in `# RVW-C2` comments. Trapping retirements
are refused. Plain logs without that extension produce `rvw.observations/1`
with explicit missing fields. Sparse imports cannot produce C2 or a match.
Unsupported Spike effects fail instead of being discarded. Conversion reports
`independent_check: false`; format conversion is not architectural validation.

### C2 custom Spike reference extensions

The cosim platform accepts `reference_extensions`, a list of objects with
`library` and `name` strings. Library paths are relative to the original platform
file. Inputs capture each library before execution and record its digest. Spike
loads captured libraries, then registers each named extension on the processor
before loading the ELF. Libraries must use the installed Spike extension ABI.
A missing library or registration failure is an error. Sail refuses this setting.
Custom CSR state uses the existing C2 `csr_snapshot` declaration. Reference trace
generation still refuses custom instructions with unknown operand layouts.

### C2 debug entry observations

C2/2 may declare `debug: true`. Every retirement then contains `debug` with
Boolean `mode` and `step`, XLEN hexadecimal `dpc`, and 32-bit hexadecimal `dcsr`.
`step` must equal `dcsr.step`. A separate `event: debug` record has a `cycle`,
`action` (`halt` or `observe`) and the same complete debug snapshot. A halt
injects a reference halt request before the next instruction. It does not inject
an ordinary exception or interrupt. All four snapshot fields compare exactly.
Spike processes a halt without executing a debug ROM instruction. Resume,
debug ROM execution, triggers and automatic single-step transitions are not yet
supported. Unsupported reference hooks fail; they cannot earn a match.

### C2 vector source setup

`rvw cosim vector-source` and MCP `cosim_vector_source` fetch pinned upstream
vector tests outside the workstation checkout. `rvw.vector-source/1` records
source and environment commits, output path, `built: false` and the vector-state
comparison prerequisite. `prepared` means the source commits were checked out.
It does not mean the tests were built or passed. A new destination is required.
The existing strict `rvw regress vector` comparison remains the suite verdict.

### C2 serialized multi-hart reference comparison

`rvw cosim check` accepts multi-hart C2 with an explicit header
`memory_profile: serialized-retirement`. One Spike machine owns shared RAM and
one processor per declared hart. Per-hart order, register state and comparison
history remain separate. Each retirement executes in global `capture_seq`
order. Thus a completed store becomes visible to all later reference steps.
This restricted sequentially consistent profile is not an RVWMO checker.

Each hart must start at epoch zero and end with `hart_end`. Reset epochs beyond
zero, external-agent events, custom extensions and absent-PMP emulation are
unsupported. All harts use the captured shared ELF and reset PC. Results retain
per-hart reports and identify the first mismatching hart. Missing hart ends are
inconclusive. No weak-memory, bus coherence or store-buffer claim is made.

### C2 independent reference adjudication

`rvw cosim adjudicate` and MCP `cosim_adjudicate` produce
`rvw.cosim-adjudication/1`. They preserve the complete Spike and Sail reports.
ELF, trace and platform capture hashes must agree across both runs. Missing or
unsupported reference evidence makes the result inconclusive. A match requires
both references to cover the same complete trace with no uncompared instructions.

At the first mismatching instruction boundary, the report records which other
reference still matches the DUT prefix. Different expected values produce
`disagreement`, never a majority-vote pass. If both references reject the same
value at the same boundary, the result is `mismatch`. The first version does not
reduce the trace or assign a specification rule to the disagreement.

### C2 optional CHERI assessment hook

A cosim platform may declare `cheri` with `repository`, a full 40-character
`revision`, and `capability_bits` (64, 128 or 256). This records an optional
architecture selection. It does not declare a standard RISC-V profile.
Stock comparison refuses this selection with `unsupported_reference:cheri`.
No C2 capability-state format or reference implementation is enabled by it.
See `Cosim/CHERI.md` for the pinned candidate and required state observations.

### C2 QEMU boot observation comparison

`rvw cosim qemu-check` and MCP `cosim_qemu_check` read a single-hart QEMU
`-d cpu,nochain` log produced with `-accel tcg,one-insn-per-tb=on` and `-smp 1`.
`rvw.qemu-observation/1` records trace/log hashes, skipped boot-ROM prefix,
compared count, scope and unchecked fields. It checks PC, next PC, integer source
values and integer destination values. `architectural_match` is always false.
`match` applies only to those observations in a completed bounded C2 segment.
Missing snapshots or asynchronous/trap/debug events are inconclusive.

`rvw cosim adjudicate --qemu-log LOG` retains QEMU as an optional partial third
reference. Its trace hash must agree with the Spike/Sail input. Missing QEMU
evidence makes the combined result inconclusive. A QEMU observation mismatch
against a two-reference match produces disagreement. QEMU does not vote away
an architectural mismatch. Full Linux boot, event injection and non-integer
state remain unsupported by this first log adapter.

## Ordered vector memory observations

A C2/2 header can declare `vector_memory: true` with its `vector` state.
Every retirement then includes `vector_accesses`, an ordered list, including
an empty list for instructions with no vector memory effect. Each entry has
`kind` (`read` or `write`), `address` (XLEN hex), `size` (1, 2, 4 or 8 bytes),
and `data` (raw little-endian bytes as a hex integer that fits the size).
The scalar memory masks stay zero for these vector operations. The checker
compares the entire ordered list as well as full vector state. Missing reference
observations are an error. Reference vector memory effects without declared
DUT capture are also an error. No register or access is inferred from DUT data.

The Spike shim currently supports successful vector memory operations in bare
RAM only, without virtual translation or devices. Loads read the unchanged RAM
bytes after execution. Stores use Spike's ordered commit log. Mixed read/write
operations and partial fault effects are refused. This support does not cover
fault-only-first completion, translated memory, or bus transactions.
