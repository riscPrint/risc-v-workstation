# Live SV VexRiscv CPU bench

This bench connects the existing `rvw_cpu_pkg::cpu_env` to VexTop.
The CPU executes a project program with arithmetic, a store, a load, a
branch and a final tohost store. Independent Spike checks every retirement.
A watchdog or a matching prefix cannot complete the test.

Prepare the inputs from the existing private VexRiscv RTL and matched shim:

```sh
rvw/.venv/bin/python Uvm/examples/vexriscv/sv/prepare.py \
 --out /tmp/vex-sv-inputs --shim Cosim/build/librvw_spike.so \
 --rtl Uvm/examples/vexriscv/VexTop.v
scripts/with-lock.sh vex-uvm nice -n 10 rvw/.venv/bin/rvw uvm build \
 /tmp/vex-sv-inputs/bench.json --out /tmp/vex-sv-build --timeout 1800
rvw uvm regress --build /tmp/vex-sv-build --seeds 1 3 --out /tmp/vex-sv-runs
```

Use `+corrupt` with the compiled simulator as a negative control.
It changes the observed next PC. The simulator must stop on `SPIKE_MISMATCH`
and must not print `RVW_UVM_DONE`.

The manifest declares the generated RTL, image, bridge header, setup,
Spike source and runtime library as native dependencies. Gate identity
checks these bytes. It also binds the project SV sources to the selected
workstation revision. The generated CPU image is fixed for this build.
A CPU source change needs regenerated RTL and a fresh build.

This configuration has no debug unit. The SV fixture does not drive IRQs,
process separate trap events or supply architectural snapshots. It does
not qualify the full ISA suite. Use the live Python binding for that path.
