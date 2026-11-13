# Map-driven SoC environment

`rvw_soc_env.py` composes the CPU Spike scoreboard, APB4 monitor,
AXI4-Lite monitor, UART stream scoreboard and Python RAL in one pyuvm
environment. `map.json` is an example `rvw soc` map with RAM and two
register windows. Generate the equivalent SV RAL with:

```sh
rvw regress uvm-ral --map Uvm/examples/soc/map.json --out /tmp/soc-ral.sv
```

Set the `soc` ConfigDB entry before build. Supply `map`, `reference`,
`protocols`, `frontdoors`, `retirements` and an async `run(services)` callback.
Use `{'control': 'apb', 'serial': 'axi-lite'}` for the example map.
Frontdoors implement async `read(address, width)` and
`write(address, value, width)`. They must drive the project bus agents.
The map supplies absolute register addresses and resets for RAL.

The project run task samples live CPU retirements into `services.cpu`, bus
pins into `services.buses[name]`, and UART TX into `services.uart`.
Use the existing agents' pin types and sampling rules. Queue expected
frames with `services.serial.expect(Frame(value))` before transmission.
The callback must wait for all required program and peripheral activity.
The environment's check phase requires CPU comparisons, transfers on each
configured bus and a complete expected UART stream. Empty activity fails.

The passive bus scoreboards use an independent register state initialized
from the map. They check read data and predict byte-strobed writes.
The current composition supports known-reset, plain 32-bit RW registers.
It refuses bus errors, APB aborts and AXI bursts. It does not model UART
register side effects. Use a project scoreboard for those semantics.
No reset during a transaction is qualified by this example.

The unit tests check composition, frontdoor routing, byte-stream monitoring,
wrong read data, wrong address, bus errors and empty CPU evidence.
They do not run a connected RTL SoC. The callback and active wire drivers
remain project work. No SoC execution or C4 acceptance is claimed.
