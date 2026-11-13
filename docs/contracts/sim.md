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
request/response), `stage` (id, optional pc; meta `stage`, `lane`; occupancy), `retire` (id),
`flush` (id), `stall` (no fields; meta `scope`, `cause`, `evidence`; level), `csr` (address,
value), `interrupt` (cause, pc, optional tval), `trace` (itype, iaddr, iretire, ilastsize,
priv, optional cause, tval), `counter` (inc, summed each cycle and written only in the end
record; optional meta `hpm`), `fault` (a register site, never sampled) and `custom`.

`rvw probes convert` writes consumer formats: `rvw.bp-events/1` (events aligned 1:1 with C2
branch retirements of the covered kinds, matching PC and taken outcome, else refused),
Kanata 0004 with `#rvw 1 stall` records, cache observer JSONL (`event` is `CACHE.EVENT`),
`rvw.mmu-observations/1`, ooo-calibrate RTL event counts (`c1_sha256`, `trace_sha256`,
`counts`, `cycles`), E-Trace encoder ingress CSV, `rvw.hpm-bindings/1` (`identity`, `cycles`,
`bindings: [{selector, counter, total}]`) and `rvw.probe-interrupts/1` (`status`
`consistent`, `mismatch` or `inconclusive`; interrupt probe causes against C2 interrupt trap
events in order). `rvw probes list` writes `rvw.probes-report/1`: `probes`, one `consumers`
row per tool with `status` `enabled`, `missing`, `unknown` or `no_converter`, and the
`enabled`/`missing` lists. Probe events are producer claims; no converter adds an event.
`rvw uvm run` writes C1 with `details.mode: uvm-bench`, null cycle and retirement
counts, and no ELF claim. A pass requires exit zero, no UVM error/fatal, and one
`RVW_UVM_DONE TEST checks=N` line with the selected test and positive N.
`rvw uvm regress` writes one C3 row per test/seed and links the corresponding
C1 and log. `source.identity_complete` is false. These results are component
checks, not a core gate identity. Native coverage merging does not merge
functional coverage plans or establish closure.

## Standard device checkpoint payload

The optional `PythonDevices.cpp` library implements `DeviceApiV1` unchanged.
Its snapshot bytes contain UTF-8 JSON with schema `rvw.standard-device/1`.
Fields are `schema`, `config`, `cycle` and `state`. Restore requires equal
configuration and the same model state inventory. Byte arrays use a `bytes`
hex object. Sets use a sorted `set` array object. The payload is trusted
same-build state. Capture the plugin, Python library and Python source digests
in the run identity. Host console output and host file writes are not emitted.
The model owns the buffered console and disk state. See
`RiscvSim/src/main/cpp/DEVICES.md` for model selection and interrupt bits.
