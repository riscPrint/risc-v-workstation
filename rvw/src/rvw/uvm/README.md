# Project UVM flow

See [Uvm](../../../../Uvm/README.md) for the bench manifest, examples and limits.
The flow uses the same pinned Accellera archive as `rvw regress uvm`.
It keeps each build and run in a new directory.

## Generate a register bench

```sh
rvw uvm new --db design.db --soc map.json --out /tmp/new-bench
rvw regress cocotb /tmp/new-bench/bench.json --out /tmp/new-bench-run
```

The first runnable profile is pyuvm with one top-level Spinal `Apb3` or
`Apb4` bus, one clock/reset domain and one MMIO region. The generator selects
the merged APB agent from the Spinal bundle class. It maps unique APB port
suffixes, copies the SoC map and builds Python RAL. The test reads declared
32-bit register resets through the actual bus. At least one known readable
reset is required. Missing or ambiguous pins fail before output is created.
APB3 omits PSTRB and PPROT. The generated profile performs reads only.

RTL paths come from the database. Use `--rtl FILE...` to select explicit
sources. Relative paths are relative to the database directory. Outputs
must be new. The source database and SoC map remain unchanged.

AXI, AXI-Lite, AXI-Stream, AHB-Lite, TileLink and UART classes are identified
but their automatic runnable wiring is not implemented. They produce an
explicit profile diagnostic. CPU/SoC virtual sequences, SV scaffold output,
multiple regions and complete automatic peripheral behavior remain open.
This register-reset smoke does not establish CPU or C4 acceptance.

## Required engine features

`rvw uvm build bench.json --out DIR --require-feature hdl_backdoor`
refuses a requirement outside the qualified runner profile before it creates
output or starts tools. Repeat `--require-feature` for each requirement.
The MCP build tool takes the equivalent `required_features` string array.
Unsupported requirements include Accellera HDL backdoor/VPI polling,
four-state behavior, advanced constraints/coverage and commercial VIP.
The error gives a specific diagnostic and a workaround. Use
`rvw uvm features RESULTS` for measured C3 evidence. Passing the requirement
filter alone is not a feature qualification result.

Accellera DPI remains disabled. A project DPI bridge needs separate ABI and
behavior checks. Imported VIP still requires usable licenses and qualified
engine support. The profile does not bypass those requirements.
