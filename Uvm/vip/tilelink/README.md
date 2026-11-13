# TileLink-UL and TileLink-UH agents

The A/D profile uses 32-bit addresses and data, 4-bit source IDs and one sink.
UL supports Get, PutFullData and PutPartialData up to four bytes.
UH adds multi-beat messages up to 64 bytes, ArithmeticData, LogicalData,
and Hint. Atomics are one, two or four bytes. Coherent B/C/E channels are
outside this profile. The encoding follows the
[TileLink 1.8.1 specification](https://sifive.cdn.prismic.io/sifive/7bef6f5c-ed3a-4712-866a-1a2e0c6b7b13_tilelink_spec_1.8.1.pdf).

`tilelink_pkg.sv` contains manager and reactive RAM drivers, a passive
monitor, directed and random sequences, mask error injection, coverage,
and a scoreboard. `agent.m.ap` publishes accepted channel items to a
project scoreboard. Set `uh` on the monitor through `uvm_config_db`.
The default is UL. `tilelink_if.sv` defines the pins and corrupt checks.
The monitor checks sizes, masks, parameters, source allocation, message
control, D opcode and size, denied/corrupt rules, message interleaving
and drain. TileLink permits a sender to change an unaccepted beat.
The checker does not apply AXI stall rules to TileLink.

`fixture.sv` supplies the seeded RAM. `test.sv` selects UH by default.
Use `+ul` for UL, `+buggy` for read corruption, and `+bad_manager` for an
invalid mask. `smoke.py` follows the pinned Accellera UVM build flow.
Seed the simulator with `+verilator+seed+N`.

The matching Python module is `rvw.vip.tilelink`. `Manager.transfer`
accepts a tuple of A beats. `Subordinate.step` supplies a seeded RAM.
`Monitor` publishes completed request/response tuples. `Scoreboard` checks
serial memory traffic. `sequences` covers sizes, opcodes and atomic params.
`inject` changes a source, mask or response data. `CocotbAgent` supports both
roles and a passive monitor. It binds flat `PREFIX_a_valid`,
`PREFIX_a_opcode`, `PREFIX_d_valid` and matching field names. The DUT supplies
`clk` and `reset_n`. Cocotb is optional at import time.

## Checks

```sh
rvw/.venv/bin/python -m pytest rvw/tests/test_vip_tilelink.py -q
verilator --lint-only --timing --assert -Wno-fatal +define+UVM_NO_DPI \
  +incdir+PATH_TO_UVM/src PATH_TO_UVM/src/uvm_pkg.sv \
  Uvm/vip/tilelink/tilelink_if.sv Uvm/vip/tilelink/tilelink_pkg.sv \
  Uvm/vip/tilelink/fixture.sv Uvm/vip/tilelink/test.sv --top-module top
```

## Decisions and limits

Source IDs can complete out of order. Beats within a multi-beat A or D
message cannot interleave. An early write acknowledgement does not release
the source until its A message ends. Same-edge A/D responses are legal.
Manager drivers consume early D beats while they finish A traffic.
The RAM accepts a full A message before it schedules a D message.
A corrupt write is denied without a memory change. Reset clears memory
and pending traffic in the fixture. The fixture scoreboard has no mid-run
reset hook. A project must reset its scoreboard with its DUT.

The provided memory scoreboards use serial request order. A project with
concurrent overlapping writes must supply its own visibility policy.
SV and Python share the declared operations, but each runtime still needs
qualification. UVM runtime builds and cocotb RTL runs were not run.
Lint and Python cycle tests do not prove native subordinate behavior.

## Bounded Python RTL evidence

The Python cocotb adapter passed a seeded good RTL test and detected the
controlled bad RTL result. See `Uvm/vip/rtl/README.md` for commands and
fixture scope. This does not establish full protocol conformance or UVM
runtime qualification.

## Measured SV campaign

The [dated SV matrix](../qualification/native-2026-11-13.md) records this
fixture's compile and runtime status on Verilator 5.052. All declared normal and fault cases passed at seeds 1, 2 and 3.
Earlier lint/unit-only notes describe the initial test set. The dated matrix
gives the current SV result and its limits. Cocotb evidence is separate.
