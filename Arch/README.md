# Native architecture exploration

`rvw arch` uses gem5 v25.1.0.1 to measure an approximate RISC-V model.
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

`compare` requires an RTL base and a gem5 candidate, in that order.
The IPC ratio is model IPC divided by RTL IPC.

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

- `schema`, `kind`, `config`, and `isa`. `config` selects the C1 preset.
  Supported pairs are O3 with `rv64gc` or `rv64gc_zba_zbb_zbs`, and Minor or
  TimingSimple with `rv32im`. Use `kind = "o3"`, `"minor"`, or `"timing"`.
  Other pairs fail. RV32 builds use ilp32 and stable high/low/high CSR reads.
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

The model has one hart. RAM defaults to 512 MiB at `0x80000000`.
Optional `ram_bytes` selects a page-aligned capacity up to that limit.
ELF load ranges must fit the selected capacity. L1 caches
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
The comparison does not fit parameters or claim calibration acceptance. It does not
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
- Report the gap before adding a fitter. Offline held-out candidate selection and measurement microbenchmarks are available.
  Bayesian parameter search is available. Live RTL event mappings remain project work.
- RV32IM uses Minor or TimingSimple, with explicit RV32 ISA configuration.
  In-order descriptions require `queues=[]` and `predictor=null`.
  Their CPU defaults apply unless scalar CPU parameters override them.
  `cpu={}` selects all defaults. Both caches can be null to bypass them.
  In-order SoC extensions are refused. See the
  [VexRiscv architecture guide](../examples/vexriscv/rvw/arch/README.md) for
  uncached models, live C1 event mappings and a held-out fitting plan.

## Limit ownership

