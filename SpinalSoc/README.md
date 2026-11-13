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
Generation does not establish a simulation pass. The native fabric profile
and its measured bounds are described below. Arbitrary peripheral bus conversion
remains open.
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
| `uart16550-full` | Full register profile with selectable 1/16-byte FIFOs, interrupt priority, modem pins, divisor, framing, errors, DMA requests and loopback. |
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

These are bounded verification profiles. The original `uart16550` subset
has no modem control, FIFO trigger levels, DMA, break or parity support.
It does not report TEMT. Select `uart16550-full` for the added behavior below. SPI/I2C register descriptions cover register
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

## Real core wrappers

[The VexRiscv example](examples/vex/README.md) has a wrapper, C1 adapter and
captured-input regression setup. [The VexiiRiscv example](examples/vexii/README.md)
has a separate source build for its pinned Spinal dependencies. Both expose
AXI4 masters through `AxiCoreWrapper` and wire machine interrupt inputs.
Debug transport and debug module integration remain open.

## Simple CPU memory bus

`SimpleCpuBus` carries one 32-bit word transfer at a time. The CPU holds `valid`,
address, write data and byte mask until `ready` completes the transfer. `error`
and `rdata` are valid with `ready`. Reads ignore the mask. Addresses select an
aligned word; the CPU performs load extraction and store lane alignment.
`SimpleToApb` buffers the request, inserts APB setup, preserves wait states,
and returns the read data/error. APB byte strobes carry the write mask.

A project wrapper implements `SimpleCoreWrapper` and exposes a master
`SimpleCpuBus`, interrupt inputs in mip positions, and a debug-reset input.
Select `core.bus = "simple"` in the composition JSON. The composer inserts the
bridge and enables byte writes in RAM. For example:

```scala
class ProjectCore extends Component with SimpleCoreWrapper {
  val io = new Bundle {
    val bus = master(SimpleCpuBus())
    val interrupts = in Bits(32 bits)
    val debugReset = in Bool()
  }
  def bus = io.bus
  def interrupts = io.interrupts
  def debugReset = io.debugReset
  // Instantiate the real CPU. Bind memory completion, interrupt and reset.
  // Freeze its pipeline until a memory request completes if it has no ready port.
}
```

The example is a binding outline. It does not execute a CPU until mapped.
`runMain rvwsoc.SimpleBusSmoke` tests wait states, strobes, data and errors.
AXI4-Lite wrappers can still use the existing `AxiLiteCoreWrapper` and ingress.
## Fabric decode proof

`rvwsoc.FabricProofGenerate OUT BASE_HEX:SIZE_HEX ...` emits a standalone
instance of the real fabric. The external master requests and peripheral
responses are unconstrained. Decode assertions remain enabled. Temporal APB
assertions are separate, since this proof target has no legal-master
assumptions. Normal compositions keep all protocol assertions enabled.

After a private build, set `decode.classpath_file` in `rvw soc verify` to run
this target through `rvw formal prove`. The Vex SoC map proved all seven
assertions on 2026-11-13. An incorrect UART decode address failed the proof.
This is a fabric-instance proof, not complete SoC correctness.

## Independent verification master

`VerificationCore` is a test wrapper over the existing `SimpleCpuBus` bridge.
It does not execute instructions. The pyuvm composed profile uses it to drive
the complete peripheral fabric through an exported `stimulus` port. Optional
`core.exports` lists the wrapper IO members to expose with a `core_` prefix.
The normal bus, interrupt vector and debug-reset port stay under composer
control. Production wrappers do not need to use this option.

## Native protocol binds

The composer binds channel stability checks to AXI4, AXI4-Lite and TileLink
core ports. The simple CPU bus gets a stable-request check. APB phase and
stability checks cover the routed fabric ports and actual peripheral pins.
A clock bridge gets checks at both clocks. A legacy bridge gets checks at
both interfaces. `composition.json` records paths, domains and check kinds.

`ProtocolSmoke` passes a stable held request at seed 37. Its `corrupt` case
changes the address under backpressure and fails the native assertion.
The VexRiscv register program passed with these binds at seed 31 in 248
cycles and 36 retired instructions. This is a sampled safety result. It is
not complete AXI/TileLink transaction, ordering, coherence or liveness proof.

