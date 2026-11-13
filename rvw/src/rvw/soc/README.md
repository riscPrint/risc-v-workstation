# SoC maps

`rvw soc generate MAP --out DIR --json` validates project data and writes:

| File | Use |
|---|---|
| `platform.json` | Existing Spike shim and `rvw cosim check --platform` input. Reference policy stays explicit. |
| `spike.args` | One native Spike argument per line: ISA, reset PC and RAM. MMIO device models are not created. |
| `memory.ld` | GNU ld MEMORY fragment. Include it from a program's section layout. |
| `soc.h` | C region bounds and absolute register addresses. No volatile access functions. |
| `soc.dts` | Device tree memory nodes. CPU, device drivers and interrupt-controller bindings need board data. |
| `sim-map.json` | Simulation region attributes, registers and interrupt wiring. Adapters must load this format explicitly. |
| `registers.svd` | CMSIS-SVD register subset. No CPU description or inferred peripheral driver. |

```sh
rvw soc generate examples/vexriscv/soc.json --out /tmp/vex-soc --json
rvw soc generate examples/boom/soc.json --out /tmp/boom-soc --json
rvw cosim check --platform /tmp/boom-soc/platform.json --trace TRACE --elf ELF --json
```

## Observed request-tag pairing

Use `rvw soc pair --capture bus.jsonl --trace rvfi.jsonl --result result.json --out pairs.json`.
MCP tool `soc_pair` uses the same command. The trace is independently observed
C2 retirement data. The capture must use `rvw.soc-events/1` with observation
`rtl_request_response_retire_tags`. Its header binds the C2 file hash, C1
source/RTL/ELF/seed identity, simulation run ID and `data_bytes`.

Each accepted bus request has a unique captured `tag`, cycle, aligned address,
write direction, byte mask and data. Responses carry the same tag, cycle, data
and error bit. A `retire_link` records the independently observed retirement
order, cycle and request tag list. A project monitor must observe that linkage.
The tool never infers it from equal addresses or copied software requests.

The checker compares split-beat byte addresses, data, direction, completion time
and memory faults. Missing responses or links remain gaps. Duplicate or reused
tags are refused. Posted-store responses after retirement need separate error
reporting evidence. Unretired requests need independent kill/flush evidence.
Matching samples remain inconclusive. Multi-hart tags, address translation,
big-endian beats, AMO pairing and full bridge/register semantics remain outside
this increment. Existing version-1 harness captures do not emit these tags.
Actual core capture integration and fresh DUT evidence remain open under #134.

## Data

`rvw.soc/1` has `name`, `address_bits`, `platform`, `regions` and `interrupts`.
All fields are required. Unknown fields are errors. Names use `[a-z][a-z0-9_]*`.
`platform` uses the existing cosim platform fields, except `ram` and `mmio`.
Regions generate those two fields. The existing platform reader validates the
result before any output is written.

Each region has `name`, `kind` (`ram` or `mmio`), `base`, `size`,
`permissions` (`r`, `rw`, `rx`, `rwx`), `cacheable` and `registers`.
Addresses and sizes accept integers or integer strings. Ranges are half-open.
Decode windows must have an aligned power-of-two size. Overlaps and address
width overflow are errors. The reset PC must lie in an executable region.

Registers have `name`, `offset`, `width` (8/16/32/64), `access` (`r`/`w`/`rw`),
`reset` (integer or null for unknown), `read_action` (`none`/`clear`) and
`write_action` (`normal`/`one_to_clear`). Registers must fit without overlap.
Interrupts have `name`, `region`, `register` and a `cause` from platform
`irq_inputs`. These declare wiring, not a complete interrupt-controller model.
BOOM's timer increments with cycles; the register subset does not model that
behavior. VexRiscv has no mapped devices; its external IRQ inputs remain in the
platform policy. Examples describe the existing simulation harnesses.

## Decisions

