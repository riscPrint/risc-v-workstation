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
