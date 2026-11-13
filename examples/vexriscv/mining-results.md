# ISA trace property candidates

Native run on 2026-11-13. The existing compiled Scala property harness ran all
49 aligned ISA programs. All 49 passed with zero assertion failures. It wrote
42,769 pre-edge signal samples in 49 separate traces. The VexRiscv source is
`a62c145aa042a5de874344e0a7683bd7c8c8c870`. The signal bindings live in
`mining-signals.json`. No transition joins two programs.

The miner retained 87 candidates: 27 Boolean implications, 46 guarded stable
relations, 13 mutex pairs and one declared one-hot-or-zero set. It dropped 730
refuted candidates and 57 candidates with insufficient activation. Each retained
candidate has at least two antecedent matches. Each mutex or one-hot set member
also appeared at least twice.

| Example candidate | Activations | Evidence |
|---|---:|---|
| stage0 fire implies stage0 valid | 17,931 | finite observed candidate |
| stage0 stuck implies next stage0 PC equals prior PC | 2,232 | finite observed candidate |
| stage0 fire and stage0 stuck are mutually exclusive | 20,163 | both members observed |
| stage0 fire/stuck one-hot-or-zero set | 20,163 | both members observed |

Read [the compact counts](mining-results.json) and
[the generated DSL candidates](MinedProperties.scala). The DSL is not enabled
in the example build. Some retained relations concern signals which were
constant in this suite. Such relations can depend on this memory model or this
program set. None of these candidates has a fresh formal proof from this run.
Do not use candidates as assumptions.

## Repeat

Set up the private VexRiscv copy and elaborate `CoreProperties` as described in
[the property run](README.md#scala-dsl-property-campaign). Run the
existing aligned ISA ELF list with optional capture:

```sh
scripts/with-lock.sh vex-sva nice -n 10 rvw/.venv/bin/python \
  examples/vexriscv/rvw/core-properties-sim.py --samples \
  --rtl RTL_DIRECTORY --out NEW_RUN_DIRECTORY ELF...
rvw formal trace-mine --manifest examples/vexriscv/mining-signals.json \
  --trace NEW_RUN_DIRECTORY/PROGRAM/samples.jsonl --out NEW_CANDIDATE_DIRECTORY
```

Repeat `--trace` for all 49 programs. Do not include `rv32ui-p-ma_data`. This
core does not implement its expected misaligned-access behavior. The measured
command selected it by an overly broad glob: it failed, while the other 49
programs passed. Its failed C1 result stays in the local run directory. It was
excluded from this aligned-suite candidate report. Native build logs, samples
and per-program C1 results stay under the selected output directory.
