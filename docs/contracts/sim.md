# Simulation server and native ports contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## C2 writer state for live native checkpoints

`rvw.rvfi-writer/1` is the `rvfi` component of a native checkpoint. It contains
header, base64 prefix, SHA-256, decimal byte position, decimal counters
`records`, `traps`, `gaps`, `next_order`, `last_cycle`, and `pending`.
`pending` is null or `[cycle, cause, intr]`, with decimal strings for integers.
The prefix is flushed before capture. Restore validates it before output opens.
The outer native checkpoint binds the writer to model and harness identity.
A writer snapshot alone does not restore a model or establish replay equality.

## Project native snapshot port control

`rvw.snapshot-adapter/1` supplies a trusted project Python `module`, optional
`options`, and ordered `identity_files` lists for the four native identities.
Hash each identity as concatenated 8-byte big-endian lengths and file contents.
The harness digest additionally binds the port source and exact manifest bytes.
The port implements native snapshot methods, `advance(unit, target)`,
`position(unit)`, `finish(out)` and `close()`. Advancement must stop at the
requested cycle or retired-instruction count. An inexact boundary is refused.
Restore uses a fresh port. `restored` is not an equivalence verdict. Exact C2
suffix comparison requires matching prefixes and complete end events.

## Project architectural injection

`rvw.arch-injection/1` and `rvw.arch-map/1` are project-port documents, not the
proposed qualified Spike interchange format. Their exact fields and port calls
are defined in `rvw/src/rvw/sim/INJECTION.md`. Both name the same profile. The
profile declares the complete CSR and RAM inventory. The implementation checks
widths, x0, unique bindings, exact CSR sets and non-overlapping memory images.
A successful `injected` result means all mapped registers and memory passed
readback before fetch release. It is not a C1 pass or C4 accept. Bare M mode
and no active devices, interrupts or hidden execution state are required.
Raw FPR bits are preserved. Native FP qualification remains required.

## Reverse execution through native checkpoints

`sim_reverse_step` and `rvw sim reverse-step` validate every supplied native
checkpoint against current identities. Each must have `counters.instructions`.
Select the greatest count at or before the target. Restore into a fresh port,
then call `replay_to_instruction(target, max_seconds=...)`. The port must cancel
native work on timeout. The reached count must equal the target before saving.
The result lists history, selected count, target and time budget. `saved` means
a stopped checkpoint exists. It does not mean native replay qualification or
ISA correctness. A target before available history is refused.

## Native project device ABI

Shared libraries export `rvw_device_plugin_v1`, returning `DeviceApiV1` with
ABI number 1 and all callbacks. Calls are serialized at stopped cycle boundaries.
Create takes project JSON and a seed. MMIO uses device-relative byte addresses,
1 to 8 byte little-endian values and byte masks. Tick takes absolute cycles;
project data declares cycle period and interrupt routing. Nonzero status is an
error. Snapshot size zero declares non-restorable effects. Store versioned
payloads under native envelope devices and bind library/configuration hashes.
DPI-C wrappers never propagate C++ exceptions. Null handles and nonzero status
must stop the run. Device maps, Linux behavior and TLM timing are not inferred.
ABI number 2 appends one callback, `set_input(handle, input, level)`, which
drives one numbered device input (for example a PLIC gateway source) to 0 or 1.
Hosts accept ABI 1 and 2 and read `set_input` only for ABI 2; driving an input
of an ABI 1 library is an error. `PythonDevices.cpp` exports ABI 2 and maps it
to `Device.set_level`. When built by `RiscvSim/scripts/build-devices.py`, it
embeds its interpreter home and `rvw/src` and starts an isolated interpreter
that ignores `PYTHONHOME` and `PYTHONPATH`.

## Mailbox stimulus option

