# SpinalBlocks: block diagrams for SpinalHDL

SpinalBlocks draws a SpinalHDL design the way Sigasi's Block Diagram view draws VHDL/Verilog: one
diagram per module, with the module's ports on the edges, child instances as boxes with their ports,
the module's own logic as blocks, and the wires between them. Double-click an instance to go inside
it; click anything to jump to the Scala line that created it.

It works on the elaborated Spinal netlist, not on the generated Verilog, so the diagram keeps the
structure you wrote:

* **Areas are blocks.** Each named `Area` (including `StateMachine` and spinal.lib `Composite`s) is
  a block; nested areas are nested, collapsible containers. Instances created inside an area sit in it.
* **Signals outside areas** become small blocks: registers, combinational signals, or a whole
  internal bundle (`val req = Stream(...)`) as one block. Anonymous registers are grouped by the
  line that created them (`rob_l338`), loop copies of a signal by name (`rob_*_valid`).
* **Wires** are named after the signal they carry. Compiler temporaries (`_zz_*`,
  `when_Foo_l12`), plain `a := b` wires and constants are folded into the wires instead of being
  drawn; names of folded wires are kept as "via" in the tooltip. `when`/`switch` conditions and mux
  selects are dashed (control), clocks and resets are hidden by default.

Parts:

* `spinalblocks/` – Scala extractor library, called by SpinalDB. It also supports standalone designs.
* `engine/` – the viewer engine, a TypeScript library with no UI around it (see below). Hosts embed it.
* `hosts/web/` – a browser host: hierarchy tree, breadcrumbs, search, details panel.
* VS Code: the `spinalblocks` feature of the RISC-V Workstation extension, in [`../vscode/features/spinalblocks/`](../vscode/features/spinalblocks/README.md).
* `docs/FORMAT.md` – the data format between the two.

```
 Spinal design → SpinalDB → rvw query export blocks → design.json(.gz) → engine → host
```

## Read the design database

Build the database with your core project's `rvw query build` command. Keep
block export enabled (the default). Export the stored diagram with no new
elaboration:

```sh
rvw query build --config NAME
rvw query export blocks blocks.json.gz
# Or use an explicit database from the workstation checkout:
SpinalBlocks/export.sh design.db blocks.json.gz
```

The viewer reads this JSON file. The artifact includes hierarchy, ports, Areas,
logic, nets, FSMs and source locations from the database's elaboration.
`export.sh` uses the workstation's `rvw/.venv/bin/rvw`. It needs no JDK, sbt,
core checkout or RTL build. A database built with `--no-blocks` has no diagram;
export then fails. Rebuild the database with blocks enabled.

The core project owns its database entry point and source roots. See
[the project guide](../docs/BRING_YOUR_OWN_CORE.md). The separate
[`SpinalDB/boom/`](../SpinalDB/boom/) build is a BOOM example. For that example:

```sh
SpinalDB/build-db.sh boom small design.db
rvw query export blocks blocks.json.gz --db design.db
```

Use `--no-pdg` when a database must use the same signal names as a plain RTL
build. The default PDG naming phase adds probe wires. It can change diagram
net names and source lines for those wires. It does not turn static nets into
waveform causes.

## Extractor library

SpinalDB calls `SpinalBlocks.extract(report.toplevel, sourceRoots)` on its own
report. It compiles the extractor sources without loading the legacy BOOM build.
That legacy build and its BOOM entry remain while full parity fails.

Implicit clock and reset signals can retain the elaboration caller as their
source location. The standalone caller and `SpinalDB.elaborate` are different
Scala statements. These locations describe generated infrastructure. They do
not describe a statement in the core. Anonymous logic groups can also use that
file and line in their names and IDs. `BlockArtifactSpec` tests this difference.
Keep these fields in parity comparisons. Do not replace them with a core source
line or discard them to claim a match. The old entry must stay until the source
attribution rule is shared by both paths and full parity passes.
A project can also
use `SpinalBlocks.generate` for a standalone diagram. It needs JDK 21, sbt,
SpinalHDL 1.15.0 and the sibling `SpinalWaves/` directory:

```scala
import spinalblocks.SpinalBlocks
SpinalBlocks.generate(SpinalConfig(targetDirectory = "rtl"),
  new java.io.File("blocks/top.json.gz"))(new MyTop)
```

`generate` uses two elaborations to find source locations. Generators must be
deterministic. `locations = false` skips the location pass. Set `sourceRoots`
when sources are outside `src/main/scala` and `src/test/scala`.

```sh
cd spinalblocks
sbt "spinalblocks/runMain spinalblocks.examples.Demo demo.json"
```

## View it in the browser

```sh
cd hosts/web && npm install
node serve.mjs /path/to/blocks.json.gz
```

