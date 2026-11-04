# SoC maps

`rvw soc generate MAP --out DIR --json` validates project data and writes:

| File | Use |
|---|---|
| `platform.json` | Existing Spike shim and `rvw cosim --platform` input. Reference policy stays explicit. |
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
and the selected harness endpoint. VexRiscv records full memory-service words.
BOOM records TileLink request sizes, including cache-line acquisitions.
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
