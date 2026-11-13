# JTAG and test access agents

The Python manager reuses the existing generic TAP transition table.
It sends TMS reset, IR scans and DR scans. Bits shift least significant
bit first. The cocotb adapter uses `PREFIX_tck/tms/tdi/tdo/trst_n`.
The SV profile supports scans up to 64 bits. Python supports 4096 bits.
The fixture loops TDI to TDO. `+buggy` changes every received bit.
This fixture is a scan-wire check, not an instruction-register model.

`Tap` declares each device's name, instruction length, TDI, TDO, test
reset, access requirements and selected mode. `topology` exports the
chain in order with total instruction bits. Supply independent captured
connections and mode transitions to check adjacent TAP connectivity and
mode reachability. Omitted evidence yields `inconclusive`. A checked
report applies only to the supplied graphs. It is not extracted evidence.
Topology database extraction and backend qualification remain open.

SV provides directed/random scan sequences, manager, passive TAP monitor,
coverage and a loopback scoreboard. Supply project expected scan data
for a real TAP. RISC-V Debug and DMI conformance remain in `rvw.debug`.
This agent does not replace those campaigns or qualify boundary cells.

Run `rvw/.venv/bin/python -m pytest rvw/tests/test_vip_jtag.py -q`.
Lint all four SV files with pinned UVM. UVM runtime builds and JTAG
cocotb RTL qualification were not run for this change.

## Measured SV campaign

The [dated SV matrix](../qualification/native-2026-11-13.md) records this
fixture's compile and runtime status on Verilator 5.052. All declared normal and fault cases passed at seeds 1, 2 and 3.
Earlier lint/unit-only notes describe the initial test set. The dated matrix
gives the current SV result and its limits. Cocotb evidence is separate.
