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

## Connected Spinal RTL example

`spinal/src/main/scala/SeededSoc.scala` builds a small SoC with an APB3 RW
register, an AXI4-Lite RW register and an 8N1 UART transmitter. A write to
the low byte of the AXI register starts UART transmission when it is idle.
The test waits for each frame before the next write. It does not test a FIFO.
The test master drives actual RTL bus pins. No CPU is present.

Generate RTL under the shared sbt lock. Run from this checkout:

```sh
cd Uvm/examples/soc/spinal
../../../../scripts/with-lock.sh sbt nice -n 10 sbt -batch \
 'runMain SeededSocMain ../rtl'
cd ../../../..
RVW_UVM_SOC_NATIVE=1 scripts/with-lock.sh soc-uvm nice -n 10 \
 rvw/.venv/bin/python -m pytest rvw/tests/test_uvm_soc_native.py -q
```

`connected_test.py` composes the existing APB, AXI-Lite and UART monitors
with independent map-initialized register state and active RAL frontdoors.
The test separates AXI write-address and write-data handshakes. It performs
reset reads, four seeded writes and checked reads on each bus, and four
independently predicted UART frames. Each handshake has a watchdog.
`RVW_SOC_SEED` selects the data seed. `soc-checks.json` records actual counts.

Use `cpu_required=False` only for an explicit bus-master profile.
`finish(0)` then requires bus and UART evidence and reports zero CPU checks.
The default CPU profile still requires nonempty CPU comparisons. A nonzero
retirement request is refused in the bus-master profile.

Native Verilator 5.049 results on 2026-11-13: seeds 1 and 7 each checked
9 APB transfers, 9 AXI-Lite transfers and 4 UART frames. The native test
returned 2 passed, 0 skipped. The composition unit tests returned 4 passed.
This qualifies the stated bus-master example. CPU boot, bus error handling,
reset during traffic and C4 acceptance remain outside this run.

See [the virtual sequence library](SCENARIOS.md) for boot, interrupt-storm,
bus-error and reset-during-traffic callbacks in Python/pyuvm and SV UVM.
The native connected example uses its boot sequence for peripheral bring-up.
