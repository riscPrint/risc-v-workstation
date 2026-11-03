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

`isa.json` declares the adapter trace ISA and pins the opcode coverage source.
Extension versions remain null until verified. Use it with `rvw cov isa-check`
and `rvw cov functional --manifest`; see the coverage tool README. It does not
certify BOOM ISA compliance or change the adapter configuration.