`run --stimulus-file F` (manifest key `stimulus_file`) loads `rvw.stimulus/1`.
Only adapters that declare `supportsStimulus` accept it. Event payload steps
are positive and strictly increasing, and every event uses the
`stimulus_step`/`stimulus_ack` RAM mailbox. RiscvSim `StimulusMailbox` serves
the next event when the program stores its step to `stimulus_step`, then
writes the step to `stimulus_ack` after `settle_ticks` cycles. The adapter
supplies the device action for each payload `kind`. C1 records
`stimulus_file` (the value as given) and `stimulus_sha256`. Option files must
lie under a declared input root (for example a `cache_paths` entry), or
regress capture refuses them.
See `RiscvSim/src/main/cpp/DEVICES.md` for exact ABI and DPI declarations.

## Simulation cost report

`rvw.sim-profile/1` reports C1 file hashes, native identities, terminal status,
recorded elaboration/native-setup/model-compile/execution times, counters and
derived throughput. Missing measurements are null. It does not infer separate
Scala compile time or process-tree RSS. `status: reported` is not qualification.
`profile_applied: false` states that proposed flag profiles were not executed
and do not classify the recorded runs. Tool statuses reflect PATH lookup only.
Unimplemented hierarchy/PGO/Arcilator paths remain explicit unsupported entries.

## External gate-netlist and SDF replay interface

`rvw.timing-request/1` names a netlist, SDF, cell libraries, top, cell inventory,
delay constructs, timing checks, unknown behavior and min/typ/max corner.
`rvw.timing-capabilities/1` declares simulator/version, supported inventories,
unknown behavior and corners. `rvw.timing-handoff/1` reports captured input
hashes and declarations. `declared_compatible` means interface readiness only.
It does not establish annotation, complete cell coverage or physical signoff.
Unsupported requested cells, delays, checks, corners or unknown behavior fail.

An external native `TimingPort` consumes captured input bytes and must refuse
ignored annotation. It returns a native C1 outcome. A compile-only result is
not a run outcome. `physical_signoff` remains false. The simulation README
lists exact fields. No standard-cell library or native gate backend is bundled.

## Native backend semantic profiles

`rvw regress backends --json` maps backend names to semantic profiles. Fields
are `values`, `scheduling`, `x_handling`, `languages`, `assertions`, `foreign`,
`coverage` and `features`. `features` is the closed set of guarantees that a
component test can require. Unknown backends or requirements are errors.
Profiles describe the adapter invocation. They do not certify every installed
simulator version. Two-state runs cannot satisfy four-state or X/Z requirements.

## Standalone HDL semantic tests

