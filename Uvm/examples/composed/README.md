# Composed SoC scenario bench

This project consumes the SpinalSoc composer and fabric. It supplies a
bounded APB bus master and one test peripheral. It executes no CPU program.
The peripheral exposes explicit wait, error and IRQ injection pins.

```sh
rvw soc compose Uvm/examples/composed/compose.json --out Uvm/examples/composed/generated
cd Uvm/examples/composed/spinal
../../../../scripts/with-lock.sh sbt nice -n 10 sbt 'runMain uvmsoc.Generate ../rtl'
cd ../../../..
scripts/with-lock.sh uvm-soc nice -n 10 rvw/.venv/bin/python \
 Uvm/examples/composed/smoke.py --out /tmp/composed-scenarios
```

The pyuvm test runs the shared `SocScenarios` backend at scenario seeds 1 and 7.
The simulator seed is 1.
The interrupt storm checks 32 actual peripheral IRQ pulses and their bit-11
routing to the core wrapper. It does not check CPU trap entry or handlers.
The bus-error case checks PSLVERROR and the absence of a write side effect.
The reset case starts a stalled write, checks that it is pending, resets
the fabric and peripheral, checks the abort, then reads the reset value.
Reset also stops the old driver task and clears its pending transaction.

Each seed writes `scenarios-SEED.json` only after all checks complete.
The reports state `cpu_checks=0`. A generated design alone is not runtime
evidence. The composer and shared peripheral implementations are unchanged.

The project runner stages Spinal's RAM initialization image. It suppresses
`WIDTHTRUNC` for the generated word-address index. Shifting the 14-bit byte
address right by two leaves two zero upper bits before the 12-bit assignment.
Other warnings remain fatal. Verilator assertions remain enabled.

Native results on 2026-11-13 used Verilator 5.052, SpinalHDL 1.15.0,
cocotb 2.1.0 and pyuvm. Both seeds passed. Each seed checked 32 IRQ pulses,
one injected error response, the absence of the failed write's side effect,
one pending-write reset abort and the peripheral reset value. CPU checks: 0.
Local evidence: `$VEXRISCV/uvm-runs/composed-scenarios-final/results.json`.

The design was regenerated after the composer update. Both seeds passed again.
See [the current measured result](native-2026-11-13.json) for source and RTL hashes.

The final regeneration used composer commit `2f961dde`. Both native tests passed.