Fitting: [#12](https://github.com/riscPrint/risc-v-workstation/issues/12). RV32/in-order models: [#13](https://github.com/riscPrint/risc-v-workstation/issues/13). Wide-core features: [#72](https://github.com/riscPrint/risc-v-workstation/issues/72). Experiments: [#160](https://github.com/riscPrint/risc-v-workstation/issues/160).

Retained limit: Complete C8 capture and immutable generations have no dedicated issue. Keep C9 reports local, with absolute paths and status=reported. Parameter generation remains a source-inspection guide, not a verified extractor. Fixed topology and benchmark sensitivity still apply.

## Event fitting

`rvw arch fit plan.json --json` selects among saved project-owned candidates.
The MCP tool is `arch_fit`. It does not run gem5 or change parameters.
Use a new held-out set after you use its result to change candidates.
Keep model parameters and event mappings in the core project.

A plan uses this format. Paths resolve against the plan directory.

```json
{
  "schema": "rvw.arch-fit-plan/1",
  "rtl": "runs/rtl.json",
  "candidates": {"baseline": "runs/gem5.json", "candidate": "runs-2/gem5.json"},
  "train": ["pointer-chase", "dependent-chain"],
  "held_out": ["branch-loop", "independent-misses"],
  "events": [{
    "name": "retired branches",
    "rtl_metric": "roi_retired_branches",
    "gem5_stat": "system.cpu.branchPred.condPredicted",
    "unit": "count",
    "semantics": "Example only. Replace with independently verified ROI event semantics."
  }],
  "scope": "Name the tested core, memory setup and workloads.",
  "uncertainty": "State counter boundary errors and measurement variation.",
  "unsupported": ["List structures that this model does not represent."]
}
```

The statistic above is a format example, not an asserted semantic match.
The project owner must check that both events count the same behavior in the
same ROI. Missing events fail. No event is inferred from an IPC ratio.
The fitter rechecks the run evidence, ELF hashes, instruction counts and run
settings through `compare`. It reads C1 `metrics` and the first complete block
in `stats.txt` beside each gem5 `bare.json`. This model resets stats at ROI
entry and writes that block at ROI exit. Use reports from this model only.
It hashes the stats files in the fit report. It does not certify the mappings.

Error is `abs(model - RTL) / max(1, RTL)` per event and workload.
The objective includes relative cycle error for every workload.
Instruction totals are consistency checks. They do not enter the objective.
This includes instruction units, retired totals and instruction-class counts.
Other events default to role `fit`. Use optional role `consistency` to exclude
another fixed event. Role `fit` cannot override a known instruction total.
The score averages cycle error and eligible event errors within each workload.
Then it averages workloads. `headline` reports cycle error, cycle gap and IPC
ratios. Matching instruction totals cannot hide a timing gap.
The lowest training score wins. Names break ties in lexical order.
Only the winner gets a held-out score. Splits must be nonempty, disjoint and
cover exactly the report workloads. Training and held-out ELF hashes must also
be disjoint. Renaming the same ELF does not make an unseen workload.
The report is `inconclusive` for fewer than three training workloads,
constant training cycle or eligible event targets, or tied scores across multiple candidates.
A selected candidate in this report does not establish a useful fit.
It gives no fidelity threshold, confidence interval or correctness verdict.
A single workload cannot establish general model fidelity.
Use `arch search` below for parameter generation. Keep plans and fitted values in the core project.
The test target uses synthetic event evidence. It does not validate RTL counters.

## Measurement microbenchmarks

The benchmark builder also accepts `pointer-chase`, `branch-loop`,
`dependent-chain` and `independent-misses`:

```sh
rvw arch build --bench pointer-chase,branch-loop,dependent-chain,independent-misses --json
```

These sources live in `Arch/bench/micro`. They use the existing ROI runtime.
The pointer chase loads one linked node per cache line. The branch loop runs
an alternating conditional branch. The dependent chain uses four dependent
integer additions per iteration. The independent load test uses four separate
arrays. Its name describes the intended pressure. Actual misses depend on
cache capacity, cache state and the compiler. Inspect disassembly and measured
events before drawing a timing conclusion. Setup and return checks sit outside
the marked ROI. No source guarantees a cold cache or a given miss count.

## CPU and ELF compatibility preflight

Run a static check before model construction:

```sh
rvw arch inspect --elf kernel.riscv --isa rv32im --kind minor --json
```

The MCP tool is `arch_inspect`. The checker accepts ELF32 for `rv32im` and
ELF64 for `rv64gc` or `rv64gc_zba_zbb_zbs`. It checks the machine, load ranges,
entry and required runtime symbols. It checks both classes against the same
512 MiB RAM range at `0x80000000`. It does not read ISA extension attributes
or validate instruction behavior. The CPU choices are `o3`, `minor` and
`timing`. Only RV64 O3 is currently compatible with the runtime runner.

A valid RV32IM ELF with `minor` is the first small preflight case. Its expected
result is `status: unsupported`, with separate CPU and RV32 runtime blockers.
CLI exit 2 keeps it blocked. ELF layout success cannot enable a simulation.
The RV32 case uses synthetic ELF data in unit tests. It is not VexRiscv
validation. Unknown choices and invalid ELFs produce errors. A compatible
RV64 O3 layout exits 0. Compatibility remains separate from performance
calibration and does not prove ISA support, ROI counters or model fidelity.

The next increments need in-order CPU construction and probe validation,
an RV32 runtime with stable 64-bit CSR reads, gem5 RV32 ISA configuration,
and second-core instruction, memory and ROI checks. The existing runner still
refuses RV32 and in-order descriptions. No VexRiscv model is claimed.

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
fixed memory latency cannot describe this topology. Ruby and matching RTL interference comparisons remain unsupported. `memory_latency` remains required metadata for old report readers;
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

## Small design-space sweeps

Create a project-owned sweep file:

```json
{
  "schema": "rvw.arch-sweep/1",
  "parameters": {"cpu.fetchWidth": [2, 4], "dcache.assoc": [2, 4]},
  "max_points": 4,
  "timeout_s": 120
}
```

```sh
rvw arch sweep sweep.json --bench median --out out/sweep-1 --json
```

MCP provides `arch_sweep` with the same inputs. The output directory must be
new. Build the selected workloads first. The command captures workload bytes
once. Each candidate uses those bytes. Dotted paths replace existing scalar
fields of the same type. Array indices use decimal path parts, for example
`soc.levels.0.assoc`. Allowed roots are cpu, icache, dcache, soc, bus_bytes,
and memory_latency. No core-specific preset mapping is added.

The Cartesian product must fit `max_points` (1 to 32). The command refuses
more than 64 model processes before running any point. `timeout_s` bounds
each process, from above zero to 3600 seconds. Thus the process-time budget
is points times workloads times timeout_s. Lock wait and tool checks are
outside this budget. Runs remain serial under the gem5 lock. This tool does
not dispatch to a farm or run RTL.

Each point ID is SHA-256 of canonical JSON with the effective description,
ordered workload IDs and hashes, model source hash and gem5 binary hash.
The point keeps identity.json, the description, model source and raw evidence.
The root keeps project data, the sweep and captured ELFs. Equal identities
can reproduce the same inputs. They do not guarantee equal timing across hosts.
The command does not resume or reuse an earlier run.

`results.sqlite` has a `points` table with id, status, cycles, and result_json.
Each point is committed as inconclusive before launch and updated after the
run. Failed points retain their error and cannot enter the frontier. `dse.json`
contains all point records and a Pareto list for the single objective: minimize
the sum of selected ROI cycles. Each workload has equal weight. Ties remain.
This is a speed-only frontier. Area, power and uncertainty are unknown. All
points are model-only and need RTL confirmation. Use `arch pareto` below for optional user-supplied cost comparisons.
The workstation does not estimate area or power. RTL performance confirmation
remains open work.
A partial sweep reports inconclusive and exits 3. Input errors exit 2.

## Linux reference flow

`rvw arch linux` separates image construction, table capture and reference boot.
The first platform is QEMU `virt`, one RV64 hart with Sv39 and 128 MiB RAM. Its declared
properties live in `examples/qemu-linux/platform.json`. This is reference data.
It does not describe a verified RTL Linux platform.

On native Linux, install GCC, make, bc, bison, flex, cpio, rsync, file, wget,
curl, unzip, Git, Python, ncurses headers, OpenSSL headers, QEMU and dtc.
Then run:

```sh
rvw arch linux build --out /tmp/linux-build --timeout 9000 --jobs 2 --json
rvw arch linux prepare --images /tmp/linux-build/build/images \
  --platform examples/qemu-linux/platform.json --out /tmp/linux-prepared --json
rvw arch linux boot --images /tmp/linux-build/build/images \
  --platform examples/qemu-linux/platform.json --out /tmp/linux-boot --timeout 120 --json
```

Each action needs a new output directory. `--timeout` bounds each build command
or QEMU process. `--jobs` accepts 1 through 4. Builds run serial commands.
The tool stops the full process group on timeout or cancellation.
The build checks the Buildroot 2025.02.1 archive SHA-256. It extracts regular
content before skeleton symlinks. It preserves absolute symlinks for the target
root filesystem. Archive errors stop the build and record an inconclusive result. Buildroot pins the
internal musl toolchain, BusyBox, Linux 6.12.9 and OpenSBI 1.6. It checks package
hashes from the release, including its QEMU board patches. The root filesystem
is a gzip cpio initramfs. `Arch/linux/overlay/init` mounts proc, sysfs and devtmpfs.
It runs a separate shell process to check the kernel type. It prints a marker
and calls poweroff. This is a minimal userspace check. It is not a Linux selftest
suite or a test of signals, page faults or scheduling correctness.

For pinned prebuilt images on macOS, see [the reference platform](../examples/qemu-linux/README.md#native-prebuilt-reference-images).
The prebuilt flow selects a small userspace from a hash-checked Debian initramfs.
It runs natively and does not require a Linux compiler.

macOS cannot build Buildroot. Use `.github/workflows/linux-boot.yml` for that
step on native Ubuntu 24.04. The workflow uses no container. It builds images,
boots QEMU and uploads images, configuration, console and reports. A workflow
that has not finished is NOT RUN evidence. To build firmware alone on macOS:

```sh
brew install make qemu dtc llvm lld
export PATH="$(brew --prefix llvm)/bin:$(brew --prefix lld)/bin:$PATH"
rvw arch linux firmware --llvm --out /tmp/linux-firmware --timeout 300 --json
```

The firmware action fetches the pinned OpenSBI v1.6 commit. It uses GNU make
and `riscv64-unknown-elf-gcc` by default. OpenSBI 1.6 requires PIE linker support.
The installed bare-metal GNU linker can lack this support. Use `--llvm` with
Clang, LLD and LLVM tools on PATH, or `--cross-compile PREFIX` with a native
Linux-target toolchain. No GNU linker check is bypassed. The LLVM build keeps the Clang 23
`unused-but-set-variable` and `unused-but-set-global` diagnostics as warnings.
The manifest records this policy. Other compiler errors still stop the build.
This action does not build Linux or a root filesystem.

QEMU starts firmware at `0x80000000` in M-mode. It supplies the hart ID in a0
and the device tree in a1. `fw_jump` enters Linux at `0x80200000` in S-mode.
QEMU places the initramfs and updates the chosen node. The same captured DTB is
passed back to the boot. Selected RAM, timer, UART, PLIC and MMU properties must
match project data. These are table checks. They do not check device state,
interrupt delivery or model timing. QEMU timing is not RTL timing.

Reports bind firmware, kernel, initramfs, device tree, command line and QEMU
by hash. Build reports also bind the source archive and configuration.
Console input, network and disk input are disabled. No external input replay
or equivalence claim is supported. A prompt or OpenSBI banner is insufficient.
The boot action requires its userspace marker, power-down message and a clean
QEMU exit. Timeouts, panics and failed property checks stay inconclusive.

`prepare` copies the images and device tree for an RTL adapter. Its manifest
lists firmware and kernel load addresses. RTL preparation remains blocked until
an adapter places the initramfs and DTB, sets a0/a1 and implements the declared
UART, timer, PLIC, reset and interrupt behavior. Do not load these images with a
bare-metal C1 adapter and infer Linux support. No full RTL Linux boot is part
of this command. Only a bounded first-N retirement comparison is permitted
when an adapter can supply the initial platform state. The current BOOM adapter
has no verified Linux loader/device contract, so that comparison is NOT RUN.
OpenSBI 1.6 also produces a PIE ELF. The current Spike shim requires a static
executable ELF. A first-N comparison needs explicit PIE loading support; do not
change an ELF header or bypass that check to infer a comparison.

The close condition for #56 remains broader: the same captured tables and images
must run on reference and RTL, device states and replay inputs must agree, and
SBI, user-process, page-fault, signal, context-switch and selected kernel selftests
must pass. FreeRTOS/Zephyr adapters also remain open. None is inferred from the
minimal reference boot.

## Bayesian fitting, repeats and predictions

`rvw arch search search.json --out runs/search --json` runs a bounded search.
Its plan has this shape. The `fit` object is a complete `rvw.arch-fit-plan/1`
plan from above, with `candidates: {}`. Its `rtl` path resolves against the
search plan. Keep the plan and output in the core project.

```json
{
  "schema": "rvw.arch-search/1",
  "fit": {"schema": "rvw.arch-fit-plan/1", "rtl": "runs/rtl.json", "candidates": {},
          "train": ["train-workload"], "held_out": ["unseen-workload"],
          "events": [{"name": "ROI cycles", "rtl_metric": "roi_cycles",
                      "gem5_stat": "system.cpu.numCycles", "unit": "cycles",
                      "semantics": "Verify the same ROI clock and boundaries in both engines."}],
          "scope": "State the target and workload scope.",
          "uncertainty": "State the counter and model limits.", "unsupported": []},
  "parameters": {"bus_bytes": [4, 8, 16]},
  "budget": 3,
  "repeats": 3,
  "timeout_s": 600
}
```

This generic example does not fit a named core. Parameter rules are the same
as `sweep`. There are at most 32 space points and 256 model processes.
The search uses an RBF Gaussian process with fixed noise variance `1e-6` and
expected improvement. Numeric ranges use unit scaling. Categories use one-hot
encoding. The first point and ties use the declared space order.
Each point runs on training workloads only. Repeated training cycle and eligible event errors
select the point. Only then does the selected point run on held-out workloads.
The saved RTL report supplies observations. It does not run RTL again.
Memory latency cannot change because RTL observations must stay comparable.
SoC fitting is not supported. An invalid run stops the search.
`progress.json` records completed training points. `search.json` records the
selected point, training intervals, held-out interval and checked event fits.
The command does not resume a partial search.

`rvw arch measure --bench NAME,NAME --repeats 3 --out runs/repeats --json`
runs both RTL and gem5 again for every repeat. It retains fresh evidence and
checks stable tool, model, description, ELF and workload identities.
`measure.json` reports mean cycles, IPC ratio and cycle gap with 95% percentile
bootstrap intervals. Search also reports bootstrap intervals for repeated
model scores. Both use 4000 resamples and bootstrap seed 0. These intervals
describe repeat variation only. Calibration keeps RTL seed 1. Deterministic
runs can give zero-width intervals even when a model has a large bias.
A constant repeat series has interval status `inconclusive`. The numerical
interval remains visible as a description of repeat variation.
Use enough independent measurements for the intended decision. These reports
do not measure generalization uncertainty or establish a fidelity threshold.

Event fits include `event_correlations` for each split. Pearson correlation
needs at least three workloads and nonconstant counters. Missing variation or
too few workloads gives `inconclusive` with a null coefficient. Correlation
does not establish event semantics or accuracy.

Store a prediction before the RTL experiment. Score it after that experiment:

```sh
rvw arch predict runs/model/gem5.json --out predictions/idea.json --json
rvw arch score-prediction predictions/idea.json runs/later/rtl.json \
  --out predictions/idea-score.json --json
```

Create the parent directory first. Each ledger file is created exclusively.
A prediction stores UTC time, the model report, its hash and local evidence
paths. Scoring rechecks the stored prediction, model evidence and later RTL
with `compare`. Each RTL evidence file must have a modification time after
the prediction. The score is a separate file linked by the prediction hash.
This local ordering check is not a trusted timestamp or proof of blinding.
Keep the original evidence trees. Do not use old RTL evidence with a changed
timestamp as a new measurement. Ledger scores currently cover ROI cycles and
IPC. Event errors remain in the separate fitting report.

MCP exposes `arch_search`, `arch_measure`, `arch_predict` and
`arch_score_prediction` with the same inputs as the CLI.
Native VexRiscv fitting still needs independently checked ROI event mappings.
Description tests and synthetic subprocess tests do not establish native model
fidelity. No BOOM fitted parameters belong in this repository.

### Multi-objective interval comparison

`rvw arch pareto plan.json --json` (MCP `arch_pareto`) compares saved model
reports. The plan has schema `rvw.arch-pareto-plan/1` and a `points` array.
Each point has a unique `id` and a `report` path. Paths are relative to the
plan. All reports must use the same ELFs and ROI instruction counts. Raw model
evidence and ELF hashes are checked again.

The optional plan `objectives` list defaults to `["cycles"]`. Model cycles
supply exact bounds when no `costs` file is given. Area and power are optional
user-supplied inputs. To compare them, explicitly select `area_mm2` or `power_w`
and supply a `costs` path for each point. The tool does not estimate or validate
area or power. PPA estimation and hardware gain claims are out of scope.

Each optional costs file has schema `rvw.arch-costs/1`, `report_sha256`, a
nonempty `method` that states the source and method, and `cycles`. `area_mm2` and `power_w`
can be absent. Each interval is null or positive ordered `[lower, nominal, upper]`.
Nominal cycles must equal summed model ROI cycles. Bounds are user declarations,
not inferred confidence levels. A missing selected objective excludes that
point and makes the result inconclusive. Unselected missing costs do not block
the default performance comparison.

Selected objectives are minimized. The nominal frontier uses central values.
The conservative frontier removes a point only when another point's upper
bounds are no greater than its lower bounds, with at least one strict gain.
Reports and supplied costs are hash-bound. Output labels supplied costs as
`user-supplied`. These labels and bounds do not establish physical measurements.
Model performance still needs RTL confirmation.

### Traffic agents and memory channels

`soc.memory` also accepts `{"kind":"multi", "interleave_bytes":64,
"controllers":[MEMORY, MEMORY]}`. Each MEMORY is a simple or DRAM object
as above. Use 2, 4 or 8 controllers. The interleave size is a power of two,
at least 64 bytes. Each channel uses an interleaved range across the full RAM.
The ranges share one backing store, including on macOS. This is channel
interleaving, not a model of arbitrary address windows or a NoC.

Optional `soc.agents` holds at most eight read-only linear traffic agents.
Each object declares `start` (physical byte address), `size`, `block_bytes`
(power of two up to 64), `period_ticks`, `duration_ticks`, `max_outstanding`
and `attach` (`memory` or an existing `level2`/`level3`). Bounds must fit RAM.
The period and duration use 1 ps ticks. Agents start after model instantiation.
After the selected duration they remain idle. They do not write guest memory.
Their raw counters and effective ports remain in gem5 stats and config files.
CPU ROI markers still select the reporting interval. A background agent is
not a hart. These observations do not establish matching RTL interference.

### Native memory counter extraction

Build `sequential-bandwidth` for sequential reads and `pointer-chase` for
serial load latency. Use `independent-misses` with and without `soc.agents`
for a model interference experiment. All three have checked return values
and paired ROI markers. Build and run them with the existing `arch` commands.

`rvw arch memory-extract mapping.json --json` (MCP `arch_memory_extract`)
extracts mapped counters from the first gem5 ROI stats block. The mapping uses
schema `rvw.memory-mapping/1`, an `inputs` object, and an `observations` array.
`inputs` has `stats`, `config`, and `bare`. Each has `path` and `sha256`.
Each observation has `point`, `region`, `hart`, `workload` and `counters`.
`point` must exist in native config. Each counter uses the existing interval
counter name and has `stats` (distinct full native counter names) and positive
`scale`. Every name must start with the observation point plus a dot.

For example, map `bytes` to `{"stats":["system.traffic0.bytesRead"],"scale":1}`,
`transactions` to `system.traffic0.totalReads`, and `latency_ns_sum` to
`system.traffic0.totalReadLatency` with scale `0.001` (ticks to ns).
The stats interval must match both ROI tick markers at a 1 ps tick period.
Later whole-program dumps are ignored. Input and mapping hashes are retained.
The tool checks exact names and object paths. The project still owns counter
semantics and unit scales. Missing counters stay unobserved. Request latency
sums do not establish an outstanding-request integral. Retry time does not
establish queue-full time. Neither establishes a cause of contention.
