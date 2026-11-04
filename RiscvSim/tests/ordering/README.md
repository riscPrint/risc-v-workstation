# Ordering suites

These sources use the C1 ELF contract. They contain no core names or signals.
Run them from any project with an RV32IMA or RV64IMA target and Zicsr/Zifencei.
The link script assumes executable, writable RAM at 0x80000000 and `tohost` support.
Use `--linker PROJECT.ld` for a different memory map. Machine traps mean failure.

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
both legal SC outcomes. The reservation set can include both addresses. The test
accepts success or failure at the second address. It checks the target bytes and
checks that the source bytes stay unchanged. It also checks that each SC consumes
the reservation. It clears both operands at full width before each case. A successful SC must write. A failed SC must not write.
It accepts spurious failure. It does not require success within a fixed time.
Do not use exact Spike lockstep for an unconstrained LR/SC run: two legal runs
can take different SC branches. The program checks each branch's required effects.

These single-hart ELF tests do not check external reservation invalidation or
independent memory observation. The fixture below adds those bounded checks.
Constrained-loop eventual progress remains untested. A finite cycle limit cannot
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
These ELF tests do not check concurrent observers or external aq/rl ordering.
The fixture below adds concurrent observers and injected faults.

## FENCE and independent observation

The FENCE program exercises 49 predecessor/successor combinations, with seeded
values and order. RAM loads check local visibility. No device accesses occur.
This exercises encodings; it does not check the ordering of device accesses.

`observer.py PLAN.json OBSERVATION.json` checks required edges from a test plan.
The project must supply an independent bus or device monitor. No current adapter
supplies this monitor. Do not use retirement records as its input.

A plan declares `boundary` (a platform-defined string) and `edges`, for example
`{"boundary":"device-visible","edges":[["write","read"]]}`.
An observation declares the same boundary, `independent:true`, `complete:true`
and an `events` list. Each event has a unique `id`, class `r`, `w`, `i` or `o`,
and integer `issue` and `complete` timestamps from the monitor's common clock.
For each required edge, predecessor completion must precede or equal successor
issue. Define completion at the selected boundary in the project test plan.
Missing events, incomplete monitoring and empty edge sets stay inconclusive.
A reversed or overlapping required edge is a mismatch. Other edges are unchecked.
The project owns class assignment, completeness and monitor independence.
The checker cannot certify those declarations. Its tests use synthetic monitors.

## FENCE.I

The program first executes each patch site. It then replaces its `addi` bytes,
executes FENCE.I, calls the site again and checks the new result. Three sites use
128-byte alignment with offsets 0, 60 and 124. Each gets eight seeded patches.
This requires writable executable RAM and a coherent data path for instruction
stores. It checks same-hart visibility after synchronization. The unsynchronized
outcome is deliberately unchecked. Cache geometry, pending fetch requests and
cross-hart publication require project-specific stimulus and remain untested.

## RVWMO litmus

