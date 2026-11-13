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
The fixture also runs a constrained LR/SC retry loop with no conflicting writer.
It has LR, SC and a backward BNE within 16 consecutive instructions. The retry
path has no other memory access, fence or system instruction. Test mode 10
permits three legal spurious failures, then services SC. Each hart has a port
slot every eight cycles and the environment enables it within three cycles.
The independent memory observer checks that failed SC has no write effect.
Mode 11 never services SC successfully. The test must reject that mode at the
fourth failed attempt. This is a bounded service test under explicit fixture
conditions. It does not prove general ISA eventuality or production-core progress.

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

Select `--suite amo-fault` in `run.py` for aligned access-fault tests. This is
opt-in. The target must support a locked NAPOT PMP region. The program makes a
64-byte region readable and not writable. It checks the effective PMP setting
before testing all nine AMOs, each width and aq/rl encoding. Each AMO must raise
store/AMO access fault (cause 7). The handler checks `mepc` and `mtval`, then
returns past that instruction. The test checks that the destination register,
operand and every adjacent byte in the protected region stay unchanged. These
are precise access-fault checks. They do not test misaligned accesses or imply
concurrent aq/rl ordering. Missing PMP support is a failure for this selected
platform test. It must not be silently skipped or treated as a generic ISA fault
policy.

```sh
rvw/.venv/bin/python RiscvSim/tests/ordering/run.py --out /tmp/amo-fault \
  --xlen 64 --seeds 7 --suite amo-fault
# Add --adapter /absolute/path/to/run.sh for the DUT.
```


## FENCE and independent observation

The FENCE program exercises 49 predecessor/successor combinations, with seeded
values and order. RAM loads check local visibility. No device accesses occur.
This exercises encodings; it does not check the ordering of device accesses.

`observer.py PLAN.json OBSERVATION.json` checks required edges from a test plan.
The project must supply an independent bus or device monitor. The BOOM adapter
supplies an external TileLink capture. See the bus checker below. Do not use
retirement records as monitor input.

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

`litmus-pins.json` pins six tests from the
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
The smoke set covers SB, MP and LB, each with and without full memory fences.
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
The separate `CoherentCacheNativeSpec` checks real cache writeback and accepted
TileLink channel backpressure. See the RiscvSim README. Cyclic resource waits
remain outside these checks under #128. The fixture measures bounded enable
and grant fairness with `FairnessMonitor`.

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

The fixture checker requires all six pinned cases. It verifies the full allowed
outcome set against canonical hashes in `litmus-pins.json`. These hashes pin
reference-model expectations. They do not come from fixture observations.
Regenerate the reference report after a pin change. A stale or partial report
cannot earn consistency.

### External bus order plans

`bus_observer.py PLAN.json memory-bus.jsonl` converts BOOM's independent bus
capture to ordering intervals. It checks the existing plan `edges`.
Add `accesses` with unique `id`, unique hex `address`, `class`, TileLink A `opcode`
and `size_log2`. Optional `data`, `mask` and `expected_read_data` are hex strings
from stimulus. Only single-beat Get and Put requests are supported. The plan
boundary must be `accepted-external-tilelink`. Each address must occur once.
The checker matches source IDs and D responses. A denied response, changed data,
missing request or incomplete capture stays inconclusive. A cache hit cannot
satisfy an external-access plan. Device-side completion needs another observer.
The project must classify accesses from its PMA map. No real-device campaign
is supplied by this converter. #102 remains open for those target checks.

## Configured Zacas campaigns

Zacas tests are opt-in. Run these only on a declared Zacas implementation:

```sh
python RiscvSim/tests/ordering/run.py --suite zacas --xlen 64 --seeds 7 --out /tmp/cas
```

The runner adds `_zacas` to the compiler and Spike ISA. The generator uses raw
AMOCAS encodings. It tests W/D on RV32 and W/D/Q on RV64, all aq/rl encodings,
success and failure, signed-extreme and seeded operands, returned values,
word sign extension, guard bytes and double-XLEN operand pairs. Separate x0
cases check that both halves read zero or are discarded. A nonzero x1 detects
accidental use of the second register in an x0 pair.

`--suite zacas-fault` requires locked NAPOT PMP. A read-only 64-byte region
must raise store/AMO access fault for every tested width and aq/rl combination.
The program checks cause, fault PC, nonzero trap address, unchanged destination pair,
trap count and every byte in the region.

`--suite zacas-align` requires a platform without a misaligned atomicity
granule for these operands. It checks address-misaligned or access-fault
exceptions at byte offset one. The program checks the same unchanged state.
This profile must not run on a platform that permits those misaligned atomics.

