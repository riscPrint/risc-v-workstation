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

## Database-selected profiles

```sh
rvw uvm new --db design.db --soc map.json --out /tmp/cpu-profile --profile cpu
rvw uvm new --db design.db --soc map.json --out /tmp/axi-profile --language sv --profile axi-lite
```

Profiles cover CPU RVFI bundles, APB, AXI4, AXI4-Lite, TileLink,
AXI-Stream, UART, SPI and I2C. Bus types come from the top-level Spinal
bundle classes. Auto selection requires one recognized bus. Use `--profile`
to select one bus type in a multi-bus design. Two buses of the same type
remain ambiguous and are refused. CPU selection requires a declared `Rvfi`
bundle. A CPU is not inferred from a module name.

Both `pyuvm` and `sv` output include the selected support path, port
inventory, clock domains, SoC map, manifest and a project scenario hook.
The Python profile imports the selected existing agent module. The SV
profile supplies a UVM test and a scenario include. The project must bind
the DUT and VIP interface, provide clocks/reset, and add its expected checks.
These are profile scaffolds. They do not provide automatic protocol wiring.
An unchanged hook fails with `PROJECT_SCENARIO_REQUIRED`. An empty Python
scenario or an SV scenario with no checks fails with `PROJECT_NO_CHECKS`.
A generated file does not qualify a simulator feature or earn C4 acceptance.

The default single-APB pyuvm path retains automatic register-reset wiring.
Use an explicit `--profile apb` for the customizable scaffold. The database
does not specify CPU software, serial framing, agent roles or device
responses. Supply those semantics in the project scenario. Per-profile
native qualification remains open.

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

The [live VexRiscv binding](../../../../Uvm/examples/vexriscv/README.md#native-results-on-2026-11-13)
has native Spike results for six RV32UI programs and six PC-corruption runs.
