# Sail M campaign on VexRiscv

The formal profile is `FormalMTop.scala`. It has RV32IM, native RVFI, simple
instruction and data buses, and a CSR controller. It has no compressed ISA.
It is separate from both the older FormalSimple RV32IC snapshot and the
workstation simulation profile. Results from these profiles must stay separate.

Core revision: `baf7dc82f855eddaf5b0a20a6802c526f127e38a`.
The measured build used SpinalHDL
`de72faf6062206a89b445e5cc07e32ed982712c8`, Scala 2.13.14 and JDK 21.
It reused the pinned compiler classpath built for the private VexiiRiscv example.
`build_m.py` can compile the profile with that supplied classpath and plugin.
The standard example sbt build uses the released SpinalHDL 1.15.0. That is a
different emitter profile and has no result substituted in this table.

Three controller transition checks now use this same export. Exception and
interrupt entry passed through cycle 25. Machine return failed at step 15.
See [the controller record](MACHINE_M.md). Full machine signoff remains incomplete.

```sh
rvw/.venv/bin/python examples/vexriscv/formal/build_m.py \
  --source "$VEXRISCV" --classpath "$CLASSPATH_FILE" --plugin "$IDSL_PLUGIN" --out BUILD
rvw formal sail-m --model "$SAIL_MODEL" --compiler "$SAIL_COMPILER" --out MODELS
rvw/.venv/bin/python examples/vexriscv/formal/sail_m_corners.py --models MODELS
rvw/.venv/bin/python examples/vexriscv/formal/run_sail_m.py \
  --rtl BUILD/rtl/VexRiscv.v --riscv-formal "$RISCV_FORMAL" --models MODELS --out RESULTS
```

Use `vex-conn` or another private core lock around native builds and campaigns.
Use `nice -n 10`. The campaign starts at most three native jobs. Each job runs
assertions, general retirement cover and instruction-specific activation in
sequence. The generated project can also run through
`rvw formal isa --project RESULTS/project --out ISA_RESULTS`.

The campaign constrains interrupt and bus error inputs to zero. Other bus
inputs stay unconstrained. It uses actual arithmetic, without
`RISCV_FORMAL_ALTOPS`. The default multiply bound is 20. Divide and remainder
use 60. Use `--mul-depth 60` to repeat the initial uniform-bound campaign.
`--checks mul,mulh,mulhsu,mulhu` selects a multiply retry.

## Measured results

Sail 0.20.1 generated all eight models from the pinned Sail model
`549e723031b34b5ffea5bbb56367be15c7a38a9e`. Each final model passed Yosys
parsing and hierarchy checks. All 392 Icarus arithmetic corner comparisons
passed. This is preparation and finite simulation evidence.

The initial native campaign used depth 60 and a 90-second limit per job.

| Instruction | Assertion job | Target cover | Outcome |
| --- | --- | --- | --- |
| MUL | timeout | reached | inconclusive |
| MULH | timeout | reached | inconclusive |
| MULHSU | timeout | reached | inconclusive |
| MULHU | timeout | reached | inconclusive |
| DIV | timeout | timeout | inconclusive |
| DIVU | timeout | timeout | inconclusive |
| REM | timeout | timeout | inconclusive |
| REMU | timeout | timeout | inconclusive |

No initial assertion proof closed. A reached multiply cover does not replace
its timeout. Divide and remainder activation remain unclosed.

RTL SHA-256:
`420f2d5bd0100a07ca48542d232c76e8048a4bb73e03757e51cd1aa664027a37`.
Model manifest SHA-256:
`8f6fb720c3fbf10bffd77b377a8a8110578f53a49342469b535be355bd43b91f`.
Private evidence directories are `sail-m-v3`, `vex-m-rtl-v2` and
`vex-sail-m-v1` under the worker's private evidence tree. The native build
first failed because the bus plugins needed an exception service. Adding the
project CSR plugin supplied that service. The next elaboration passed in 3.700 s.

## Multiply retry at depth 20

The four multiply assertion jobs also timed out with a 120-second limit at
cycle 20. All four instruction activation covers reached. The outcomes remain
inconclusive. Evidence directory: `vex-sail-m-short-v2`. The RTL and model hashes
match the initial campaign. No failed result was changed to a pass.