`rvw regress hdl` reads `rvw.hdl/1` and writes `rvw.hdl-result/1`.
This standalone format is not C1, C3 or C4 acceptance evidence.
The manifest fields are `schema`, `backend`, `top`, `sources`, optional
`requires`, and optional `vhdl_sources` plus `vhdl_top` for mixed synthesis.
A per-run `--backend` override must meet every declared requirement.
The [simulation guide](../rvw/src/rvw/sim/README.md#native-hdl-testbenches)
defines supported profiles and testbench completion rules.

The result records `status` (`pass` or `error`), `reason`, the selected `backend`,
`capabilities`, source-file SHA-256 `inputs`, resolved `tools`, `versions`,
`jobs`, `wall_s`, `timeout_s` and `replay`. Each job records its argument vector,
exit code, timeout flag, and paths to stdout/stderr logs. Exit zero plus exactly
one testbench `RVW_PASS` line and no native error diagnostic earns a pass.
A failed compile, failed run, timeout or missing completion marker gives error.
Requirements and missing-tool errors occur before output creation (CLI exit 2).
This format does not capture transitive file inputs or establish C8 reuse.

## Probe event stream (`rvw.probe-events/1`)

`<adapter> run ... --probes` (C1, optional) elaborates a separate model with the core's
`spinalprobes.Probe` calls enabled and writes `probe-events.jsonl` (C1 artifact
`probe_events`). The model key adds `probes` (name suffix `_probes`). Adapters without
probe support refuse the flag. A run with `--probes` and no registered probe is an error.

The stream is JSONL. Line 1 is the header: `schema`, `identity` (the C2 header's `core`,
`config`, `elf`, `elf_sha256`, `rtl_sha256`, `seed` when present) and `probes`, a list of
`{id, kind, name, fields: [[name, width]...], meta: {...}}` with ids `0..n-1`. Each event is
an array `[cycle, id, value...]` with integer values in the probe's field order. Cycles do not
decrease and use the C2 writer's cycle number. The last line is
`{"end": true, "cycles", "counters": {name: total}, "events": {id: count}}`. A stream without
it is incomplete; totals from it are refused.

Kinds: `branch` (pc, taken, target, optional predicted_taken, predicted_target; meta
`semantics`, `covers`), `cache` (address, optional hit, write, data, mask, way; meta `cache`,
`event`), `tlb` (optional va, pa, asid, entry, size, global, pte_address, pte; meta `event`
fill/hit/miss/invalidate), `walk` (address, optional data, level, fault; meta `event`
request/response; or the result of one walk: va, access 0 load/1 store/2 fetch, root, status
0 success/1 page-fault/2 access-fault, pa; meta `event` result, `mode` sv32/39/48/57), `stage` (id, optional pc; meta `stage`, `lane`; occupancy), `retire` (id),
`flush` (id), `bus` (address, optional write, data, mask, size; meta `bus`; one accepted
request at a core port, before any cache), `stall` (no fields; meta `scope`, `cause`, `evidence`; level), `csr` (address,
value), `interrupt` (cause, pc, optional tval), `trace` (itype, iaddr, iretire, ilastsize,
priv, optional cause, tval), `counter` (inc, summed each cycle and written only in the end
record; optional meta `hpm`), `fault` (a register site, never
sampled; meta `path` is the register path that C1 `--fault` resolves) and `custom`.

`rvw probes convert` writes consumer formats: `rvw.bp-events/1` (events aligned 1:1 with C2
branch retirements of the covered kinds, matching PC and taken outcome, else refused),
Kanata 0004 with `#rvw 1 stall` records and, for branch events with an `id` field (the
stage probes' instruction ID) and `predicted_taken`, `#rvw 1 prediction` direction records
(predictor = probe name; recovery, work, warmup, alias and context `?`) before the
instruction's retire, cache observer JSONL (`event` is `CACHE.EVENT`),
`rvw.mmu-observations/1`, ooo-calibrate RTL event counts (`c1_sha256`, `trace_sha256`,
`counts`, `cycles`), E-Trace encoder ingress CSV, `rvw.hpm-bindings/1` (`identity`, `cycles`,
`bindings: [{selector, counter, total}]`) and `rvw.probe-interrupts/1` (`status`
`consistent`, `mismatch` or `inconclusive`; interrupt probe causes against C2 interrupt trap
events in order). `rvw probes list` writes `rvw.probes-report/1`: `probes`, one `consumers`
row per tool with `status` `enabled`, `missing`, `unknown` or `no_converter`, and the
`enabled`/`missing` lists. Probe events are producer claims; no converter adds an event.
`--to bus` writes `rvw.probe-bus-check/1`: the data bus probe's writes against retired C2
stores one to one (bytes and values, in order), and each retired C2 load covered by a later
bus read in order; `unretired_reads` counts reads no load used. `--to csr-writes` writes
`rvw.probe-csr-writes/1`: each retired C2 instruction that writes a CSR matches the next
`csr` event by address, and by value when C2 operands give it (`csrrw*` always, `csrrs*`/
`csrrc*` when `rd` is not x0); a trapped CSR write may consume one event, as may an event
followed by a C2 exception before the next retirement (an illegal-instruction `tval` must
name the same CSR). `--to mmu-walks` writes a new C2 trace: each walker's `response` events
up to its `result` become one `mmu_walk` record (sequential `access_id`), on the first
retirement at or after the result cycle. `--to fault-sites` writes `{source, identity, sites:
[{path, width, clock_domain, probe}], bits}` for `rvw fault plan --sites`. Both have `status`
`consistent`, `mismatch` or `inconclusive` and a `mismatches` list.
`rvw uvm run` writes C1 with `details.mode: uvm-bench`, null cycle and retirement
counts, and no ELF claim. A pass requires exit zero, no UVM error/fatal, and one
`RVW_UVM_DONE TEST checks=N` line with the selected test and positive N.
`rvw uvm regress` writes one C3 row per test/seed and links the corresponding
C1 and log. `source.identity_complete` is false. These results are component
checks, not a core gate identity. Native coverage merging does not merge
functional coverage plans or establish closure.

## Standard device checkpoint payload

The optional `PythonDevices.cpp` library implements `DeviceApiV1` (ABI 2).
Its snapshot bytes contain UTF-8 JSON with schema `rvw.standard-device/1`.
Fields are `schema`, `config`, `cycle` and `state`. Restore requires equal
configuration and the same model state inventory. Byte arrays use a `bytes`
hex object. Sets use a sorted `set` array object. The payload is trusted
same-build state. Capture the plugin, Python library and Python source digests
in the run identity. Host console output and host file writes are not emitted.
The model owns the buffered console and disk state. See
`RiscvSim/src/main/cpp/DEVICES.md` for model selection and interrupt bits.

## Scalar native engine probe

The scalar model library supplies port access, not a core-specific driver.
A project adapter can use it to write existing C1 and C2 files. The VexRiscv
probe records its source/tool/library hash map in C1 `details.native_identity`.
This map is a build record, not a complete captured C4 identity. Its C1
`source` and `tools` inventories are empty. Such runs must not earn C4 reuse
or acceptance. The probe reports complete C2 only after its terminal condition.
A cycle-bound timeout has status `timeout`. Build failure returns inconclusive.

### Blocking TLM memory timing

`TlmMemory` applies transaction bytes at call time and adds configured latency
to the blocking transport delay annotation. It never waits or retains payload
pointers. A caller must consume the delay before it publishes completion.
The supplied SystemC bridge has one initiator and one outstanding transaction.
It samples RTL requests at falling edges and consumes a 2 ns delay before the
next rising edge of a 10 ns clock. The target alone has loosely timed
semantics. No DMI, temporal decoupling or cycle-accurate device timing is implied.

### Captured project adapter registry

A debug configuration can set `core.adapter_versions` to a path relative to
that configuration. The capture freezes its directory. Adapter commands resolve
inside the captured registry directory. A marker still resolves inside the
captured core tree. Exact revision entries take precedence. Missing entries are
unsupported and cannot fall back to the current adapter. The existing
`rvw.adapter-selection/1` record adds `manifest_scope` as `project` or `source`.
C1 source identity preserves that selection. The launch descriptor includes
registry dependencies. This extension applies to debug launches and bisect.
It does not provide historical gate selection or C4 acceptance.

### Captured scalar native build profiles

The opt-in `rvw.native-build-profile/1` has `threads`, `hierarchy`, `ccache`,
`ccache_dir`, `compiler_pgo`, `training_elf` and `reuse_manifest` fields.
Compiler PGO mode is `off`, `generate` or `use`. Paths resolve from the profile
file. Unknown fields and unsupported inherited compiler/make flags are refused.
The capture freezes profile configuration, RTL, generated hierarchy control,
SDK settings, make rules, training ELF and reused raw/merged profile bytes.
A `rvw.compiler-pgo/1` binding includes exact input and compiler/tool hashes,
flags, thread count and hierarchy. A changed binding or profile digest fails.
`PROFOUTOFDATE` and compiler outdated/unprofiled diagnostics fail too.
The namespace is `scalar-native-profile-v3`. These build records are not C4
cache identities. The production Spinal collector remains unchanged.

C1 `details.model_compile_s` records model build/setup duration for the scalar
probe. `details.execution_s` includes its port bridge and C2 publication.
`details.child_peak_rss_bytes` is normalized maximum child-process RSS during
build. It is not total concurrent memory. `details.native_profile` records the
captured request and binding. The existing `rvw.sim-profile/1` report exposes
these fields as `native_probe_profile`, `peak_rss_bytes` and `peak_rss_scope`.
A report never applies a profile or establishes a throughput improvement.

## Project scalar IRQ reduction probe

The project scalar probe can consume the existing ordered `--irq-schedule`
format. Each `CYCLE:0xLEVELS` event changes input levels before that cycle.
Levels persist until the next event. The first event must be at cycle 1.
The project port map determines supported interrupt inputs. Unsupported bits
fail before a native build. C2 records level changes as `irq` events and
observed traps with the canonical `intr` boolean. C2 headers include `config`
and `elf`. Completed Python scalar traces pass the shared C2 parser before
C1 publication. No C2 format change or C4 reuse identity is introduced.

The project reduction adapter accepts an existing output directory and writes
native artifacts below `native-run/`. Its C1 replay preserves the selected
private lock, CIRCT path, ELF, seed and IRQ schedule. C8 captures its project
assets. Instruction reduction retains code addresses through NOP replacement.
IRQ reduction retains the required initial event. A conclusive native pass
after removing the final retained item supports `one_minimal`, never a global
minimum claim. Deliberate fixture failures do not establish a core defect.

## Native server process observation

C1 `details.simulation_session.process_id` is the host JVM process ID as an
integer. It identifies the process that ran the model. It is observational
metadata, separate from model identity and C4 reuse. It does not enter C2.
A completed server request does not establish process teardown. A caller can
check this PID after EOF, shutdown or launcher cancellation. PID exit proves
that the process and its threads stopped. It does not prove that each
simulation thread was released between requests in a live JVM.

## Live MMIO devices in a simulation map

A `rvw.sim-map/1` file can contain a `devices` array. Each entry names an
uncached MMIO `region` and a `model`. The generic `LiveDevices` harness supports
`ns16550`, `clint` and `plic`. The map bytes, including input schedules and pin
routes, are captured with the run. A fresh instance is required for each run.

The UART uses byte accesses at 16550 register offsets. It supports RX and TX,
a 16-byte RX FIFO, RX overrun, RX and TX interrupt enables, divisor and scratch.
`rx` contains ordered `{cycle, byte}` input entries. Input arrives at settled
sample boundaries. TX completes immediately into captured state. Baud timing,
modem signals, FIFO trigger levels and DMA are unsupported and not qualified.

CLINT uses aligned 32-bit accesses to MSIP at 0, MTIMECMP at 0x4000/0x4004
and MTIME at 0xbff8/0xbffc. `cycles_per_tick` sets the timer period.
`software_bit` and `timer_bit` name the adapter interrupt bits. MTIME writes
are refused. One hart is supported.

PLIC supports one context and sources 1 through 31. `sources` contains
`{device, id}` routes. `interrupt_bit` names the adapter input bit. Priority,
pending, enable, threshold, claim and completion use standard PLIC offsets.
The gateway masks a claimed source until completion. A level that remains
asserted after completion raises the request again. Unsupported accesses fail.

The VexRiscv example connects these generated levels to its real interrupt
pins. An explicit IRQ schedule overrides device-generated input levels.
C1 `details.device_output` captures each UART's output. This is software
simulation evidence. It does not qualify physical device timing or Linux boot.
`LiveDevices.snapshot()` returns `rvw.live-devices/1` trusted same-build state.
It binds the complete device state to the map digest. UART FIFO, output,
registers, input position, CLINT time and deadline, PLIC priorities, enables,
active levels and claims are retained. The outer envelope must bind device
implementation bytes and the RTL/harness boundary. Discard the instance after
a restore error. This does not serialize host handles or the JVM scheduler.

## Native packed-port model API

`rvw.sim.native_models.Model` accepts packed integer ports with widths from 1
through 65,536 bits. Inputs must fit the declared width. The Arcilator state
layout supplies byte offsets and widths. Verilator wide ports use explicit
little-endian byte transfer to generated 32-bit word arrays. High padding
bits do not become part of a returned value.

Optional `wave=PATH` creates a new public-port two-state VCD. A sample follows
each model evaluation. Timestamps count evaluation calls. The 1 ps display
unit is not a timing claim. Files refuse overwrite. Close the model to flush
the wave. This API supplies no internal-signal, four-state or HDL-delay wave
guarantee. Project adapters must identify these limits in their run artifacts.

## Settled native port snapshots

`Model(..., port_snapshot=True)` refreshes scalar Verilator port values after
`eval()`. Arcilator captures its state bytes at that boundary. Input writes
invalidate the snapshot. Reads before the next evaluation use current native
storage. Wide Verilator reads retain the byte interface. Set the option to
false for a measured control. Public wave capture uses the same settled values.
Execution CPU time, when present in the example's C1 details, includes the
Python adapter and C2 write/validation. It does not isolate generated RTL code.
## Host device plugins

The Scala `PluginDevice` binding uses DeviceApiV1 ABI 1 or 2 (`setInput` needs 2). Each run
owns a fresh handle. The adapter serializes tick and MMIO calls at sampled
boundaries and supplies all address and interrupt routing data. Libraries
remain loaded for the process lifetime. Callback failure stops the operation.
This binding does not provide checkpoint capture or restore.

## Local live simulation service and FST

Generic RiscvSim wave models now write `wave.fst` by default. The model key
records `wave_format: fst` and uses a separate wave workspace name. Cycle
windows still enable and disable capture inside the native simulator.

`rvw sim server --socket PATH --command JSON` owns one native adapter process.
JSON is an argument array ending in `serve`. The local Unix socket accepts
one JSON job per connection and returns the adapter's `rvw.sim-server/1`
reply. Jobs execute serially. An `op: shutdown` request ends the process.
A native timeout or exit stops the service. A service owns its socket and
refuses an existing socket or log. The adapter command retains responsibility
for project locks, captured inputs and native identity.

MCP `sim_server_request` submits jobs to this socket. `rvw bundle --sim-server
PATH` requests wave/trace reruns through it. The bundle requires the original
and rerun simulation-session IDs to match before using the rerun as reproduced
evidence. Its existing ELF/options checks, failure signature and cycle checks
still apply. Captured command inputs are verified. Unsupported historical
adapter selections remain errors. Live requests do not change the already
running adapter's source, native environment or build options.

Live bundle reproduction also requires equal generated RTL hashes. The live
path captures request ELF bytes and a captured simulation map. It does not
launch or copy another core tree. Structured boot payloads, hart images and
fault-file inputs currently refuse this live path. Normal process reruns keep
the existing source-capture path. Live C5 replay scripts still require the
original project setup; they are not standalone portable archives.

## Single-file offline replay archive

`rvw replay-pack` writes `rvw.portable-replay/1` in one ZIP file. The manifest
binds every member by SHA-256 and mode. It contains the ELF, seeded options,
inline interrupt schedule, optional captured simulation map, expected C2,
checkpoint, adapter/core Git bundles, tracked patches and declared untracked
source inputs. `rvw.replay-adapter/1` project data supplies the adapter command,
source environment selector, source-input roots and optional host-tool bindings.
Absolute host-tool paths are recorded for diagnosis and rebound from the target
environment. Other nonportable environment values refuse packaging.

`rvw replay` checks member names and hashes before checking out source or
running the adapter. It creates fresh source snapshots and an isolated Python
environment that imports the archived rvw package. It requires matching C1
ELF/seed/limits/memory timing, terminal behavior, failure signature, generated
RTL and complete architectural C2 events. The result is `reproduced` only when
all checks agree. A different result is `mismatch`, not acceptance.

`rvw.portable-trace-checkpoint/1` is explicitly `mode: from-reset`. It stores
a cycle and canonical prefix/suffix event hashes. Replay executes from reset
and verifies both hashes. It is not a live model image. The live bridge
snapshot contract remains separate. No native state portability is implied.
Target build tools and cached dependencies remain prerequisites. Native
execution on another machine needs its own evidence. Local source relocation
is not cross-machine qualification.

Portable replay compares semantic C2 header fields as well as events. Only
`elf` and `source` header fields are excluded for path/provenance relocation.
A changed ISA, XLEN, capability, CSR layout, seed or RTL declaration fails the
header check. The validated C1 ELF identity remains a separate required check.

## Per-request simulation threads and device reset

Generic RiscvSim accepts `--sim-threads N` or JSON `sim_threads` for adapter
implementations that declare `supportsSimThreads`. N is an integer from 1
through 64. VexRiscv opts in. Other adapters must opt in before an explicit
count can be selected. An absent count preserves the existing build profile.
C1 records the override, or null, in `sim_threads` and `details.model`.
Replay keeps an explicit override. Build and identity commands honor it too.

An explicit count supplies Verilator `--threads N`. It has a distinct model
key/workspace and a distinct native cache directory. This prevents reuse of
a build with another count. An inherited `SPINAL_VERILATOR_FLAGS --threads`
setting conflicts with an explicit request and is refused. Counts select
compiled models in the same persistent process. They are not a measured
OS-thread count or a speed-gain claim.

`LiveDevices.reset()` restores its complete initial snapshot for a new run
whose cycle origin is zero. It clears UART FIFO/output/registers/overrun/input
position, CLINT time/deadline/software level and PLIC priority/enable/threshold/
active/claimed state. VexRiscv allocates a fresh device set for each request
and records `details.initial_device_state_sha256` before simulation.
`details.device_reset` records this lifecycle. The native fixture dirties all
three models, then checks reset and UART echo across one-/two-thread builds.
Other adapter/device implementations still own their reset behavior.

Portable and live-bundle paths also refuse interactive debug bindings and
external trace-ingress bindings. These inputs need explicit transaction
capture before they can supply deterministic reproduction evidence.

## VexiiRiscv live-map adapter

The VexiiRiscv example can consume the existing `rvw.sim-map/1` live-device
map. Its uncached MMIO ranges must match the project PMA map. Live devices
and DeviceApiV1 selection are mutually exclusive. C1 `details.device_output`
contains UART output. The model drives software, timer and external core
interrupt inputs from device state. This adds no new generic map fields.

## Fault injection cycle sampling

The generic injector counts clock sampling edges from the adapter cycle at
attachment. The adapter must call `SimControl.tick()` once per sampled edge.
The tick can run before or after the injector on that edge. A change in thread
order must not skip a one-cycle flip. If the adapter count differs by more than
one tick, pending faults remain unapplied with an ambiguous-cycle reason.
Read-back confirmation remains required before `details.fault.applied` is true.
## VexiiRiscv boot payloads

The example adapter loads the captured `RunContext.loadMemory` image. Its
uncached RAM can span up to 128 MiB. The existing `rvw.boot-payloads/1` and
`rvw.sim-map/1` formats apply. The `rv64imacsu` profile adds compressed
instructions to the RV64 supervisor configuration. The `rv64imacsu_linux`
profile uses bounded execution and disables bare-metal `tohost` completion.
C1 `details.last_retired_pc` and `details.last_retired_mode` report the last
observed retirement. They are null if no instruction retired.
`details.retired_by_mode` counts observed instructions per privilege mode.
The bounded profile records `details.completion=bounded` and a null `tohost`. Native live checkpoint
save and restore are not supplied by this adapter.

UART live-device state adds the modem-control register. Reset clears it.
Snapshots retain its four supported output bits. Loopback mode is refused.
Older snapshots without this register restore it as zero.

The live CLINT model supports aligned eight-byte accesses to `mtime` and
`mtimecmp`. Both halves use one sampled device state. MSIP and PLIC registers
use four-byte accesses. UART registers use byte accesses.

## Device and per-hart reduction

The `uart_rx` reduction stage consumes the captured `soc_map` artifact and its
C1 SHA-256. It removes only timed UART RX entries. Retained cycles and order
stay fixed. The `hart_instructions` stage consumes `rvw.hart-images/1` and
checks each ELF against C1 `details.hart_images`. It preserves hart IDs and
entries. Named private code symbols use address-preserving NOP replacement.

The SMP example records C1 `details.hart_failures` as a map from decimal hart
IDs to program failure codes. C1 `fail_code` is the code from the lowest
failed hart. Per-hart reduction also requires the complete failure-code map
to match. Missing codes are inconclusive. Other failure-signature and timeout
rules still apply. Each stage reports local minimality and budget exhaustion.

## Blocking TLM multi-initiator memory

`TlmMemory.socket` accepts multiple initiator bindings. The SystemC kernel
orders calls. Each call applies bytes at call time before it returns. Successful
reads and writes increment `initiatorReads` and `initiatorWrites` by binding ID.
The caller consumes the annotated delay. Completion times do not reorder memory
effects. Calls at the same time use kernel process order. Arbitration, fairness,
parallel host-thread access and separate kernels are outside this contract.
