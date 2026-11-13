# SpinalSoc

SpinalSoc composes small verification SoCs from project data. It uses SpinalHDL
1.15.0 `Apb3Decoder` and `Apb3Router` with optional bus ingress bridges.

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

The original profile uses one clock domain and full 32-bit APB3 word accesses.
The wrapper owns instruction/data arbitration. Clock frequency and reset kind
are explicit. Missing decode windows return APB errors through the library.
The existing map stays compatible with software, RAL and UVM consumers.

## Limits

The executable stub example has a C1 runner. No production CPU is bundled.
Generation does not establish a simulation pass. Native AXI4/TileLink crossbars,
AXI width adaptation and arbitrary peripheral bus conversion remain open.
The software device tree is still a memory fragment. Peripheral pins need
project exports. Debug reset is tied inactive until a project binds debug.

## Local evidence

On 2026-11-13 the fixture compiled and elaborated with SpinalHDL 1.15.0 and
JDK 21.0.13. The six composer Python tests passed. No CPU simulation was run.

## Peripheral profiles

`rvw soc peripheral KIND --name NAME --base ADDRESS --out NEW_JSON` exports a
map region and a composer binder. MCP: `soc_peripheral`. Add the region to the
software map and the binder to the composition file. The existing SVD and RAL
exports then use these registers. Autonomous and mixed-side-effect register
values use unknown reset values where a generic reset read is unsafe.

| Kind | Profile |
|---|---|
| `uart16550` | 16550 register subset, reg-shift 2, fixed 8N1, one holding slot per direction. Spinal UartCtrl implements serial timing. |
| `clint` | One hart, MSIP, 64-bit MTIMECMP and MTIME. MTIME counts input clocks. |
| `plic` | Seven level sources, one machine context, priorities 0/1, claim/complete. |
| `gpio` | 32 synchronized inputs, output values/enables and level IRQ mask. |
| `spi` | Spinal Apb3SpiMasterCtrl, one chip select, 8-bit data, four-entry FIFOs. |
| `i2c` | Spinal Apb3I2cCtrl with master mode and no address filters. |
| `timer` | Enable/count/compare and watchdog output. Writing count services it. |
| `finisher` | Nonzero tohost register asserts done and exports its code. |

Project binders can declare `exports` with peripheral IO member names. These
become top-level IO with a region prefix. An optional `irq` dictionary maps a
map interrupt name to a device IO member. For CLINT, select `softwareIrq` for
MSIP and `irq` for MTIP. PLIC sources must be exported or bound by a project
wrapper. There is no automatic inference of PLIC source IDs.

These are bounded verification profiles. UART has no modem control, FIFO
trigger levels, DMA, break or parity support. TEMT is not reported. It is not
a complete 16550 implementation. SPI/I2C register descriptions cover register
addresses, not all bit fields and dynamic side effects. Generic register
checks cannot establish those protocols. VIP pin bindings and behavioral
scoreboards still need project configuration.

On 2026-11-13 all eight profiles compiled and elaborated with SpinalHDL
1.15.0. `rvwsoc.PeripheralSmoke` passed in Verilator at seed 17. It checked
four CLINT conditions and six PLIC claim/complete conditions. It did not
execute a CPU or qualify UART/SPI/I2C behavior.

## Executable example

See [the RV32 stub example](examples/stub/README.md) for a C1 adapter,
`rvw regress` configuration, UART hello-world and timer/PLIC interrupt programs.
The example runner is enabled only with `-Drvw.soc.stub=true` in sbt. The adapter
sets that property. The default build compiles the stub wrapper but excludes its simulation runner.

Fabric assertions run on every APB endpoint and decode output. On 2026-11-13
the PLIC interrupt example passed with Verilator `--assert` at seed 23
(224 measured loop cycles, 74 retired instructions). Formal decode and
interrupt value-transfer proofs were NOT RUN.

Composition exports `registers.ipxact.xml` for the strict IP-XACT register
subset and `registers.svd` for CMSIS-SVD. `board.dts` includes the CPU and
known peripheral descriptions. `link.ld` supplies a basic section layout.
The profiles use custom compatible strings where no standard driver binding
is established. The device tree is not a Linux boot qualification result.

`rvw soc new NAME --out NEW_DIR` creates an editable idle-core project.
On 2026-11-13 the scaffold compiled and elaborated in 13 seconds after it
acquired the sbt lock. `dtc` accepted the composed board description. RISC-V
GCC linked hello-world with the generated linker script. Startup code, drivers
and a production core remain project work.

## Bus ingress and clock domains

`core.bus` can be `apb3`, `axi4`, `axi4-lite` or `tilelink`. The new wrapper
traits are `AxiCoreWrapper`, `AxiLiteCoreWrapper` and `TileLinkCoreWrapper`.
They keep the interrupt and debug-reset members of `CoreWrapper`. AXI ports
have 32 data bits. TileLink uses negotiated Get/Put node parameters without
BCE and accepts 32, 64 or 128 data bits through the library width adapter.
AXI uses the library ID remover and burst splitter before AXI4-Lite conversion.
All endpoints share the library APB decoder and router. These are bus ingress
bridges, not native AXI or TileLink crossbars. Atomic and coherent accesses
are outside this profile.

The new ingress paths preserve byte strobes in memory. Read data uses bus
lane positions. Legacy APB3 MMIO accepts only full-word writes. A partial
write returns SLVERR before the peripheral sees PSEL. No read/modify/write
operation is used. SpinalHDL 1.15.0 omits the optional strobe wires in its
APB decoder and router. `Fabric` supplies those wires through `rework` and
keeps the library address decode and error response logic.

An optional `domains` object names peripheral clock domains:

```json
"domains": {"slow": {"clock_hz": 10000000, "reset": "async_high"}}
```

A device binder can select `"domain": "slow"`. The top exposes `slow_clk`
and `slow_reset`. The core uses the default clock and reset. `BusClockCrossing`
packs byte strobes with data through Spinal `Apb3CC`. Its underlying
`FlowCCUnsafeByToggle` is a recognised `rvw lint` handshake primitive.
Interrupt levels return through `BufferCC`. Hold interrupt levels until the
core acknowledges them. Pulses can be lost. Assert both resets together and
keep them asserted long enough for both clocks. Independent reset during a
transaction is not supported. Structural CDC recognition is not a protocol
proof or a reset-domain qualification result.

Native checks: `runMain rvwsoc.BusSmoke` checks byte writes, halfword writes,
zero strobes, MMIO rejection, decode errors and response backpressure with
Verilator assertions. `runMain rvwsoc.BusElaborate` elaborates AXI, TileLink
and CDC fixtures. Run sbt under the shared lock as shown above.

On 2026-11-13 the bus fixtures compiled with SpinalHDL 1.15.0. AXI4,
TileLink and CDC fixtures elaborated. A generated APB3 composition with a
separate memory domain elaborated. `BusSmoke` passed at seed 31 with
Verilator assertions, both on one clock and across periods 10 and 14.
AXI/TileLink transaction simulation, wider TileLink simulation, structural
lint extraction and formal CDC/reset checks were NOT RUN.