AXI4 and TileLink binds also call the existing SpinalChecks transaction
checkers through its new `BusAssertions` facade. AXI tracking requires
positive issuing limits in the wrapper's bus config. Missing limits emit
a gap warning. The Vex wrapper declares two read and two write requests.
The build compiles those generic checker sources into its private output.
It does not build a core or write shared SpinalChecks output directories.

## Typed composed database

The optional `db` sbt project depends on the normal composer and SpinalDB.
`rvwsoc.Database DB CLOCK_HZ RESET_KIND [COMPONENT_CLASS] --rtl DIR` extracts
fresh RTL and a typed database. The default class is `generated.ComposedSoc`.
The Vex verification helper also builds `generated.MultiDomainSoc` from the
separate two-clock composition. Use the `sbt-soc` lock for these private outputs.
See the Vex example for its build helper and combined verification manifest.

## Watchdog

`rvw soc peripheral watchdog --name wdt --base 0x10000000 --out wdt.json`
exports the watchdog map and binder. The independent profile has five words:
control at 0, reload at 4, remaining count at 8, service at 12 and status at 16.
Control bit 0 enables counting and IRQ. Control bit 1 enables the reset request.
Write `0x51f15e` to service to reload the counter and clear expiry. Other keys
have no effect. The counter saturates at zero. Zero reload expires on the next
enabled clock. Expiry is sticky. Status bit 0 is W1C; expiry wins on a concurrent
clear. Service wins on a concurrent expiry. Disable counting before clearing an
expired zero counter. Reload changes apply at the next service operation.

The reset request is a level output. Export `resetRequest` and bind it to the
project reset controller. The composer does not connect it to its own reset.
The profile uses the peripheral clock. It is not an independent safety clock.
See [the composed test](examples/watchdog/README.md).

## Volatile block device

`rvw soc peripheral block --name disk --base 0x10000000 --out disk.json`
exports an eight-sector verification block device. Each sector has 512 bytes.
It has no physical SD signalling or persistent storage. The words are:

| Offset | Register | Meaning |
|---|---|---|
| 0 | LBA | Sector number, 0 to 7. Writes during a transfer return an error. |
| 4 | COMMAND | Write 1 to read, 2 to write, or 0 to abort. Reads return an error. |
| 8 | STATUS | Bit 0 active, bit 1 command error, bit 2 done. Bits 1 and 2 are W1C. |
| 12 | SECTORS | Read-only sector count, 8. |
| 16 | DATA | One full 32-bit word per access, in sector order. |
| 20 | INDEX | Read-only current word index, 0 to 127. |

A successful command clears error and done. Exactly 128 DATA accesses complete
a transfer and set done. The index stays at 127 after completion. DATA must
match the selected read/write direction. An inactive or wrong-direction
access returns an APB error and does not advance the index. An invalid LBA,
unknown command or overlapping command returns an APB error and sets error.
IRQ is the OR of done and error. Abort stops the transfer; it does not clear
status or undo accepted writes. Stores are initialized to zero at elaboration.
Controller reset aborts a transfer and clears status. It retains stored data.
Byte access and a disk-image preload interface are outside this profile.
See [the composed test](examples/block/README.md).

## Scoped Vex verification results

The fresh combined campaign on 2026-11-13 produced these results. Each pass
refers to a declared consumer scope. The report is not whole-SoC acceptance.

| kind | generated | ran | result |
|---|---|---|---|
| protocol | yes | yes | pass |
| registers | yes | yes | pass |
| vip | yes | yes | pass |
| uvm | yes | yes | pass |
| connectivity | yes | yes | proven |
| decode | yes | yes | proven |
| cdc_rdc | yes | yes | findings |

Protocol checks ran over 49 selected ISA programs with native assertions.
The APB fabric passed 31 bounded assertions at depth 8. The directed register
program checked ten reads and write/read obligations for UART scratch, CLINT
MSIP and PLIC priority 1. Four generated peripheral cocotb tests passed 17
known-value reads. The separate pyuvm bench passed the same 17 reset reads.
All four connection rows proved with activation witnesses. The decode target
proved seven assertions. The multi-domain inventory retains 2,507 findings
and recognizes BufferCC and FlowCCUnsafeByToggle. Temporal CDC/RDC rules
remain unproved. See [the evidence scopes](examples/vex/VERIFICATION.md).

## Full-register UART

