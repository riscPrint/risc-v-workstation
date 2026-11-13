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
