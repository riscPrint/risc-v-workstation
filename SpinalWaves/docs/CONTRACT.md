# SpinalWaves ⇄ SpinalTrace interface contract

This file fixes the interfaces shared by the two ports so they can be built in parallel.
Change it only by agreement (note the change and the reason at the bottom).

- **SpinalWaves** = Tywaves for SpinalHDL: typed waveform viewing (types, bundles, vecs, enums, areas,
  constructor params) in the Tywaves fork of Surfer.
- **SpinalTrace** = ChiselTrace for SpinalHDL: dynamic signal-dependency tracing from a VCD back to
  SpinalHDL source lines, using the ChiselTrace Rust back-end and Tauri GUI.

## Toolchain (this machine, macOS arm64)

- `source ../../spinal-boom/env.sh` (spinal-boom checkout next to this repo) → Zulu JDK 21 + oss-cad-suite (Verilator, Surfer
  0.4.0-dev stock, GTKWave) on `PATH`. Without it, `java` is missing.
- sbt (Coursier), Scala **2.13.14**, SpinalHDL **1.15.0** (core/lib/idsl-plugin; cached). Spinal core
  sources are unpacked at `ref/spinal-src/core/` of the development workspace.
- Rust (Homebrew cargo 1.98), node 26 / npm. Network is available.
- Reference sources (read-only, Apache-2.0 unless noted) in `ref/tracing/` of the development workspace:
  `rameloni_tywaves-chisel`, `rameloni_tywaves-rs`, `jarlb_tywaves-chisel`, `jarlb_tywaves-rs`
  (newer, used by ChiselTrace), `jarlb_surfer-tywaves` (EUPL-1.2, Surfer fork), `jarlb_chiseltrace`
  (Rust lib + CLI + Tauri/Svelte GUI), `jarlb_chisel` (branch `chiseltrace`: Chisel-side PDG builder in
  `core/src/main/scala/chisel3/chiseltrace/`).

## Layout

```
risc-v-workstation/SpinalWaves/
  spinalwaves/            sbt project, Scala library  `spinalwaves`  (package spinalwaves)
  third_party/tywaves-rs/ vendored copy of jarlb/tywaves-rs (+ Spinal patches, documented)
  surfer-tywaves/         vendored jarlb/surfer-tywaves (+ patches), built binary on PATH via script
  examples/, scripts/, docs/, README.md, PORTING_NOTES.md, UPSTREAM_WATCH.md
risc-v-workstation/SpinalTrace/
  spinaltrace/            sbt project, Scala library `spinaltrace` (package spinaltrace),
                          dependsOn ProjectRef(file("../../SpinalWaves/spinalwaves"), "spinalwaves")
  spinaltrace-rs/ cli/ gui/   fork of jarlb/chiseltrace (Cargo workspace), Spinal patches documented
  examples/, scripts/, docs/, README.md, PORTING_NOTES.md, UPSTREAM_WATCH.md
```

Both folders are separate local git repos. Commit in logical steps (local only, never push).

## Elaboration hooks (Scala)

- Neither library forks SpinalHDL. Hooks use public `SpinalConfig` extension points
  (`phasesInserters`, `transformationPhases`) and post-elaboration walks of `SpinalReport.toplevel`.
- **SpinalWaves must not change the generated RTL.**
- **SpinalTrace may only name and `keep` signals that already exist** (when conditions, switch
  values, mux selects, dynamic indexes) so they survive into the RTL/VCD. No new logic. It is opt-in.
- **Source locations**: Spinal only records stack traces when `debugComponents` is non-empty. Use
  Spinal's own two-pass trick: elaborate once to collect all component classes, then elaborate again
  with `debugComponents = <all classes>` so every `ScalaLocated` (statements, BaseTypes, Data) has a
  trace. Location = first frame that `ScalaLocated.filterStackTrace` keeps. Assignment statements
  also get `locationString` when `genLineComments = true`.
  SpinalWaves owns the shared helper `spinalwaves.SourceLocator` (stack frame → `(absPath, line,
  col)`; resolves the bare file name against source roots, default `src/main/scala`,
  `src/test/scala`, plus user-supplied roots; falls back to the bare file name).

