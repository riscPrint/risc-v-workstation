# SpinalTrace: automatic signal-dependency tracing for SpinalHDL

SpinalTrace is a port of [ChiselTrace](https://github.com/jarlb/chiseltrace) (J. Brand et al., NorCAS 2025)
to [SpinalHDL](https://github.com/SpinalHDL/SpinalHDL). Given a simulation (VCD) and a signal or statement
that misbehaves, it builds the **dynamic program dependence graph**: which SpinalHDL source statements,
in which clock cycles, actually produced that value, through data, control (`when`/`switch`) and index
(mux select, dynamic `Vec`/bit index, memory address) dependencies. Values are shown typed when
[SpinalWaves](../SpinalWaves) HGLDD is available, raw otherwise.

It has four parts:

* `spinaltrace/` – Scala library: a naming phase that keeps the signals the tracer must read
  (no new logic), a netlist walker that writes `W/spinaltrace/pdg.json` in ChiselTrace's format
  (docs/PDG_FORMAT.md), and `SpinalTraceSim`, a SpinalSim helper that offers a trace on failures.
* `spinaltrace-rs/` – the ChiselTrace back-end, patched for Spinal (PORTING_NOTES.md).
* `cli/` – `spinaltrace-cli`.
* `gui/` – `spinaltrace`, the ChiselTrace Tauri + Svelte graph viewer.

Example (GCD from the ChiselTrace README, `io.result` traced back to the load):

```text
t=4    Gcd.scala:30    Connection connect_io_result      12 (0xc)    data->Gcd.scala:20@t4
t=4    Gcd.scala:20    Connection connect_x              12 (0xc)    cond->Gcd.scala:19@t3 data->Gcd.scala:20@t2 data->Gcd.scala:22@t3
t=3    Gcd.scala:22    Connection connect_y              0 (0x0)     cond->Gcd.scala:19@t2 ...
...
t=0    Gcd.scala:26    Connection connect_x              24 (0x18)   cond->Gcd.scala:25@t-1 data->Gcd.scala:8@t-1
```

## Install

Tested on macOS arm64 with: JDK 21, sbt 1.10, Scala 2.13.14, SpinalHDL 1.15.0, Verilator 5.x,
Yosys (only for one test), Rust 1.98 (edition 2024), Node 26 / npm. From the workstation root, run
`scripts/install.sh --with-sim --with-formal` and source the generated `env.sh`.
From `SpinalTrace/`, use `source ../env.sh`.
SpinalTrace expects the sibling checkout `../SpinalWaves` (sbt source dependency and tywaves-rs).

```bash
# CLI (target/release/spinaltrace-cli)
cargo build --release -p spinaltrace-cli

# GUI (target/release/spinaltrace); uses the repo-local Tauri CLI from gui/package.json
cd gui && npm ci && npm run tauri -- build --no-bundle && cd ..

# Scala library (published locally if you want to use it from another build)
cd spinaltrace && sbt compile && cd ..
```

Put `target/release` on `PATH` or point `SPINALTRACE_CLI` / `SPINALTRACE_GUI` at the binaries.
Tauri's [prerequisites](https://v2.tauri.app/start/prerequisites/) are needed for the GUI build only.

## Quick start: simulation helper

```scala
import spinal.core._
import spinal.core.sim._
import spinaltrace._
import spinaltrace.SpinalTraceSim.expect

val t = SpinalTraceSim.compile(SimConfig.workspacePath("simWorkspace"))(new GCD)  // instrumented, VCD, HGLDD, pdg.json
t.doSim("gcd") { dut =>
  dut.clockDomain.forkStimulus(10)
  dut.io.a #= 24; dut.io.b #= 36; dut.io.loadValues #= true
  dut.clockDomain.waitSampling()
  dut.io.loadValues #= false
  dut.clockDomain.waitSampling(10)
  expect(dut.io.result, 13)   // wrong on purpose (README of ChiselTrace)
}
```

When `expect` fails, an HDL `assert` fires, or the testbench throws, `SpinalTraceSim` prints:

```text
[SpinalTrace] Simulation 'gcd' failed at t=270: Expectation failed on io_result at t=270: observed value 12 != 13
[SpinalTrace] CLI: spinaltrace-cli dyn-pdg -s signal:io_result -p .../GCD/spinaltrace/pdg.json -v .../GCD/gcd/wave.vcd --hgldd-path .../GCD/spinalwaves/hgldd --top-module GCD --extra-scopes TOP GCD --at-time 269 -o .../dynpdg.json --summary
[SpinalTrace] GUI: spinaltrace -s signal:io_result -p ... --at-time 269
```

What happens next is chosen by `SpinalTraceSimOptions.onFailure` or the environment:

| mode | behaviour |
|---|---|
| `Prompt` (default with a console) | ChiselTrace's `continue? (Y/n/t/dt)`: `Y` continue, `n` fail, `t` / `dt` open the GUI (full / data-only) |
| `Print` (default without a console, or `SPINALTRACE_NONINTERACTIVE=1`) | print the commands, fail with `SpinalTraceFailure` |
| `RunCli` (`SPINALTRACE_ON_FAILURE=cli`) | also run the CLI, write `dynpdg.json`, print its summary, fail with `SpinalTraceFailure` (has `.session` and `.cliOutput`) |

It never opens a GUI or reads stdin unless `Prompt` is active. HDL assertions use the `assert_<File>_l<line>`
statement as criterion; other exceptions print a template command. The traced time is `t-1`: in SpinalSim a
check right at a clock edge sees the values from before the edge.

Without a simulation helper: `SpinalTrace.generateVerilog(config)(new Top)` writes
`<targetDirectory>/spinaltrace/pdg.json`, `SpinalTrace.instrument(config)` adds the naming phase to your own
config, and `PdgExtractor.extract(report)` works on any report elaborated with `debugComponents`
(e.g. `SpinalTrace.elaborate`).

## Quick start: CLI and GUI

```bash
spinaltrace-cli dyn-pdg -s signal:io.result -p W/spinaltrace/pdg.json -v W/test/wave.vcd \
    [--hgldd-path W/spinalwaves/hgldd] [--at-time 269 | --at-cycle 9] -o dynpdg.json --summary
spinaltrace -s signal:io.result -p W/spinaltrace/pdg.json -v W/test/wave.vcd --hgldd-path W/spinalwaves/hgldd
```

* Criteria: `signal:<RTL path>` (`io_result`, `mid.stage`) or Spinal path (`io.result`),
  `statement:<vertex name>` (`statement:connect_io_result`, `statement:assert_Features_l153`),
  `line:<file>:<line>` (`line:Gcd.scala:20`).
* `--at-time T` / `--at-cycle N` choose the cycle (default: end of the VCD; `--max-timesteps` kept for
  ChiselTrace compatibility). Cycle 0 is before the first rising edge.
* `--top-module`, `--extra-scopes` (Verilator: `TOP <Toplevel>`), `--clock` (`clk`), `--reset` (`reset`),
  `--reset-kind async|sync|none`, `--reset-active-low`, `--no-reset` default to the values recorded in
  `pdg.json`.
* `--data-only` traces data dependencies only; `--fir` keeps the netlist-level graph.
* Other subcommands from ChiselTrace: `dyn-slice` (dynamic slice as a list of source statements),
  `slice` (static slice), `convert`.

The GUI is the ChiselTrace viewer: timeline, hover for source and typed values, hierarchical grouping
(`--hier-grouping`), re-rooting.

## Tests

```bash
source ../env.sh
cargo build --release -p spinaltrace-cli      # the Scala tests call this binary
cargo test -p spinaltrace-rs                   # engine unit tests + fixture traces (no JVM needed)
cd spinaltrace && sbt test                     # 20 tests, Verilator simulations, ~2 min
```

`ExamplesTraceSpec` simulates each example in `examples/src/spinaltrace/examples/` and checks the traced
source lines and edge kinds (and that spurious ones are absent): the ChiselTrace GCD (passing, and with
the README's wrong expectation 13), an injected GCD bug, `when`/`elsewhen`/`otherwise`, a `switch` on a
SpinalEnum with `default`, a `Vec` with dynamic read and write index, `Mux`, a two-level hierarchy with
the bug in the leaf, a register with init and a reset pulse, a sync-read `Mem`, a failing HDL `assert`,
partial bit assignments and a BlackBox. `InstrumentationSpec` proves the instrumented RTL equivalent to the
plain RTL (Yosys), checks every probe/predicate is in the VCD and checks the PDG structure.
`spinaltrace-rs/tests/fixtures` are regenerated with
`cd spinaltrace && sbt "Test/runMain spinaltrace.FixtureGen ../spinaltrace-rs/tests/fixtures"`.

## Documentation

* [PORTING_NOTES.md](PORTING_NOTES.md): FIRRTL → Spinal mapping, design decisions, every Rust patch,
  limitations.
* [docs/PDG_FORMAT.md](docs/PDG_FORMAT.md): `pdg.json` (vertex/edge conventions, extensions).
* [../SpinalWaves/docs/CONTRACT.md](../SpinalWaves/docs/CONTRACT.md): interface shared with SpinalWaves.

## Licence and attribution

Apache License 2.0 (LICENCE, from ChiselTrace). The Rust back-end, CLI and GUI are forked from
ChiselTrace by Jarl Brand (jarlb/chiseltrace `f4bf63a`); the Spinal front-end re-implements the Chisel-side
PDG builder of jarlb/chisel (`chiseltrace` branch). tywaves-rs (Apache-2.0) comes from SpinalWaves.
`sim_data_injection.rs` contains code adapted from surfer-tywaves (EUPL-1.2, Raffaele Meloni), as in
ChiselTrace.

If you use this work, please cite ChiselTrace: J. Brand, C. Cromjongh, H.P. Hofstee, Z. Al-Ars,
"ChiselTrace: Typed Behavioral Debugging in Chisel Through Signal Dependency Tracing", IEEE NorCAS 2025.

## Trace accuracy

Read `accuracy.status` and `accuracy.reasons` in every graph or slice JSON result.
The GUI shows the same status above the graph. Source grouping reports `approximate`.
Missing causes or unmodeled timing report `incomplete`. Do not use either result as
an exact dependency trace. Limits apply to the whole design, including paths outside
the criterion. Legacy extraction files report incomplete. Re-extract with the current
front-end to use the formatVersion 2 contract.

The supported subset uses one rising-edge clock without a clock enable or soft reset.
Memory writes must be synchronous, equal-width and unmasked. Memory reads can be
synchronous or asynchronous. Large memories and dynamic partial writes report
incomplete. See [the accuracy contract](docs/PDG_FORMAT.md#accuracy-contract-formatversion-2)
for the bounds and source grouping rules.

## Viewer node IDs

The viewer assigns each long-distance pseudo-node the ID `vertex_count + edge_index`.
This reserves real vertex IDs and gives repeated relations distinct IDs in both
views. IDs must fit JavaScript's exact integer range. Source navigation follows
the relation's destination. Test with `cargo test -p spinaltrace --lib viewer_tests`
and `cargo test -p spinaltrace-rs viewer_ids`.