Reserved odd pair encodings are not assigned mandatory behavior. The suite
does not require a particular trap for a reserved encoding. Unsuccessful CAS
may write back its unchanged old value. Only the resulting bytes are checked.
These rules follow the [Zacas 1.0 specification](https://riscv.github.io/riscv-unified-db/manual/html/isa/isa_20240411/chapters/zacas.html).

Native Spike smoke tests cover the programs and injected missing CAS, wrong
return and failed-CAS write defects. No RTL or concurrent observer is supplied
by these programs. Integer matches do not establish contention atomicity or
external acquire/release ordering. The default four suites are unchanged.

### Reference fallback without herd7

If herd7 is installed, `--herd-source` remains required. The runner checks the
pinned executable version, model library and test bytes before execution.
If herd7 is absent, the runner reads `model-results/herd.logs` from the external
suite at the same pinned revision. It verifies the full log SHA-256 and each
test hash. It requires one complete state block for each of the six tests.

```sh
python RiscvSim/tests/ordering/litmus.py --tests /tmp/rv-litmus --out /tmp/recorded
```

The fallback report says `reference_source: suite-recorded`. Its native herd
version and executable hash are null. These are historical suite expectations,
not a new run of the pinned herdtools7 7.58 model. The fixture planner checks
their complete allowed-set hashes as before. The DUT remains `not_run` unless
an adapter supplies complete observations. The same forbidden-outcome checker
handles both reference sources. Do not use these RVWMO sets to qualify Ztso.

## Configured cache-block byte campaigns

Select `--suite cbo --cache-block-size 64` on the existing generator or runner.
The size is mandatory and must match the target's declared CMO size. Supported
campaign sizes are powers of two from 16 to 4096 bytes. Native Spike receives
`--blocksz` with that size. The runner records the ISA and block size.
The target adapter must select a matching platform configuration itself.

The machine-mode program uses Zicbom, Zicboz and Zicbop. It fills three aligned
blocks with seeded nonzero bytes. It zeros the middle block through addresses
at its start, middle and last byte. It checks every zeroed byte and both full
adjacent blocks. It then executes clean, flush and invalidate with explicit
fences and checks retained data. Invalidate runs only after clean/flush with
no later dirty store. Prefetch R/W/I hints must preserve memory. They do not
have a required cache allocation, completion or ordering effect.

The [CMO 1.0 specification](https://riscv.github.io/riscv-unified-db/manual/html/isa/isa_20240411/chapters/cmo.html)
defines these byte and hint rules. This program does not assume block zeroing
is one atomic store. Native fault checks remove zeroing, zero only part of a
block or corrupt an adjacent byte. Each defect must fail the program.

Limits: native Spike checks architectural byte assertions. No clean/flush
writeback, device observation, RTL cache behavior, privilege-control matrix
or concurrent agent campaign is established. Those require a project observer.
The default suites are unchanged. Unsupported extensions must not be selected.

### Pinned Ztso model selection

Use `litmus.py --model ztso --herd /path/to/herd7 --herd-source /path/to/source`
with the same pinned suite. The model is `riscv-tso.cat` in herdtools7 7.58 at
`1ca343e16a2038e406d1ac674e7e3a1b722b36c7`. The existing full library hash
covers this model and its includes. Reports record `memory_model`, `model_file`
and the reference source. Allowed-set hashes are separate for RVWMO and Ztso.
The fixture planner validates the selected model's complete pinned sets.

Add `--declared-ztso` only when the project declares DUT support. A Ztso DUT
adapter run requires that declaration. Reference-only generation leaves
implementation support `not_verified`. No RVWMO recorded fallback is available
for Ztso. Missing native herd gives inconclusive. Device ordering remains a
separate platform obligation.

Native model smoke checks retain SB's all-zero outcome and exclude the MP
message-passing violation and LB's all-one outcome. These are model results,
not evidence that a DUT implements Ztso. No target Ztso support is inferred.

Zacas fault profiles accept `mtval=0` where the platform permits it. A nonzero
value must equal the fault address. This follows the [machine trap-value
rules](https://docs.riscv.org/reference/isa/priv/machine.html). The fault PC,
cause, unchanged destination pair and unchanged memory remain mandatory.

## RV64 concurrent subset smoke

`riscvsim.Rv64AtomicFixtureSpec` extends the existing two-hart subset fixture to
64-bit data. It checks all nine doubleword AMOs and all four aq/rl encodings,
external LR/SC invalidation, and contended doubleword Zacas with a failed CAS
and a successful retry. Independent operands and initial bytes drive the
`AtomicMemoryObserver`. The DUT supplies old data, complete post-action bytes
and an adjacent guard word. Seed defects cover torn writes, wrong returns,
missing reservation invalidation, adjacent corruption, missing CAS writes and
failed-CAS writes.

Run only this tiny fixture with the sbt lock:

```sh
cd RiscvSim
RVW_RV64_TRACE_OUT=/tmp/rv64-traces ../scripts/with-lock.sh sbt nice -n 10 sbt -batch 'testOnly riscvsim.Rv64AtomicFixtureSpec'
```

The optional output contains 40 C2/2 AMO/LRSC traces. Empty dependency sets are
complete for these constant-address, constant-operand, branch-free snippets.
The memory checker accepts decimal strings for full-width annotation values.
Check them with `rvw memory axiomatic` and an initial location at address zero,
size eight and value zero. Both RVWMO and Ztso allowed all 40 native traces in
the bounded smoke. CAS stays outside the scalar axiomatic capture profile.

This fixture has a serialized shared-memory port and a small instruction
subset. It is not a production RISC-V core. Encoding coverage is not external
aq/rl ordering evidence. Word/quadword CAS contention, production adapters and
weak-memory RTL campaigns remain open.


## Production SMP execution

The [cacheless SMP example](../../../examples/smp/README.md#measured-results)
links these LR/SC and AMO programs into separate hart images. Both run on two
real VexiiRiscv RTL instances. At seed 17, LR/SC passed with 498 retirements in
1060 cycles. AMO passed with 8346 retirements in 18630 cycles. Each hart keeps
private functional-test operands. Generated programs exercise shared targets.

The same example captures all six pinned litmus cases for the outcome checker.
All six seed-17 outcomes are consistent with native herd7 7.58. Its cross-hart
FENCE.I, IPI and HSM runs passed with 62/74/530 retirements in 191/247/1431 cycles.
The HSM observer checks two starts and one stop. Shared-RAM Spike comparison
matched 38 instructions with no masks or synchronizations. These captures are
bounded RTL evidence. They do not turn the fixtures above into whole-core
coherence proofs or establish complete outcome coverage.