`serve.mjs` builds the page if needed, serves it with the design, and opens the browser. Reloading the
page re-reads the file, so regenerate and reload. `npm run build` gives a static site in `dist/`
that opens any file by drag and drop or `?file=<url>`.

It follows Sigasi's conventions:

* Double-click a block, port or wire to open its Scala source. Go inside an instance with its open
  glyph (↘), the right-click menu ("Open Module"), or the tree on the left. The breadcrumb, Backspace
  and the browser's back button go up; the URL (`#/tile/core/rob`) links to an instance.
* Right-click for Open Module, Open Source, Collapse/Expand Area, Show State Machine.
* Click anything to highlight it with its wires, and for details (signals, ports, the nets behind a
  bus) in the side panel.
* Input ports on the left, outputs on the right, as triangles; inout as squares. Instances are
  solid blocks with their ports in source order, logic is rounded (`:=` blocks for single
  assignments), expanded areas are dashed containers. Buses are thick.
* Block size grows with the logic inside (log scale, capped). Big modules start with areas
  collapsed, loose logic grouped as "glue logic", ports folded by bundle (`+` opens one) and parallel
  wires merged into buses.
* ⌘F searches blocks, ports, signals inside blocks and nets of the current module.
* Toolbar: net labels, control nets (`when`/`switch` conditions, mux selects), clocks, wire
  bundling, SVG and PNG export.

### State machines

"State machines" in the toolbar shows the state machine diagrams of the current module: every
spinal.lib `StateMachine`, every `SpinalEnum` register, and every small `UInt`/`Bits` register used
like Chisel's `Enum(n)` (only ever assigned constants, tested in `switch`/`when`). BOOM has ten:
`rob_state`, the LSU's `hella_state`, the MSHRs, the TLBs, the PTW, ...

* States are named after the enum element or the named constant (`val s_normal = U(1, 2 bits)`).
* The reset state has a dashed arrow from a dot (a StateMachine's entry state; its internal BOOT
  state is hidden). Dead states (no way out) have a red outline, unused states are red, a target that
  is not a constant goes to `?`, assignments outside any per-state branch come from "any".
* Transitions show their condition (the other enclosing `when`/`switch` conditions, compiler
  temporaries expanded) and, optionally, the `//` comment on the `goto` line.
* Double-click a state or transition to open its source.

### Live update

Rebuild the database, export the diagram again, then reload the page. The VS Code
extension reloads the exported file when it changes.

## The engine

`engine/` is plain TypeScript (no framework). It has two layers:

* **Core** (`@spinalblocks/engine/core`, no DOM; runs in browsers, workers, Node and VS Code's
  extension host): `loadDesign` (plain/gzipped bytes or text), the `ViewState` (current instance
  path, collapsed areas, open bundles, options; plain JSON, so hosts can persist it), `buildViewGraph`
  (port folding, area collapsing, merging parallel nets into one wire), `layoutGraph` (ELK; the host
  passes the ELK instance, so layout can run in a worker, on the main thread or in Node) producing a
  `Scene`: absolute coordinates for every port, block and wire.
* **Engine + renderer** (`@spinalblocks/engine`): `createEngine(container, host, { layout })`
  draws scenes as SVG into the container and handles pan, zoom, hover, selection and navigation.
  The renderer sits behind the `Renderer` interface (`src/render/types.ts`), so another one (canvas,
  WebGL) can be swapped in. Colours are CSS variables (`--sb-*`).

The engine never opens files, windows or editors. A host implements:

```ts
interface Host {
  openSource(loc: Loc): void;                       // required: jump to Scala source
  stateChanged?(state: ViewState, viewport: Viewport): void;   // persist the view
  navigated?(path: string[], modules: string[]): void;         // breadcrumbs, tree
  selectionChanged?(details: Details | null): void;            // details panel
  hoverChanged?(details: Details | null): void;
  contextMenu?(details: Details | null, x: number, y: number): void;
  busy?(busy: boolean): void;
  error?(error: Error): void;
}
```

and calls the engine: `setDesign(bytesOrJson, state?, viewport?)`, `navigate(path)`, `descend(id)`,
`up()`, `toggleArea(id)`, `setAllAreas(collapsed)`, `toggleBundle(owner, bundle)`,
`setOptions({showClocks, showControl, maxPortsPerSide, maxBlocks, busThreshold})`, `setRenderOptions(...)`,
`hierarchy()`, `search(query)`, `describe(target)`, `reveal(target)`, `select(target)`, `fit()`,
`exportSvg()`.

The VS Code host is the `spinalblocks` feature of the RISC-V Workstation extension (`../vscode/`). It opens `.json`/`.json.gz` designs as a custom editor
(webview running the engine, native instance tree in the Explorer, QuickPick search, source links
open beside the diagram, follows the colour theme, reloads when sbt rewrites the file). Install with
`cd ../vscode && npm install && npm run build && npm run package && code --install-extension risc-v-workstation-*.vsix`;
see [its README](../vscode/features/spinalblocks/README.md).

