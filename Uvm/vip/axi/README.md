# AXI4 and AXI4-Lite agents

The profile has 32-bit data and addresses, 4-bit IDs, and aligned transfers.
It supports all five independent channels, FIXED/INCR/WRAP bursts, narrow
transfers, byte strobes, per-ID response queues, and exclusive reservations.
Different IDs can return out of order. AXI4-Lite uses the same engine with
single-beat transfers, no IDs, and no exclusive access.

`axi_if.sv` defines the pins and stall assertions. `axi_pkg.sv` contains the
manager driver, reactive RAM subordinate, passive monitor, channel analysis
port, directed and random sequences, error sequence, and functional coverage.
Connect `agent.m.ap` to a project scoreboard. `fixture.sv` supplies the seeded
RAM DUT. `+buggy` corrupts reads. `+bad_manager` in `test.sv` breaks WLAST.
Set `lite` on the monitor through `uvm_config_db` for the Lite profile.
The Lite bus wrapper must tie absent fields to the defaults in `axi_if`.

Python uses immutable `Pins`, `Address`, `Write`, and `Response` values.
`Manager` and `Subordinate` drive either role. `Monitor` checks the protocol
and calls a hook on completed bursts. `Scoreboard.observe` checks byte data.
`sequences(seed, lite)` makes repeatable bursts. `inject` changes a stalled
payload or drops VALID. `CocotbAgent` uses flat `PREFIX_awvalid` names and
supports both roles with optional Lite pin omission. It uses `clk` and
`reset_n` on the DUT. Cocotb imports occur only when an async method runs.

## Checks

Run `rvw/.venv/bin/python -m pytest rvw/tests/test_vip_axi.py -q`.
Lint with the pinned UVM source from `rvw.sim.uvm`:

```sh
verilator --lint-only --timing --assert -Wno-fatal +define+UVM_NO_DPI \
  +incdir+PATH_TO_UVM/src PATH_TO_UVM/src/uvm_pkg.sv \
  Uvm/vip/axi/axi_if.sv Uvm/vip/axi/axi_pkg.sv \
  Uvm/vip/axi/fixture.sv Uvm/vip/axi/test.sv --top-module top
```

## Decisions and limits

The pin monitor checks channel stability, address rules, response causality,
lengths, LAST, strobe lanes, and outstanding drain. Coverage records channel,
ID, length, burst kind, response and exclusive traffic. Python also records
stalls. The scoreboard requires reads after the relevant write response.
Concurrent read/write visibility is a target policy, not an AXI ordering rule.
Reset clears pending traffic. The Python fixture resets memory as well.

Unaligned transfers, optional user/QoS/region signals, and wider data/IDs
are outside this bounded profile. The RAM uses exact exclusive reservations.
It invalidates them on overlapping writes. It is not a cache or coherence
model. Runtime UVM and cocotb qualification has not been run. SV lint does
not establish simulator behavior or reactive subordinate qualification.

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