The additive `uart16550-full` profile exposes `Uart16550Full`. The original
subset remains available. The new profile has word-spaced RBR/THR/DLL,
IER/DLM, IIR/FCR, LCR, MCR, LSR, MSR and scratch registers. It supports FIFO
thresholds, four-character receive timeout, line/modem errors, THRE/TEMT,
DMA request modes, serial/modem loopback and programmable framing.
See [the UART example](examples/uart16550/README.md) for exact semantics.

On 2026-11-13 the native directed bench passed 240 checks at seed 31. The
independent UART VIP checked 28 transmitted frames. The same bench passed
through the elaborated Spinal wrapper. It measured 361 clock cycles between
two queued 5N1.5 frames at a 48-clock bit period, including the engine's
one-clock inter-frame gap. No hardware or complete compliance result is claimed.

## SPI flash boot

The [flash example](examples/flash/README.md) composes the real RV32IM core,
a boot ROM, empty application RAM, SPI and a finisher. The ROM reads a payload
through real SPI pins, checks its byte sum, copies it into RAM and jumps to it.
The host supplies no application RAM preload. A read-only NOR model supports
normal/fast reads and explicit project identity. Program/erase are unsupported.

| Image at seed 31 | CPU cycles | Retired | Flash bytes | Result |
|---|---:|---:|---:|---|
| Unchanged 16-byte payload | 5,150 | 573 | 16 | finisher 1; pass |
| One corrupted payload bit | 5,130 | 569 | 16 | finisher 3; rejected |

These 2026-11-13 runs observed RAM word zero as zero before execution. The
successful run observed the expected first payload word after boot. The
independent SPI monitor checked 20 wire words in each run. This is a composed
CPU development simulation. C1 gate acceptance, XIP and hardware are unrun.
The legacy APB bridge now handles a peripheral without PSLVERROR while still
rejecting partial writes before target select. Its native smoke passed.

## Native multi-master fabrics

`NativeAxiCrossbar` and `NativeTileLinkCrossbar` compose SDK decoders and
arbiters for N masters and M targets. `AxiDataWidth` converts AXI data widths
without losing original IDs, burst framing or early narrow errors. These
components are separate from the existing APB peripheral ingress. A project
wrapper can place them before that ingress. See [the fabric example](examples/fabric/README.md)
for the profile, commands and measured transaction table.

At seed 31, native two-master/two-target AXI4 and TileLink tests passed with
independent endpoint scoreboards. Native AXI4 conversion passed in both
directions between 32 and 64 bits. A real composed CPU with an RTL DMA-style
master passed in 2,135 cycles with 236 CPU retirements and 33 DMA write/read
pairs. These are finite simulation results. Exclusive accesses and coherent
TileLink are outside the profile. Native 128-bit conversion was NOT RUN.

## Optional SMP host

[The SMP host example](examples/smp/README.md) uses the unchanged cacheless
`examples/smp` harts. Its wrapper routes peripheral accesses through the
composer and retains external RAM/atomic service. Host-owned RAM uses a
`host` binder. The composer keeps its software map and emits no duplicate
RTL memory. RV64 metadata with 32 physical address bits is supported.
The peripheral fabric stays 32 bits. Per-hart IRQ routing, coherence and
synthesized atomic memory are outside this optional profile.

The optional two-hart host passed its seed-31 Verilator test in 133 cycles.
Hart retirements were 21 and 22. Both harts completed, each with two RTL GPIO
accesses and three external RAM data requests. The pinned core dependencies
were private cached class copies. Their source rebuild and standalone SMP C1
campaigns were NOT RUN for this change.

## External Verilog IP

`rvw soc import-ip` accepts explicit TOML port, bus and register descriptions.
It generates an APB3 wrapper and composer binder for APB3 or classic Wishbone
IP. [The external UART example](examples/import/README.md) uses pinned
OpenCores RTL outside the repository. It captures source hashes and checks
registers and serial pins through the composed fabric. Imported declarations
are project claims until native tests check them. IP-XACT bus import and port
inference are outside this profile.

The pinned imported UART passed 23 directed checks, two transmit frames and
one receive frame through the composer at seed 31 on Icarus. The UART VIP
checked the serial bytes. The wrapper also compiled and elaborated with
SpinalHDL 1.15.0. This test executes no CPU and is not full UART qualification.
