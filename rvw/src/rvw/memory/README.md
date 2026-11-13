# Memory verification

`rvw memory images --hart-image 0=writer.elf --hart-image 1=reader.elf`
prints `rvw.hart-images/1`. Each row gives a hart ID, an absolute ELF path
and the SHA-256 of its bytes. A project adapter must load these images and
record each reset PC. This command does not execute or load an image.

`rvw memory check --trace rvfi.jsonl --reference reference.json`
checks a declared serialized memory boundary. MCP exposes `memory_images`
and `memory_check`. Exit 0 means observed consistency, 1 means mismatch,
and 3 means missing evidence or an input error.

The reference uses this format:

```json
{
  "schema": "rvw.serialized-memory/1",
  "boundary": "shared-ram",
  "initial": [{"address": "0x80000000", "bytes": "00000000"}],
  "writes": {
    "producer-store": {"address": "0x80000000", "data": "0x25", "mask": "0xf"}
  }
}
```

Initial bytes use increasing addresses. Write expectations must come from
stimulus or an independent architectural model. Do not copy them from the DUT.
C2/2 external read/write events name the boundary and have contiguous decimal
string `serialization` IDs. Reads provide one `read_from` ID for each selected
byte, in increasing byte-lane order. `initial` identifies initial bytes.
Every expected write must occur. Every hart must finish with pass.

## Decisions

Reuse the C2 reader for reset, epoch, capture and retirement validation.
Sort accepted actions by serialization ID. Capture order can differ.
Keep write stimulus separate from observed writes.

## Limits

This checker does not establish RVWMO or instruction semantics. It supports
read/write boundaries with at most XLEN bytes per event. It does not support
combined atomic boundary events. It checks sampled actions only. Missing events
need a project capture-completeness check. No production multi-image adapter
or general multi-hart architectural reference is supplied.

## Scalar axiomatic execution search

`rvw memory axiomatic --trace rvfi.jsonl --reference initial.json --model rvwmo`
searches candidate write orders and read-from choices. Select `ztso` for TSO.
The checker builds co, rf, fr, po-loc and preserved program order. It checks
coherence and model acyclicity and the RMW atomicity constraint. Preserved
order includes address, data, control and pipeline dependencies, fences and
acquire/release rules. The relation definitions follow herdtools7 7.58
`herd/libdir/riscv.cat` and `riscv-defs.cat`. This implementation is independent
Python code. It does not call herd7.

The initial-state file has schema `rvw.axiomatic-initial/1` and `locations`.
Each location has hex `address`, integer byte `size` and hex `value`.
C2/2 must declare `memory_dependencies: complete` and
`memory_addresses: physical`. Virtual RVFI addresses cannot stand in for
physical memory locations. Each retired memory action
and FENCE must have a `memory_model` object with `id`, `hart`, integer `order`,
`kind`, and complete `addr`, `data`, `ctrl` dependency ID lists. Dependencies
name earlier memory events on that hart. Non-fence events need integer byte
`address` and `size`, and `read` or `write` values. Address, order and data
can use canonical nonnegative decimal strings to preserve all 64 bits. Kinds are R, W, LR,
SC, AMO, FENCE. Successful SC also names its LR as `rmw`. The adapter must
compute dependencies through intervening non-memory instructions. Empty
lists are assertions that no such dependencies exist. Missing lists are not
empty lists. RVFI bytes, masks, hart identity and instruction kind are checked
against the annotation. aq/rl and fence domains come from the instruction.
`MultiHartSession` can take a complete-dependency declaration, a physical-address declaration
and an annotation callback. Adapters without these observations get `inconclusive`.

The supported profile has aligned scalar accesses with no mixed-size overlap,
one reset epoch per hart, no memory faults or trap events, no external
writers or maintenance events, and no device memory. LR/SC pairing cannot
cross a hart reset. Unsupported
instructions and profiles are inconclusive. A candidate limit also gives
inconclusive. `allowed` supplies a candidate witness under the declared
dependencies. `forbidden` means every candidate was rejected for this finite
execution. Neither result establishes full-core correctness or reference
instruction semantics. No native herd differential validation is claimed.

## Concurrent programs

`rvw memory generate --seed 7 --harts 3 --length 20` returns independent RV64
assembly fragments with races, lock loops, AMOs and fences. A project must
define RVW_SHARED_BASE, link each fragment at a distinct executable address,
initialize the shared 40 bytes and detect each completion symbol. Feed its
captured C2/2 execution to the axiomatic checker. Generation does not run a
DUT. The lock loops need declared fairness and a bounded watchdog. The project
must collect complete dependencies to earn an axiomatic result.

## Concurrent ELF inputs

