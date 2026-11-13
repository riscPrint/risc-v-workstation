# Optional CHERI comparison assessment

The candidate reference is [CHERI RISC-V Sail](https://github.com/CTSRD-CHERI/sail-cheri-riscv/tree/cf36cfd4fca0bd10a5906651bf48b9674ccd0a2b),
commit `cf36cfd4fca0bd10a5906651bf48b9674ccd0a2b`. Its README describes C,
OCaml and TestRIG builds. This assessment has not built or run them. Its ISA
revision and dependency pins need review against the target CHERI core.

A project can record this optional architecture in its cosim platform:

```json
{"cheri": {
  "repository": "https://github.com/CTSRD-CHERI/sail-cheri-riscv",
  "revision": "cf36cfd4fca0bd10a5906651bf48b9674ccd0a2b",
  "capability_bits": 128
}}
```

A future capability snapshot must preserve tags, base, top, permissions,
sealed state, object type and offset for capability registers and PCC. It must
also preserve memory tags and capability store/load effects. A fault record
needs the ordinary cause/tval plus the capability cause and register index.
Compressed capability bytes alone do not establish decoded bounds or tags.

The first independent cases should check tag loss after integer writes, bounds
failure, permission failure and sealed capability use. Negative cases must
change each observed tag, bound, permission and fault independently. Shared
Sail-generated expected values are reference fixtures, not independent proof.

The config hook currently fails closed. Stock Spike and Sail scalar comparison
cannot earn a CHERI match. No capability trace schema, reference bridge or
qualification claim is added. CHERI remains separate from standard profile
compliance.
