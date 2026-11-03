# Porting notes: ChiselTrace → SpinalTrace

## Origin

| part | upstream | how it was used |
|---|---|---|
| `spinaltrace-rs/`, `cli/`, `gui/` | [jarlb/chiseltrace](https://github.com/jarlb/chiseltrace) `f4bf63ab036181ca9a37d1f4b2779569ab09b5a2` (Apache-2.0, Jarl Brand) | forked; imported verbatim in the first commit, Spinal patches in later commits (listed below, marked `SPINALTRACE:` in the Rust sources) |
| Chisel-side PDG builder | [jarlb/chisel](https://github.com/jarlb/chisel) branch `chiseltrace` `8cc6ea6b` (`ChiselTracePDGBuilder.scala`, `ProgramDependencyGraph.scala`, `BuildProgramDependencyGraph.scala`) | **re-implemented** for the Spinal netlist (`spinaltrace/src/main/scala/spinaltrace/`), same output format and naming conventions; no code copied |
| tywaves-rs | jarlb/tywaves-rs `215ff16` as vendored and patched by SpinalWaves | used from `../SpinalWaves/third_party/tywaves-rs` (no copy here) |
| naming / locations / HGLDD | SpinalWaves `spinalwaves` library | `HglNaming`, `SourceLocator.fromFrame`, `SpinalWaves.elaborateWithLocations`, `SpinalWavesSim`, `HglddEmitter`, `SimLayout` |

## Concept mapping

| ChiselTrace (FIRRTL) | SpinalTrace (Spinal netlist after `PhaseAllocateNames`) |
|---|---|
| FIRRTL circuit, modules, `DefInstance` | `SpinalReport.toplevel`, `Component.children`, one walk of each `dslBody` |
| `FileInfo` source locators | ScalaLocated stack traces (two-pass `debugComponents` via `SpinalWaves.elaborateWithLocations`), first user frame → `SourceLocator.fromFrame`; `genLineComments` as fallback |
| flattened symbol `sub.io.a` (prefix + FIRRTL name, compound signals split) | `HglNaming.rtlPath(bt)` per leaf `BaseType` (`sub.io_a`); Spinal is already flat, no compound/flip resolution needed |
| `relatedSignal` (root, field path) | `HglNaming.hglPath(bt)` (agrees with the SpinalWaves HGLDD) |
| `Connect` | `DataAssignmentStatement` (full) and `BitAssignmentFixed/Floating`, `RangedAssignmentFixed/Floating` targets (partial, new `assignRange`) |
| `DefNode` | combinational signal declared and assigned once on the same line (`defnode_`) |
| `DefWire` | combinational `BaseType` declaration (`defwire_`) |
| `DefRegister` / `DefRegisterWithReset` | `BaseType.isReg` declaration / `InitAssignmentStatement` (+ `InitialAssignmentStatement`) |
| `Conditionally` + inserted `pred_*` node | `WhenStatement`; the condition is an existing Bool (Spinal names it `when_<File>_l<n>`; the SpinalTrace phase names the remaining anonymous ones) |
| — (Chisel `switch` lowers to `when`) | `SwitchStatement` with `is` keys (literal, `EnumLiteral`, `MaskedLiteral` via `SwitchStatementKeyBool`, signal) and `default` → CFG switch extension |
| `Mux` + inserted `probe_*` select | `BinaryMultiplexer` (cond) — conditions on the existing select signal |
| `SubAccess` dynamic vector index + `probe_*` | `Multiplexer` (dynamic `Vec` read), `BitVectorBitAccessFloating`, `BitVectorRangedAccessFloating`, `*AssignmentFloating`; dynamic `Vec` writes are Spinal's `when((U(1) << idx)(i))` per element, recognised and turned into vertex conditions `idx == i` |
| `CDefMemory` + `CDefMPort` (read/write/infer, seq → `assignDelay`) | `Mem` + `MemReadAsync`, `MemReadSync` (`assignDelay = 1`), `MemWrite`, `MemReadWrite`; per-word symbols |
| `DefMemory` (SRAM, opaque) | memories above `maxMemWords` (coarse single symbol) |
| `ExtModule` | `BlackBox` (opaque) |
| `IntrinsicStmt` | `AssertStatement` (assert / assume / cover) |
| implicit `clock`, `reset` | `ClockDomain` signals; ports with `ExternalDriverTag` and their wiring into children are dropped as plumbing; clock / reset / polarity / kind recorded in the PDG metadata |
| `ChiselTraceDebugger` (ChiselSim, `expect`, Y/n/t/dt prompt) | `SpinalTraceSim` (SpinalSim + Verilator, `SpinalTraceSim.expect`, HDL `assert` failures, same prompt or non-interactive print / run-CLI modes) |

## Front-end design decisions

* **No new logic.** ChiselTrace inserts `probe_*` and `pred_*` nodes into the FIRRTL. CONTRACT.md only
  allows naming existing signals, so `ProbeNamingPhase` (inserted right after
  `PhaseCollectAndNameEnum`) gives a REMOVABLE-priority name (`when_`, `switch_`, `case_key_`, `mux_sel_`,
  `index_`, `mem_addr_`, `mem_wen_`, `mem_ren_`, `mem_cs_` + `<File>_l<line>`) to anonymous signals that
  the engine must read. Named signals are not inlined by `PhaseRemoveIntermediateUnnameds`, so they
  appear as wires in the RTL and the VCD. Literal-driven signals are never named (they must still fold).
  The probe *vertices* of ChiselTrace (`defnode_probe_*`) are still emitted, but only in the graph.
  `InstrumentationSpec` proves with Yosys `equiv_*` that the instrumented RTL is equivalent to the
  plain RTL for every example, and that every predicate/probe is in the Verilator VCD.
* **Switch.** Implemented as a CFG extension with case-value matching (bit patterns with don't-care
  bits, or a signal value) instead of chained boolean forks, because the chained forks would need
  `value === key` signals that do not exist in the netlist. See docs/PDG_FORMAT.md.
* **Partial assignments** (`x(3) := ...`, `x(7 downto 4) := ...`, `x(idx) := ...`) do not exist in
  FIRRTL. They get an `assignRange` key; the engine keeps a provider *set* per signal (see Rust patches).
* **Memory writes** are placed by Spinal in the memory's scope with the `when` condition folded into a
  write-enable signal. The write vertex therefore carries a vertex condition on address *and* enable
  and an Index dependency on the enable (instead of ChiselTrace's Conditional edge to the `when`).
* **Child IO** declarations are Definition vertices without `assignsTo` (ChiselTrace keeps `assignsTo`,
  which can make an undriven-in-this-cycle child input resolve to its own declaration).
* **Locations** skip `java.*`, `spinal.core`, `spinal.sim`, `spinaltrace`, `spinalwaves` and by default
  `spinal.lib` frames, so library-generated statements map to the user's call site
  (`ExtractOptions.includeLibraryFrames = true` keeps library frames). SpinalWaves' `SourceLocator.locate`
  uses the first frame Spinal keeps; SpinalTrace only reuses its `fromFrame` resolution.
* **Failure time.** In SpinalSim a read right after `waitSampling()` returns the *pre-edge* value
  (verified: count 5 at t=170 while the VCD shows 6), and HDL assertions also fire on pre-edge values.
  `SpinalTraceSim` therefore traces `--at-time t-1` (the cycle ending at the failing edge).

## Rust patches (all marked `SPINALTRACE:`)

`spinaltrace-rs` (fork of `chiseltrace-rs`):

1. `pdg_spec.rs`: optional `spinaltrace` metadata on `PDGSpec`; `assignRange` on vertices; CFG
   `cases` / `defaultBranch` with `CFGSpecCase` / `CFGCaseKey`; `assigns_to` on `ExportablePDGNode`.
2. `graphbuilder.rs`:
   1. `TraceSignals`: configurable extra scopes, clock, reset (optional), reset polarity and kind
      (`async` / `sync` / `none`); `GraphBuilder::new` keeps ChiselTrace's `clock`/`reset` defaults.
   2. Probes are every VCD signal named in a vertex/edge condition, predicate or case key, looked up by
      path; no `probe_` name prefix, no scope scan. Missing signals produce a warning.
   3. Watched values are bit strings committed with ChiselTrace's pre-edge rule; predicates are read from
      scalar *and* vector changes (multi-bit switch values, x/z aware).
   4. Switch forks: first case with a matching pattern / signal key, else the default branch.
   5. Provider sets for partial assignments: a full assignment replaces every provider, a partial one
      replaces the provider with the same key (`dyn` keys accumulate, newest 16 kept); dependencies go
      to every provider; a `signal:` criterion returns the newest one.
   6. Reset handling: reset is sampled like the other signals; init values apply immediately when the
      (async) reset was active during the cycle, and a reset held over the clock edge dominates the
      register writes of that cycle (ChiselTrace let same-cycle writes override the reset value and read
      the reset value including post-edge changes); a reset released at the cycle's opening edge does not
      count as active in that cycle; sync reset applies at the edge only.
   7. Delayed (sync-read) statements evaluate their vertex condition (read enable) when issued and use
      the control flow (Conditional edges) of their issue cycle (ChiselTrace used the ready cycle's);
      snapshots are kept for the longest `assignDelay` only.
   8. `StopAt::Cycle` / `StopAt::Time` (`--at-cycle`, `--at-time`): stop in that cycle without applying
      its register updates, so a `signal:` criterion reports the value during the cycle. The tail after
      the last edge is processed as a cycle. A vector-valued clock is accepted.
   9. Dependencies are de-duplicated per (signal, edge kind) and a node never depends on itself (needed
      for partial self-assignments).
   10. `line:<file>:<line>` criterion (`util.rs`).
3. `sim_data_injection.rs`: extra scopes and clock configurable (ChiselTrace hardcoded
   `TOP svsimTestbench dut` and `clock`); **nested-scope bug fixed** in `build_signal_map` (the "."
   between scopes was dropped: `subio` instead of `sub.io`); the Tywaves-rewritten VCD is written next to
   the input as `<top>.tywaves.vcd` instead of `./<top>.vcd`; new `inject_raw_values` attaches plain VCD
   values when no HGLDD is available.
4. `pipeline.rs` (new): the trace pipeline shared by CLI and GUI (ChiselTrace duplicated it); flag
   defaults from the PDG metadata; HGLDD optional with fallback to raw values; `signal:` criteria by RTL
   path or Spinal/HGL path (`io.result`); multi-clock-domain warning; text summary.
5. `slicing.rs`: CFG reduction understands switch forks; metadata kept; statistics to stderr.
6. `conversion.rs`: statement grouping by file/line, `defnode_probe` filtering, Index
   redirection; accuracy status survives conversion and reports grouping limits.

`cli/`: crate/binary `spinaltrace-cli`; `dyn-pdg` and `dyn-slice` take flags shared with the GUI
(ChiselTrace's `dyn-pdg` used positional arguments with an optional one in the middle):
`-s -p -v --hgldd-path -t -e --clock --reset --no-reset --reset-active-low --reset-kind
--max-timesteps --at-cycle --at-time --data-only --fir -o --summary`.

`gui/`: crate/binary `spinaltrace`, lib `spinaltrace_lib`; same flags as the CLI plus `--hier-grouping`;
HGLDD optional; uses `pipeline::trace`; product name / identifier / window title renamed. The
SvelteKit front-end shows trace accuracy above the graph.

Workspace: crates renamed (`chiseltrace-rs` → `spinaltrace-rs`, `chiseltrace-cli` → `spinaltrace-cli`,
`chiseltrace` → `spinaltrace`), tywaves-rs taken from `../SpinalWaves/third_party/tywaves-rs`.

## Limitations

* **One clock.** Like ChiselTrace, all registers are stepped on one clock (the domain with most
  registers). Multiple clock domains are detected and reported (PDG `warnings`, JSON accuracy, GUI status);
  dependencies through other domains are timed incorrectly. Clock enables and soft resets are not
  modelled (warned).
* VCD from Verilator only (FST and other simulators untested).
* BlackBoxes are opaque and combinational (every output depends on every input in the same cycle).
* Memories: write masks ignored (masked writes count as full-word writes); mixed-width ports and
  memories above 4096 words are tracked as one symbol (a read depends on the last write anywhere);
  `MemReadAsyncWrite` only on its read side.
* Dynamic partial writes keep the 16 newest providers per signal; overlapping different fixed ranges are
  kept side by side (conservative).
* Selects/indexes/conditions that are still anonymous expressions (should not happen after the naming
  phase) are handled conservatively and reported: all mux inputs / both `when` branches count.
* The static `slice` command's CFG reduction does not renumber predicates (inherited; only the vertex
  list is written, so there is no visible effect).
* Signals assigned straight from clock-domain signals are treated as clock plumbing only if they are
  child ports or anonymous wires; user-named signals derived from `reset` stay traceable.
* Switch keys other than literals, enum literals, masked literals and named signals are unsupported
  (that case is never taken; reported).
* Spinal reports an `is(...)` at the line of its block's first statement (JVM line numbers), so a case
  vertex is grouped with that statement; the `switch` line is separate.
* Spinal formal constructs (`past`, `initstate`, ...) and analog / inout signals are not specially handled.
* Inherited from ChiselTrace: grouping into source statements is by (file, line); several statements on
  one line merge; `statement:` criteria pick the latest activation; combinational nodes of cycle 0 are
  labelled -1; typed values are rendered as raw bits with the Tywaves type name.

## Simulation time limit

`SpinalTraceSim` arms `spinalwaves.SimGuard` (Spinal `SimTimeout`) in every `doSim`: default 10,000,000 sim time
units, `SpinalTraceSimOptions(simTimeout = None)` or env `SPINAL_SIM_TIMEOUT=0` disables it. Hitting it is a sim
failure, so the usual trace commands are printed. Without it, a hung testbench writes an unbounded VCD.

## GUI dependency updates (2026-10-19)

The npm lockfile inherited from ChiselTrace had 12 audit findings (7 high: Vite dev-server file access, Svelte SSR
XSS, `uuid` via vis-data/vis-network). All packages were updated within their existing major versions
(`npm update`): Svelte 5.57, SvelteKit 2.70, Vite 6.4, vis-network 9.1.13, vis-data 7.1.10, Tauri JS 2.12.
The Rust Tauri crates were moved to the same minor (`tauri` 2.12, `tauri-build` 2.7, `tauri-plugin-opener` 2.7)
because Tauri rejects mismatched JS/Rust versions. `svelte-check`, the GUI build, the Rust tests and the Scala tests pass.

Remaining: 3 low findings, all one advisory (`cookie` < 0.7 inside SvelteKit 2). It concerns server-side cookie
parsing; the GUI is a static, server-less Tauri page, so it is not reachable. The fix needs SvelteKit 3 (major).

## Accuracy reporting

Format version 2 makes the limits above part of the result. Extraction warnings
produce incomplete status. Rust graph and slice exports preserve status and reasons.
Source conversion reports approximate grouping. The GUI displays the original trace
status even when hierarchy groups change. Dynamic partial attribution remains bounded
at 16 providers and reports incomplete. Clock enables, soft resets, multiple domains,
falling edges and unsupported memory writes remain outside the exact subset.
The signed initial timestamp regression verifies separate groups at -1 and 0;
the obsolete unsigned timestamp TODO in conversion.rs was removed.

The mixed-width reference design reaches a Spinal Verilog backend refusal before
PDG extraction. Its extraction test also changes a completed reference netlist to
exercise the mixed-width warning directly. This is extraction evidence, not a
mixed-width simulation result. The unsupported switch-key test likewise exposes a
raw expression after naming. Normal named keys remain supported.