`rvw memory concurrent-build --out seed7 --seed 7 --harts 3 --length 20`
compiles one RV64 ELF per hart. MCP exposes `memory_concurrent_build`.
The output directory must be fresh. RISC-V GCC must be installed. `--gcc`
selects its executable. `--timeout` is a total compiler budget of at most
60 seconds. Each compiler process runs with `nice -n 10`.

The build writes `hart-images.json` for `--hart-images` and `initial.json`
for `rvw memory axiomatic`. `build.json` records entry PCs, completion PCs,
private tohost addresses, source hashes and linker hashes. Each hart writes
one to its private tohost before it reaches its completion PC. `programs.json`
keeps the generated assembly fragments. Build logs and linker scripts remain
beside each ELF.

Private regions start at `--base`, default `0x80000000`, with 128 KiB per hart.
The shared 40-byte zeroed region starts at `--shared-base`, default
`0x81000000`. The linker emits the same shared BSS segment in every ELF.
Private ELF segments are disjoint. The initial-state file includes the five
shared doublewords and each private tohost. The adapter must load all images
before it releases the harts. It must finish each hart separately and capture
physical C2/2 events with complete dependencies. The lock loops need declared
bounded service and a watchdog. `built` means compilation completed. It does
not mean a DUT ran or that ordering passed.

## Concurrent program campaign

`rvw memory concurrent-run --adapter /project/run.sh --config dual --out seed7
--seed 7` builds per-hart ELFs, invokes an explicit project C1 adapter and feeds
its C2 capture to the scalar axiomatic checker. MCP exposes
`memory_concurrent_run`. The adapter must support the generic `run` command,
`--hart-images` and RVFI capture. No core is selected by default.

The default model is RVWMO. `--model ztso` selects Ztso. `--harts`, `--length`,
`--base` and `--shared-base` select the generated inputs. `--max-cycles`
bounds the RTL run. `--timeout` covers compilation, adapter execution and
candidate search. It is at most 90 seconds. `--limit` bounds candidates.
All subprocesses run with `nice -n 10`. The output directory must be fresh.

The adapter must report passing C1 with the requested config, seed, cycle
limit, primary ELF hash and `details.hart_images`. C2 must contain the same
hart IDs and `hart_images` hashes. Each hart starts at its generated entry
and reaches its completion PC. Every retired instruction must match the
captured pre-launch ELF bytes. The current smoke profile supports at most
10000 retirements and direct boot into these 32-bit instruction streams.
Instruction byte checks bind the capture to its input images. Projects still
need architectural reference comparisons.

A scalar ordering result also requires all harts to complete, complete
physical memory dependencies, and the axiomatic profile's other limits.
Missing evidence, timeout or inconsistent process results give `inconclusive`.
`campaign.json` records the build, adapter command/hash, C1 status, capture
hash/counts and checker result. Adapter and checker logs remain beside it.
`allowed` applies only to the captured finite execution and selected model.
The workflow tests use synthetic C1/C2 adapters. A production multicore run
still needs a project adapter and is not supplied by those tests.

## Generated TileLink-C channel monitor

`rvw memory tilelink-bind --database design.sqlite --profile tlc.json --out monitors`
selects two typed TileLink `Bus` bundles from SpinalDB and writes a
SystemVerilog monitor and bind. Existing output files are not overwritten.
The project profile uses `rvw.tlc-bind/1`. It supplies `source_bits`, `sink_bits`,
`address_bits`, `data_bits`, `size_bits`, `line_bytes`, hex `line_address`,
positive `bound_cycles`, and a named `fairness` service assumption. The line
contains one or more complete power-of-two data beats. Other-line traffic is
outside this profile.

`clients` has two rows with `bundle_id` and a `signals` map from channel field
name to SpinalDB signal ID. `FIELDS` in `tilelink_bind.py` lists every required
field and width. Both bundles and all mapped signals must belong to the same
bind component. The generator checks bundle types, signal widths and pruning. C6 can store
the simple type name `Bus`. For that form, set `bus_family` to
`spinal-tilelink`. The generator requires `ChannelA` through `ChannelE` below
each bus and checks each mapped signal against its exact bus member path.
Qualified `spinal.lib.bus.tilelink.Bus` records remain supported. All opcode
and param carriers have three bits, including the B and D param fields.
The profile also supplies signal IDs for active-high `clock` and `reset` and
`expected_data`. Set `oracle_kind` to `independent-stimulus`. Expected data must
come from a project stimulus/reference signal. It must not come from channel
read data. The generator cannot prove that independence from a signal ID.

