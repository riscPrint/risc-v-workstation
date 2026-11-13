
## Generated-suite selection

`rvw.regress-features/1` contains a `capabilities` list of explicit strings.
`rvw regress plan --features FILE` and MCP `regress_plan` compare that list
with a requirement catalog. Each catalog row has a unique `name`, a `source`
and a `requires` list. A row applies only when every requirement is declared.
`rvw.regress-plan/1` reports each row, missing capabilities and the reason.
The result is a selection aid. It contains no DUT pass or coverage evidence.
