# Protocol verification agents

The agents work without UVM. Pure Python cycle models use immutable pin
samples. Optional cocotb adapters drive and observe RTL interfaces.
No cocotb dependency is needed to import the cycle models.

| Module | Profile | SV agent and fixture |
|---|---|---|
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
