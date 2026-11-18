# SMP RTL examples

The cacheless C1 example runs two to eight RV64IMA VexiiRiscv RTL cores in Verilator.
Each core has a separate fetch bus, LSU bus, reset PC and retirement probe.
All cores use one simulation RAM. The simulation memory service implements
LR/SC reservations and the nine standard AMOs at word and doubleword widths.
It invalidates overlapping reservations when a write is accepted.

## Setup

Use a private external VexiiRiscv checkout. No core source is changed.
The pinned revision is `9f70315deb3390b283995c5b8f1bd38215ecf52b`.
Its SpinalHDL pin is `de72faf6062206a89b445e5cc07e32ed982712c8`.
Its rvls pin is `847ce99fd2b28a5c0ccb1ec2683311cf97a9fefc`.
Use JDK 21, sbt, Verilator and RISC-V GCC.

```sh
export RVW_HOME=/path/to/risc-v-workstation
export VEXIIRISCV=/path/to/private/VexiiRiscv
export RVW_VEX_LOCK=vex-mem
# For a new checkout only:
examples/smp/rvw/bootstrap.sh
source /path/to/spinal-boom/env.sh
export PATH=/opt/homebrew/opt/riscv-gnu-toolchain/bin:$PATH
rvw/.venv/bin/python examples/smp/rvw/programs.py --suite smoke --out examples/smp/rvw/out/smoke
examples/smp/rvw/run.sh run --config smp2 \
  --elf examples/smp/rvw/out/smoke/hart-0.elf \
  --hart-images examples/smp/rvw/out/smoke/hart-images.json \
  --out examples/smp/rvw/out/smoke-run --rvfi-trace --seed 17 --json
```

The launcher takes the private `vex-mem` lock. Compilation takes the private `sbt-mem`
lock. Outputs stay in this example or the private source directory.
Select `smp3` through `smp8` and build the same number of hart images for N harts.
Each entry must equal `0x80000000 + hart * 0x20000`.
RAM spans `0x80000000` through `0x81ffffff`.
Every hart must retire a nonzero store to its own ELF `tohost` symbol.
An incomplete hart prevents a passing C1 result.

## Trace and reference scope

The upstream retirement probe produces per-hart C2/2 streams in one file.
Capture order is not a memory-order oracle. The header declares physical addresses and unavailable memory dependencies.
The project scalar binding below can add complete dependency observations to
a separate derived trace. The original trace remains unchanged. Completion
alone does not establish RVWMO correctness.

Use `programs.py --suite amo` for 72 checks per hart. Each check verifies
the returned old value and the new memory value. The matrix covers nine AMOs,
two widths and four aq/rl combinations. Use `--suite lrsc` for successful
LR/SC retries and SC-without-LR failure at both widths. These programs use
separate target words per hart. They do not check cross-hart reservations.

## Decisions and limits

SpinalSoc currently exposes a single-core APB wrapper. This example uses a
small project-owned Spinal top instead. Core buses are separate RTL ports.
Shared RAM and atomic service are simulation models, not synthesized fabric.
There are no caches and no TileLink-C channels. Cache and coherence observer
bindings are therefore absent. This example cannot qualify coherent caches.
CLINT and a seven-source machine-context PLIC are simulation models.
CPU claim/complete races against this model are described below. The sections below describe the
bounded IPI, HSM and cross-hart instruction visibility programs. Do not use this example as a Linux-capable SoC.
The identity is available, but complete reusable build-input capture is not
claimed. `input_complete` remains false.

## Measured results

These runs used the pinned VexiiRiscv core on 2026-11-13. All harts must
complete. C1 retirement totals equal the parsed C2/2 record counts.
RAM, atomic service and devices are simulation models. These are RTL simulation
results, not hardware or full ISA qualification.