```sh
cd engine && npm install
npm run build       # dist/index.js, core.js, elk.js, elk-main.js, elk-worker.js
npm test            # core tests on test/fixtures/demo.json
npm run typecheck
```

## How the extraction works

`Extractor.scala` runs on the design after Verilog generation, so names and the module list match
the RTL (one diagram per Verilog module; deduplicated components share a diagram). For each module:

1. Its signals are classified. IO and child IO are endpoints. Registers and named signals become
   members of a block (their innermost named area, or a loose group as described above).
   Everything else is *transparent*.
2. For every block member, output port and child input, the assignments that drive it are walked:
   data expressions, the `when`/`switch` conditions they sit under, and mux selects (control). Reads
   of transparent signals are followed through to the non-transparent signals behind them.
3. Reads become nets from the driver's block/port to the reader's block/port. Memory reads are
   drawn from the memory; the address and enable go into it.

Areas are found through Spinal's naming owners (`refOwner`), following composite names
(`stream_fire`) to the object they are named after. Locations come from Spinal's `ScalaLocated`
traces: a component's class line for the module, the creating line for instances and areas.

## Tests

```sh
cd spinalblocks && sbt spinalblocks/test     # extractor, on examples/Demo.scala
cd engine && npm test                         # engine
```

`examples/Demo.scala` (a FIFO, two GCD units, an FSM area and a memory) is the shared fixture; its
JSON is checked in as `engine/test/fixtures/demo.json`.

## Decisions and limits

- Read stored block artifacts through `rvw query`. New core entry points belong
  in project data or separate example builds. The extractor library has no BOOM
  dependency. Build BOOM databases with `SpinalDB/build-db.sh boom small OUT`.
  Export diagrams with `rvw query export blocks blocks.json.gz --db OUT`.
  The core project owns the top-level construction; the viewer reads the database.
- Diagram nets and database edges show possible structural influence. They do
  not select the active driver at a waveform time. Use SpinalTrace for that.
- A BlackBox diagram shows ports only. The database uses coarse dependencies:
  each output or inout can depend on each other input or inout. No internal
  behavior is inferred from this diagram.
- Inout ports are shown. Analog attachment nets are omitted from the diagram.
  Use database queries for conservative inout paths. The diagram does not
  resolve analog drive strength or tri-state values. SpinalHDL's `PhaseAnalog` can reject sliced wide inout
  attachments before either extractor runs. See [SpinalDB limits](../SpinalDB/README.md#limitations).
- Verilog and SystemVerilog exports use the same diagram format. Other compiler
  backends need separate checks. The workstation's Scala and SpinalHDL versions
  must match the core build. NaxRiscv's upstream build uses Scala 2.12 and local
  SpinalHDL submodules; it cannot use a Scala 2.13 library `ProjectRef` unchanged.

## Limit ownership

Database migration and legacy entry removal: [#44](https://github.com/riscPrint/risc-v-workstation/issues/44). More-design checks: [#70](https://github.com/riscPrint/risc-v-workstation/issues/70). Cross-navigation: [#24](https://github.com/riscPrint/risc-v-workstation/issues/24).

Retained limit: Diagrams read the database. Missing source files and extraction approximations do not become verified navigation.

### Compare caller locations

Use `rvw.debug.parity.compare(..., kind='blocks')` for an explicit caller-location
comparison. It ignores only the extraction timestamp by default. A declared
caller mapping can replace a file/line pair and the exact generated identifier
that contains that pair. All port, node, instance and net fields remain checked.
Check both source destinations before treating a changed elaboration caller as
equivalent information. This comparison does not relabel stored source locations.
See the source-root and caller rules in [RiscvSim](../RiscvSim/README.md).
The comparison cases are BOOM `small` and VexRiscv `rv32im`.
Compare legacy diagrams with a database built with `--no-pdg`.
Check every module, port, instance, node, net, FSM and source location.
Audit caller differences on clock/reset ports separately. The caller must perform
the same top-level construction. Keep both actual destinations in the artifacts.
PDG naming is a separate opt-in transformation; do not compare a plain diagram
against an instrumented diagram and drop the changed names.
The Vex example exports independent cases with
`db/Test/runMain rvwvex.DebugParity OUT` from `examples/vexriscv/rvw`.
Hold the `vex` and `sbt` locks for this command. Set `RVW_HOME`, `RVW_ADAPTER`
and `VEXRISCV` to the selected checkouts. OUT must not exist.

## Viewer package notices

The engine build copies the pinned ELK license and source notice into
`engine/dist/third_party/elkjs/`. Keep these files with the worker and bundles.
The extension retains the same files. See [the package check](../vscode/README.md#package-notices)
for local archive inspection. These files do not resolve the project license
choice in #37.
