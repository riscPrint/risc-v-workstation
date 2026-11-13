# Wishbone Classic agents

This profile has 32-bit byte addresses and data, four byte selects and
one outstanding Classic transfer. STB requires CYC. ACK and ERR are
exclusive. The request stays stable until termination. There is no RTY,
STALL, pipelined mode or block-cycle support. Use aligned word addresses.

The SV agent has directed/random sequences, a driver, monitor, coverage
and a memory scoreboard. Connect the monitor to the scoreboard. Reset the
scoreboard with each new DUT reset. The fixture has 16 words and seeded
waits. `+buggy` changes read data. The Python module supplies matching
cycle models, seeded traffic and a cocotb adapter with `PREFIX_` pin names
from `Pins`. Clock and active-low reset are external.

Run `rvw/.venv/bin/python -m pytest rvw/tests/test_vip_wishbone.py -q`.
Lint all four SV files with the pinned UVM package. The native smoke
entry point is `smoke.py --out NEW_DIRECTORY`. UVM runtime builds and
Wishbone cocotb RTL qualification were not run for this change.
