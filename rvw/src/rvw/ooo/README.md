# Generic OoO timing experiment

`rvw ooo CONFIG TRACE --max-cycles 1000000 --json` predicts timing from a
complete single-hart C2 trace. This engine does not use gem5. Spike traces
must first be exported as C2. RTL cycle timestamps are validated but do not
drive the prediction. The full trace is the measured region.

Create CONFIG in your core project. This generic example is not a core preset:

```json
{
  "fetch_width": 2, "fetch_entries": 4, "rename_width": 2,
  "rob_entries": 8, "issue_width": 2, "issue_entries": 4,
  "load_entries": 2, "store_entries": 2, "commit_width": 2,
  "latencies": {"alu": 1, "multiply": 3, "divide": 12, "load": 4, "store": 2}
}
```

All fields are required. Unknown fields are errors. Sizes, widths and latencies
must be positive integers. These latency classes support decoded integer
instructions only. Compressed integer instructions use the shared decoder.
Branches, jumps, fences, atomics, privileged, FP and vector operations are
unsupported. The engine rejects their traces. A missing or unsuccessful end
marker is an error. An exhausted model cycle budget is an error.

## Decisions

Within a cycle the engine commits, issues, renames, then fetches. Latency one
completes on the next cycle. Instructions can issue out of order. Rename
binds source operands to older producers. Integer x0 has no dependency.
Issue uses one shared queue and oldest-ready selection. Execution uses a
shared issue width with unlimited pipelined units. ROB and LSQ slots remain
allocated until commit. Memory instructions wait for older memory completion.
There is no address disambiguation, forwarding or store buffer model.

`cycles` includes fill and drain from cycle zero through the last commit.
The report gives IPC, issued instructions, queue peaks and event counts.
`rob_full`, `issue_full`, `load_full` and `store_full` count rename stall
cycles. At most one is counted per cycle, in that precedence order.
`dependency_blocked` counts issue phases with an inspected unready entry.
It can overlap queue stalls. A counter absent from `events` is zero.
This phase-sampled counter is not a hardware stall-cause measurement.

## Limits

`rvw.ooo-run/1` is an experimental C9 extension. Report creation exits zero.
Bad input or budget exhaustion exits two with a JSON error. Success does not
establish core correctness, configuration agreement or model accuracy.
`accuracy_status` is always `inconclusive`. `configuration_status` is always
`unchecked`. No native RTL speedup has been measured. The 50x and accuracy
budgets in the design note are targets.

The engine uses fixed latencies. It does not model branch prediction, caches,
TLBs, wrong-path work, replay, functional unit ports or physical registers.
It retains the full trace in memory. Core configuration export, calibration,
held-out RTL correlation, prediction ledgers and MCP jobs are later phases.
Do not use the existing gem5 report readers to certify this model.

Run targeted tests from the workstation root:

```sh
PYTHONPATH=rvw/src python -m pytest rvw/tests/test_ooo.py -q
```

See [the design](../../../../docs/design/own-core-model.md) for phases,
contracts, prior art and acceptance targets. Keep tuned core values in the
core project. Store measured evidence outside the repository.
