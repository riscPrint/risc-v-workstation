# SpinalKonata

A generic simulation event writer and SpinalHDL tags for Kanata 0004. Scala 2.13.14,
SpinalHDL 1.15.0. The generic build has no dependency on BOOM.

```sh
source ../spinal-boom/env.sh
cd SpinalKonata
sbt -J-XX:ActiveProcessorCount=2 test
sbt 'runMain spinalkonata.Demo demo.log'
cd ../rvw
uv run rvw perf ../SpinalKonata/demo.log --json
```

The demo is an actual three-register Spinal pipeline. Tests also need Python 3.11 or later. It holds for three cycles
and discards instruction 2. The simulation test checks six creations, five
retirements and one discard. Writer tests cover future event ordering, parallel
lanes, dependencies, sanitization, quiet tails and invalid events.

## Tag a design

Instantiate tags only when tracing is enabled; keep them off in a production
elaboration. `valid` below means a one-cycle event or handshake, not occupancy.
An instruction held in a stage must not generate another enter event each cycle.

```scala
import spinalkonata._
val tags = new PipelineTags
tags.fetch(fetchFire, fetchId, () => s"${fetchPc.toBigInt.toString(16)}: custom class=alu")
tags.enter(fetchFire, fetchId, "Fetch")
tags.enter(issueFire, issueId, "Issue")
tags.retire(commitFire, commitId)
tags.flush(killFire, killedId)
// In simulation, after reset:
val writer = new KanataWriter(new java.io.File("pipeline.log"))
var cycle = 0L
clockDomain.onSamplings {
  tags.sample(writer, cycle)
  cycle += 1
}
// At the end of simulation:
writer.close()
```

Signals read by custom label closures (such as `fetchPc`) also need `simPublic()`
at elaboration. Tags expose and name their valid/ID signals automatically.
Register same-cycle fetches before their labels/stages/terminal events. IDs in the
tag API must fit the simulator's `UInt.toLong`; use nonnegative IDs below 2^63.
Use a fresh monotonically assigned fetch ID, carried along the pipeline, rather
than recycling a PC or ROB index. Thread names and all stage names are arbitrary.

The lower-level `KanataWriter.record(cycle, Event)` API also works from another
simulator or a software adapter. Events are `Fetch(id, simId, thread)`, `Label`,
`Enter`, `Leave`, `Retire`, `Flush`, and `Dependency(consumer, producer)`. `Enter`
implicitly ends the previous stage in the same lane. Multiple lanes run in parallel.
`seal(cycle)` writes all buffered events through that cycle; producers may schedule
future events before sealing the current cycle. Events retain insertion order
within a cycle. Sending an event at or before a sealed cycle is an error.

## BOOM adapter and migration

`boom/` is a separate sbt subproject/build referencing the private BOOM clone's
Compile and Test code. It is optional. `BoomKonataTracer` consumes the existing
`KonataProbe` directly. Its instruction matching, redirects, rollback, ROB index
reuse and replay algorithm are adapted from `Konata.scala` at `0cb0b69`; only the
event serialization uses the generic writer. BOOM signal names never enter the
generic project or Python parser.

`ProbeRun` is a bounded migration harness, copied from that revision's
`BoomSim.run`. It attaches the generic tracer. It keeps the original memory model,
interrupt handling, tohost check, counter semantics and random seed. `BenchTrace`
compiles once and runs several ELFs with seed 1, fixed memory latency 20, a
300,000-cycle default budget and C1-style `result.json` files. It refuses to
overwrite an output directory. Analysis helpers live in `scripts/`.

```sh
cd SpinalKonata/boom
export SPINAL_BOOM=/path/to/your/boom-checkout
export SPINAL_MAKE_CMD="$PWD/make-j4.sh"
../../scripts/with-lock.sh boom sbt -J-XX:ActiveProcessorCount=4 -J-Xmx3g \
  'runMain spinalkonata.boom.BenchTrace /absolute/new-output /absolute/benchmark.riscv'
```

