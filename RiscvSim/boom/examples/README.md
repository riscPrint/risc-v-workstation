# Example outputs

Real outputs of `RiscvSim/boom/run.sh` on BOOM small (seed 1), for testing tools that read them.
Paths use neutral `/work` examples. These files are reader fixtures.
They are not complete C8 evidence.

| Directory | What |
|---|---|
| `pass-rv64ui-p-add/` | pass, with `--rvfi-trace` |
| `traps-rv64mi-p-ma_addr/` | pass, with misaligned-access trap events (cause, tval) in the trace |
| `fail-code3/` | `fail`, `fail_code` 3 (tests/programs/fail.S) |
| `timeout/` | `timeout` at `--max-cycles 20000` (tests/programs/hang.S) |
| `bench-metrics/` | pass with `metrics.roi_cycles/roi_instret` from `bench_stats`, `--mem-latency 20` |
| `run-many-summary.json` | the `run-many --summary` file for these five runs |

`rvfi.jsonl` files are truncated: the header and first 150 records, then the last 4 lines of the
full trace (so `order` jumps once).
