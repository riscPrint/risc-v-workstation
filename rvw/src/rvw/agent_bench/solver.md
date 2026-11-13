# Scripted evidence workflow

Run `rvw agent-bench evidence-solve --plan PLAN.json --out NEW_DIRECTORY`.
The client starts `rvw mcp` over stdio. It calls only MCP tools. It does not
call a registry or run a tool's Python API directly.

The plan contains five `steps`. Each step has `tool` and `arguments`.
Use this order:

| Step | Tool | Project inputs |
|---|---|---|
| Regression | `regress_run` | project, suite, config, output directory, one job, RVFI trace |
| First mismatch | `cosim_check` | failing trace, ELF, platform, strict comparison |
| Failure bundle | `bundle_make` | failed run directory and bundle output directory |
| Source drivers | `query_drivers` | database and the signal that represents the mismatching state |
| Dynamic explanation | `wave_why` | database, wave, signal and mismatch time |

Use the documented schemas from `rvw mcp --describe TOOL`. The plan must use
actual paths and a project-owned signal binding. The client does not infer a
microarchitectural signal from an architectural register. This missing join is
a tool limit. The client records tool errors, missing observations and elapsed
time. It waits on native jobs through `job_status`. Status calls count toward
the call budget. The default limits are 32 calls and 110 seconds.

The plan can have evaluator-only `truth: {"file": "src/Core.scala", "line": 12}`.
The client never sends this object to MCP. It gathers `loc` fields from driver
and wave outputs. It removes repeated locations and retains tool traversal
order. `true_line_rank` is the one-based position of the exact source suffix
and line. A missing line has null rank. This rank measures tool output order.
It is not a causal confidence score. A correct line in the output does not
prove the signal binding, database identity or explanation is correct.

`solver.json` retains the complete transcript and budgets. Keep this output
outside the repository. `observed` means all five tool requests returned.
`inconclusive` means a tool failed or a budget expired. Neither result is a
repair verdict. The solver does not edit sources or claim a fixed core.
Native localisation measurements still require a qualified failing run, a
matching database and a waveform for each task.

A driver or wave step can add `mismatch_signals`. This maps fields such as
`rd_wdata` or `pc_next` to project-owned observable signal names. The client
selects a field from the live strict cosim result. A wave step can also add:

```json
"wave_time": {"order_signal": "retire_order", "valid_signal": "retire_valid"}
```

The client finds this retirement in the actual wave with MCP `wave_find`.
This avoids a guessed reset offset. Missing retirement evidence is an error.
With no architectural mismatch, it uses the actual `wave_info` end time and
labels the explanation as the run end. The extra request counts against the
same budget. It does not turn a matching prefix into a failing instruction.
