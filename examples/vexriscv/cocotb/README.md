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
