# Sampled RTL simulation

`rvw sample STUDY.json --out /path/to/runs --interval 10000 --max-k 8 --warmup 1000`
profiles an instruction budget on Spike. It uses the existing BBV clustering.
It captures architectural checkpoints and calls a project RTL bootstrap adapter.
`sample_run` provides the same flow through MCP. Runs are serial.

A study uses `schema: rvw.sample-study/1`, with `elf`, `platform`, `shim`,
`mapping` paths relative to the study, `instructions` as the profiling budget,
`adapter` as an argv array and optional `timeout` in seconds (default 120).
The adapter gets one additional argument: the absolute `request.json` path.
It must write a complete C2 trace to `out/rvfi.jsonl`, starting at the checkpoint,
with exactly `warmup + instructions` retirements. See `docs/contracts/sample.md`.
Use absolute adapter paths. Launch the parent with `nice -n 15`.

Repeat the same command to resume. Completed points are checked again.
Changed inputs require a new output directory. Failed points are excluded and
reported. Missing cluster weight makes the whole estimate inconclusive.
The report includes a conditional estimate for the surviving weight only.
Weighted IPC is the reciprocal of weighted CPI, not the mean of point IPCs.
Timing uses N-1 retirement gaps for each N-instruction measured interval.

## Decisions and limits

The first profile is single-hart RV32IM, M-mode, physical RAM, disabled interrupts.
The bootstrap rejects FP, devices, translation and unsupported CSR state.
The instruction budget must end before a trap or halt. Capture reads declared RAM.
Each point replays Spike to its checkpoint. This costs functional-model time.
Warm-up uses detailed RTL execution. No cache or predictor injection is claimed.
Reset/bootstrap cycles are excluded. At least two measured retirements are needed.
A final partial interval of one instruction is excluded.

| Evidence | Result |
|---|---|
| Full RTL versus sampled accuracy | NOT RUN |
| Cached-core warm-up bias | NOT RUN |
| Long-workload IPC | NOT RUN |

These results require native runs. Unit tests establish orchestration and arithmetic
only. No statistical confidence or timing fidelity is inferred from them.
