# Simulation semantics examples

Run these commands from the workstation root. Each output directory must be new.
Install native Icarus, Verilator, make and a C++ compiler. The mixed example also
needs GHDL with synthesis support and Yosys. Use a machine lock on shared hosts.

```sh
rvw regress backends --hdl --json
rvw regress hdl examples/sim-semantics/xreset.json --out /tmp/xreset --json
rvw regress hdl examples/sim-semantics/xfree.json --out /tmp/xfree-4 --json
rvw regress hdl examples/sim-semantics/xfree.json --backend verilator-timing --out /tmp/xfree-2 --json
rvw regress hdl examples/sim-semantics/timing.json --out /tmp/timing --json
rvw regress hdl examples/sim-semantics/mixed.json --out /tmp/mixed --json
```

`xreset` checks uninitialized X arithmetic, Z, zero masking, reset clearing X,
and a post-reset count. Selecting Verilator for this case must fail preflight.
`xfree` checks reset and four known counter values after nonblocking updates.
The native Python test compares its `OBS` lines between Icarus and Verilator.
`timing` checks delays, fork/join, edge controls, repeat and settled nonblocking
updates against explicit expected times and values. `mixed` checks a VHDL
counter after GHDL/Yosys synthesis, from an Icarus SystemVerilog testbench.
Expected values come from the testbench checks, not another DUT run.

## Decisions and limits

This is a small conformance subset. It does not establish commercial simulator
parity, complete SystemVerilog support or VHDL event co-simulation. See the
[runner limits](../../rvw/src/rvw/sim/README.md#native-hdl-testbenches).
Native tests skip only when required tools are absent. Compiler or simulator
failures with installed tools fail the tests.