| Suite | Config | Seed | Cycles | Retirements | Result |
|---|---|---:|---:|---:|---|
| Three-hart smoke | smp3 | 17 | 86 | 35 | pass |
| LR/SC | smp2 | 17 | 1060 | 498 | pass |
| AMO | smp2 | 17 | 18630 | 8346 | pass |
| SB | smp2 | 17 | 82 | 26 | consistent with herd7 |
| MP | smp2 | 17 | 82 | 25 | consistent with herd7 |
| LB | smp2 | 17 | 82 | 26 | consistent with herd7 |
| SB+fence.rw.rws | smp2 | 17 | 82 | 28 | consistent with herd7 |
| MP+fence.rw.rws | smp2 | 17 | 81 | 27 | consistent with herd7 |
| LB+fence.rw.rws | smp2 | 17 | 82 | 28 | consistent with herd7 |
| Generated seed 1 | smp2 | 1 | 208 | 75 | allowed on checker recheck |
| Generated seed 7 | smp2 | 7 | 119 | 40 | allowed on checker recheck |
| Generated seed 17 | smp2 | 17 | 87 | 26 | allowed on checker recheck |
| Generated seed 23 | smp2 | 23 | 105 | 39 | allowed on checker recheck |
| Cross-hart FENCE.I | smp2 | 17 | 191 | 62 | pass |
| IPI | smp2 | 17 | 247 | 74 | pass |
| HSM | hsm2 | 17 | 1431 | 530 | pass |
| Spike shared RAM | serial2 | 17 | 122 | 38 | 38 instructions match; zero masks/sync |

Each litmus case has one captured outcome. Seed 17 used two generated program
steps. Seeds 1, 7 and 23 used four. An allowed execution is a finite checker
result. The original candidate-limit result was inconclusive. A later checker
recheck found a valid witness. The HSM observer saw two starts, two S-mode entries, one stop/stopped transition and two IPIs.
Clock/reset/power control and coherent-cache RTL remain unqualified.
The JSON files under `rvw/` record the RTL and trace hashes.


## Ordering campaigns

`suite_programs.py` links the existing portable LR/SC, AMO and fence programs
at each hart's private reset vector. It leaves their assertions unchanged.
For example, from the workstation root:

```sh
rvw/.venv/bin/python examples/smp/rvw/suite_programs.py --suite amo --seed 17 --out examples/smp/rvw/out/amo
examples/smp/rvw/run.sh run --config smp2 --elf examples/smp/rvw/out/amo/hart-0.elf --hart-images examples/smp/rvw/out/amo/hart-images.json --out examples/smp/rvw/out/amo-run --rvfi-trace --seed 17 --json
```

At seed 17, LR/SC passed on two RTL harts: 1060 cycles and 498 retirements.
AMO passed: 18630 cycles and 8346 retirements. AMO checks 144 operand cases per
hart, including signed extrema, random operands, word sign extension and
guard bytes. Targets are private to each hart. The generated programs below
also exercise shared targets.

`litmus_programs.py TEST --out DIR` compiles one of the six pinned SB, MP and
LB tests, with and without fences. The parser checks the exact source hash.
Run each resulting hart manifest with `smp2`. Store inputs at
`rvw/out/litmus/TEST_NAME` and captures at `rvw/out/litmus/TEST_NAME-run`.
Then use the existing outcome checker:

```sh
export PATH="$RVW_HOME/rvw/.venv/bin:$PATH"
python RiscvSim/tests/ordering/litmus.py --tests /path/to/pinned/litmus-tests-riscv --herd /path/to/herd7 --herd-source /path/to/pinned/herdtools7 --dut-adapter examples/smp/rvw/litmus-outcome.py --out examples/smp/rvw/out/litmus-checked
```

Use the revisions in `RiscvSim/tests/ordering/litmus-pins.json`. Set
`RVW_SMP_LITMUS_OUT` when captures use another root. All six native captures
at seed 17 are consistent with native herd7 7.58 outcomes. Each case has one
observed outcome. This does not establish outcome coverage or ISA compliance.
The reader checks completion, ELF hashes and every retired instruction byte.

## Scalar RVWMO observations

Use `rvw memory concurrent-build` to generate per-hart inputs. Run those inputs
with `smp2`. Then bind dependencies and run the independent checker:

