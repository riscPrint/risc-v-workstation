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
no memory faults, no external writers, and no device memory. Unsupported
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

## Generated TileLink-C channel monitor

`rvw memory tilelink-bind --database design.sqlite --profile tlc.json --out monitors`
selects two `spinal.lib.bus.tilelink.Bus` bundles from SpinalDB and writes a
SystemVerilog monitor and bind. Existing output files are not overwritten.
The project profile uses `rvw.tlc-bind/1`. It supplies `source_bits`, `sink_bits`,
`address_bits`, `data_bits`, `size_bits`, `line_bytes`, hex `line_address`,
positive `bound_cycles`, and a named `fairness` service assumption. The line
contains one or more complete power-of-two data beats. Other-line traffic is
outside this profile.

`clients` has two rows with `bundle_id` and a `signals` map from channel field
name to SpinalDB signal ID. `FIELDS` in `tilelink_bind.py` lists every required
field and width. Both bundles and all mapped signals must belong to the same
bind component. The generator checks bundle types, signal widths and pruning.
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
state. Independent client resets and stalled-payload stability are not checked.
Error responses are rejected by this success-only profile.

The native test uses a scripted two-client channel fixture and a typed SQL
fixture. Verilator elaborates the generated bind and runs five injected defects:
early grant, stale grant data, lost GrantAck, missing grant and stale intervention
data. This is monitor runtime evidence. It is not a real home/cache refinement
proof or a production design-database integration result. Real coherent-fabric campaigns and independent protocol-model cross-checks
remain open.

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
