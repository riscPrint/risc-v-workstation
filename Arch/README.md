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
The build checks the Buildroot 2025.02.1 archive SHA-256. Buildroot pins the
internal musl toolchain, BusyBox, Linux 6.12.9 and OpenSBI 1.6. It checks package
hashes from the release, including its QEMU board patches. The root filesystem
is a gzip cpio initramfs. `Arch/linux/overlay/init` mounts proc, sysfs and devtmpfs.
It runs a separate shell process to check the kernel type. It prints a marker
and calls poweroff. This is a minimal userspace check. It is not a Linux selftest
suite or a test of signals, page faults or scheduling correctness.

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
