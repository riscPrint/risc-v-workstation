# Memory order and multi-hart contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Concurrent reference completion smoke

`rvw.concurrent-smoke/1` records source and ELF hashes, seed, ISA, hart count,
program length, command and bounded native completion status. Pass requires
all generated fragments to reach their completion flag before HTIF exit.
`ordering:not_checked` and `rtl:not_run` keep reference completion separate
from memory-model and RTL evidence. Tool absence or timeout is inconclusive.

## Finite coherence directory experiments

`rvw.coherence-fair/1` reports pass, fail or inconclusive for a finite model
under named weak-fairness action sets. Directory reports add a MESI/MOESI
profile, queue capacity, line count, request count and value bounds. Incomplete
searches cannot pass. A failure includes a safety witness or a prefix to a
fair noncompletion component. A model pass is not an RTL liveness or protocol
refinement result. Independent-model cross-check status remains explicit.

## Bounded TileLink-C monitor generation

`rvw.tlc-bind/1` is a project profile for two typed Spinal TileLink Bus bundles
and explicit channel signal IDs in one SpinalDB component. It declares bus
widths, one line address, a bounded service assumption and
an independent expected-data signal. `rvw.tlc-monitor/1` reports generated
monitor and bind paths with `executed:false`. Generation is not a monitor
runtime pass. C/D data messages can span several equal beats. The expected
data signal contains one full line. This profile rejects other-line and
error traffic. C6 simple `Bus` types need `bus_family: spinal-tilelink`, typed
ChannelA through ChannelE descendants and exact signal member paths. B/D
param fields use the three-bit Spinal carriers. The result records the
finite model source SHA256 and generated permission relation under
`permission_model`. That relation hides channel and data state.
The monitor requires reset before clocks after time zero. Reset is active
high and clears the monitor asynchronously.
Actual protocol refinement and project oracle independence remain separate
obligations. The memory tool README defines profile fields and runtime limits.

## Generic multi-hart harness inputs

C1 adapters can declare `hartIds(config)` and accept `--hart-images PATH`.
The file uses `rvw.hart-images/1` from `rvw memory images`. Each row must match
one declared hart and its captured ELF hash. Relative ELF paths resolve beside
the manifest. The driver captures all images before compilation. Shared
segments must have identical address, file bytes and memory size. All other
segments must be disjoint, including BSS. `--boot-payloads` is incompatible.
The primary `--elf` remains the legacy C1 identity. `details.hart_images` holds
all captured identities and entries. Replay includes the manifest path.
`MultiHartSession` writes one C2/2 trace with per-hart retirement orders,
reset epochs and completion. It does not infer a memory order from capture.


The temporal frontend can combine captured source files for module-target
checker bindings. Original source records remain in the input snapshot. The
combined `inputs/temporal.sv` is a sealed generated proof artifact. Module-local
argument-free named properties resolve before monitor generation. Recursive or
unused named properties are refused. Only explicit ANSI input checker ports and
named-port module-target bindings are supported. Instance-target bindings and
checker scheduling extensions remain unsupported.

## Scalar axiomatic memory annotations

C2/2 can declare `memory_dependencies: complete` and
`memory_addresses: physical` and add `memory_model` to
retirement records. This object identifies the event by string `id`, integer
`hart` and integer per-hart `order`. It carries `kind` R/W/LR/SC/AMO/FENCE and
complete dependency source ID arrays `addr`, `data`, `ctrl`. Scalar memory
events carry byte `address`, integer `size` and `read` and/or `write` values.
Address, order and data can be nonnegative integers or canonical decimal
strings. Producers must use strings when their JSON library uses doubles.
A successful SC names its paired LR ID in `rmw`. Fences and aq/rl attributes
are decoded from RVFI instructions. The checker validates annotated bytes
against RVFI. Dependency completeness is a project observation contract.

`rvw.axiomatic-initial/1` has `locations` with string hex `address`, integer
byte `size` and string hex `value`. `rvw.axiomatic/1` reports allowed, forbidden
or inconclusive, the model, candidate count and an optional witness. Results
apply to one finite scalar execution under declared dependencies. Limits and
unsupported profiles cannot produce allowed or forbidden. No full-core proof
is implied. `rvw.concurrent-programs/1` contains seeded per-hart RV64 assembly
fragments and project requirements. `executed:false` is mandatory at generation.


## Concurrent per-hart ELF build

`rvw.concurrent-build/1` reports the result of `memory concurrent-build`.
`built` requires one compiled ELF per generated hart. `executed:false`,
`rtl:not_run` and `ordering:not_checked` keep compilation separate from
execution. `hart_images` names the hashed `rvw.hart-images/1` manifest.
`reference` names `rvw.axiomatic-initial/1`. `programs` records per-hart
entry, completion PC, private tohost, source SHA256 and linker SHA256.
Each image has disjoint private load memory and the same 40-byte shared
zeroed BSS segment. The reference includes shared doublewords and private
tohost locations. Projects must load all images before release, detect each
hart's completion and supply complete physical memory-event dependencies.
The command does not supply a scheduling or liveness guarantee.

