# rvw init

Minimal supported path: an existing Spinal/sbt core repository with `build.sbt`
and Scala sources under `src`. Start with one config and one smoke ELF.
The command creates setup stubs. It cannot infer a safe bus or RVFI mapping.

```sh
cd /path/to/core
rvw init --isa rv32im --dry-run --json
rvw init --isa rv32im
rvw doctor --json
```

The command scans the build for literal Spinal version declarations and the
sources for candidate `Component` classes. These are hints, not elaboration.
If exactly one literal ISA string is found, it can use that string. Otherwise
supply `--isa`. There is no interactive prompt. `--xlen` can check the width.
`--name` overrides the directory name. A mismatched width is an error.
Verify ISA extensions against the core specification.

Files:

- `rvw.toml`: exact `rvw --version` pin, one `default` config and a smoke suite.
- `rvw/run.sh`: executable C1 info stub. Build and run return 2.
- `rvw/src/main/scala/rvwcore/CoreAdapter.scala`: typed RiscvSim adapter skeleton.
- `rvw/.gitignore`: ignores `out/` and local sbt output.
- `rvw/README.md`: the core's setup playbook and remaining actions.

`--dry-run` returns every planned file with its full text. It writes nothing.
The command checks all target conflicts before writing. It refuses any existing
target unless `--force` is set. `--force` replaces only the listed files. It
still refuses directory targets and blocked parent paths. Keep edited adapters
before using `--force`. Existing root `.gitignore` and `AGENTS.md` stay intact.

`--json` returns `rvw.init/1` with `status`, `exit_code`, `root`, `files`,
`overwritten`, `isa`, `xlen`, `spinal_versions`, `candidate_tops` and `next`.
Exit 0 means created or planned. Exit 2 means invalid input or write failure.
Failures include an `error` string. No MCP mutation tool is added.

## Non-Spinal cores (`--hdl`)

```sh
rvw init --hdl sv --top ibex_core --isa rv32imc -I vendor/lowrisc_ip/ip/prim/rtl --dry-run --json
rvw init --hdl vhdl --top neorv32_cpu --isa rv32i --library neorv32 --source rtl/core/neorv32_package.vhd ...
rvw init --hdl chisel --top Top --isa rv64gc --fir out/Top.fir --source-root src/main/scala
rvw query build --config default        # runs rvw/build-db.sh
```

`--hdl` selects the query front end: `sv` uses slang, `vhdl` GHDL, `chisel`
firtool. Without `--source`, it discovers `.sv`/`.v` or `.vhd` files outside
test and tool directories (`tb`, `test`, `dv`, `sim`, `rvw`, ...), packages
first. `--top` must be declared in them; candidates are listed in the JSON.
`--fir` names the FIRRTL file that the Chisel build emits; the scaffold does
not run sbt.

Files: `rvw.toml` (with `[query] build = ["./rvw/build-db.sh"]` and
`db = "rvw/out/design.db"`), `rvw/build-db.sh` (an explicit `rvw query
build-hdl` command; `$RVW` selects the `rvw` executable), `rvw/run.sh` (C1
launcher: `info` works; `build` compiles the design with Verilator and
`rvw/sim/harness.cpp`, through GHDL+Yosys for VHDL and firtool for Chisel;
`run` exits 2). The build creates its output directory before Verilator runs.
It passes an absolute harness path to the generated makefile. Build does not
require an earlier query build. Other files are `rvw/sim/harness.cpp` (compiles for any top, maps nothing,
exits 2), `rvw/.gitignore` and `rvw/README.md`. Every `rvw query` and `rvw
lint` command works after `rvw query build`. C1 runs need the bus, ELF and
completion mapping in the harness. The same conflict and `--force` rules apply.

## Decisions and limits

The output passes the shared project and regression loaders. Doctor reports
`project: ready` and `adapter.info: ready`. It returns exit 1 until the adapter,
tests, input declarations and clean commits are ready. A stub must not earn a
ready setup verdict. Use the core's playbook to finish these actions.

The default path stays minimal. Optional scaffolds use explicit inputs:

```sh
rvw init --isa rv32im --wire-build --sbt-project cpu --dry-run --json
rvw init --isa rv32im --linker-script memory.ld --ram-region ram --reset-pc 0x80000000 --dry-run --json
rvw init --isa rv32im --sbt-project cpu --db-top demo.Top --dry-run --json
```

`--wire-build` detects one literal sbt project declaration. If selection is
ambiguous, it asks for `--sbt-project` in an error. This is a noninteractive CLI.
The explicit project option also enables wiring. The generated `rvw/build.sbt`
depends on that core project and the installed generic RiscvSim library. It does
not copy core sources. Set `RVW_HOME` before use. Wiring supports a literal
Spinal 1.15.0 build with Scala 2.13.14, the simulator's current versions.
It uses `RVW_CORE_SOURCE` for captured core builds. It leaves the core's build intact and pins the local sbt launcher to 1.10.7.
A dependency file is not a compiled adapter. The generated launcher uses the generic supervisor, native identity collector
and source identity collector. It holds the core and sbt locks. It streams sbt and lock messages to stderr
while it captures the runtime classpath. Build and run
reach the adapter skeleton, which throws until the real signals are mapped.
The default scaffold without build wiring still returns exit 2 directly.