Each new run includes `report.json` and `report.txt`. To read the saved trace-only
report through the CLI, use `rvw perf /absolute/new-output/benchmark/report.json`.
Direct analysis of `konata.log` still discovers the adjacent inconclusive C1 and
refuses its counter claim.

The make wrapper enforces `-j4`: Spinal 1.15 queries physical host logical CPUs
through OSHI, so JVM `ActiveProcessorCount` alone does not constrain its make job
count. Every BOOM compile or run must hold the machine-wide `boom` lock.

Migration into the core:

1. Add a dependency on the generic library in the core's test build; keep probe
   construction optional and off by default.
2. Move `BoomKonataTracer` beside the BOOM probe, replacing its local serialization.
   Retain the matching algorithm and explicitly monitor `desyncs`.
3. Wire that tracer into `BoomSim.run`; remove this snapshot of `ProbeRun` once
   the adapter can inject the tracer. Do not carry two complete harnesses long term.
4. For future cores, propagate unique fetch IDs explicitly. BOOM currently matches
   decode against fetch-buffer PCs, so a nonzero mismatch count invalidates
   attribution and must be reported rather than hidden.
5. If measuring causes, add explicit dependency, cache-miss and stall-reason
   events. The present probe provides none of these. Add an observed ROB head
   and explicit commit timestamps before treating inferred heads as hardware facts.
6. Expose `commit.arch_valids` or an explicit per-operation predicated-off flag.
   The existing probe's `comValid` comes from physical `commit.valids`. Its R count
   includes predicated-off operations, while the harness and minstret use
   `arch_valids`. Until that signal is added, event IPC cannot be substituted for
   architectural IPC.

## Decisions

- Keep event tagging and serialization generic. Put signal matching and pipeline
  reconstruction in core adapters. Tags add simulation visibility, not behavior.
- Validate lifetimes and stage nesting. Leave instructions open at EOF.
  Advance quiet cycles when sealing. Do not infer flushes, stalls or branch penalty.
- Use RiscvSim's ELF parser. Load, hash and disassemble the same saved bytes.
- Keep `ProbeRun` until the core supports a tracer hook. New runs use only the
  generic tracer. Past migration checks apply only to their selected workloads.
- Keep the standalone C1 inconclusive until compiled-model capture is complete.
  Successful measurements return 0, with `status=error`, the capture cause and
  `cache_key=null` in C1. Core failures and simulator errors still fail the command.
- Use the existing perf analyzer on the captured log alone. Retain C1 as producer
  metadata. Do not cross-check inconclusive counters or create a result cache.
- Run the standalone JVM in `SpinalKonata/boom`. Pass fixed memory latency 20
  explicitly for the benchmark measurements. Heavy BOOM jobs use the `boom` lock.
- Scala input tests compile real orchestration against fixture BOOM seams.
  They do not establish BOOM execution or silicon behavior. Generic simulation
  tests use Verilator.

