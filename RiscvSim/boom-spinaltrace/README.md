# RiscvSim/boom-spinaltrace (prototype)

BOOM's run-contract adapter (C1) with a **SpinalTrace-instrumented model**, so `rvw bundle` can trace
a failing assertion back to the Spinal statements that caused it (`spinaltrace-cli dyn-pdg`).

It reuses RiscvSim's generic `Driver` and `riscvsim.boom.BoomAdapter`'s run loop unchanged; only the
model build differs (`TracedBoomAdapter.compile` goes through `SpinalTraceSim.compile`: SpinalTrace's
probe-naming phase, two-pass located elaboration, `pdg.json`). The naming phase adds no logic, so a
seed that fails on the plain model fails the same way here. `result.json` gets `details.pdg` (the
PDG, kept under `$RISCVSIM_WORK/spinaltrace/`) and `details.spinaltrace = true`.

```sh
RiscvSim/boom-spinaltrace/run.sh run --elf ELF --out DIR --config large --seed 1 \
    --wave --wave-from 412000 --wave-to 412050      # same options as RiscvSim/boom/run.sh
```

Always pass a wave window: the model is built with tracing, and `dyn-pdg` unrolls every cycle of the
wave (20 cycles of BOOM small: 5 s, 0.9 GB; 2,500 cycles: 34 GB). `rvw bundle` uses this adapter
automatically through `[spinaltrace].adapter` in `RiscvSim/boom/debug.toml`.

Why a separate project: it needs the SpinalTrace library on the classpath, which the plain adapter
does not. Suggested final form: a `--spinaltrace` model flag in `RiscvSim` (`ModelKey.spinaltrace`,
applied in `BoomAdapter.compile`, PDG recorded as the `pdg` artifact), which removes this directory.
It starts through sbt and compiles the BOOM checkout,
so run it under `scripts/with-lock.sh boom`.
