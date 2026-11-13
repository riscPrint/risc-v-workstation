# Live VexRiscv pyuvm environment

This project binding connects `LiveCpuEnvironment` to the simple instruction
and data buses of `examples/vexriscv` VexTop. Both ports use its shared byte
memory with seeded response delays. The scoreboard steps independent Spike
once per live retirement. A pass requires a full-word `tohost=1` retirement.
A matching prefix cannot pass. A failed program or watchdog stops the test.

Install `rvw[cocotb]` and pyuvm 4. Build the matched Spike shim with
`Cosim/build.sh`. Generate VexTop RTL from the project adapter under the
`vex` and `sbt` locks, or copy the generated `VexTop.v` from that adapter to
this folder. Generated RTL is ignored by Git. Do not change the core.
Use the existing RV32IM ISA ELFs built by the VexRiscv project.

From the workstation checkout, with Verilator on PATH:

```sh
export RVW_CPU_SHIM="$PWD/Cosim/build/librvw_spike.so"
export RVW_CPU_ELF=/absolute/path/to/rv32ui-p-add
scripts/with-lock.sh vex nice -n 10 rvw/.venv/bin/rvw regress cocotb \
 Uvm/examples/vexriscv/bench.json --out /tmp/vex-live-add --timeout 120 --json
```

Repeat with other ISA ELFs and new output directories. Set `RVW_VEX_SEED`
to choose memory timing. `--seed` controls the simulator seed separately.
Set `RVW_VEX_CORRUPT=1` for a negative run. It changes the sixth retirement's
next PC before comparison. That run must fail with `SPIKE_MISMATCH:pc_next`.

`bindings.json` maps the project's RVFI pins. The runner writes C3 through
the cocotb adapter. `cpu-checks.json` records actual comparisons and observed
coverage only after the final store passes Spike. `spike-capture` retains
the captured reference inputs. C3 source identity remains incomplete.
This example does not earn C4 acceptance.

The profile uses scalar RV32IM retirements, RAM and M-mode. It supplies no
interrupt or debug stimulus. The selected VexTop has no debug unit.
Architectural IRQ/debug checks, SoC peripheral integration and full ISA
qualification remain open. The RAM-only binding reports no data faults.
It does not qualify access-fault behavior.
