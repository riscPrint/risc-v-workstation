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

## Compare with a full RTL run

`rvw sample STUDY.json --validate --out /path/to/validation --intervals 10000 50000 --clusters 1 4 8 --warmup 1000`
runs the same prefix from reset and at sampled points. The prefix ends at the
instruction budget or the successful `tohost` write. MCP: `sample_validate`.
`validation.json` reports full IPC, sampled IPC and signed relative IPC error
for every setting. A failed setting remains visible. Maximum observed error
is an empirical result for this prefix. It is not a confidence interval.
Use multiple workload classes before applying the method to a long program.

Two deterministic programs are in `examples/vexriscv/rvw/sample-workloads`:
heapsort and run-length compression with a round-trip check. Build short cases:

```sh
nice -n 15 examples/vexriscv/rvw/sample-workloads/build.sh "$RUN_ROOT/kernels"
```

`SIZE=1024 ROUNDS=10` are the defaults. Increase `ROUNDS` for a long workload.
Each program reports success through `tohost`. The linker keeps code and data
below the stack and bootstrap reserve. Set each study's instruction budget
above completion for full-program calibration, rather than prefix calibration.
Compilation does not establish RTL or sampled timing accuracy.

| Functional smoke build | Spike instructions to successful `tohost` | RTL timing |
|---|---:|---|
| Heapsort, `SIZE=128 ROUNDS=1` | 20,038 | NOT RUN |
| Compression, `SIZE=128 ROUNDS=1` | 3,958 | NOT RUN |

Regenerate these small functional profiles with studies whose ELF files come
from this build and whose instruction budgets are 1,000,000:

```sh
SIZE=128 ROUNDS=1 nice -n 15 examples/vexriscv/rvw/sample-workloads/build.sh "$RUN_ROOT/kernel-smoke"
mkdir -p "$RUN_ROOT/profile-sort" "$RUN_ROOT/profile-compression"
nice -n 15 python -c 'import sys; from pathlib import Path; from rvw.sample.validation import load; from rvw.sample.flow import profile; profile(load(sys.argv[1]), Path(sys.argv[2]))' sort.json "$RUN_ROOT/profile-sort"
nice -n 15 python -c 'import sys; from pathlib import Path; from rvw.sample.validation import load; from rvw.sample.flow import profile; profile(load(sys.argv[1]), Path(sys.argv[2]))' compression.json "$RUN_ROOT/profile-compression"
```

Each `profile.csim` ends with `END N`. Run in the installed `rvw` Python
environment. The counts above qualify only these small functional runs.
They do not fill the full-RTL sampling error table.
