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

### Blocking online comparison

Use `rvw cosim live --lockstep --elf ELF --core CORE --out OUT --simulator COMMAND`.
The generic `RvfiTraceWriter` connects through `RVW_COSIM_PORT`. Each C2 record
blocks until the reference checks it. A mismatch stops the run and returns the
usual `rvw.cosim/1` report with reproduction data and the first difference.
Write interrupt input events before the affected retirements. Write taken trap
events at the instruction boundary where the DUT takes the trap. Spike receives
the interrupt cause at that boundary. Debug requests are not yet supported.

SystemVerilog adapters can link `Cosim/lockstep_dpi.cc` and import
`int rvw_cosim_observe(input string c2)` through DPI-C. Send a header first.
Stop on any nonzero return. Call `rvw_cosim_close()` at shutdown. The Scala
harness uses the same protocol through `riscvsim.Lockstep`.
