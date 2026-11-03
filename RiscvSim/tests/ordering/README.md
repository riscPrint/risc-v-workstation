# Ordering suites

These sources use the C1 ELF contract. They contain no core names or signals.
Run them from any project with an RV32IMA or RV64IMA target and Zicsr/Zifencei.
The link script assumes executable, writable RAM at 0x80000000 and `tohost` support.
Change the link script for a different memory map. Machine traps mean failure.

```sh
rvw/.venv/bin/python RiscvSim/tests/ordering/run.py --out /tmp/ordering --xlen 64
# Add --adapter /absolute/path/to/run.sh for a C1 DUT run.
```

The runner compiles the sources and runs their assertions on native Spike.
It writes a separate reference log per ELF. A reference failure stops the DUT run.
An adapter run uses the same ELFs and seeds. It omits `mem_latency` from the C1
manifest to select RiscvSim random timing. The seed reproduces that timing.
Use the project lock around a DUT run. The runner has a process-group timeout.
Reference-only success is not a DUT pass. Ordering stays `inconclusive`.

## LR/SC

The suite checks `.w` and, on RV64, `.d`, with all aq/rl encodings.
It checks SC without a reservation, SC to a different address and the bytes after
both legal SC outcomes. A successful SC must write. A failed SC must not write.
It accepts spurious failure. It does not require success within a fixed time.
Do not use exact Spike lockstep for an unconstrained LR/SC run: two legal runs
can take different SC branches. The program checks each branch's required effects.

Reservation invalidation by another agent, independent memory observation and
constrained-loop eventual progress remain untested. A finite cycle limit cannot
establish eventuality without environment and fairness assumptions.

## Decisions and limits

Spike validates single-hart assertions. It is not an RVWMO outcome oracle.
A retired load after a store does not establish external bus order.
These programs do not establish concurrent AMO atomicity or cross-hart visibility.
No pass from these programs closes those coverage gaps.

## AMO

All nine integer AMOs run at each supported width and aq/rl encoding.
Signed extrema and seed-based random operands exercise the returned old value,
new memory value, RV64 word sign extension and adjacent guard bytes.
The same assertions run on Spike before the DUT. This is a functional check.
Concurrent observers, faults and external aq/rl ordering remain untested.
