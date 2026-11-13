# Design queries contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Explained design diff (`rvw.diff-explain/1`)

`rvw query explain OLD NEW [--coverage COV] [--effect CMP]` and MCP `query_explain` return
`schema`, `old`, `new`, `summary` (as `rvw query diff`), `items`, `count`, `selection` and
`effect`. Each item has `kind`, `change` (`added`, `removed`, `changed`), `path`, `detail`,
`locations` (`file`, `line`), `tests` (`status` one of `covered`, `unhit`, `unmapped`,
`uncovered`, `unknown`; `tests`, `mapped_points`, `cause` when present) and `effect`
(`status: unknown`). `selection` has `mode` (`covering` or `all`), `tests`, `covering_tests`,
`uncertain_items` and `basis`. `effect.status` is `not_measured` or `measured` (whole change).
A covering selection is a coverage claim on the base revision, not a gate verdict.

## C6 HDL front ends: GHDL

`build-hdl --frontend ghdl` writes `meta.frontend=yosys-ghdl`, `meta.hdl_options`
(JSON: `std`, `library`, `parameters` as top generics), `meta.ghdl_version` and
`meta.ghdl_plugin_sha256`. Source files are captured one by one before analysis.
Locations come from the GHDL XML AST: component lines are entity declarations,
signal lines are port or signal declarations, and an assignment line is the
first VHDL assignment statement to that signal. Component `module` is the
entity name. Generate instance paths keep GHDL's `label:k` names (k counts
iterations from 1). In every `yosys-*` frontend a clock or reset root follows
ports, aliases, buffers and inverters only; each inverter flips the recorded
edge or polarity. A register net's `reset_value` is the concatenation of its own
bits' reset values, NULL when a bit has none.

## C6 HDL front ends: Chisel (firtool)

`build-hdl --frontend chisel` writes `meta.frontend=yosys-firtool`,
`meta.firtool_version`, `meta.firtool_options` (JSON list) and `meta.hdl_options`
(`source_roots`). `input_files` holds the FIRRTL file and each Scala file that a
firtool location names and a source root holds. Database locations point at
those Scala files only; none points at emitted Verilog. Artifacts: `rtl/<file>`
(emitted Verilog, media type `text/x-systemverilog`), `hgldd/<module>.dd`
(firtool HGLDD) and `hdl/source-map.json` (`{rtl file: {verilog line: ["file:line", ...]}}`).
`spinal_path` holds the Chisel name from HGLDD when it differs from the Verilog name.

## C6 HDL front ends: block diagrams

Every `build-hdl` database holds artifact `blocks.json` (gzip, SpinalBlocks format version 1),
derived from the database tables only. Modules are keyed by `components.module`; the first
instance in path order defines the diagram and `instanceCount` counts all instances. Nodes are
named registers (`sig:<name>`) and memories (`mem:<name>`); there are no areas or FSMs. A net's
`control` is true when every hop into its sinks is a `sel` or `cond` edge; `clock` marks a
driver with a `clock_role`.

## Agent semantic navigation

`query definition`, `references`, `parameters`, `explain-module`, `type`,
`port-status` and `hierarchy-diff` expose captured structural data. Each has a
matching `query_*` MCP tool. Module summaries use `rvw.module-explanation/1`.
Hierarchy comparisons use `rvw.hierarchy-diff/1` and do not assert equivalence.
HDL builders store `hdl/port-connections.json`: instance path to native port
bindings with direction, width, status and LSB-first constant bits. Integer net
IDs become null. Only all-known binary constants earn `tied`. Missing bindings
in older databases are unavailable. Unknown bits do not prove an open port.
Expression types cover captured signals and normalized constant selects only.

## Language server

`rvw lsp --db PATH` serves JSON-RPC 2.0 with LSP Content-Length framing on stdio.
It supports initialize, shutdown, exit, full document synchronization, definition,
hover, references and document symbols. Positions use UTF-16 code units. Source
locations use captured declaration and assignment lines. Missing locations give
empty results. Ambiguous names return a query error. `lsp_request` gives agents
the same navigation without starting a server. Optional `--lint-settings PATH`
runs the shared lint report on open and save. Active located findings become
publishDiagnostics notifications. This is captured navigation, not live parsing.
