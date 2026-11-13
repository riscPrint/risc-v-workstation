# Workload designer report

Run `rvw arch ooo-designer PLAN --out NEW_DIRECTORY --json`.
The matching MCP tool is `arch_ooo_designer`.

The plan uses paths relative to its directory:

```json
{
  "schema": "rvw.ooo-designer-plan/1",
  "config": "model.json",
  "workloads": [{"id": "kernel", "trace": "trace.jsonl", "elf": "program.elf"}],
  "sensitivity_parameters": ["rob_entries", "issue_width", "latencies.load"],
  "search_parameters": {"rob_entries": [32, 64], "issue_width": [2, 4]},
  "budget": 4,
  "max_cycles": 1000000
}
```

The report directory contains `report.json` and `report.md`. It also contains
the full sensitivity report, DSE report and SQLite points. Each workload gets
IPC and slot attribution by ELF function. Omit `elf` to use the unmapped region.
The report uses the existing Python observer for function attribution.

The bottleneck list ranks absolute finite-difference elasticity. It measures
local parameter effects. The next three changes rank improving DSE points by
aggregate model cycles. Each point can change more than one parameter. The
report gives the exact changes. If the grid finds fewer than three improving
points, the report says so. It does not invent more recommendations.

All reports use the same committed C2 paths. The top-down partition is a model
slot accounting method. It is not a hardware top-down measurement. The report
does not infer physical feasibility, area, power or RTL accuracy.
