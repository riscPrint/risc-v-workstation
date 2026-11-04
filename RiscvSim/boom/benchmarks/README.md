# Simulation throughput workload

`sim-accel.S` repeats a store, a load, a value check and a branch 100000 times.
It reports pass through tohost only after all value checks pass. A wrong load
reports failure. It uses RV64IM and no external input.

Build from the workstation root with the RISC-V GNU toolchain on PATH:

```sh
riscv64-unknown-elf-gcc -march=rv64im -mabi=lp64 -nostdlib -nostartfiles -static \
  -T RiscvSim/tests/programs/link.ld -o /tmp/sim-accel.elf \
  RiscvSim/boom/benchmarks/sim-accel.S
rvw regress speed-sweep --adapter RiscvSim/boom/run.sh --elf /tmp/sim-accel.elf \
  --config medium --lock boom --threads 2 --repeats 5 --min-seconds 10 \
  --max-cycles 2000000 --timeout 1800 --out /tmp/sim-accel-new
```

Use a new output path. The sweep uses the existing explicit thread opt-in.
No thread count is recommended without the comparison and reference checks.
The timeout above applies to each launch. Use an outer process-group timeout
when the whole campaign needs one budget. The design protocol is in
[sim-accel.md](../../../docs/design/sim-accel.md). Results belong in the PR.