JSON is the primary format. It fits the existing cosim reader, requires no new
runtime package and can carry simulation and reference policies in one file.
SystemRDL and IP-XACT import/export were considered. A full importer needs
register elaboration and bus/interrupt semantics beyond this increment. It must
reject unsupported constructs before it can replace project data. The strict IP-XACT import subset below now covers simple register blocks. CMSIS-SVD export covers the simple register
subset, including [access and reset](https://arm-software.github.io/CMSIS_5/SVD/html/elem_special.html)
and [read/write side effects](https://arm-software.github.io/CMSIS_5/5.8.0/SVD/html/elem_registers.html).
No lossless round trip is claimed.

## Limits

Generation does not change RTL. Adapters can load the runtime map as described below. The two examples
preserve their current cosim settings. Generated device trees are memory fragments,
not bootable board descriptions. Bus decoding, bridge behavior, physical hardware
and reference device models need separate evidence. No export establishes a pass.

## Bounded consistency checks

```sh
rvw soc check examples/vexriscv/soc.json \
  --bindings examples/vexriscv/soc-bindings.json --db /path/to/vex.db --json
rvw soc check examples/boom/soc.json \
  --bindings examples/boom/soc-bindings.json --db /path/to/design.db --json
```

The database opens read-only. Schema `rvw.designdb/20` is required.
`rvw.soc-bindings/1` contains three lists:

- `signals`: `path` and `width`. Width is a positive integer or `address_bits`.
- `decoders`: `region`, `path` and `key_template`. The template is an exact
  SpinalDB assignment key. It must contain `{base}` and `{mask}`. The checker
  inserts hexadecimal literals without `0x`, from the region base and complement
  of its size minus one within `address_bits`. Only one full, unconditional assignment is supported.
  Hashed and incomplete expressions give no evidence. This is a comparison of a
  project-declared expression shape, not a general decoder inference engine.
- `bridges`: `name`, `region`, `local_base` and `data_bytes` (1/2/4/8/16).
  These select the expected translation for optional transaction samples.

`--transactions FILE` reads JSONL records with `bridge`, `software_address`,
`bus_address` and `size` in bytes. Each record must pair the same access at the
software and bus endpoints. The checker tests software bounds, local address
translation and beat crossing. The capture adapter must pair transactions.
The checker does not infer pairs from an RVFI trace. A fixture is not evidence
that a real bridge performed the access.

Each check returns `consistent`, `mismatch` or `unavailable`. Missing paths,
multiple assignments and opaque keys give `unavailable`. Any observed mismatch
sets overall `status=mismatch` (exit 1). Otherwise the result is always
`inconclusive` (exit 3). Invalid input gives `error` (exit 2).
There is no pass mode: widths, expression snapshots and finite samples cannot
establish all bridge behavior. The result lists the missing behavior checks.

Example bindings currently select only external bus widths. The VexRiscv RAM
map lives in the Scala simulation harness, outside the elaborated RTL. BOOM also
uses a simulation memory agent. Neither example claims decoder or bridge
coverage. Rebuild each database through its project query adapter to refresh
source identity. A cached database check establishes only the listed widths in
that file. Real paired transaction capture, generated bridge assertions,
endianness, error responses and side-effect models remain open under #134.

## Runtime maps and live capture

Generate a map, then give `sim-map.json` to the adapter:

```sh
rvw soc generate examples/boom/soc.json --out /tmp/boom-soc
RiscvSim/boom/run.sh run --elf ELF --out OUT --max-cycles 20000 \
  --soc-map /tmp/boom-soc/sim-map.json --rvfi-trace --json
rvw soc capture-check examples/boom/soc.json \
  --capture OUT/soc-transactions.jsonl --result OUT/result.json --json
```

The VexRiscv launcher accepts the same `--soc-map` option. Its RAM agents use
map bounds and permissions for fetches, loads and stores. It refuses MMIO regions.
Its reset vector stays fixed in RTL. BOOM checks ELF segments and accepted
TileLink A requests against the map. BOOM takes device addresses and initial
values from `clint` and `intgen` registers. Device placements must stay in the
existing RTL device windows. This option does not change the core's cacheability
or RTL decoder. BOOM refuses different cacheability, RAM permissions or interrupt
wiring. Its RAM regions must stay within the fixed RTL RAM window. A missing map keeps the legacy adapter behavior.

The driver captures map bytes when it parses the job. It saves those bytes as
`OUT/sim-map.json`. Results include `soc_map_sha256`. Replay names the original
map path; keep that input unchanged, or use the saved map. The capture header
records map, source and RTL identity. Each record observes an accepted request
and the selected map region. VexRiscv uses `observation=harness_decoder` and
records full memory-service words at its RAM decoder. BOOM uses
`observation=map_monitor` and records TileLink request sizes, including cache-line
acquisitions. BOOM classifies requests with the map; it does not observe RTL
decoder selects. Its capture cannot establish actual RTL decoder selection.
The checker compares the saved map with project data and checks each selection.
It rejects different map, source or RTL identities. A missing end record stays
inconclusive. The checker has no pass verdict.

These records do not pair retirement accesses with bus requests. They do not
check bridge width conversion, byte ordering, response errors, register side
effects or all decode inputs. BOOM cache hits need no external request.
These limits keep issue #134 open.

Cosim also accepts `rvw.soc/1` directly as `--platform MAP`. The command captures
that file before it derives RAM, MMIO and Spike policy. Generated `platform.json`
remains supported. No new Spike device model is inferred from a region.

## IP-XACT register import

```sh
rvw soc import-ipxact registers.xml --template soc.json --out imported.json
```

The importer accepts a standalone `memoryMap` in the IP-XACT 1685-2014 namespace.
It requires `name`, `addressUnitBits=8` and at least one `addressBlock`.
Each block requires `name`, `baseAddress`, `range`, `width`, and `usage=register`.
Its name and bounds must equal a template MMIO region. Registers require `name`,
`addressOffset`, `size` and `access`. The supported access values are `read-only`,
`write-only` and `read-write`. Each register requires one field at `bitOffset=0` with `bitWidth` equal to `size`.
The field can have one `resets/reset` with `value` and a full `mask`.
Optional `readAction=clear` and `modifiedWriteValue=oneToClear` map to JSON side
effects. Unknown elements and attributes are errors. Partial or multiple fields, arrays, aliases,
expressions, component wrappers and bus interfaces are refused. No unsupported
semantics are silently removed. Template regions and interrupts remain explicit.
The complete resulting map must validate before the output is written.
This is a register subset import, not a lossless IP-XACT round trip.

The subset follows the [Accellera 1685-2014 memory map schema](https://www.accellera.org/XMLSchema/IPXACT/1685-2014/memoryMap.xsd).
The importer checks its subset; it does not run full XSD validation.

### Concurrent device events

`rvw formal device-events --model soc.json --trace events.json --out result.json`
checks independent register state across concurrent masters. MCP:
`formal_device_events`. The map is the existing `rvw.soc/1` format.
The trace uses `rvw.device-events/1`, `linearization=accepted_request`, and an
`events` array. Each event has a nonnegative `cycle`. Array order declares the
order within one cycle. Cycles must not decrease.

A `request` has `master`, nonnegative `id`, `address`, byte `size`, boolean
`write`, write `data`, and optional expanded bit `write_mask`. IDs are unique
within each master's outstanding requests. A `response` has `master`, `id`,
boolean `error` and read `data`. Responses can reorder across IDs and masters.
A `hardware` event has `address`, optional nonnegative `increment`, and optional
`clear` and `set` bit masks. Increment wraps to register width; clear then set
follow it. A `state` event has `address` and observed `value`.

The oracle starts from map reset values. It never starts from DUT read data.
Accepted requests apply software effects in array order. Read responses compare
against the value before read-clear. The model checks decode/access errors and
exact full-width accesses. Outstanding requests at trace end remain listed.
A mismatch returns 1. Matching observations remain inconclusive and return 3.
This contract does not bind a real device or establish trace completeness,
independent event provenance, interrupt behavior, or device-specific latency.

### Paired bridge beat samples

Bridge bindings can set `byteorder` and `software_byteorder` to `little` or
`big`. Both default to `little`. An extended transaction record keeps `bridge`,
`software_address`, `bus_address` and `size`. It adds `write` (boolean), `data`
(the software value), `error` (the software response) and `beats`.
Each beat has `address` (aligned local bus word address), `data` (full bus word),
`mask` (one bit per byte lane, indexed by ascending address), `write`, and `error`.
Each beat direction must match the software operation.
Both data values accept integer strings. A sample covers 1 to 64 software bytes.

The checker compares the selected byte lanes with the software byte range.
It detects duplicate, missing and extra lanes. Transfers can span several bus
words. It compares byte values through each endpoint's byte order. It compares
the software error with the OR of bus errors. Failed response data is unspecified.

Optional `register` has independently observed `before` and `after` values.
It requires an exact full-width mapped register access. The checker uses the
map's access policy, read-clear and write-one-to-clear rules to compute the
expected next value. Failed accesses must keep the value. Autonomous registers,
partial register accesses and multi-master interference need a richer model.

The capture producer must pair the same operation and observe both endpoints.
These fields do not establish capture provenance. Fixture tests check comparison
rules only. The supplied BOOM and VexRiscv captures do not yet emit these fields.
A matching sample remains inconclusive. Real decoder bindings, source freshness
and complete decode coverage remain open under #134.

Register observations can also declare expanded bit `write_mask`, `hw_clear`
and `hw_set`. Missing masks select all write bits; missing hardware masks are
zero. The checker applies software effects, hardware clear, then hardware set.
Hardware events can change state during a failed bus access. Supply independent
hardware observations for the full transaction interval. The checker does not
infer them from the observed final register value. These paired observations
do not establish behavior between transactions or under concurrent bus masters.

Use `rvw soc check MAP --bindings BINDINGS --db DB --connections TABLE` to
include structural connectivity checks in the memory-map report. TABLE uses
the CSV, JSON or TOML format of `rvw formal connectivity`. The report retains
map/bridge transaction checks and adds endpoint resolution, input influence
and input hashes. Structural paths do not prove bridge behavior. Run the same
table with `rvw formal connectivity --run --proof-mode prove` to request
value-transfer proofs. Real retirement/bus pairing and source provenance are
still required for a mapped DUT integration claim.

## Spinal composition

`rvw soc compose SPEC --out NEW_DIR [--elf FILE]` generates a Spinal top and
software exports. MCP: `soc_compose`. See [SpinalSoc](../../../../SpinalSoc/README.md)
for the explicit APB3 wrapper profile and its limits. This command generates
source. It does not report a run or proof result.

## Implementation handoff

`rvw soc handoff --db design.db --out NEW_DIR [--settings FILE]` copies every
captured input after it verifies the database hash binding. MCP: `soc_handoff`.
The bundle contains `files.f`, `constraints.sdc`, clock/reset and frequency
lists, memory dimensions and ports, component hierarchy and blackbox generics.
SDC comes from the existing `rvw lint` SDC backend. Settings can contain its
`sdc` and `intent` dictionaries. SDC findings remain in `handoff.json`.

RTL must have captured input bindings. Missing or stale files are errors.
Blackboxes remain unresolved entries. Ordinary Scala constructor parameters
are not in the database; the bundle states that gap. The bundle preserves
database metadata and file hashes. It is an implementation input package,
not physical implementation, timing signoff or tape-out evidence. Keep
bundles outside version control.

## External implementation feedback

`rvw soc feedback --db design.db --source feedback.json --out NEW_JSON`
imports external report links. MCP: `soc_feedback`. Input schema
`rvw.soc-feedback/1` requires `database_sha256`, `tool`, `scope`, `constraints`,
`reports` (paths relative to the input) and `findings`. Each finding has `kind`
(`timing`, `area`, `cdc`, `dft`), `endpoint`, `message` and `report`.

The database hash must match. The importer hashes reports and resolves signal
names with the existing design query reader. It preserves unmatched or
ambiguous names with diagnostics. Matched rows retain RTL paths and Scala
file/line links. Output is `imported_claims`. It does not validate the report's
analysis or promote an external signoff claim to a workstation result.

## Memory BIST requirements

`rvw soc mbist --db design.db --source mbist.json --out NEW_JSON` exports
memory BIST intent. MCP: `soc_mbist`. Input `rvw.soc-mbist/1` has a `memories`
list. Each entry has `path`, `width`, `depth`, `test_enable`, binary
`functional_value`, a `repair` list of signal names and `isolation_connections`.

Dimensions must match the database. Test enable must resolve to one bit.
Repair signals must resolve. Output includes memory ports, their clock/reset
domains, undeclared memories and functional-mode isolation obligations.
Isolation is `not_run`. The command returns inconclusive (3). It performs no
BIST insertion and makes no manufacturing-test readiness claim. Supply the
connection declarations to `rvw formal connectivity` for separate proofs.

## Fabric and SoC audit

SpinalSoc binds APB phase/stability assertions to the core master and every
peripheral port. It asserts one-hot decode, exact window selection and error
completion on unmapped addresses. Assertion emission is not a proof result.
Enable simulator assertions when running the generated RTL.

`rvw soc audit --source MAP --db DB --bindings BINDINGS --out NEW_JSON`
checks exact map intervals, all declared IRQ bindings, every fabric endpoint
and clock/reset domains through the existing lint structural reader. MCP:
`soc_audit`. Bindings contain `interrupts` (map IRQ name to formal connection
fields) and `bus_ports` (every `core.bus` and `REGION.io.bus` to APB pin paths).
Each port needs PADDR, PSEL, PENABLE, PWRITE, PWDATA, PRDATA and PREADY.

The report distinguishes disjoint map arithmetic from unrun RTL decode proof.
IRQ paths use `rvw formal` connectivity resolution. A sibling
`OUT.connections.json` can be used with `rvw formal connectivity --run`.
The audit remains inconclusive until behavioral and proof evidence exists.

## Composition fragments

Composition files can add `fragments`, an ordered list of JSON paths relative
to the composition file. Each fragment can set `core`, `clock_hz`, `reset` and
`devices`. Later fragments replace earlier values. The main file wins last.
Device dictionaries merge by region name; each binder replaces the previous
binder as one unit. Fragments cannot include more fragments or change the map.
The generated manifest records every fragment hash and the effective config.

See [the Chipyard study](../../../../docs/design/chipyard-study.md) for the
source of this small config/harness separation and deferred integration work.

## Register export and project scaffold

`rvw soc export-ipxact MAP --out NEW_XML` exports the strict 1685-2014
register memoryMap subset accepted by `import-ipxact`. MCP:
`soc_export_ipxact`. It preserves access, known resets and the supported whole
register side effects. It does not export CPU models, bus interfaces, fields,
arrays or a complete IP-XACT component. `rvw soc generate` already writes
CMSIS-SVD. Composition now emits both register formats when registers exist.

Composition also writes `board.dts` with the CPU, memory, known peripheral
profiles and declared CPU interrupt wires. The UART subset has a custom
compatible string. No complete 16550 driver compatibility is claimed. PLIC
source IDs and device drivers remain project data. `link.ld` supplies a basic
section layout when executable and writable memory exist. Invoke ld from the
export directory so it can find `memory.ld`. Startup code remains project-owned.

`rvw soc new NAME --out NEW_DIR` creates an editable SoC project. MCP:
`soc_new`. It has a map, composition file, sbt build, idle wrapper and project
file. The build points to SpinalSoc sources in `RVW_HOME` at creation time.
Replace the idle wrapper and add a C1 adapter before running programs.
Scaffold creation is not simulation evidence.
## Sample RTL transaction pins

`rvw soc observe --binding binding.json --out observer` generates a
simulation-only SystemVerilog monitor. MCP tool: `soc_observe`. The binding
uses `rvw.soc-observer/1`. See `examples/soc-observer/binding.json`.
Replace its paths with the project's sampled handshake, transaction tag,
retirement order and retirement tag signals. No DUT signal is driven.

Compile `observer/observer.sv` beside the DUT. Enable its top module
`rvw_soc_observer`. Supply these simulation plusargs:

```text
+RVW_SOC_EVENTS=pins.jsonl
+RVW_RUN_ID=the-C1-simulation-run-id
+RVW_RTL_SHA256=the-C1-RTL-hash
+RVW_ELF_SHA256=the-C1-ELF-hash
+RVW_SEED=the-C1-seed
```

The monitor samples accepted requests and responses at the bound clock edge.
It also samples the independent memory-retirement tag. `cycle` must use the
same clock count as C2. `retire_valid` identifies memory retirements only.
`retire_count` must be a known one. Tags must be unique across the capture.
The monitor does not read C2 or infer links from addresses.

Package the completed pin capture and compare it with independent C2:

```sh
rvw soc observe-pack --binding binding.json --pins pins.jsonl \
  --trace rvfi.jsonl --result result.json --out events.jsonl --json
rvw soc pair --capture events.jsonl --trace rvfi.jsonl \
  --result result.json --out pairs.json --json
```

MCP tool `soc_observe_pack` returns the full pairing report. Packaging checks
the binding hash, run ID, RTL hash, ELF hash and seed. It captures the pin and
C2 hashes. The packaged output path must be new. Matching samples exit 3 and remain
inconclusive. Mismatched samples exit 1. Format or identity errors exit 2.

This producer supports a single hart and one bus transaction per memory
retirement. Split transactions, finite tag reuse, multi-hart links, posted
stores, killed speculative requests and core-specific probe wiring need
project work. The native test observes a small RTL bridge with a stalled
request, a store and a load. It compares against separate expected memory
effects. A corrupted read response produces a mismatch. This is a native
bridge fixture test. It is not an ELF execution or a VexRiscv/BOOM capture.

### Bus ingress and clock domains

Composition accepts `apb3`, `axi4`, `axi4-lite` and noncoherent `tilelink`
core buses. The new ingress profiles preserve memory byte strobes and reject
partial writes to legacy APB3 peripherals. Device binders can select an
explicit clock/reset domain through `domain`. See
[SpinalSoc](../../../../SpinalSoc/README.md#bus-ingress-and-clock-domains)
for the wrapper traits, library adapters, reset rules and current limits.

## Generate and run verification consumers

`rvw soc verify MAP --out NEW_DIR [--manifest verify.json]` generates checks
and runs configured consumers in one command. MCP tool: `soc_verify`.
It prints one table with kind, generated, ran and result. Exit 3 means that
one or more kinds lack complete evidence. Output includes the full per-kind
reasons in `result.json`. This first runner does not provide automatic whole
SoC qualification. A missing database or project bench remains explicit.

The manifest has schema `rvw.soc-verify/1` and a `checks` dictionary. Keys are
`protocol`, `registers`, `vip`, `uvm`, `connectivity`, `decode`, `cdc_rdc`.
A check can supply `database` for existing bus, VIP, pyuvm and lint generators.
`connectivity` can supply a connection `manifest`. Paths are relative to the
verification manifest. Register maps emit `registers.json`; decode windows
and unmapped intervals emit `decode.json`. Neither file is a proof.

Optional `prepare` is an argument list. It runs once before consumers.
Each check can supply a `command` argument list. Tokens `{out}`, `{map}` and
`{result}` name the fresh output directory, captured map and per-kind result.
Commands run without a shell. Each has a timeout of at most 120 seconds.
A command must write `rvw.soc-verify-evidence/1` with `kind`, `map_sha256`,
positive integer `checks`, and `status`. The map hash is the SHA-256 of the
captured `map.json`. Zero exit alone cannot pass. `decode` and `connectivity`
require `proven`; a finite simulation pass cannot satisfy those rows. These
are project consumer claims; their scope and artifacts need project review.

Protocol, VIP and register entries can instead supply a `capture` path.
The Vex SoC adapter now writes `apb.jsonl` from actual peripheral pins.
The checker uses the APB VIP and an independent register side-effect oracle.
Unknown reset values are never learned from DUT responses. Captured matches
remain inconclusive. Core AXI ingress is outside this peripheral capture.
Missing end records, pending transfers and unexercised buses remain visible.

A `decode` entry can supply `classpath_file`. It must contain the classpath
of a private SpinalSoc build that includes `rvwsoc.FabricProofGenerate`.
The consumer elaborates the real `Fabric.connect` implementation with every
map window. It then runs `rvw formal prove` with a bounded wall time. All
requests and peripheral responses are free. The proof covers one-hot decode,
exact window selection and unmapped error completion. It does not substitute
map arithmetic for RTL proof. Core and peripheral state are outside this
fabric proof target. The normal composer keeps protocol assertions enabled.
The proof target omits temporal APB assertions because it does not assume a
legal master. A native failure to generate or prove remains inconclusive.

Fresh compositions now contain native channel-stability binds on the core
bus. APB checks also cover the actual peripheral pins after legacy/clock
bridges. The generated `composition.json` has `protocol_bindings` with each
port's clock domain and check scope. Rebuild the generated source before a
native run. Cached development classes cannot establish new binding runs.

Supply `protocol.composition` to emit native binds with the source
composition's clocks and bridge boundaries. The selected map must match.
The Vex example does this before its native program run. Map-only SV bind
files need project instance/clock review; use native composition or a typed
database for automatic domain association.

A connectivity entry with both `database` and `manifest` runs the existing
formal connectivity consumer in `prove` mode. Optional `engine` and `depth`
select its backend and activation depth. Each declared transfer needs an
unbounded proof and a reachable activation witness. Timeouts, absent results
and bounded results stay inconclusive. The report preserves reverse influence
gaps. A proved table row covers the declared contracts only.

The optional `SpinalSoc` `db` project extracts the current generated top with
`rvwsoc.Database DB CLOCK_HZ RESET_KIND --rtl DIR`. Build it with `db/compile`
and obtain its classpath with `export db/Compile/fullClasspath`. Use private
build output and the `sbt-soc` lock. Recompose and rebuild before extraction.
Supply the database to `cdc_rdc.database` to run the existing structural lint
consumer. That consumer reports unrun protocol and reset-release obligations.
It does not establish CDC or RDC qualification.

`prepare_steps` can hold several argument lists. Each step runs in order
with the same per-command timeout. A failed step stops verification.
Database paths can use `{out}` for databases created by these steps.

The `watchdog` peripheral profile supplies a keyed-service countdown device,
W1C expiry status, an IRQ and an explicit reset-request output. Its composer
example runs a directed bus-master test through the generated fabric. See
[SpinalSoc](../../../../SpinalSoc/README.md#watchdog) for register semantics.

The `block` peripheral profile exports an eight-sector volatile verification
store and its register map. The directed composed example checks sector data,
completion, IRQ and error handling. See SpinalSoc's block-device section.

Use `connectivity.cone_cut = true` for per-connection source-cut proofs. The
structural pre-check must resolve each required dependency. The reduced RTL
keeps actual wiring and makes unrelated module outputs free. A transfer proof
and activation witness remain mandatory. Clock and reset rows are sampled
value checks. They do not qualify clock sequencing or reset release.

Use `registers.write_read` to name directed write/read obligations. A pass
requires a checked read after a write for each name. Plain capture matches
without declared obligations still remain inconclusive.

A VIP entry accepts the composition settings used by `uvm`. It generates one
cocotb test per MMIO bus. Each test uses the APB VIP and independent register
oracle on actual peripheral pins. A CDC/RDC entry can list
`required_libraries` to require recognition of its declared synchronizers.
Its structural summary reports findings and protected crossings separately
from unproved temporal obligations.

`verify` names missing manifest fields for each verification kind and explains
how to supply them. JSON uses `missing_bindings`, `binding_help`, and
`needed_evidence`. The text report prints the same instructions. Supplied
bindings still need native evidence. A generated monitor is not a pass.
## External Verilog IP

`rvw soc import-ip DESCRIPTOR --root RTL_ROOT --base ADDRESS --out NEW_DIR`
uses a small TOML description of APB3 or classic Wishbone ports and registers.
MCP: `soc_import_ip`. It captures declared RTL with hashes and generates an
APB3 wrapper, Scala binder and map region. It does not download or qualify IP.
See [the contract](../../../../docs/contracts/soc-ip.md) and
[the OpenCores UART example](../../../../SpinalSoc/examples/import/README.md).

`soc new` selects the current project's core-map when present. One mapped
RV32 Spinal req/rsp memory bus gets a real `SimpleCoreWrapper`, core build
dependency and RVFI exports. The default map contains RAM at the declared
address and size. Other protocols need a project wrapper. The unselected
project path still creates an explicitly labelled idle scaffold.

Composition also writes `verify.json`, `connections.json` and
`register-checks.json`. Use the generated verify manifest with `soc verify`.
It names `runtime-classpath.txt`, `soc.db` and `apb.jsonl` in its directory.
These are native inputs to supply, not generated evidence. The protocol
consumer can run a bounded fabric proof with the classpath. Decode uses an
unbounded fabric proof. CPU ingress and peripheral state are outside those
proofs. Direct scalar interrupt transfers and selected device clock/reset
connections are listed. Aggregated or crossed interrupts need a project
contract. A RAM-only map has no MMIO register checks to execute.
