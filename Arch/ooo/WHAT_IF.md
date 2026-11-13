# One parameter comparison

```sh
rvw arch ooo-what-if project.json trace.jsonl \
  --set ooo.latencies.load=2 --out new-comparison --json
```

For a plain own-model configuration, use `--set latencies.load=2`.
The matching MCP tool is `arch_ooo_what_if`. It takes `config`, `trace`,
`parameter`, numeric `value`, `out` and optional `max_cycles`.

The command validates the original and changed descriptions. It writes both
configurations and `report.json` in a new directory. It leaves the source file
unchanged. The report includes both complete runs and deltas for cycles, IPC
and event counts. A positive cycle delta means slower. A positive IPC delta
means faster. `speedup` is baseline cycles divided by candidate cycles.

The parameter must be an existing numeric field. Its numeric type must stay
the same. Shared description consistency checks still apply. Invalid values
fail before the output directory is created. A later run failure can leave
an incomplete directory. Use a new directory for each run.

Both runs use the same trace bytes. The command does not predict a changed
program path, physical PPA or RTL timing. Accuracy remains inconclusive.
