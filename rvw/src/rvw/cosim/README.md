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

### Serialized multi-hart comparison

`rvw cosim check` detects multi-hart C2 automatically. The header must declare
`memory_profile: serialized-retirement`. One Spike machine contains all harts
and shared RAM. Instructions execute in capture order. Each hart has separate
register, synchronization and recent-match state. Results retain per-hart reports
and identify the first mismatching hart. All hart end records are required.

This first profile requires a shared ELF/reset PC and initial epoch zero.
It refuses later resets, external-agent events, custom reference extensions and
absent-PMP emulation. Stores are visible to subsequent captured retirements.
A valid weak-memory execution can fall outside this profile. This does not check
RVWMO, coherent bus transactions or store-buffer visibility.

### Two independent references

Use `rvw cosim adjudicate --elf ELF --trace TRACE --core CORE --json`.
The MCP tool is `cosim_adjudicate`. Set `RVW_SAIL` for the Sail executable.
Both references receive the same inputs through their normal captured flow.
The output retains both full reports and checks their input hashes. It names
which reference the DUT matches at the first disagreement. If neither matches,
that list is empty. A missing model or unsupported capability is inconclusive.

A complete match requires both references to compare the same complete trace.
A disagreement never becomes a pass. Automatic reduction and specification-rule
attribution remain future work. Inspect the original synchronization records
before interpreting a disagreement. Use `--strict` to disable synchronization.

### CHERI assessment hook

The optional platform `cheri` object records a pinned reference and capability
width. See [the short assessment](../../../../Cosim/CHERI.md). Stock comparison
reports unsupported reference evidence when it is selected. The hook does not
compare capabilities or establish standard RISC-V profile compliance.

### Optional QEMU boot observations

Capture a matching QEMU machine with `-smp 1 -accel tcg,one-insn-per-tb=on
-d cpu,nochain -D qemu.log`. Use the same memory map, image and boot inputs as
the DUT. QEMU's CPU log records state before each instruction. The comparator
uses the next snapshot to check a destination write. It can skip up to 4096
boot-ROM snapshots before the first DUT PC. `--max-prefix` changes this bound.

Use `rvw cosim qemu-check --trace TRACE --log qemu.log --json` for a bounded
single-hart boot segment. The MCP tool is `cosim_qemu_check`. Only PC, next PC,
integer sources and integer destinations compare. The report lists unchecked
state and always sets `architectural_match: false`. Interrupt, trap and debug
events return inconclusive. This is useful for early Linux boot segments before
those events. It does not establish a full Linux boot match.

Add `--qemu-log qemu.log` to `rvw cosim adjudicate` for an optional partial third
reference. The result retains all three reports. QEMU can expose disagreement
in the observed fields. It cannot outvote an architectural mismatch. An actual
native bare-metal smoke is tested. Full Linux and asynchronous injection remain
NOT RUN/unsupported.