`--linker-script` reads a literal GNU linker `MEMORY` block. `ORIGIN` and
`LENGTH` accept decimal or hex values and K/M suffixes. Expressions and included
files are refused. Select `--ram-region` if there is more than one region.
Supply `--reset-pc` from the core specification. It must be in the selected RAM.
The command writes `rvw/cosim.json` and connects `[cosim]` in the project file.
The linker does not establish MMIO, PMP, IRQ, privilege or fault policies.
The platform has `review_required: true`. The cosim loader refuses this template
until the owner reviews these policies and removes that flag. No reference
comparison can silently use the template's default policies.

`--db-top` enables build wiring with SpinalDB and adds a C6 query entry. Supply
a fully qualified Component class with a no-argument constructor. The entry
supports only `default`. It forwards paths without passing them through the sbt
command parser. It holds the core and sbt locks and uses `nice -n 10`.
Parameterized tops need a manual Scala entry. Source inspection does not prove
that the selected class elaborates.

All optional files participate in the same dry-run and overwrite preflight.
The tests check generated files, project loading, launcher arguments and refusal
paths. They do not establish Scala compilation, DUT runtime or C2 mapping.
This command makes no integration-model decision under #34.

## Mapped adapter: a working C1 adapter from one command

`--spinal-top CLASS` (a no-argument Spinal Component) or `--verilog-top MODULE` with
`--verilog FILE` selects the mapped mode. It writes a project that runs: the
generic RiscvSim `MappedAdapter` reads `rvw/core-map.json` (`rvw.core-map/1`).

```sh
# Verilog core (ports read with Yosys; one valid-ready bus found by name):
rvw init --isa rv32im --verilog-top picorv32 --verilog picorv32.v \
  --define RISCV_FORMAL --param PROGADDR_RESET=0x80000000 --param ENABLE_MUL=1 \
  --param ENABLE_DIV=1 --clock clk --reset resetn --reset-active low \
  --reset-pc 0x80000000 --accept-platform-defaults
# Spinal core (ports are known only after elaboration, so name the buses):
rvw init --isa rv32i --spinal-top demo.Top --sbt-project cpu --reset-pc 0x80000000 \
  --bus 'i:req-rsp:cmd_valid=iBus_cmd_valid,cmd_ready=iBus_cmd_ready,address=iBus_cmd_payload_pc,rsp_valid=iBus_rsp_valid,rdata=iBus_rsp_payload_inst' \
  --bus 'd:req-rsp:cmd_valid=dBus_cmd_valid,cmd_ready=dBus_cmd_ready,address=dBus_cmd_payload_address,write=dBus_cmd_payload_wr,wdata=dBus_cmd_payload_data,mask=dBus_cmd_payload_mask,rsp_valid=dBus_rsp_ready,rdata=dBus_rsp_data'
```

Files: `rvw.toml` (complete adapter input declarations, a smoke suite, `[cosim]`
and `[query]`), `rvw/core-map.json`, `rvw/run.sh` (supervised launcher with
native and source identity), `rvw/build.sbt`, `rvw/build-smoke.sh`,
`rvw/programs/{smoke.S,link.ld}`, `rvw/cosim.json`, `rvw/build-db.sh` (SpinalDB
for `--spinal-top`, `rvw query build-hdl` for `--verilog-top`), `rvw/README.md`, and
for `--spinal-top` the RVFI wiring template `rvw/templates/RvfiPort.scala` and
`rvw/templates/CoreProbes.scala`. Copy the templates into the core and bind them
to actual retirement signals. The probe template uses `SpinalProbes`; add that
build dependency before use. Probes stay off by default.

`--bus NAME:PROTOCOL:key=port,...` maps a memory port (`req-rsp` or
`valid-ready`; keys in RiscvSim/README.md). For a Verilog top, buses can be found
by name (`<p>valid`, `<p>ready`, `<p>addr`, `<p>rdata`, optional `<p>wdata`,
`<p>wstrb`). `rvfi_` ports are used when present (`--rvfi-prefix` selects
another prefix). Every RVFI field must exist. `--irq BIT=PORT` maps MSIP, MTIP,
SEIP or MEIP. `--const PORT=VALUE` holds an input. A Verilog input that nothing
maps is tied to 0 and listed in `unmapped_inputs`. `--ram BASE:SIZE` (default
`0x80000000:0x100000`) and `--reset-pc` are required inputs from the core
specification. The cosim platform keeps `review_required` unless
`--accept-platform-defaults` is set. The defaults are machine mode only, aligned
RVFI memory words, alignment traps, absent-PMP traps and ECALL `tval` 0.

Checked on PicoRV32 `ef203c2b` (see `examples/picorv32/`): smoke and 45
PicoRV32 RV32IM test programs pass in `rvw regress`. 40 of 46 traces match
Spike. The `--spinal-top` path has unit tests only; no Spinal core was run through it.

