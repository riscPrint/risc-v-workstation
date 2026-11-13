# SpinalSoc

SpinalSoc composes small verification SoCs from project data. It uses SpinalHDL
1.15.0 `Apb3Decoder` and `Apb3Router`. It does not implement a second bus fabric.

```sh
rvw soc compose SpinalSoc/examples/compose.json --out SpinalSoc/generated
cd SpinalSoc
../scripts/with-lock.sh sbt nice -n 10 sbt 'runMain generated.Generate'
```

The example uses `IdleCore`. This fixture does not execute instructions.
A project supplies a `Component with CoreWrapper`. The wrapper exposes a
unified APB3 master, 32 interrupt inputs in `mip` bit positions, and an active
high `debugReset` input. Place its source in this sbt project's source path.
Use SpinalHDL library bridges inside the wrapper for other core buses.

The composition file names a `rvw.soc/1` map. Every region has one binder.
`ram` and `rom` use initialized 32-bit word memories. `rom` needs read-only map
permissions. `project` names a no-argument peripheral class with `io.bus`
and, when the map declares an interrupt, `io.irq`. The decoder removes the
window base through address truncation. Windows must be aligned powers of two.
The interrupt wires OR together when they use the same cause.

`--elf FILE` preloads little-endian RV32 ELF PT_LOAD segments at physical
addresses. Unwritten bytes and BSS start at zero. Each segment must fit one
memory window. The manifest records the input hashes. Memory windows have a
1 MiB limit to keep this verification profile small.

## Decisions

The first profile uses one clock domain and full 32-bit APB3 word accesses.
The wrapper owns instruction/data arbitration. Clock frequency and reset kind
are explicit. Missing decode windows return APB errors through the library.
The existing map stays compatible with software, RAL and UVM consumers.

## Limits

No executable CPU is bundled in this increment. There is no C1 runner yet.
Generation does not establish a simulation pass. Byte writes, multiple clock
domains, AXI4/TileLink composition and automatic bridge selection remain open.
The software device tree is still a memory fragment. Peripheral pins need
project exports. Debug reset is tied inactive until a project binds debug.

## Local evidence

On 2026-11-13 the fixture compiled and elaborated with SpinalHDL 1.15.0 and
JDK 21.0.13. The six composer Python tests passed. No CPU simulation was run.
