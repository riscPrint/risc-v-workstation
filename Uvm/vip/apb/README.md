# APB agents

This profile implements one APB4 peripheral select, 32-bit byte addresses,
32-bit data, PPROT, PSTRB, PREADY and PSLVERR. It follows
[Arm IHI 0024E, sections 3.1 to 3.4](https://documentation-service.arm.com/static/63fe2c1356ea36189d4e79f3).
APB5 wakeup and user signals are outside this profile.

## UVM

Compile `apb_if.sv` before `apb_pkg.sv`. Use the pinned Accellera UVM
library described in [the UVM guide](../../README.md). Define `UVM_NO_DPI`.
Enable `--timing --assert --coverage` on Verilator.
Set `uvm_config_db#(virtual apb_if)` key `bus` before build.
Instantiate `apb_checker` on the interface.

`apb_vip::agent` creates a sequencer and manager driver by default.
Set its `subordinate_role` bit in config DB to create the reactive RAM
subordinate instead. Use one active role per interface. Set `is_active`
to `UVM_PASSIVE` for a monitor only. Connect `m.ap` to your scoreboard.
`directed`, `random_sequence` and `error_sequence` provide stimulus.
Set driver `inject_address` for the error sequence.
The monitor publishes completed transfers and reset aborts.
The subscriber has coverage for direction, response, delay, strobes and
operation/response crosses. Call `reset_model()` when the DUT resets.

The fixture uses four aligned RW words. Other addresses return an error.
Error writes have no effect. This is a fixture policy. APB allows a DUT to
change state on an error response. Replace the scoreboard for that policy.
The checker does not require PSLVERR low outside completion. It permits
PENABLE high when this peripheral is not selected.
A driver timeout is a test policy. APB has no maximum wait count.

Run the short native campaign from the repository root:

```sh
nice -n 10 rvw/.venv/bin/python Uvm/vip/apb/smoke.py --out /tmp/apb-new
```

The script checks the pinned archive hash. Use `--archive PATH` offline.
It builds the UVM agent and RAM. Three seeds run normal traffic, reset
interruption, read corruption and an illegal manager address change.
A negative run must fail with its specific diagnostic and no done marker.
Logs remain in the output directory. Missing tools or build errors fail.

## Python and cocotb

`rvw.vip.apb` supplies `Manager`, `Subordinate`, `Monitor`, `Checker`,
`RegisterScoreboard`, `sequences` and `inject`. The cycle API needs no
simulator. Pass a callback to `Monitor` for your scoreboard.
`Manager.tick` must return the pin values accepted at the rising edge.
Use `Monitor.sample(Pins(reset_n=0))` on reset. Reset your scoreboard
separately. Coverage is a Counter of observed functional bins.

`CocotbAgent` uses the same checker and sequence items. It imports cocotb
only when an async method runs. Start `run_monitor()` once. Use
`await agent.transfer(item)` for a manager, or start `run_subordinate()`
for a peripheral model. Supply a clock as `dut.clk`. Supply all fields
of `Pins` as lower-case DUT ports. Drive reset externally. Drive requests
on falling edges. The adapter samples on rising edges before sequential
updates. The reactive model waits 1 ps after each falling edge to let the
manager drive requests. Use a clock period greater than 2 ps.

## Decisions and limits

These are component agents. They do not prove a SoC conforms to APB.
The native campaign covers the manager against an RTL subordinate.
The UVM reactive subordinate needs separate native qualification.
The cocotb manager and monitor passed three good RTL runs and three
read-corruption runs on Verilator 5.052 with cocotb 2.0.1. Run that
campaign with `nice -n 10 rvw/.venv/bin/python
Uvm/vip/apb/cocotb_smoke.py --out /tmp/apb-cocotb-new` after installing
`cocotb==2.0.1` in the rvw environment. The cocotb reactive subordinate
has not had native qualification. The UVM executable build exceeded the
120-second smoke budget. UVM runtime qualification remains open. Four-state X checks are not qualified on two-state Verilator.
Python errors on unresolved cocotb values. The fixture uses little-endian
byte lanes. Multi-select decode and bridge integration need project tests.
