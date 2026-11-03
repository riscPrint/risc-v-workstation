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
wave (20 cycles of BOOM small: 5 s, 0.9 GB; 2,500 cycles: 34 GB).
`rvw bundle` now requests `--spinaltrace` from the standard adapter. This prototype
stays as the old implementation for dependency-trace parity checks.

Remove this directory only after a BOOM failure bundle has equal old/new
signatures, cycles, criteria and dependency traces. Use the same ELF, seed,
model options and wave window under the `boom` lock. Normalize generated IDs
and checkout paths before comparing source statements and dependency edges.
Record the measured result in the PR.
It starts through sbt and compiles the BOOM checkout,
so run it under `scripts/with-lock.sh boom`.
