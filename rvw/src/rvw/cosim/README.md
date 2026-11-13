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
the interrupt cause at that boundary. Declared C2/2 debug halt events use the same instruction boundary.

SystemVerilog adapters can link `Cosim/lockstep_dpi.cc` and import
`int rvw_cosim_observe(input string c2)` through DPI-C. Send a header first.
Stop on any nonzero return. Call `rvw_cosim_close()` at shutdown. The Scala
harness uses the same protocol through `riscvsim.Lockstep`.

### Observation exchange

`rvw cosim exchange --source INPUT --from c2 --to rvvi --out OUTPUT` exports
RVVI-TEXT 0.5. Select `--from rvvi --to c2` to restore a complete exported trace.
The `rvw.c2` vendor STATE extension retains C2 fields that have no native mapping.
The standard source is [RVVI-TEXT 0.5](https://github.com/riscv-verification/RVVI/blob/04dc469012f718ffe104c1c1d0cd8cea66f96724/RVVI-TEXT/README.md).

Use `spike` for commit logs. Exports include lossless `# RVW-C2` comments.
Plain Spike logs can be imported with `--to observations`. They lack sources,
next PC, memory observations and asynchronous events needed for full C2 checks.
They cannot be converted to full C2. Unsupported effects are errors. The bounded
RVVI importer retains raw elements for sparse retirements. It does not implement
all RVVI state latching. `cosim_exchange` provides the same operation over MCP.
Format exchange does not run an independent reference or establish a match.

### Custom reference extensions

Set `reference_extensions` in the project's cosim platform JSON:

```json
{"reference_extensions": [{"library": "extensions/custom.so", "name": "rvw_example"}]}
```

The path is relative to the platform file. Build the library against the same
Spike headers and library used by `Cosim/build.sh`. Export a Spike extension
factory with `REGISTER_EXTENSION`. Inputs capture each library and record its
digest. Spike loads the captured library and registers the named extension
before it runs the ELF. Declare custom CSRs in C2 `csr_snapshot` to compare them.
`Cosim/tests/custom_extension.cc` is a small custom-0 instruction example.

Missing libraries, unknown extensions and unsupported reference state give
errors. Sail does not load these libraries. C2 reference generation still refuses
unknown custom operand layouts. This does not establish custom ISA compliance.
Native extension dependencies must use the same installed Spike ABI.

### Debug entry state

C2/2 adapters can declare `debug: true` and emit complete `debug` snapshots
with `mode`, `dpc`, `dcsr` and `step` on every retirement. Emit a separate
`event: debug`, `action: halt` record at the taken halt boundary. Spike takes a
halt request without executing debug ROM. The checker compares all four fields.
Use `action: observe` for a snapshot without an injected request. Ordinary trap
events remain separate. This also works through the blocking DPI transport.

Resume, debug ROM execution, triggers and automatic single-step transitions
remain unsupported. The step bit is compared as state. A full halt/step campaign
around WFI, interrupts and exceptions is not claimed.

### Hypervisor delegation cases

`rvw.cosim.hypervisor_cases.cases()` supplies three RV64H assembly programs:
VS ECALL to HS, VU ECALL to HS, and delegated VU ECALL to VS followed by VS
ECALL to HS. Each program includes literal expected privilege, cause and
virtualization transitions. Core adapters can compile these programs and capture
C2/2 `hypervisor` snapshots for the existing comparator. The native tests run
these programs on Spike. They establish reference readiness, not an H-capable
DUT result. Two-stage stores, fault precedence and full H interrupt campaigns
remain outside these small cases.

### Pinned vector suite sources

Use `rvw cosim vector-source --out /external/path/riscv-vector-tests --json`.
The MCP tool is `cosim_vector_source`. Setup fetches CHIPS Alliance vector tests
at `f76bff121dce91b6b23e1d37be77a5e44af914c3` and its test environment at
`81721c126d7dd7335829948b4a19070546e465d6`. Both are ordinary external clones.
No submodule is added to the workstation. Setup writes `rvw-source.json`.
It does not build or run the suite.

Follow [the vector suite guide](../regress/README.md#riscv-vector-tests) to build
stage2 ELFs, register the project suite and compare captured C2/2 vector state.
A passing self-check without vector-state comparison cannot pass that flow.
The upstream tests derive expected values from Spike. Their self-check is not
an independent second reference. Memory partial effects and permitted agnostic
values remain outside the current comparator.
