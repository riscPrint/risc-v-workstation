# Single-port SRAM and ROM agents

This profile uses word addresses, 32-bit data and four byte write masks.
Reads have a fixed declared latency. Writes produce no response. Reset
cancels pending reads and restores the initial image. This reset policy
is explicit and differs from SRAMs that retain contents through reset.

Python supports configurable depth, read latency and ROM initial words.
ROM writes are errors. `Reference.step` models one sampled clock edge.
`Monitor` checks read data and latency. `Manager` sends blocking reads
and writes. Seeded sequences and a flat-pin cocotb adapter are included.
Pins are `PREFIX_enable/write/address/data/mask/valid/response`, with
external `clk` and `reset_n`. Sample before sequential RTL updates.

SV has 16 words and one-cycle read latency. The UVM package supplies
sequences, driver, monitor, coverage and a scoreboard. Its ROM mode uses
the scoreboard `readonly` bit and zero initial contents. The fixture is
a RAM. `+buggy` corrupts read data. Multiport memories, ECC and collision
semantics are outside this profile.

Run `rvw/.venv/bin/python -m pytest rvw/tests/test_vip_sram.py -q`.
Lint the four SV files with pinned UVM. UVM runtime builds and SRAM cocotb
RTL qualification were not run for this change.
