# C9. Native architecture models

These reports measure model performance. They do not produce C4 gate verdicts
or claim C8 completeness. Every CLI action supports `--json`. A bad selection,
invalid input, failed run or comparison mismatch exits 2. Stdout then contains
one error object with `--json`. Success exits 0 and means a report was produced.

`[arch]` in `rvw.project/1` has three path fields: `description`, `sources`,
and `benchmarks`. Each path resolves against the project file. An absent or
invalid selected section is an error. No core preset is selected implicitly.

`rvw.arch-core/1` describes one hart. O3 uses RV64; Minor and TimingSimple use
RV32IM (see the RV32 in-order extension below). Required fields are `schema`,
`config` (C1 preset), `isa`, `kind`, `cpu`, `queues`, `predictor`, `icache`,
`dcache`, `itlb_entries`, `dtlb_entries`, `line_bytes`, `bus_bytes`, and
`memory_latency`. Unknown top-level fields are errors. `cpu` contains scalar
gem5 parameters for the selected CPU. The cache tables contain scalar Cache parameters.
Unknown gem5 parameters and object references are errors. Omitted scalar
parameters use gem5 defaults. Each queue has `entries` and `units`. Each unit
has `ops` (gem5 opclass names), `count`, `latency`, and `pipelined`.
`predictor` has `tage`, `loop`, `btb`, and `ras_entries`. TAGE has
`nHistoryTables`, `minHist`, `maxHist`, `tagTableTagWidths`, `logTagTableSizes`,
and `logUResetPeriod`. Loop has `logSizeLoopPred` and `logLoopTableAssoc`.
BTB has `numEntries` and `associativity`. Clock is 1 GHz. Memory defaults to 512 MiB
at 0x80000000. `memory_latency` is a positive whole number of cycles.

`rvw.arch-build/1` records config, ISA, source path, gem5 and compiler identity (path, SHA-256,
version), and benchmark IDs, paths and SHA-256 hashes. Builds use native
newlib GCC and the description's ISA. RV64GC with optional Zba/Zbb/Zbs
and RV32IM are supported. The source path points to riscv-tests.

`rvw.arch-run/1` records `engine` (`rtl` or `gem5`), core, config, memory
latency, project capture, description/model hashes and a nonempty `benchmarks`
list. `benchmark_build`, when present, records the captured build manifest
and compiler identity. A null value means the ELF build provenance is unknown.
A supplied manifest must bind each selected ELF hash. gem5 runs also record the native binary identity in `tool`. Each row
has `id`, `elf`, `elf_sha256`, `status="pass"`, positive ROI `cycles` and
`instret`, and `evidence` plus `evidence_sha256`. Paths are absolute.
`evidence` is a C1 result for RTL or gem5's `bare.json`. The latter requires
integer `tohost=1`, integer `exit_code=0`, `roi="setStats"` and positive
integer `bench_stats.cycles` and `bench_stats.instret`. A model run requires
exactly two setStats entries and four ELF symbols: tohost, tohost_exit,
setStats and bench_stats. A tick limit or incomplete exit fails the run.

Calibration captures each selected ELF once in a fresh output directory.
Both engines run those copied bytes. The C1 adapter gets fixed latency,
seed 1 and the description's preset through `run-many` with one worker.
A conclusive pass is required. ELF hash, core, preset, seed and latency must
match the requested job. ROI counters are mandatory. Whole-program counters
are never substituted. Raw C1 evidence includes the adapter's source identity.

`rvw.arch-compare/1` records base/candidate report paths and SHA-256 hashes,
core, config, latency, `status="reported"`, per-benchmark counters and
`geomean_ipc_ratio`. Comparison rechecks raw evidence and ELF hashes. Both
sets must be nonempty with unique identical IDs, identical ELF hashes and
equal ROI instruction counts. Core, config and memory latency must match.
`ipc_ratio` is candidate IPC/base IPC, or base cycles/candidate cycles when
instructions match. `cycle_gap_percent` is 100*(candidate cycles/base cycles-1).
Comparison requires an RTL base and a gem5 candidate, in that order.
The aggregate is the geometric mean of IPC ratios. No acceptance threshold
or parameter fit is applied. `calibrate` writes this JSON to calibration.json
and a short table to summary.txt. Reports depend on the recorded local paths.

The model uses upstream gem5 v25.1.0.1. Runtime and setup are native. gem5
runs serially under the machine-wide `gem5` lock. RTL uses the project's
shared lock and C1 adapter. C1 termination has a 20-second cleanup grace,
so the 15-second adapter supervisor can stop its child group. Architecture MCP
workers have at least 30 seconds. Server shutdown honors that job grace.
MCP exposes arch_build, arch_run, arch_calibrate
and arch_compare as cancellable jobs. See Arch/README.md for commands and
limits. gem5 shows trends; RTL is the truth.

## Typed retry costs in the trace timing model

The optional `retry_costs` object maps `memory_order_violation`,
`store_forward_miss`, `cache_miss_retry` and `tlb_miss` to nonnegative integer
cycle counts. An omitted cause keeps the earlier policy. The record does not
contain dynamic RTL events. Each run detects causes from its own schedule,
addresses, component service and translation state.

With `replay_window`, memory-order recovery starts at the oldest violating
load. Older independent instructions survive. Its declared cost blocks
readmission. A declared cache cost selects a local load retry after the
component response. It does not invalidate independent younger work. The
`cache_miss_replay` switch still controls activation. A long component
response remains a miss proxy, not a proven RTL retry predicate.

A partial forward miss sets one local retry interval from detection while
it waits for older store completion. An own-model TLB miss adds its declared
cost after the page walk. These two policies do not invalidate younger work.
Their counters count modeled retry episodes, not each rejected RTL attempt.
The compiled scheduler refuses nonempty costs and uses Python.

Costs are project declarations. A zero cost is not a measured zero overhead.
The NaxRiscv experiment measures one detection-to-restart span on its base
configuration. Local additional costs remain unmeasured. This does not
establish exact replay, causal cost isolation or cross-program accuracy.

Local cache retries use a local LSU return path. They do not wait for an IQ
slot. The declared load port limits simultaneous local returns, and shared
execution ports remain occupied. This avoids a cycle where younger work
fills the IQ while a dependent branch waits for the missed load.
