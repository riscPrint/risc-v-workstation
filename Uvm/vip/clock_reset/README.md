# Clock and reset agents

This profile generates a digital clock with equal high and low times.
Reset is active low. Assert reset at sequence start. Hold it through the
declared number of rising edges. Release it on a falling edge. Python
times are integer nanoseconds. The default half-period is 5 ns and the
reset hold is two clock cycles. All timing values must be positive.

The Python module has a waveform generator, callback manager, timing
monitor, scoreboard and cocotb source. The source must own the selected
clock and reset pins. Do not start another clock source on these pins.
The monitor checks observed samples. The cocotb source checks its planned
waveform; connect a separate observer if the design transforms the clock.

SV provides directed/random sequence items, driver, passive monitor,
coverage and timing scoreboard. The driver and scoreboard timing fields
must match. The fixture copies clock/reset. `+buggy` releases reset on a
rising edge. The test uses one directed clock sequence. Its auxiliary
interface `clk` is a test timebase, separate from the generated clock.

Clock gating, frequency changes, analog jitter, PLL lock, reset recovery
and metastability are outside this profile. A project must state its
own clock-domain and reset-domain crossing requirements.

Run `rvw/.venv/bin/python -m pytest rvw/tests/test_vip_clock_reset.py -q`.
Lint all four SV files with pinned UVM. UVM runtime builds and clock/reset
cocotb RTL qualification were not run for this change.
