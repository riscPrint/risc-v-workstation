# Executed resource scenario

This example compiles one scenario into an RV32 bare-metal test and a pyuvm
virtual sequence. Both execute the real composed VexRiscv SoC. The virtual
sequence starts the generated CPU image and observes its MMIO transfers. It is
not an independent bus master or an independent stimulus backend.

The scenario has 12 serialized actions. It writes and reads UART scratch,
CLINT MSIP and PLIC source-1 priority. It reserves one CPU and one MMIO resource.
The assembly checks the six read values and writes the finisher. The pyuvm
sequence checks all 12 transfer values. Both observation streams pass through
`formal scenario check`. Their outputs are also compared by action ID.

## Run

Use this worktree's installed rvw interpreter. Set `VEXRISCV` to a private core
copy. Source the JDK 21 and OSS CAD Suite environment. Install the optional
`pyuvm` dependency group. The measured run used pyuvm 4.0.1 and cocotb 2.0.1.
Use a worktree with no existing `SpinalSoc/generated` directory. Commands below
write only in this worktree and its private core build directories.

From the workstation root:

```sh
rvw/.venv/bin/python examples/vexriscv/scenarios/prepare.py prepare --out rvw/out/scenario
riscv64-unknown-elf-gcc -march=rv32im_zicsr -mabi=ilp32 -nostdlib -nostartfiles \
  -T rvw/out/scenario/link.ld rvw/out/scenario/program.S -o rvw/out/scenario/program.elf
rvw/.venv/bin/python examples/vexriscv/scenarios/prepare.py elaborate-input --out rvw/out/scenario
cd SpinalSoc
../scripts/with-lock.sh sbt-sva nice -n 10 sbt -batch -Drvw.soc.vex=true \
  compile 'export Runtime/fullClasspath' 'runMain generated.Generate ../rvw/out/scenario/rtl'
cd ..
rvw/.venv/bin/python examples/vexriscv/scenarios/run.py baremetal --out rvw/out/scenario
scripts/with-lock.sh vex-sva nice -n 10 rvw/.venv/bin/python \
  examples/vexriscv/scenarios/run.py pyuvm --out rvw/out/scenario
rvw/.venv/bin/python examples/vexriscv/scenarios/run.py check --out rvw/out/scenario
```

The generic generation command is also available:

```sh
rvw formal scenario-compile --source examples/vexriscv/scenarios/scenario.json \
  --finisher 0x10001000 --out rvw/out/scenario-source --json
```

Generation reports `generated`. It does not execute either backend.

## Measured result

On 2026-11-13, with VexRiscv `a62c145a`, SpinalHDL 1.15.0 and Verilator 5.049:

| Consumer | Native result | Observations |
|---|---|---|
| Bare-metal self-check and APB capture | pass; 324 measured cycles, 54 retirements | all 12 values match |
| CPU-backed pyuvm virtual sequence | 1 test passed, 0 failed, 0 skipped | all 12 values match |
| Shared scenario checker | both match | 24 comparisons; no missing records, dependency overlaps or resource conflicts |

Read [the compact evidence](results.json). Raw C1, C3, JUnit, APB samples and
observations stay in the selected output directory.

The first pyuvm build stopped on the library bridge's implicit narrowing after
an address shift. The wrapper makes the existing assignment conversion explicit
with a sized cast in the pyuvm RTL copy. This changes no assigned bits. It does
not suppress warnings or remove assertions. Two such casts were inserted.
Memory initialization files are copied and hashed. The wrapper resolves their
paths and checks that their bytes stay unchanged during native execution.
The earlier build and missing-image failures remain in the local run artifacts.

## Limits

Execution is serial. The two consumers use the same CPU program. This does not
provide independent stimulus generation or a general pyuvm bus executor.
Dynamic produced data, symbolic constraints, randomized schedules and PSS
parsing remain unsupported. Backend durations are planning data. Observation
timestamps come from RTL samples. This run does not qualify all peripheral
behavior, interrupts, CPU correctness, input closure, C4 acceptance or hardware.
