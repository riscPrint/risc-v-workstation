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

## C4 adapter for a compiled SV bench

```sh
rvw uvm gate-config --build /tmp/bench-build --source-repo /path/to/bench-repo \
 --out /tmp/uvm-core.toml --seeds 1 3
rvw regress gate --core /tmp/uvm-core.toml --tier quick \
 --base-rev COMMIT --cand-rev COMMIT --json
```

The existing C4 runner executes this as a build-suite job. The adapter runs
all declared UVM tests and seeds. A build alone cannot pass that job.
The runner captures the source revision, Python environment, adapter code,
UVM source inputs, pinned library, build metadata and simulation executable.
The adapter binds its C1 build claim to source hashes, executable hash,
test matrix, seed matrix and the pinned Accellera identity.

Every source input must be within `source_repo`. Each selected revision
must match the compiled input bytes. A source change requires a fresh build.
Pure SV sources need no native dependency declaration. A DPI bench or a
bench with custom `build_args` must declare `native_dependencies` in its
manifest. The build hashes those files and all files in declared directories.
The runner checks their bytes before execution. The C4 identity and capture
include those hashes and files. Project-owned dependency sources must also
match the selected revision. Generated inputs outside the source repository
need an explicit native dependency declaration. The project must list every
DPI header, runtime library, generated image and other native input. A missing
declaration is refused for custom builds. This does not infer native library
dependencies from arbitrary compiler options. Failed, empty or incomplete matrices cannot pass. Existing C4
dirty-source and incomplete-identity checks still apply.

The native regression's full C1/C3 logs remain in the output path printed
in the C1 build stdout. Standalone `uvm regress` retains its incomplete
source identity. The C4 wrapper supplies the additional captured identity.
This is acceptance for the selected bench, source and matrix. The adapter
fixture is a component test. Its acceptance does not qualify a CPU or ISA.

Native validation on 2026-11-13 built the adapter fixture on Verilator
5.049. A clean committed same-revision gate returned `accept`. Base and
candidate each ran `adapter_smoke` at seeds 1 and 3 through one build-suite
job. The tested implementation commit was `6665411b`. This checks the gate
integration. It does not test acceptance of a changed CPU revision.

## Untyped HDL databases

Automatic bench generation requires supported typed bus metadata. A database
with plain Verilog ports returns `status: unsupported` and writes no bench.
The CLI exits 2. MCP returns the same status. Supply a project-owned bench
and explicit protocol pin bindings. Port names alone do not establish a bus.
`rvw.uvm.soc.SocRegisterEnvironment` adds passive APB register side-effect
checks for multiple mapped regions. Sample each bus monitor at its own clock.
Call `reset()` when the peripheral reset is asserted. Unknown-reset reads do
not add a comparison. Use separate scoreboards for autonomous registers.
The existing `SocEnvironment` interface is unchanged.

## Custom project buses

`uvm new --adapter adapter.json` (MCP `uvm_new.adapter`) accepts a project-owned
`rvw.uvm-adapter/1` file for pyuvm. It names `bus` (a top-level database bundle),
`profile` (the agent family), `bindings` (an object of project pin mappings), and
`scenario` (a Python file relative to the adapter). The generator copies that
scenario into the bench. The scenario binds the custom pins and uses
`services.checked(...)` for each expected result. Zero checks still refuse a pass.
For example: `{"schema":"rvw.uvm-adapter/1","bus":"top.io.mem","profile":"cpu",
"bindings":{"address":"io_address"},"scenario":"scenario.py"}`.
Generation does not establish protocol or CPU qualification.
