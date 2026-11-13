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
