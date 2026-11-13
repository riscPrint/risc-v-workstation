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
C2/2 must declare `memory_dependencies: complete`. Each retired memory action
and FENCE must have a `memory_model` object with `id`, `hart`, integer `order`,
`kind`, and complete `addr`, `data`, `ctrl` dependency ID lists. Dependencies
name earlier memory events on that hart. Non-fence events need integer byte
`address` and `size`, and integer `read` or `write` values. Kinds are R, W, LR,
SC, AMO, FENCE. Successful SC also names its LR as `rmw`. The adapter must
compute dependencies through intervening non-memory instructions. Empty
lists are assertions that no such dependencies exist. Missing lists are not
empty lists. RVFI bytes, masks, hart identity and instruction kind are checked
against the annotation. aq/rl and fence domains come from the instruction.
`MultiHartSession` can take a complete-dependency declaration and an annotation
callback. Adapters without these observations get `inconclusive`.

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