```sh
rvw/.venv/bin/python examples/smp/rvw/scalar_dependencies.py --trace RUN/rvfi.jsonl --out RUN/dependencies.jsonl
rvw memory axiomatic --trace RUN/dependencies.jsonl --reference INPUTS/initial.json --limit 100000
```

The binding uses the RVWMO source/destination register rules. It tracks address,
data and control dependencies per hart. It pairs LR/SC. Failed SC creates no
memory event and does not kill old register provenance. Loads and atomics do
not carry source dependencies to their destination. Unknown instructions,
faults, traps, device accesses and later resets refuse a complete binding.
The derived header records the input trace hash and binding source hash.
See the [RVWMO dependency tables](https://docs.riscv.org/reference/isa/v20260120/unpriv/rvwmo.html).

The four original generated programs used length 2 at seed 17 and length 4
at seeds 1, 7 and 23. All four saved captures now have allowed witnesses.
Seed 1 previously reached 100000 candidates. The checker now finds a sparse
SC witness. No candidate limit was waived. See `rvw/search-scale-results.json`.
The later 16-seed default and stress campaigns each have 16 allowed captures.
These finite results do not prove general RVWMO compliance.

## Multi-hart Spike comparison

`serial2` boots both harts at `0x80000000` from one common ELF. Each hart uses
its own 8-byte slot in `tohost`. The harness serves one data operation at a
time. It waits for that operation's retirement before serving another.
This enforces the existing `serialized-retirement` cosim profile.
The concurrent `smp2` profile makes no such declaration.

```sh
rvw/.venv/bin/python examples/smp/rvw/cosim_program.py --out examples/smp/rvw/out/serial
examples/smp/rvw/run.sh run --config serial2 --elf examples/smp/rvw/out/serial/shared.elf --hart-images examples/smp/rvw/out/serial/hart-images.json --out examples/smp/rvw/out/serial-run --rvfi-trace --seed 17 --json
rvw --project examples/smp/rvw.toml cosim check --elf examples/smp/rvw/out/serial/shared.elf --trace examples/smp/rvw/out/serial-run/rvfi.jsonl --json
```

Spike matched all 38 instructions in the captured two-hart shared-memory test.
It applied zero masks and zero synchronizations. A seeded observation-bit fault
was rejected at hart 0, instruction 0, with an `rd_wdata` mismatch. This is a
negative control, not a core defect. Serialized comparison is not an RVWMO
outcome oracle. Interrupts and WFI are not qualified in `serial2`.

## Cross-hart visibility and lifecycle

`visibility_programs.py --suite fence-i-cross --out DIR` builds a writer and
an instruction receiver. The receiver executes `FENCE.I`, calls the written
code, checks its result and acknowledges completion. Both harts must pass.
The seed-17 RTL run passed in 191 cycles with 62 retirements. This is a
cacheless instruction-visibility check. There is no instruction-cache monitor.

`--suite ipi` builds a CLINT software-interrupt sender and a receiving handler.
The handler checks `mcause`, clears MSIP and acknowledges the sender.
The seed-17 run passed in 247 cycles with 74 retirements. C2 records one
software-interrupt trap and MSIP transitions from zero to eight to zero.
The adapter samples trap values before the upstream probe reports the trap.
It records actual IRQ input changes and trap events per hart.

`hsm2` adds S/U privilege with physical addresses and concurrent memory service.
Build its common test firmware with `cosim_program.py --source
examples/smp/rvw/programs/hsm.S --out DIR`. Use configuration `hsm2` for the run.
The firmware exercises selected SBI HSM start, stop and status calls. Hart 1
starts twice with distinct opaque values. The observer checks the retired
service points, actual S-mode entry PC, opaque values and IPI inputs.
The seed-17 run passed in 1431 cycles with 530 retirements. The observer
recorded two starts, two S-mode entries, one stop, one stopped state and two
IPIs. Nine separate device-model checks also passed.
This is a bounded software lifecycle test. It does not qualify all SBI calls,
clock gating, independent reset or power control.

`rvw/native-results.json`, `visibility-results.json`, `litmus-result.json`,
`random-results.json`, `ipi-result.json`, `hsm-result.json` and
`serial-cosim-result.json` hold measured evidence.
Use `summarize.py RUN...` to validate C1/C2 count and completion consistency.

## Cache and protocol observer scope

See [the cache and coherence scope](COHERENCE.md). Both observer groups are
unbound in the cacheless C1 profiles. These profiles have no caches or
TileLink-C ports. C1 reports
`cache_coherence: not_present`. Native program passes do not change that limit.

## Timing stress and replay

The top gives each hart its own synchronous clock enable. The harness changes
these enables after sampling. It holds responses until the target hart has an
enabled clock edge. Disabled harts cannot accept bus requests. Fetch and LSU
command backpressure are separate per-hart draws. Response waits and same-edge
hart service order also use the run seed.

| Variable | Default | Range | Effect |
|---|---:|---:|---|
| `RVW_SMP_MAX_DELAY` | 3 | 0..1024 | Seeded response wait in base-clock cycles. |
| `RVW_SMP_READY_PERCENT` | 100 | 1..100 | Probability that an enabled hart's fetch/LSU command port is ready. |
| `RVW_SMP_CLOCK_PERCENT` | 100 | 1..100 | Probability that each hart's next clock edge is enabled. |

`--mem-latency` selects a fixed response wait instead of the seeded delay.
C1 `details.timing` records all settings, the seed and each hart's disabled
clock-edge count. Its base sample count includes the terminal sample and can
exceed `cycles` by one. The replay command includes the three environment
variables when set. A C1 pass still requires every hart to complete.

For example, set these variables before the existing C1 command:

```sh
export RVW_SMP_MAX_DELAY=11
export RVW_SMP_READY_PERCENT=60
export RVW_SMP_CLOCK_PERCENT=70
# Pass --seed 17 to rvw/run.sh run, as in the examples above.
```

The native stress control used those settings:

| Case | Seed | Cycles | Retirements | Result |
|---|---:|---:|---:|---|
| LR/SC run A | 17 | 2132 | 498 | pass |
| LR/SC replay B | 17 | 2132 | 498 | byte-identical C2 |
| AMO | 23 | 35860 | 8326 | pass |
| Generated shared program | 7 | 230 | 39 | RVWMO allowed on checker recheck |
| HSM | 17 | 2813 | 520 | two starts, one stop, two IPIs |
| Serialized shared AMO | 23 | 152 | 30 | Spike match; zero masks/sync |

Both LR/SC runs recorded 585 disabled edges on hart 0 and 603 on hart 1.
Their full C2 SHA-256 values match. The native test checks settings in each
replay command, nonzero stalls on every hart, completion and C1/C2 counts.
Run `pytest -c rvw/pyproject.toml examples/smp/rvw/tests/test_timing_native.py`
after setup. Use a base temporary directory under `rvw/out` for retained runs.
See `rvw/stress-results.json` and the stress checker JSON files.

The default-timing three-hart control passed at 86 cycles and 35 retirements.
All three clock-stall counters were zero. Native checks now cover N=2 through N=8. Clock enables test synchronous state stalls.
Independent clock frequencies, CDC, physical clock gates, reset and power
control remain outside this example's measured scope.

## Fixed-budget SMP campaign

`rvw/campaign.py prepare --out DIR --tests PINNED_TESTS` builds all six cases
in the pinned litmus manifest, seeds 1..16 at 16 generated steps per hart,
and LR/SC contention plus AMO suites for N=2, 3 and 4. The manifest has 28
runs. The contention program increments one shared doubleword 32 times per
hart. Each hart waits for all peers, then checks the exact shared total.
The AMO matrix uses private targets. This distinction is retained in results.

Run `rvw/run.sh run-many --manifest DIR/jobs.jsonl --jobs 1`, then
`rvw/campaign.py summarize --out DIR`. Use the Python interpreter from the
workstation environment for both campaign commands. The summary checks C1/C2
counts and completion before it binds dependencies for each generated trace.
It records each axiomatic verdict, branch count and checker time separately.
Completion does not imply an allowed memory execution.

For the pinned outcome checker, set `RVW_SMP_LITMUS_OUT=DIR` and
`RVW_SMP_LITMUS_PREFIX=litmus-`. Use the pinned herd source and executable as
shown above. The original pinned manifest contains six tests. The larger upstream
profile below is a separate campaign.

The 2026-11-13 default-timing budget completed 28/28 RTL runs. All 16 generated
captures are allowed by the axiomatic checker. All six observed litmus outcomes
are consistent with native pinned herd7. Each litmus has one captured outcome.
These finite results do not establish complete outcome coverage.
See `rvw/campaign-results.json` and `rvw/campaign-herd-results.json`.

The same 28 jobs passed with delay 0..11, readiness 60% and clock enables 70%.
All 16 stressed generated traces are allowed. All six stressed litmus outcomes
are consistent with native herd7. The maximum checker time was 180 ms.
See `rvw/campaign-stress-results.json` and
`rvw/campaign-stress-herd-results.json`. No forbidden native execution was
found in this budget. The negative controls are checker tests, not core bugs.

## Full-program DUT-order replay

`rvw/programs/full-replay.S` runs 128 shared AMOs per hart, register arithmetic,
branches, a completion barrier and exact final-value checks. Build the common
ELF with `rvw/cosim_program.py --source rvw/programs/full-replay.S --out DIR`.
Use full paths from the workstation root as in the earlier build example.
Run `serial2` with seeds 17 and 23 into `DIR/run-17` and `DIR/run-23`.
Then run `rvw/replay_check.py --inputs DIR` with the workstation Python.

The serialized memory gate permits later requests from its current hart while
previous requests retire. It blocks every other hart until that interval ends.
Blocking later requests from the owner froze the core pipeline on the longer
program. The gate retains an outstanding count and checks retirement ownership.
It does not change the core or replace DUT values with reference values.

Both native runs passed. Spike matched 2,622 retirements at seed 17, with
1,317 on hart 0 and 1,305 on hart 1. It matched 2,613 at seed 23, with
1,308 on hart 0 and 1,305 on hart 1. Each hart used zero masks and zero
synchronizations. Separate injected result faults were rejected on hart 0 and
hart 1. See `rvw/full-replay-results.json`. The eight gate checks also passed.
These are complete finite programs under serialized memory visibility.
They do not qualify arbitrary concurrent weak-memory replay.

## Cached SMP path

`rvw/cached.sh ELF OUT` hosts two cached RV64IMA VexiiRiscv cores.
It uses the pinned upstream TileLink coherent hub. Boot RAM has 64 KiB.
Shared RAM has 4 KiB. The RAM, CLINT and PLIC use RTL. It is a separate native path. The `smpN` C1 profiles remain cacheless.
The cached path uses `vex-mem`, `sbt-mem`, and the private source checkout.
It does not edit core source. The project `SnapshotPlugins` wrapper gives the
upstream TileLink plugin loop a fixed iteration snapshot. This avoids its
Scala 2.13 mutable-buffer iteration failure. It does not change the plugin set.

Build the fixed handoff with the workstation Python:

```sh
rvw/.venv/bin/python examples/smp/rvw/cached_program.py --out INPUTS
examples/smp/rvw/cached.sh INPUTS/shared.elf RUN
```

Hart 0 writes 37. Hart 1 checks 37 and writes 85. Hart 0 then checks 85.
Flags use a separate line. The byte observer checks fills, retired reads and
stores, dirty transfers and invalidations for the line at `0x80080000`.
Its expected bytes come from the fixed program. Permission observers consume
accepted transactions from the real LSU TileLink-C buses. Same-cycle shrinks
are processed before grants. They do not use CPU completion as a coherence
oracle. Only the selected data line has an independent byte binding.

The passive `observed0` and `observed1` bundles project this line. They track
request sources and grant sinks. They do not control any core/fabric handshake.
`expected_data` is an independent test input. The native runner writes
`projected.jsonl` with clock and reset events for generated-monitor replay.

The `db` sbt project provides `rvwsmp.CachedDatabase ELF DATABASE`. Run it with
JDK 21, the same private source checkout, and the `sbt-mem` lock. Then use:

```sh
rvw/.venv/bin/python examples/smp/rvw/cached_bind.py --database DATABASE --out BINDING
rvw/.venv/bin/python examples/smp/rvw/cached_monitor_replay.py --database DATABASE --binding BINDING --capture RUN/projected.jsonl --out REPLAY
```

The binder selects typed members from the extracted design database. It refuses
missing, pruned or wrong-width fields. The replay uses Icarus to run the generated
monitor. A separate corrupted GrantData beat must fail. This is monitor replay
on RTL samples. Executing an SV bind inside the native model is a separate check.

At seed 17, the cached handoff passed in 686 cycles with 99 retirements
(56 on hart 0 and 43 on hart 1). The LSU caches use 64 sets and one way.
The permission observer saw ten grants and seven shrinks. The byte observer
checked three fills, two stores, two reads, two dirty writebacks and one actual
invalidation. No-op acknowledgments do not count as invalidations.

The generated monitor passed on 688 recorded clock/reset events, including the
asynchronous reset assertion while the clock was stopped. A corrupted GrantData
beat was rejected. The typed bind was generated from the real design database.
The native bound-monitor regression also passed its control and rejected six
planted defects. The cached model did not execute the SV bind in simulation.
These finite checks cover data coherence on the selected handoff line.
Instruction-cache visibility, replacement and reset during traffic remain open.
See `rvw/cached-results.json` for hashes and separate evidence results.
The generated monitor, bind and profile are in `rvw/monitors/`.

## N=2..8 stress and PLIC races

`rvw/scaling.py prepare --out DIR` builds seven smoke cases and seven PLIC
race cases. Run `rvw/run.sh run-many --manifest DIR/jobs.jsonl --jobs 1`.
Use the workstation Python for `scaling.py`.
Set `RVW_SMP_PLIC_SOURCE_MASK=2` to hold source 1 high in the simulation PLIC.
The replay command records the mask. Use delay 0..11, readiness 60% and clock
enables 70%, as in the earlier stress commands.

Each race has eight rounds. All harts try to claim the same source before a
shared barrier. The winner checks that a second claim returns zero. It then
completes the interrupt. All harts reach a second barrier before the next round.
The program checks one winner per round. C1 records claims and completions per
machine context. The peripheral is a simulation model. The CPUs execute RTL.

All 14 seed-17 cases passed. Each race case recorded eight claims and eight
completions. The budget has 56 successful claim/complete pairs. Some contexts
won no rounds. This budget does not establish starvation freedom.
Use `scaling.py summarize --out DIR --log ADAPTER_LOG` to check C1/C2 counts
and device totals. See `rvw/scaling-results.json`.

| Harts | Smoke cycles | Smoke retirements | PLIC race cycles | PLIC race retirements |
|---:|---:|---:|---:|---:|
| 2 | 144 | 23 | 1979 | 485 |
| 3 | 157 | 35 | 1930 | 697 |
| 4 | 141 | 45 | 1908 | 914 |
| 5 | 153 | 59 | 2014 | 1177 |
| 6 | 140 | 71 | 2043 | 1406 |
| 7 | 148 | 83 | 2115 | 1679 |
| 8 | 163 | 95 | 2148 | 1938 |

## Simulation time and replay at N=2..8

`scaling.py timing-prepare --out DIR` builds a 1000-iteration ALU loop per hart.
Run its manifest with one worker and the same timing settings. Set the PLIC
source mask to zero. Each N has one warmup and three measured runs.
Use `scaling.py timing-summarize --out DIR --log ADAPTER_LOG` after the run.
The summary checks the actual C1 seed and controls. It rejects mixed settings
or non-identical C2 captures. All 28 native runs passed. The four C2 captures
at each N have identical bytes.

| Harts | Cycles | Retirements | Median simulation seconds |
|---:|---:|---:|---:|
| 2 | 25946 | 4025 | 10.681 |
| 3 | 25968 | 6037 | 4.462 |
| 4 | 25894 | 8051 | 6.862 |
| 5 | 26121 | 10065 | 13.490 |
| 6 | 26263 | 12077 | 17.718 |
| 7 | 26097 | 14090 | 14.439 |
| 8 | 26017 | 16103 | 25.621 |

These are the simulator's wall times. They exclude model builds. The host was
shared, and the samples vary with host load. Raw samples and trace hashes are
in `rvw/timing-results.json`. The RTL cycles and retirement counts are separate
from host simulation cost.

## Private per-hart reduction

`reduction_programs.py --out DIR` builds a two-hart failure and three controls.
Hart 1 reports fail code 7. Only one of its three `fault_region` instructions
causes the failure. The controls retain that instruction, remove it, or move
the same failure code to hart 0.

C8 source capture requires regular files. For a pinned checkout with dependency
Git links, `rvw/flat-source.py --source CORE --revision REV --out NEW_DIR`
creates a private Git snapshot with the pinned dependency files. It records
the component revisions in `rvw-source-pins.json`. It checks tracked changes
and dependency pins. It does not change the source checkout. Use that snapshot
as `VEXIIRISCV` before recording the original run.

```sh
export RVW_VEX_LOCK=vex-simsrv RVW_SBT_LOCK=sbt-simsrv
rvw/.venv/bin/python examples/smp/rvw/reduction_programs.py --out INPUTS
examples/smp/rvw/run.sh run --config smp2 --elf INPUTS/original/hart-0.elf --hart-images INPUTS/original/hart-images.json --out RUN --rvfi-trace --seed 17
rvw reduce RUN --project examples/smp/rvw.toml --hart-symbol 1:fault_region --modes hart_instructions --out REDUCED
```

The native sample reduced three slots to slot 1. It confirmed fail code 7 on
hart 1. The empty and wrong-hart controls were rejected. All six reducer
trials used one captured RTL hash. Source capture changed only the generator
Git comment relative to the original RTL. See `rvw/reduction-results.json`.
This is a stage-local one-minimal result. It is not a global minimum or
proof of a core defect. Other hart images and the hart inventory stay fixed.

## Upstream scalar litmus catalog

`rvw/upstream_campaign.py` reads the complete non-mixed-size test tree at
revision `08728edcd99c7e1819d2d4c6789df6d5299ccb69`. It checks every source
file against the pinned Git archive. It accepts straight-line scalar RV64IMA
programs with two to eight harts, zero initial memory and final register
projections. It preserves each accepted instruction. It initializes unspecified
registers to zero. Registers x30 and x31 are reserved for completion.

The catalog lists each unsupported case and its reason. Branches, nonstandard
load/store acquire/release suffixes, nonzero initial memory and final memory
projections are outside this profile. These exclusions are not passing tests.
The profile does not claim the complete upstream suite or outcome coverage.

From the workstation root, use its Python environment and the pinned external
source checkouts:

```sh
rvw/.venv/bin/python examples/smp/rvw/upstream_campaign.py prepare --tests TESTS --out RUN_ROOT
examples/smp/rvw/run.sh run-many --manifest RUN_ROOT/jobs.jsonl --jobs 1
rvw/.venv/bin/python examples/smp/rvw/upstream_campaign.py summarize --tests TESTS --out RUN_ROOT --herd HERD7 --herd-source HERD_SOURCE
```

The summary checks completion, retirement counts, ELF hashes and retired
instruction bytes. It compares each final register state with the native
pinned herd7 result. It keeps per-case trace, ELF and herd-output hashes.
A missing native result gives an inconclusive outcome.

The 2026-11-18 run passed all 314 applicable RTL programs at seed 17.
Native herd7 7.58 accepted all 314 observed outcomes. The programs retired
33,504 instructions across 179 two-hart cases, 129 three-hart cases and six
four-hart cases. Each case has one observation with default timing.
The other 7,593 source cases are listed as unsupported. A planted forbidden
register outcome is rejected as a checker control. This is not a core defect.
See `rvw/upstream-results.json` for counts, hashes and exclusions.