The monitor assembles accepted C/D data beats into complete messages. Headers
must stay constant through a message. Partial messages retain a bounded age.
The expected-data signal has one full line of bits. The project must hold the
correct reference value for each message epoch, including simultaneous C/D
completions. The monitor checks accepted Acquire, Probe, ProbeAck, Release, Grant,
ReleaseAck and GrantAck actions. It tracks source and sink lifetimes, probe
responses, N/B/T permission safety, complete-line data and bounded outstanding
ages. Set `trunk_dirty` only if the project model treats every Trunk copy as
dirty. That policy requires data on a shrinking Trunk acknowledgment/release.
Same-cycle shrinks precede grants in the observer. Reset clears all monitor
state. The monitor accepts reset asynchronously. It ignores initial evaluation
at time zero until reset arrives. A later clock without a prior reset is an
error. Independent client resets and stalled-payload stability are not checked.
Error responses are rejected by this success-only profile.

The permission check is generated from the exhausted finite model in
`SpinalChecks/coherence/model.py`. The result records its SHA256, state and
edge counts and finite permission projection. The projection hides data,
channels and request history. It is a permission safety check. It does not
prove that channel RTL refines the full protocol model.

`TypedCacheBindSpec` extracts a real C6 database from two Spinal TileLink
client ports and a real `CacheFiber`. It generates the monitor and bind from
that database, compiles both with the cache RTL, and runs seeded coherent
traffic with backpressure. `RVW_TYPED_TLC_OUT` can retain the database, profile,
RTL and generated monitor in a fresh directory. `RVW_TYPED_TLC_CORRUPT=1`
changes a backing-memory byte before the first grant. Run that negative case
in a separate JVM because a native monitor fatal stops the process.
Scripted channel tests also check incomplete messages, changed headers,
stale data, missing acknowledgments and missing reset. These runs do not
prove full coherence refinement or qualify a production multicore design.

## Queued directory experiments

`rvw memory directory --profile moesi --lines 2 --requests 1` checks a finite
queued directory model. Select MESI or MOESI, one or two lines, and one to three
requests per client. `--limit` bounds state exploration. `--bug` selects a seeded
counterexample. The report states the named weak-fairness assumptions and model
bounds. Use RVW_ROOT to select the installed tools checkout. See the queued
profile section in `SpinalChecks/coherence/README.md` for semantics and limits.
A finite-model pass is not a coherent-fabric RTL result.

## Native concurrent completion smoke

`rvw memory concurrent-smoke --out smoke --seed 7 --harts 3 --length 20`
links the generated fragments into one bare-metal image. A hart-ID dispatch
starts one fragment per Spike hart. Separate completion flags and a final
HTIF tohost write require every hart to finish. The wrapper has no C runtime
or shared stack. Shared data starts at zero in a separate writable section.

The command uses installed RISC-V GCC and Spike through `nice -n 10`. Each
command has a timeout of at most 60 seconds. Missing tools and timeout are
inconclusive. The report records source/ELF hashes, ISA, seed, hart count and
the Spike command. It also records `ordering:not_checked` and `rtl:not_run`.
A pass establishes native completion only. It is not an RVWMO result. Capture
a project C2/2 trace with complete dependencies to use the axiomatic checker.

The multi-beat native smoke uses 64-byte lines over 64-bit data beats. It rejects
an early grant, a corrupt middle D beat, a truncated ProbeAckData, a changed D
header, a corrupt middle C beat and a truncated ReleaseData. The original
single-beat cases remain regression checks. This is scripted channel evidence.
It does not establish refinement of a real cache/home implementation.


## Production multicore RTL evidence

The [SMP example](../../../../examples/smp/README.md#measured-results) now declares
two to eight cacheless VexiiRiscv RTL harts. Each hart has a C2/2 stream and
completion record. Shared RAM, atomic service, CLINT and PLIC are simulation
models. The example also has separate serialized comparison and S-mode HSM
profiles.

At seed 17, LR/SC passed in 1060 cycles with 498 retirements. AMO passed in
18630 cycles with 8346 retirements. Six pinned litmus captures are consistent
with native herd7 7.58 outcomes. Cross-hart FENCE.I passed at 191/62 cycles/
retirements; IPI at 247/74; HSM at 1431/530. Spike matched all 38 instructions
in a shared-RAM two-hart capture with zero masks and zero synchronizations.

Generated seeds 7, 17 and 23 are allowed by the independent RVWMO checker after
project dependency binding. Seed 1 remains inconclusive at 100000 candidates.
The original captures retain unavailable dependency status. The binding writes
a separate trace and records its input/source hashes. These are finite results.
They do not qualify a coherent cache, complete RVWMO implementation or all SBI
behavior. See the example's full counts, reproduction commands and JSON evidence.
