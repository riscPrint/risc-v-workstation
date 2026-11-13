# SpinalBlocks feature

Open block diagrams and state machine diagrams beside the Scala source of an elaborated SpinalHDL design. The feature uses the SpinalBlocks engine (`SpinalBlocks/engine` in this repository) in a read-only webview, with a native instance tree in Explorer.

It is part of the RISC-V Workstation extension; install that (see [../../README.md](../../README.md)). Commands and settings keep the `spinalblocks.` prefix.

Build the design database with your core project's `rvw query build --config NAME`.
Export its diagram with `rvw query export blocks blocks.json.gz`. Open that file
in the extension. Rebuild the database and export again after a source change.
The extension watches the exported file and refreshes both diagram panels.
See [SpinalBlocks](../../../SpinalBlocks/README.md).

## Work from Scala

- Run **SpinalBlocks: Open Block Diagram**, click the Scala editor-title button, or click **Block Diagram** above a Component class found in a generated design. The diagram opens at that module's first instance. For older exports whose class location points at a shared base class, it falls back to recorded elements in the source file.
- Right-click a Scala line and choose **SpinalBlocks: Show in Block Diagram**, or follow the link in its hover. The diagram opens if needed, navigates to the module, then selects and centres the matching element. Lookups use recorded declarations and the nearest declaration up to three lines above the cursor.
- Run **SpinalBlocks: Open State Machines Diagram**, or click **State Machines Diagram** above a recorded machine declaration. It opens a separate panel with a machine picker. **SpinalBlocks: Show in State Machines Diagram** is available in Scala context menus and hovers on recorded states and transitions.
- When several designs match, choose one in the QuickPick. That design is remembered per source file and diagram kind in workspace state. Multiple modules or machines in that design still get a picker. Run **SpinalBlocks: Forget Remembered Design Choices** to choose again.

The extension activates for `.scala` files without requiring Metals. Code Lenses and hovers come from generated source locations, so regenerate the design when declarations move. The commands are also available from the Command Palette. A Scala file need not be inside the workspace if its absolute path occurs in a discovered design.

## Diagrams

Double-click a block, state or transition to open its Scala source beside the diagram. An instance's open glyph or **Open Module** context action descends into it. The instance context menu also has **Open Source** and **Show in Explorer tree**. Areas have **Collapse Area** / **Expand Area** actions. The tree and breadcrumbs navigate the hierarchy; Backspace goes up in the block diagram.

Use **SpinalBlocks: Find in Diagram** or Ctrl+F / Cmd+F in a block diagram to search its blocks, ports, signals and nets. Choose a result to select and reveal it. The toolbar controls area expansion, clocks, control nets and net labels. Block navigation, viewport, area and bundle state and display options persist per design file.

The state machine toolbar selects a machine, shows or hides transition conditions and source comments, and fits the diagram. Both panels have **Save SVG** and **Save PNG** buttons with native save dialogs. PNG export uses twice the diagram's pixel dimensions. Colours follow VS Code light, dark and high-contrast themes.

Design files can also be opened from Explorer with **Open With... > SpinalBlocks Diagram**, or **SpinalBlocks: Open Block Diagram** on a JSON file. Generic JSON is an optional custom editor association; the extension does not take it over by default.

## Settings

| Setting | Default | Purpose |
| --- | --- | --- |
| `spinalblocks.designFiles` | `["**/blocks/*.json.gz", "**/*.spinalblocks.json"]` | Workspace globs searched for designs that reference the current Scala file. Add globs for designs in other locations within the workspace. |
| `spinalblocks.followCursor` | `false` | Debounce Scala cursor movement and select matching elements in visible panels. Block cursor following stays in the shown module and ignores module-definition lines to preserve zoom. Does not open new panels or move editor focus. |

## Verify

```sh
npm run typecheck
npm run build
npm test
npm run test:integration:spinalblocks
```

The integration runner uses `@vscode/test-electron` with an isolated workspace and settings under `.vscode-test/`. It opens the BOOM gzip design and its recorded Scala source, exercises editor commands and selection, source navigation, search, reloads and persistence. It tests FSMs using generated data when available, otherwise a synthetic design with recorded states and transitions. Light and dark screenshots are written to `.vscode-test/screenshots/spinalblocks/`. CDP is enabled on a random local port for the test run.

Run these from `vscode/`. By default the test uses `spinal-boom/blocks/boom-small.json.gz` from a spinal-boom checkout next to this repository. Set `SPINALBLOCKS_TEST_DESIGN` to another BOOM design with a `tile/core` hierarchy, or `VSCODE_EXECUTABLE` to test an existing VS Code executable. Recorded absolute paths must exist on this machine.

## Host protocol

Messages are validated at both boundaries in `src/protocol.ts`. `load` sends binary design bytes and optional saved block state. `navigate`, `search` and `pick` drive the block view. `showFsm` chooses a module and machine; `showLocation` selects a recorded source location in either view. `exportImage` requests SVG or PNG output. The webview sends source requests, tree navigation, save data, correlated search results and export payloads back to the host. Selection acknowledgements and the exported test API are enabled only in extension test mode. Tests capture export payloads before the save dialog, then check SVG content and PNG signatures.

The webview fetches the packaged ELK worker through `asWebviewUri` and creates a blob URL for it. Its CSP permits packaged resources, nonced scripts, the renderer's CSSOM bootstrap and blob images for PNG export.

## Limitations

Desktop VS Code only. Source links require accessible absolute paths; paths from another machine are not remapped. Discovery follows workspace globs and excludes `node_modules`, `.git` and `.vscode-test`. Malformed or unfinished design files are skipped during discovery and retried after a file change. Search covers the current module and returns at most 200 results; details show at most 200 entries. State machine data is optional in older design files. Uninstantiated modules cannot be opened as block diagrams. Closing an FSM panel drops its panel state; block view state persists per design. Hidden panels retain their webviews. Deleting a design has no special UI; creating it again reloads the panel.
