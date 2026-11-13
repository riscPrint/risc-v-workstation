# RV32 architecture models

These descriptions select the example's RV32IM preset. They are model
approximations for trends. They are not VexRiscv timing models.

`VexTop.scala` selects a single in-order RV32IM hart without caches or an MMU.
`VexAdapter.scala` supplies 16 MiB RAM at `0x80000000`. Both descriptions use
that range and bypass caches. ELF load segments must fit in that range.
The model bus is four bytes wide. The 64-byte line setting is a gem5 transport
setting. It does not add a cache. TLB size one is a gem5 object setting;
benchmarks stay in M-mode with physical addresses.

`minor.json` selects `RiscvMinorCPU` with issue and commit limits of one.
Other Minor pipeline, functional unit and predictor values use gem5 defaults.
`timing.json` selects `RiscvTimingSimpleCPU` with its defaults. Neither CPU
matches all VexRiscv pipeline stages, branch prediction or multiply/divide
latencies. The source of the RTL settings is `../src/main/scala/rvwvex/VexTop.scala`.
No BOOM parameters are used.

The model uses a fixed memory latency of 1 ns at 1 GHz. C1 receives latency 1.
The adapter adds its bus response cycle. gem5 has bus and request timing.
Equal numeric latency does not imply equal effective load or fetch delay.

## Run

Copy this directory with the other example project files into the external
VexRiscv checkout. Set `arch.sources` to the riscv-tests benchmark source
folder. Keep `core.source_repo` set to the actual VexRiscv source checkout.

```sh
rvw arch build --bench dependent-chain,branch-loop
rvw arch calibrate --bench dependent-chain,branch-loop --out rvw/out/arch/minor
```

For TimingSimple, use a separate project file with
`arch.description = "rvw/arch/timing.json"`. Keep the same ELF directory.
Use a new calibration output directory. Both CPU/ISA combinations use ELF32,
ABI ilp32 and stable high/low/high CSR reads. The build adds Zicsr and Zifencei
assembler support. The benchmark code still targets RV32IM.

## Live counters and fitting

The C1 adapter observes RVFI retirement directly. Trapping records do not count. It excludes the first retired
`setStats` entry and includes the second. It emits `roi_retired`, `roi_loads`,
`roi_stores` and `roi_branches`. Loads have opcode 0x03. Stores have opcode
0x23. Branches include conditional branches, JAL and JALR. This mapping applies
to this noncompressed RV32IM configuration. It does not count speculative
requests, misses or stalled cycles. A complete `bench_stats` store and exactly
two markers are required before the adapter publishes these metrics.

`roi_cycles` and `roi_instret` come from the guest's 64-bit CSR deltas. Their
window lies inside `setStats`. It differs from the retired-PC window. Do not
replace one window with the other. In particular, load/store events in the
entry runtime are part of the retired-PC window.

Copy `fit-plan.json` beside the output directories. Update its report paths.
It trains on dependent-chain and scores branch-loop as a disjoint holdout.
The plan maps live RTL counts to gem5's first ROI statistics block. Inspect
raw evidence before extending the event mapping to another configuration.

```sh
rvw arch fit fit-plan.json --json > fit.json
```

This fits saved candidate choices only. It does not search parameter values.
One run does not supply repeatability or a confidence interval. Branch counts
and other event errors are measurements of model gaps. They are not a general
fidelity verdict. Cache misses, speculative work, stall causes and replay
causes remain unsupported. BOOM needs optional core probes tracked by
riscPrint/spinal-boom #12 and #13. No BOOM tuning is supplied here.

## In-order own-model description

`own.json` also uses `rvw.arch-core/1` with kind `minor`. Its explicit `ooo`
table selects single-issue in-order scheduling in the trace-driven model.
This mode does not use gem5. Latencies and queue sizes are approximations.
They are not an elaborated snapshot.

```sh
rvw ooo rvw/arch/own.json RUN/rvfi.jsonl --json
```

See [the RTL correlation experiment](../../../../Arch/ooo/correlation/README.md)
for actual C1 cycle counts, converted SpinalProbes totals, a training-only
parameter fit and held-out IPC errors. The model uses sequential branch
prediction. The RTL uses STATIC prediction. Fitted recovery cost can absorb
that policy difference.
