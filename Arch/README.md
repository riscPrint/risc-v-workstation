# Native architecture exploration

`rvw arch` uses gem5 v25.1.0.1 to measure an approximate RISC-V O3 model.
It runs the same bare-metal ELF on gem5 and the project's C1 RTL adapter.
It reports ROI cycles, instructions, IPC, and the gap per benchmark.
gem5 shows trends; RTL is the truth.

## Setup

Keep the workstation and the core in separate repositories. Install the native
tools once. Use `RVW_GEM5` to reuse an existing native RISC-V gem5 binary.

```sh
cd /path/to/risc-v-workstation
scripts/install.sh --with-gem5 --with-riscv-gcc
source env.sh
scripts/install.sh --with-gem5 --check
```

The installer supports macOS with Homebrew and Linux with apt or dnf. It pins
the gem5 release and commit. It uses two build jobs. It installs gem5 below
`.tools/src/gem5-v25.1.0.1`. `--dry-run` prints the actions without running them.
`RVW_GEM5=/absolute/path/gem5.opt` selects a prebuilt binary. The installer and
`rvw arch` refuse an invalid selection. No container is part of this flow.

Add these paths to the project's `rvw.toml`:

```toml
[arch]
description = "rvw/arch/large.json"
sources = "../riscv-tests/benchmarks"
benchmarks = "rvw/out/arch/bench"
```

Paths resolve against `rvw.toml`. `sources` points to the native riscv-tests
benchmark sources. `benchmarks` is the output directory for the ELFs.
`RVW_RISCV_CC` selects the bare-metal GCC executable. The default is
`riscv64-unknown-elf-gcc` from PATH. GCC must have newlib and the required ISA.
No Linux toolchain or picolibc is used.

```sh
cd /path/to/core
rvw arch build --bench median,vvadd,memcpy --json
rvw arch run --bench median,vvadd,memcpy --out rvw/out/model-1 --json
rvw arch calibrate --bench median,vvadd,memcpy --out rvw/out/calibration-1
rvw arch compare rvw/out/calibration-1/rtl.json rvw/out/calibration-1/gem5.json --json
```

`build` locates gem5, checks its version and RISC-V support, and builds the ELFs.
Run the installer first if gem5 is absent. Without `--bench`, the nine default
benchmarks are median, qsort, rsort, towers, vvadd, memcpy, multiply, dhrystone,
and spmv. Every selected source must exist. Empty or duplicate selections fail.
`run` and `calibrate` require a new output directory. `--timeout SECONDS` bounds
the C1 batch and each gem5 process. Calibration uses RTL seed 1 and the fixed
memory latency from the description. It uses the C1 `run-many` command with
one worker. The adapter must support this command and report ROI metrics.

All heavy RTL work uses the project's lock and `scripts/with-lock.sh`. gem5 uses
the machine-wide `gem5` lock. Runs are serial. Thus at most one gem5 process
from this tool runs at once. Cancellation stops the child process group.
C1 calls allow 20 seconds for cleanup. MCP workers allow at least 30 seconds,
so they outlive the C1 supervisor while it stops nested groups.

The MCP server exposes `arch_build`, `arch_run`, `arch_calibrate`, and
`arch_compare`. Each tool runs as a cancellable background job and accepts
the same inputs as the CLI. Use `project` to select the core file per call.

## Core description

The JSON format is `rvw.arch-core/1`. See the complete project data in
[`examples/boom/arch/large.json`](../examples/boom/arch/large.json).
The shipped BOOM project also has small, medium, and mega data. It has no giga
mapping. These data came from the earlier core-owned model.

The default BOOM data preserve that model's effective queue placement. Its
unique-queue fallback accepts scalar classes as well as unused classes. Thus
some classes overlap with the ALU, memory and FP queues. This is a limit of the
old model, not a claim about BOOM hardware. The historical table depends on
this placement. `large-disjoint.json` is a separate experiment that removes
those scalar classes from the fallback. Use it explicitly and rerun gem5.
Do not compare its ratios with the old table as if only the compiler changed.

The required fields are:

- `schema`, `kind = "o3"`, `config`, and `isa`. `config` selects the C1 preset.
  This version builds `rv64gc` or `rv64gc_zba_zbb_zbs`. Other ISAs need an
  extension to the runner and benchmark runtime.
- `cpu`: gem5 scalar `RiscvO3CPU` parameters. These describe widths, pipeline
  delays, the ROB, registers, load/store queues, and memory ports. Parameters
  left out use gem5 defaults. The generated `config.json` records the effective
  values. Execution mode and instruction limits cannot be overridden here.
- `queues`: explicit issue queues. Each has `entries` and `units`. Each unit
  has gem5 `ops`, `count`, `latency`, and `pipelined` fields.
- `predictor`: `tage`, `loop`, `btb`, and `ras_entries`. This version models
  LTAGE with a loop predictor, a SimpleBTB, a RAS, and SimpleIndirectPredictor.
- `icache` and `dcache`: scalar gem5 `Cache` parameters. Set size, ways,
  latencies, and MSHRs explicitly for a calibration baseline.
- `itlb_entries`, `dtlb_entries`, `line_bytes`, `bus_bytes`, and
  `memory_latency`. Memory latency is in cycles at the fixed 1 GHz clock.

The model has one RV64 O3 hart. RAM is 512 MiB at `0x80000000`. L1 caches
connect directly to fixed-latency memory. The model uses no L2. Use a new
project description for a sweep. Set `RVW_ARCH_CONFIG` to another JSON path
with the shipped BOOM project. No generic code maps a core preset.

