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
reject unsupported constructs before it can replace project data. Neither
format is claimed as supported here. CMSIS-SVD export covers the simple register
subset, including [access and reset](https://arm-software.github.io/CMSIS_5/SVD/html/elem_special.html)
and [read/write side effects](https://arm-software.github.io/CMSIS_5/5.8.0/SVD/html/elem_registers.html).
No import or lossless round trip is claimed.

## Limits

Generation does not change RTL or existing harness constants. The two examples
preserve their current cosim settings. Generated device trees are memory fragments,
not bootable board descriptions. Bus decoding, bridge behavior, physical hardware
and reference device models need separate evidence. No export establishes a pass.
