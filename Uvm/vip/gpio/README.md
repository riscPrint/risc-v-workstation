# GPIO agents

The Python profile has 1 to 32 pins. The SV profile has eight pins.
A direction bit of one selects output. External input drives all other
pins. The resolved digital pin passes through a declared synchronizer.
The default latency is two previous sample calls. Reset clears all state.

IRQ is a per-pin vector. Rising, falling, high and low masks select the
trigger modes. IRQ does not latch. The scoreboard checks sampled state
and IRQ independently. A project must model sticky pending bits separately.
Set SV scoreboard masks to the same values as the interface masks.

The UVM package supplies stimulus, monitor, coverage and reference scoreboard.
The fixture has two input registers. `+buggy` flips interrupt bit zero.
The Python module supplies `Reference`, `Manager`, `Monitor`, `Scoreboard`,
seeded sequences and a cocotb adapter. Flat cocotb pin names use
`PREFIX_external/direction/output/sampled/irq`, with `clk` and `reset_n`.

## Timing and limits

Sample on the rising clock edge before sequential DUT updates. Change
stimulus on the falling edge. Inputs must remain stable across the setup
and hold interval. This contract checks digital latency only. It cannot
qualify metastability, analog pin contention or asynchronous pulse capture.
The reference assumes push-pull outputs and external inputs selected by
direction. It does not model tri-state resolution.

## Checks

Run `rvw/.venv/bin/python -m pytest rvw/tests/test_vip_gpio.py -q`.
Lint all four SV files against the pinned UVM library.
UVM runtime builds and cocotb RTL simulation were not run for this change.

## Bounded Python RTL evidence

The Python cocotb adapter passed a seeded good RTL test and detected the
controlled bad RTL result. See `Uvm/vip/rtl/README.md` for commands and
fixture scope. This does not establish full protocol conformance or UVM
runtime qualification.