`litmus-pins.json` pins four tests from the
[official RISC-V concurrency collection](https://github.com/litmus-tests/litmus-tests-riscv)
and the herdtools7 7.58 model library. No third-party sources are copied here.
The [collection README](https://github.com/litmus-tests/litmus-tests-riscv/blob/08728edcd99c7e1819d2d4c6789df6d5299ccb69/README.md)
explains its use by the RISC-V Memory Model Task Group.

Use native `opam install herdtools7.7.58` to install the reference tool.
Prepare source checkouts outside this repository:

```sh
git clone https://github.com/litmus-tests/litmus-tests-riscv.git /tmp/rv-litmus
git -C /tmp/rv-litmus checkout 08728edcd99c7e1819d2d4c6789df6d5299ccb69
git clone https://github.com/herd/herdtools7.git /tmp/rv-herd
git -C /tmp/rv-herd checkout 1ca343e16a2038e406d1ac674e7e3a1b722b36c7
rvw/.venv/bin/python RiscvSim/tests/ordering/litmus.py \
  --tests /tmp/rv-litmus --herd-source /tmp/rv-herd \
  --herd "$HOME/.opam/default/bin/herd7" --out /tmp/rv-outcomes
```

The runner verifies revisions, selected test bytes and the whole model library.
It checks the tool version and records the executable hash. The tool version
alone cannot certify a custom executable's source. Use the pinned native release.
The model uses `riscv.cat`. Allowed sets come only from herd, never from the DUT.
The output contains every allowed final-register state and separate raw logs.
The smoke set covers SB, MP, LB and SB with full memory fences.
It does not cover the whole upstream collection. It does not use isla-axiomatic.

When a multi-hart target exists, add `--dut-adapter /path/to/project-script`.
The runner calls that script with one absolute `.litmus` path. The script owns
translation, target loading, shared-memory initialization, hart start barriers,
execution, observation and iteration reset. It must implement the same litmus
semantics. It writes only this JSON to stdout:

```json
{"harts":2,"complete":true,"observations":[{"state":{"0:x7":0,"1:x7":1},"count":100}]}
```

Return every final register in herd's projection. Do not omit failed or timed-out
iterations. Set `complete:false` if required observations are missing.
No target means `dut:not_run`. Empty or incomplete samples mean `inconclusive`.
Any observed forbidden state means `mismatch`. Permitted states not observed stay
in `permitted_not_observed`. A consistent finite sample is not exhaustive proof.
The bounded fixture path below executes these tests on subset RTL harts.
No production multi-hart core adapter is supplied.

## Tests

```sh
rvw/.venv/bin/python -m pytest rvw/tests/ordering -q
RVW_SPIKE_SHIM=/path/to/librvw_spike.so RVW_SAIL=/path/to/sail_riscv_sim \
  rvw/.venv/bin/python -m pytest rvw/tests/cosim/test_ordering_reference.py -q
```

The second command compares Spike-generated traces with Sail for one RV64 seed.
It is a reference cross-check. It is not a DUT comparison.
The first command runs assertions on Spike for both XLENs and three seeds.
Observer and outcome tests include forbidden and missing-evidence cases.
Synthetic SC tests run the generated checker on Spike. They cover operand-sized
and 64-byte reservation sets, legal outcomes, wrong memory effects and reuse of
a consumed reservation. These are checker tests, not DUT geometry evidence.

## Bounded two-hart RTL fixture

`AtomicFixtureSpec` extends the round 2 `FixtureHart`. It runs two RV32 subset
interpreters in native Verilator. It checks word LR/SC external invalidation,
SC without reservation, successful SC without interference, all nine word AMOs
and all four aq/rl encodings. Both harts access shared memory while a separate
observer checks every memory word each cycle. Expected values come from program
operands and an independent integer model, never from DUT read data.

The fixture serializes memory operations. It gives each hart a slot every eight
cycles. After test barriers, the environment enables each hart within three cycles.
The invalidation test orders LR, the external store and SC with start barriers. A logical
request has a 32-cycle deadline and retains its identity during retries.
The campaign has a 400-cycle limit. These are bounded fixture checks under stated
environment conditions. They do not prove constrained LR/SC eventuality or general
arbiter fairness. No unbounded liveness claim follows.

The fixture has per-word N/B/T permissions. Tests connect observed changes to
`CoherenceMonitor`. They check intervention, invalidation, dirty-data transfer,
racing requests under port backpressure and explicit final eviction. These are
fixture permission transitions. They are not accepted TileLink-C channel events.
There are no caches, resource dependency graphs or full RISC-V implementations.
Real cache writeback, channel backpressure, cyclic resource waits and independent
fairness measurement remain open under #108 and #128.

Fault controls omit reservation invalidation, expose a partial AMO write, corrupt
an AMO return, retain a conflicting permission, omit dirty transfer, starve one
hart, or retry both requests without completion. Each negative test requires its
specific checker message. The litmus fault returns 2 for loads. For that isolated
outcome-checker test, value assertions are disabled and final registers come from
RTL. Its observed states must be rejected by the herd outcome checker.

Run the reference and prepare the plan first. Use fresh output paths:

```sh
rvw/.venv/bin/python RiscvSim/tests/ordering/litmus.py \
  --tests /tmp/atomics-litmus --herd-source /tmp/atomics-herd \
  --herd "$HOME/.opam/default/bin/herd7" --out /tmp/mhart2/herd
rvw/.venv/bin/python RiscvSim/tests/ordering/fixture.py \
  --reference /tmp/mhart2/herd/outcomes.json --tests /tmp/atomics-litmus \
  --out /tmp/mhart2/plan.json
(cd RiscvSim && RVW_FIXTURE_PLAN=/tmp/mhart2/plan.json \
  RVW_FIXTURE_OUT=/tmp/mhart2/samples.json \
  ../scripts/with-lock.sh sbt nice -n 10 sbt -batch -J-XX:ActiveProcessorCount=2 \
  'testOnly riscvsim.AtomicFixtureSpec riscvsim.TwoHartNativeSpec riscvsim.CoherenceMonitorSpec riscvsim.ProgressMonitorSpec')
rvw/.venv/bin/python RiscvSim/tests/ordering/fixture.py \
  --reference /tmp/mhart2/herd/outcomes.json --samples /tmp/mhart2/samples.json \
  --out /tmp/mhart2/comparison.json
# This fault comparison must exit 1 (forbidden outcomes):
rvw/.venv/bin/python RiscvSim/tests/ordering/fixture.py \
  --reference /tmp/mhart2/herd/outcomes.json --samples /tmp/mhart2/samples.json.fault.json \
  --out /tmp/mhart2/fault-comparison.json
```

Each pinned test runs 32 bounded seeded iterations.
Each seed controls independent hart enables. Every third cycle enables both harts. Missing plans fail the Scala test.
Missing, duplicate or incomplete samples cannot earn consistency. The comparison
lists permitted states not observed. Serial memory can miss legal RVWMO outcomes.
The fixture does not establish external aq/rl ordering, RV64 doubleword atomics,
architectural faults, or production multi-hart core behavior. The existing C1 ELF
suite supplies separate bounded single-hart checks on BOOM.

The fixture checker requires all four pinned cases. It verifies the full allowed
outcome set against canonical hashes in `litmus-pins.json`. These hashes pin
reference-model expectations. They do not come from fixture observations.
Regenerate the reference report after a pin change. A stale or partial report
cannot earn consistency.
