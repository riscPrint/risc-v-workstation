# BOOM project data

This example uses the installed workstation adapter with a separate BOOM source
checkout. It has O3 description data for small, medium, large and mega. It has
no giga model. These data do not define an acceptance threshold.

```sh
export RVW_HOME=/path/to/risc-v-workstation
export SPINAL_BOOM=/path/to/your/boom-checkout
export RVW_GEM5=/absolute/path/to/gem5.opt
export RISCV_TESTS_SRC=/path/to/riscv-tests/benchmarks
export PATH=/path/to/riscv-gcc/bin:$RVW_HOME/rvw/.venv/bin:$PATH
rvw --project "$RVW_HOME/examples/boom" arch build
rvw --project "$RVW_HOME/examples/boom" arch calibrate --out /path/to/new/calibration
```

`RVW_ARCH_CONFIG` selects another description path. Its default is
`arch/large.json` relative to this project. `RVW_ARCH_BENCHMARKS` selects an
existing ELF directory. Its default is `out/arch/bench`. Use this override only
when `arch build` must write there or when calibration must read existing
binaries. Calibration copies each selected ELF before either engine runs it.

For a core-owned adapter, keep the same description data beside the core's
`rvw.toml`. See [Arch](../../Arch/README.md) for the generic format and limits.

The default presets preserve the old model's effective fallback unit. It accepts
scalar classes too. This overlaps with other issue queues and is not a faithful
model of BOOM's disjoint queues. Keep it for comparison with the historical
calibration. `large-disjoint.json` removes the overlapping scalar classes as a
separate experiment. Select that file explicitly with `RVW_ARCH_CONFIG`.

A nine-benchmark native gem5 v25.1.0.1 comparison with BOOM `large`, seed 1 and
fixed memory latency 20 had a geometric mean model/RTL IPC ratio of 0.906 with
equal ROI instruction counts. This measures the model gap; it does not establish
cycle accuracy, hardware behavior or a C8 gate verdict.

The [Konata event mapping](konata-events.md) lists the core-owned probe changes
needed for measured stall causes and predicated-off commit counts.

## SoC map

`soc.json` describes this example's simulation map and reference policies.
Run `rvw soc generate soc.json --out /tmp/boom-soc --json` from this folder.
See the [format and limits](../../rvw/src/rvw/soc/README.md).
Pass `--soc-map DIR/sim-map.json` to the launcher to use the generated map.
The adapter reads device addresses and reset values from that map. It captures
accepted TileLink A requests with a map monitor. This does not observe RTL
decoder selects. See the SoC guide for fixed RTL limits.

`isa.json` declares the adapter trace ISA and pins the opcode coverage source.
Extension versions remain null until verified. Use it with `rvw cov isa-check`
and `rvw cov functional --manifest`; see the coverage tool README. It does not
certify BOOM ISA compliance or change the adapter configuration.

## Bounded single-hart cache program

`cache-behavior.S` writes and checks 32 KiB, repeats a line access, checks byte
stores, and patches a fetched function with `FENCE.I`. Expected values are
constants or loop indices. The program reports through `tohost`.
Build and run from the workstation root:

```sh
riscv64-unknown-elf-gcc -march=rv64gc -mabi=lp64d -nostdlib -nostartfiles \
  -static -T RiscvSim/tests/programs/link.ld examples/boom/cache-behavior.S \
  -o /tmp/boom-cache-behavior
RiscvSim/boom/run.sh run --elf /tmp/boom-cache-behavior --out /tmp/boom-cache-run \
  --config small --seed 1 --max-cycles 200000 --mem-latency 0 --wall-timeout 120 --json
```

The launcher takes the `boom` and `sbt` locks. Do not run it beside another heavy
job. This is a bounded functional test. It does not observe hit/miss counts,
prove eviction, or connect the generic cache scoreboard to BOOM internals.
BOOM remains single-hart. Coherence and DMA RTL campaigns need another adapter.
