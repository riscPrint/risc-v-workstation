# Cocotb examples

This folder tests one small Spinal-generated counter and the unmodified upstream
VexRiscv `vexriscv.plugin.PmpSetter(2)` unit. Bindings and test oracles stay here.
The PMP test checks aligned NAPOT base and mask formulas for 29 region sizes
and eight seeded addresses per size. It does not test the complete PMP plugin
or privilege enforcement. The counter checks reset, increment, wrap and hold.

Set `RVW_HOME` to the workstation checkout. Set `VEXRISCV` to the upstream core
checkout. Use JDK 21 and the dependencies in the parent README. From this folder:

```sh
cd ../rvw
"$RVW_HOME/scripts/with-lock.sh" vex "$RVW_HOME/scripts/with-lock.sh" sbt \
  nice -n 10 sbt -J-Xmx2g -batch -Dsbt.offline=true \
  'runMain rvwvex.CocotbUnits ../cocotb/rtl'
cd ../cocotb
"$RVW_HOME/scripts/with-lock.sh" vex nice -n 10 rvw regress cocotb \
  counter-icarus.json --out out/counter-icarus --seed 1 --json
"$RVW_HOME/scripts/with-lock.sh" vex nice -n 10 rvw regress cocotb \
  counter-verilator.json --out out/counter-verilator --seed 1 --json
"$RVW_HOME/scripts/with-lock.sh" vex nice -n 10 rvw regress cocotb \
  pmp-icarus.json --out out/pmp-icarus --seed 1 --json
"$RVW_HOME/scripts/with-lock.sh" vex nice -n 10 rvw regress cocotb \
  pmp-verilator.json --out out/pmp-verilator --seed 1 --json
```

Install `rvw[cocotb]` first. Each output directory must be new. RTL and outputs
are ignored by Git. See [adapter contracts and limits](../../../rvw/src/rvw/sim/README.md).

## PLIC controller adapter

`rvwvex.PlicUnit` emits the unmodified SpinalHDL 1.15.0 PLIC library with
three level sources, two target contexts and an APB3 register interface.
`plic_bus.py` drives that interface. Expected state comes from the independent
Python PLIC reference. The test changes source levels during APB accesses.
It checks arbitration, tie breaking, threshold, shared pending state and
claim/complete gateway behavior across both contexts.

Generate RTL with the same setup as above. Replace the main class with
`runMain rvwvex.PlicUnit ../cocotb/rtl`. Then run:

```sh
"$RVW_HOME/scripts/with-lock.sh" vex nice -n 10 rvw regress cocotb \
  plic-icarus.json --out out/plic-icarus --seed 1 --json
```

`claim_must_ignore_threshold` is a conformance test for a known source-level gap.
The library gates the claim value with the interrupt threshold. The reference
requires a claim to select an enabled pending source regardless of threshold.
A mismatch makes the native suite fail. Do not waive this failure.
The other test checks the directed arbitration sequence. A CPU is not connected to this component
adapter. Real-core PLIC delivery and full simultaneous context arbitration
remain open in #131. Do not use this suite to claim complete PLIC compliance.

## Core reset lifecycle

`rvwvex.LifecycleUnit` uses the unchanged VexTop configuration. It adds output
observations for privilege, machine status and WFI activity. Generate it with
`runMain rvwvex.LifecycleUnit ../cocotb/rtl` under the same `vex` and `sbt` locks.
Run `reset-icarus.json` with `rvw regress cocotb` under the `vex` lock.

The test pulses synchronous reset on one native instance. It checks cold reset
and three rounds of warm reset during a stalled fetch, a stalled data request
and ECALL trap entry. The declared contract checks M-mode, MIE/MPIE clear,
MPP=M, invalid retirement and trap outputs, and the first fetch at 0x80000000.
Each reset discards harness-owned bus responses. General-purpose registers
have no reset contract here. The test does not use their initial values.
The current example has no local reset or debug port. Those parts of #111
remain open. A system reset does not establish local reset behavior.