Format reference: [upstream Kanata 0004 documentation](https://github.com/shioyadan/Konata/blob/master/docs/kanata-log-format.md).

## Input capture limits

`BenchTrace` captures every ELF before compilation. It resolves lookup paths,
records symlinks, checks metadata, and writes private read-only copies. The loader,
symbols, `tohost`, tracer labels and SHA-256 use those bytes. It selects objdump once,
records its identity, and checks the tool before execution and publication.
`RISCV_OBJDUMP` selects another disassembler. Capture failure refuses publication.

The harness saves `KONATA_CONFIG`, `KONATA_MAX_CYCLES`, `RISCV_OBJDUMP`,
`KONATA_PYTHON` and `PATH`. Each run uses a new directory and an atomic rename.
It never updates an existing run. Reports need Python 3.11 or later.
`KONATA_PYTHON` selects the reporter interpreter; the default is `python3`.
The script and interpreter identity are captured before compilation. Raw report
inputs remain in `report-inputs/`.

The standalone harness does not capture its compiler, loaded JVM classes,
classpath, generated RTL dependencies, native compiler, Verilator dependencies
or complete build environment. C1 therefore has `status=error`,
`input_not_captured:compiled_model`, and `cache_key=null`. `observed_status` records
the simulator outcome. It writes `konata.log`, `report.json` and `report.txt` before
publication. Reports use `measurement_scope=trace_only`, no `cross_check`, and
`cache_key=null`. They cannot support a passing result cache or gate acceptance.
Historical benchmark evidence is not recaptured or revalidated by this workflow.

The input tests compile the real `BenchTrace` orchestration against test-only
BOOM seams. They do not build or write to a BOOM checkout. Run them from
`SpinalKonata/`:

```sh
../scripts/with-lock.sh sbt nice -n 10 sbt -Dsbt.offline=true 'inputs/test' test
```

The local cache lacks `scala-reflect:2.13.10`. Validation used the cached
`2.13.14` version with this temporary sbt setting:

```text
set ThisBuild / dependencyOverrides += "org.scala-lang" % "scala-reflect" % "2.13.14"
```

## Saved-run analysis

`python3 scripts/trace_report.py RUN ../rvw/src` writes a trace-only report
from captured inputs. Run this command from `SpinalKonata/`.
`BenchTrace` calls it after a run. Select the disassembler with `RISCV_OBJDUMP`;
the default is `riscv64-unknown-elf-objdump` on `PATH`.
`scripts/roi_observations.py` and `scripts/collect.py` analyze conclusive C1 runs.
The collector captures the batch before analysis and publishes an immutable
`.analysis` generation. It refuses the standalone harness's inconclusive C1.
The harness keeps `cache_key=null` until compiled-model capture is complete.
Physical commit events can include predicated-off operations. Event IPC cannot
replace architectural IPC. These trace checks do not establish silicon behavior.

## Stall, replay and commit events

`Stall(scope, cause, evidence = "measured")` records one sampled cycle. A scope
names a resource, pipeline or thread. It does not require a live instruction.
Emit it on each blocked cycle. Several causes can apply to the same cycle.
`StallCause` supplies `OperandWait`, `Structural`, `LoadMiss`, `RobFull` and
`LsqFull`. Custom nonempty names also work. Evidence must be `measured` or
`inferred`. Set `inferred` when an adapter estimates the cause.

`Replay(id, cause, evidence = "measured")` records an explicit replay event for
a live instruction. A repeated stage visit alone does not establish a replay cause.
`Dependency(consumer, producer)` records an optional `W` edge. The consumer must
be live. The producer must have appeared in the trace. An edge alone does not
establish a stall.

`Commit(id, predicatedOff)` records a physical commit with an observed flag and
ends the instruction with R type 0. False means architectural commit; true means
predicated-off physical commit. Use this only when the producer can establish
those semantics. `Retire(id)` still emits R type 0 without a commit kind. Perf
keeps such events unknown. It never guesses predication from a counter mismatch.

```scala
tags.stall(operandBlocked, "issue", StallCause.OperandWait)
tags.stall(cacheBlocked, "memory", StallCause.LoadMiss)
tags.replay(replayFire, replayId, "memory_order")
tags.dependency(waitEdgeFire, consumerId, producerId)
tags.commit(physicalCommitFire, commitId, predicatedOff)
```

Register these tags only when tracing is enabled. Register commit tags after all
other events for the same instruction. The demo now emits three measured global
hold samples and one predicated-off commit. It still emits five R type 0 events.

The writer uses the `#rvw` version 1 comment extension described in
[PLATFORM_CONTRACTS.md](../docs/PLATFORM_CONTRACTS.md#pipeline-cause-event-extension).
Ordinary stage and R records remain intact. `rvw perf` reports cause unions,
overlaps, unknown intervals, replay counts and commit kinds. These measurements
are producer claims from sampled signals, not proof that a cause blocks all
retirement. BOOM probe changes remain core-owned. See
[the BOOM mapping](../examples/boom/konata-events.md).
