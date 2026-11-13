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