## Results and limits

Each output directory keeps copies of the model, description, project, and
selected ELFs. A build manifest, if present, is captured and checked against
the ELF hashes. It records the compiler identity. Each engine uses the copied ELF. The run report records hashes,
config, latency, counters, tool identity, and paths to the raw evidence. C1
files also record core and tool source identity. Reports use absolute paths.
Keep the output tree at its recorded location when using `compare`.

Calibration writes `rtl.json`, `gem5.json`, `calibration.json`, and `summary.txt`.
It requires conclusive RTL passes, matching ELF hashes, matching preset and
latency, positive ROI counters, and equal ROI instruction counts. It never
falls back to whole-program counters. Comparison rechecks the raw evidence
and ELF hashes. A missing, failed, changed, or unequal run gives an error.

`ipc_ratio` is candidate IPC divided by base IPC. With RTL as the base, a
ratio above 1 means gem5 ran the ROI faster. `cycle_gap_percent` is candidate
cycles divided by base cycles, minus 1, times 100. The aggregate is a geometric
mean of IPC ratios. The report status is `reported`. It is not a gate verdict.
The tool does not fit parameters or claim calibration acceptance. It does not
claim complete C8 capture or immutable generations. Reports are local measured
evidence. The threat model excludes file races and hostile input.

Short benchmark results depend on the compiler, code layout, predictor, and
cache state. Rebuild and rerun both engines after a compiler or model change.
An equal instruction count is necessary but does not prove a cycle model.
Use the model to select ideas. Confirm each claimed gain in RTL.

## Decisions

- Reuse upstream gem5 and the C1 adapter. Do not change core RTL.
- Use bare-metal ELFs with `tohost`, `tohost_exit`, `setStats`, and `bench_stats`.
  The runtime drops console HTIF calls and stores ROI counters for both engines.
- Require exactly two ROI markers and a passing tohost value. A tick limit or
  incomplete exit must not produce successful evidence.
- Report the gap before adding a fitter. Held-out fitting, event-counter
  alignment, and automated microbenchmarks remain open work.
- An in-order or RV32 core needs a CPU model selection, a matching runtime and
  ISA build options, a description, and a C1 adapter. VexRiscv is not validated.

## SoC topology

A project description can add `soc`. Without it, the previous L1 and fixed
memory path stays in use. `icache` and `dcache` still define split L1 caches.
This example adds L2, LLC, a classic crossbar per level, and one DRAM controller:

```json
"soc": {
  "levels": [
    {"size": "256KiB", "assoc": 8, "tag_latency": 8, "data_latency": 8,
     "response_latency": 1, "mshrs": 16, "tgts_per_mshr": 8},
    {"size": "2MiB", "assoc": 16, "tag_latency": 20, "data_latency": 20,
     "response_latency": 1, "mshrs": 32, "tgts_per_mshr": 8}
  ],
  "interconnect": {"width": 16, "frontend_latency": 1, "forward_latency": 2,
                   "response_latency": 1, "snoop_response_latency": 1},
  "memory": {"kind": "dram", "model": "DDR4_2400_8x8",
             "controller": {}, "interface": {}}
}
```

`levels` has zero, one, or two cache parameter objects in CPU-to-memory order.
The DRAM model can be `DDR3_1600_8x8` or `DDR4_2400_8x8`. `controller` and
`interface` accept scalar gem5 parameters. The RAM window stays at 512 MiB.
The interconnect object sets each classic crossbar. It does not describe a NoC.
For fixed memory use `{"kind":"simple","latency":"40ns","bandwidth":"8GiB/s"}`.
All values above are examples, not tuned core data. The captured description
and gem5 `config.json` retain the declared and effective settings.

Use `arch run` for SoC descriptions. `calibrate` refuses them because C1's
fixed memory latency cannot describe this topology. Multiple traffic agents,
multiple controllers, Ruby, and matching RTL interference comparisons remain
unsupported. `memory_latency` remains required metadata for old report readers;
it does not set the SoC memory timing.

## Memory observations

`rvw arch memory-report observations.json --json` reports explicit interval
counters. MCP provides `arch_memory_report`. The input uses schema
`rvw.memory-observations/1`, engine `gem5` or `rtl`, and a nonempty `observations`
array. Each row requires string `point`, `region`, `hart`, `workload`, positive
`duration_ns`, `evidence` (path relative to the input), its `evidence_sha256`,
and `mapping` (the producer's counter names, units and interval selection).
One row covers one point, region, hart and workload. Aggregate repeated trials
before import or give each trial a distinct workload ID.

Optional counters are `bytes`, `transactions`, `latency_ns_sum`, `cache_accesses`,
`cache_misses`, `outstanding_ns` (the integral of outstanding transactions),
and `queue_full_ns`. All must be finite and nonnegative. The report computes
decimal GB/s, mean transaction latency, miss rate, mean outstanding count,
and full-queue fraction. A missing counter or zero denominator gives null,
with the metric listed as `unobserved`. Contention causes stay unobserved.
A hash binds the input and each raw evidence file. Mapping is declared by the
producer; the tool cannot verify that mapping against arbitrary raw formats.

Use separate regions for sequential bandwidth, dependent pointer-chase latency,
and concurrent-traffic contention experiments. Record every active traffic
agent and the observation boundary in the mapping. This command does not
generate or run microbenchmarks, infer interference, or extract gem5 counters.
