# Protocol verification agents

The agents work without UVM. Pure Python cycle models use immutable pin
samples. Optional cocotb adapters drive and observe RTL interfaces.
No cocotb dependency is needed to import the cycle models.

| Module | Profile | SV agent and fixture |
|---|---|---|
| `rvw.vip.rnm` | Real-number boundary stub contract only | `Uvm/vip/rnm/` |
| `rvw.vip.ethernet` | Optional MAC client-packet model, descriptors, DMA and interrupts | `Uvm/vip/ethernet/` |
| `rvw.vip.pcie` | Optional transaction-model adapter, windows, completions and DMA | `Uvm/vip/pcie/` |
| `rvw.vip.dram` | Optional digital DRAM model contract and reduced command checker | `Uvm/vip/dram/` |
| `rvw.vip.stress` | Abstract memory/NoC latency, bandwidth, refresh pauses and QoS | `Uvm/vip/stress/` |
| `rvw.vip.coherent` | Reduced coherent event bridge, credits, snoops and ownership | `Uvm/vip/coherent/` |
| `rvw.vip.jtag` | Generic TAP scans and declared chain topology | `Uvm/vip/jtag/` |
| `rvw.vip.clock_reset` | Integer-time clock and reset pulse/release checks | `Uvm/vip/clock_reset/` |
| `rvw.vip.interrupt` | Interrupt line levels, pulse widths and scheduled timing | `Uvm/vip/interrupt/` |
| `rvw.vip.sram` | Single-port SRAM/ROM, word addresses, byte masks and fixed latency | `Uvm/vip/sram/` |
| `rvw.vip.wishbone` | Wishbone Classic, 32-bit, byte selects and ACK/ERR | `Uvm/vip/wishbone/` |
| `rvw.vip.gpio` | GPIO direction, synchronization and edge/level interrupts | `Uvm/vip/gpio/` |
| `rvw.vip.i2c` | Resolved open-drain I2C, ACK/NACK, stretching and arbitration | `Uvm/vip/i2c/` |
| `rvw.vip.spi` | Four-wire SPI, all modes, 1 to 32 bits, both bit orders | `Uvm/vip/spi/` |
| `rvw.vip.uart` | UART, 5–9 data bits, parity, 1–2 stop bits, receive FIFO reference | `Uvm/vip/uart/` |
| `rvw.vip.tilelink` | TileLink-UL/UH A/D, 32-bit, bursts, atomics and hints | `Uvm/vip/tilelink/` |
| `rvw.vip.axi` | AXI4 and AXI4-Lite, 32-bit, aligned bursts and exclusive access | `Uvm/vip/axi/` |
| `rvw.vip.axis` | AXI4-Stream, 32-bit, byte qualifiers and sidebands | `Uvm/vip/axis/` |
| `rvw.vip.ahb` | AHB-Lite, 32-bit, one manager | `Uvm/vip/ahb/` |
| `rvw.vip.apb` | APB4, 32-bit, one peripheral select | `Uvm/vip/apb/` |

See each SV agent's README for its sequence library, scoreboard policy,
coverage, pin names, native smoke command and conformance limits.

## Decisions and limits

Each protocol owns its pin and transaction types. A callback connects
observed transactions to a project scoreboard. There is no inferred SoC
pass and no simulator dependency at package import. Native smoke results
apply only to their declared profile and fixture.

See `Uvm/vip/rtl/README.md` for bounded good/bad cocotb RTL campaigns for
the nine modules present in that campaign. This evidence establishes real RTL adapter execution
within the stated fixture scope. It does not qualify every protocol mode.
## Agent discovery and bench skeletons

`rvw vip list` lists Python and SV agents. `rvw vip buses --db design.db`
finds buses by exact Spinal bundle class. It does not guess from pin names.
`rvw vip bench --db design.db --bus io.bus --out test_bus.py` writes a
cocotb skeleton with captured RTL pin bindings. Use `--clock` and `--reset`
to select the test clock and active-low reset. Paths are relative to the
cocotb DUT handle. The generator refuses existing output files.

MCP tools are `vip_list`, `vip_buses` and `vip_bench`. They use the same
implementation. A generated skeleton raises `NotImplementedError` until
the project adds reset, stimulus and expected results. It is not a pass.
Inspect all bindings before use. Select the DUT hierarchy root to match
the database paths. Unsupported bundle types need a project adapter.

Type discovery currently supports APB3/APB4, AHB-Lite, AXI4/AXI4-Lite,
UART and SPI. APB3 configurations without the APB4 agent's optional pins
need an explicit project adapter. Missing APB/AHB pins cause an error.
Other generated bindings need project review for width and optional pins.
Generic Stream payloads and TileLink configuration classes do not yet have
an automatic mapping. Agent inventory remains available for these profiles.

## SV runtime qualification

The [SV runtime campaign](../../../../Uvm/vip/qualification/README.md)
builds each protocol once and records compile, good-DUT and corrupt-DUT
checks separately. Empty native-model stubs remain unqualified. Read its
measured matrix before choosing an SV agent for a project.

## Untyped HDL databases

Automatic bench generation requires supported typed bus metadata. A database
with plain Verilog ports returns `status: unsupported` and writes no bench.
The CLI exits 2. MCP returns the same status. Supply a project-owned bench
and explicit protocol pin bindings. Port names alone do not establish a bus.
