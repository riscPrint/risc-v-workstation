# One parameter comparison

```sh
rvw arch ooo-what-if project.json trace.jsonl \
  --set ooo.latencies.load=2 --out new-comparison --json
```

For a plain own-model configuration, use `--set latencies.load=2`.
The matching MCP tool is `arch_ooo_what_if`. It takes `config`, `trace`,
`parameter`, scalar `value`, `out` and optional `max_cycles`.

The command validates the original and changed descriptions. It writes both
configurations, `report.json` and `report.md` in a new directory. It leaves the source file
unchanged. The report includes both complete runs and deltas for cycles, IPC
and event counts. A positive cycle delta means slower. A positive IPC delta
means faster. `speedup` is baseline cycles divided by candidate cycles.

The parameter must be an existing numeric, Boolean or string field. Its type must stay
the same. Shared description consistency checks still apply. Invalid values
fail before the output directory is created. A later run failure can leave
an incomplete directory. Use a new directory for each run.

Both runs use the same trace bytes. The command does not predict a changed
program path, physical PPA or RTL timing. Accuracy remains inconclusive.

Use `--set branch_speculation=true` for a Boolean. Use
`--set 'issue_order="in_order"'` for a string in a plain own-model configuration.
The JSON report retains the source configuration hash and the old value.

## Saved RTL trace example

On the saved VexRiscv branch trace, changing `ooo.branch_penalty` from 3
to 1 changes model cycles from 2,573 to 2,371. The IPC increase is 8.52%.
The 101 branch misses stay unchanged. This is a same-path model comparison.
It is not a measured RTL improvement. See [both runs and hashes](what-if-sample.json).