## Naming API (owned by SpinalWaves, used by SpinalTrace)

SpinalWaves provides, early, and keeps stable:

```scala
package spinalwaves
object HglNaming {
  /** Instance path from the toplevel (toplevel excluded), e.g. Seq("sub", "inner"). */
  def instancePath(c: Component): Seq[String]
  /** For a leaf signal: (rootPath, fieldPath).
    * rootPath  = (instancePath :+ hglRootName).mkString(".")      e.g. "sub.io"
    * fieldPath = path inside the root, "." separated; Bundle elements by name, Vec elements by
    *             decimal index, Areas by name; "" when the leaf is the root.  e.g. "a.b.3" */
  def hglPath(bt: BaseType): (String, String)
  /** Full RTL path for VCD lookup: (instancePath :+ bt.getName()).mkString(".") e.g. "sub.io_a_b_3" */
  def rtlPath(bt: BaseType): String
}
```

These must agree with the emitted HGLDD, i.e. `tywaves-rs` `find_trace(extraScopes ++ rootPath.split
++ fieldPath.split)` finds the leaf.

## Simulation / VCD conventions

- Simulation via `SimConfig` + Verilator, VCD output (`withVcdWave`). FST is out of scope for now.
- Observed with SpinalHDL 1.15.0 and this workstation's Verilator: `$scope module TOP`, then
  `$scope module <Toplevel>` around the DUT's own signals. Top-level ports also have aliases
  directly under `TOP`. Child instances appear under `TOP <Toplevel> <instance> ...`.
- The complete prefix for typed lookup is `Seq("TOP", "<Toplevel>")`, **including the DUT scope**.
  Pass this as `--extra-scopes TOP <Toplevel>` and pass the emitted definition name as
  `--top-module <Toplevel>`. For example, the GCD simulation uses `--extra-scopes TOP Gcd
  --top-module Gcd`. tywaves-rs renames the HGLDD top definition to the final prefix element before
  adding its ancestor scopes; omitting the DUT element gives incorrect paths.
- SpinalWaves exposes the following stable header-reading API. It requires a unique scope named
  `topModule` and reports missing/ambiguous matches rather than guessing:

  ```scala
  object SimLayout {
    def extraScopes(vcd: java.nio.file.Path, topModule: String): Seq[String]
    def extraScopes(vcd: java.io.File, topModule: String): Seq[String]
    def extraScopes(vcd: String, topModule: String): Seq[String]
  }
  ```

- Default SpinalSim wave output is `W/<testName>/wave.vcd`; for the GCD test it was
  `target/integration/gcd/Gcd/gcd/wave.vcd`, with HGLDD at
  `target/integration/gcd/Gcd/spinalwaves/hgldd/Gcd.dd`. SpinalSim can suffix workspace/test names
  to avoid collisions. Read the actual returned compiled workspace and VCD path.
- Default clock/reset names come from the toplevel ClockDomain (Spinal default `clk` / `reset`,
  async, active high). SpinalTrace must make clock, reset, and reset polarity configurable (ChiselTrace
  hardcodes `clock`/`reset` and `TOP svsimTestbench dut`).

## Output files

For a toplevel `Top` compiled into workspace dir `W` (Spinal sim default `simWorkspace/Top`):

- `W/spinalwaves/hgldd/Top.dd` — HGLDD JSON (one file, all module objects), schema of
  `tywaves-rs/src/hgldd/spec.rs`, file paths in `file_info` absolute.
- `W/spinaltrace/pdg.json` — ChiselTrace `PDGSpec` (`spinaltrace-rs/src/pdg_spec.rs`) plus the Spinal
  extensions SpinalTrace documents in `SpinalTrace/docs/PDG_FORMAT.md`.
- VCD where SimConfig puts it (`W/<testName>/wave.vcd`).

## Change log

- 2026-10-19: initial version.
- 2026-10-19: populated the requested VCD conventions from the GCD Verilator run; documented
  the `SimLayout.extraScopes` overloads without changing the shared naming signatures.
