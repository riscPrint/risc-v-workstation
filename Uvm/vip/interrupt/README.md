# Interrupt-line agents

This digital profile drives and observes sampled interrupt vectors.
Python supports 1 to 64 lines. SV has eight lines. Each event declares
levels and duration in clock samples. The monitor counts edges and pulse
widths. It rejects unknown values and pulses below the declared minimum.
Reset cancels pulse tracking. A held level is permitted at test end.

The Python scoreboard checks every supplied expected sample. The SV
scoreboard checks driver-scheduled windows. Between these windows, the
SV monitor continues passive pulse checks. It does not infer expected
values for unplanned traffic. Connect a project reference for that traffic.
The good fixture copies levels. `+buggy` changes line zero.

The cocotb adapter uses external `clk` and active-low `reset_n`. Choose
the interrupt signal name explicitly. Use one active driver per line.
Do not run the same adapter's active send and passive monitor together.

Interrupt controller pending bits, priority, CPU trap delivery, electrical
pulse capture and metastability are outside this line-level profile.
Projects must reset scheduled expectations with their DUT reset.

Run `rvw/.venv/bin/python -m pytest rvw/tests/test_vip_interrupt.py -q`.
Lint all four SV files with pinned UVM. UVM runtime builds and interrupt
cocotb RTL qualification were not run for this change.
