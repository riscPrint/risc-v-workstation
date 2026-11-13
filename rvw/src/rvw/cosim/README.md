# rvw cosim

See [Cosim/README.md](../../../../Cosim/README.md) for build, use, MCP tools and limits.

## Decisions

[Cosim/README.md](../../../../Cosim/README.md#decisions) is the canonical cosim documentation.

Set `pmp_granularity` in the platform JSON to the minimum PMP region size in
bytes, as a power of two of at least 4. Spike applies the selected grain.
The lowest matching PMP entry has priority, as required by the ISA. Sail
currently refuses a grain other than 4.

Sail fault records now include independent scalar attempts and completion bytes
from its memory log. The checker compares those observations when present.
Only accesses within one virtual page are supported. Split-page fragments need
translation observations. Spike partial effects remain unsupported. Full Sail
CSR snapshots remain unavailable; memory logs do not supply CSR state.
