# Protocol verification agents

The agents work without UVM. Pure Python cycle models use immutable pin
samples. Optional cocotb adapters drive and observe RTL interfaces.
No cocotb dependency is needed to import the cycle models.

| Module | Profile | SV agent and fixture |
|---|---|---|
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
all agent modules. This evidence establishes real RTL adapter execution
within the stated fixture scope. It does not qualify every protocol mode.