## Generic multi-hart execution loop

`MultiHartExecutor` consumes captured C1 hart images and one RVFI probe per
hart. Project `MultiHartBackend` callbacks bind reset, shared memory, boot
vectors, cycle steps and completion. All images load while every hart is held
in reset. All boot vectors are set before release. Each step ends at a stable
RVFI sample boundary. Completion includes drained earlier effects. The park
callback prevents later effects. The executor emits independent C2/2 streams
and per-hart completion. Unfinished harts receive timeout at the cycle or
wall-clock limit. Dependency completeness and physical addresses default to
unavailable. This API does not infer global memory order or HSM transitions.


## Axiomatic reset and maintenance limits

The scalar axiomatic profile supports one boot epoch per hart. A second
reset, a trap event or an external maintenance event gives `inconclusive`.
These events do not silently disappear from the candidate graph. An LR
before reset cannot pair with an SC after reset. Initial reset records and
ordinary single-epoch executions remain supported under RVWMO and Ztso.


## Concurrent execution campaign

`rvw.concurrent-campaign/1` records `memory concurrent-run`. The command builds
seeded per-hart images, invokes an explicit C1 adapter and checks captured C2
with the selected scalar model. It records build metadata, adapter command and
SHA256, C1 status, trace SHA256, retirement counts and the axiomatic answer.
C1 config, seed, cycle limit and image hashes must match the generated run.
C2 hart IDs and image hashes must match too. Retired instruction bytes come
from the captured pre-launch images. Each hart starts at its entry and reaches
its generated completion PC. This direct-boot smoke profile has at most 10000
retirements. All scalar checker requirements still apply. A total budget of
at most 90 seconds bounds compiler, adapter and checker subprocesses. An
`allowed` result requires a passing C1, valid capture, and an allowed answer
from the selected model with a matching process exit. This is finite ordering
evidence. Project architectural and production qualification remain separate.

## SMP interrupt capture

The C2/2 writer can emit `irq` and `trap` events for an active hart.
Each event has that hart's current reset epoch and the common capture sequence.
The event payload uses the existing C2 IRQ or trap fields. File order remains
capture order. It does not establish cross-hart memory order.

## Project scalar dependency observations

The SMP example writes a separate derived C2/2 file. It sets
`memory_dependencies` to `complete` only after every captured instruction
matches its supported scalar dependency profile. The header's
`dependency_binding` gives the profile, original trace SHA-256 and binding
source SHA-256. The original capture stays unchanged. Unsupported instructions,
traps, faults, later resets and device accesses refuse this binding.

The profile uses RVWMO's syntactic source/destination rules. Loads and AMOs do
not carry source dependencies to their result register. Successful SC is a
memory event and defines its destination register. Failed SC creates no memory
event and has no syntactic destination register. It consumes the LR pairing.
A finite allowed execution is not a core compliance proof.

The example's `serial2` profile allows one accepted LSU transaction at a time.
It releases service at that memory instruction's retirement. Its common ELF
and per-hart tohost slots support shared-RAM Spike comparison. WFI and interrupt
programs are outside its qualified scope. The HSM profile uses concurrent
memory service and does not declare serialized-retirement ordering.

## SMP timing stress observations

The example's C1 `details.timing` records `seed`, `random_max_delay`,
`ready_percent`, `clock_enable_percent`, optional `fixed_latency`,
`base_sample_edges` and `clock_stall_edges` by hart. The terminal sample is
included in the edge count. It can exceed C1 `cycles` by one.

Clock enables change after capture. The memory service accepts a command only
on that hart's enabled edge. A response stays pending until an enabled edge
consumes it. The three `RVW_SMP_*` timing variables are included in replay.
They do not change the core source or the selected ISA. A replay claim requires
actual equality of the captured streams under the same inputs and settings.
These synchronous stalls do not qualify CDC or physical clock gating.

## Sparse axiomatic witnesses

The checker can emit `engine: sc-witness`. This is a sufficient sequential
consistency witness for either selected model. `witness.global_order` lists
every event. `witness.rf` lists the last preceding write for each read.
`witness.co` contains adjacent edges per location, including the initial write.
Its transitive closure gives coherence order. The checker uses observed read
values and checks successful LR/SC pairs before it emits this witness.
Failure to construct this witness does not reject an execution.

The bounded fallback enumerates store orders that preserve per-hart order at
each location. It filters read sources by address, size and observed value.
It rejects partial cycles with incremental graphs. `branches` counts prefix
search states. The limit bounds these states as well as complete candidates.
A limit produces `inconclusive`, including when no complete candidate was tried.
Independent enabled SC operations have one deterministic schedule. Stores with
equal values are not merged because their identities can affect dependencies.
