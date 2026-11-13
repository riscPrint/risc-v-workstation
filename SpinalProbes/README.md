# SpinalProbes

One instrumentation layer for the event-consuming tools. A core designer calls a small typed
API in the RTL (`Probe.branch(...)`, `Probe.stage(...)`, ...). The generic harness samples the
enabled probes each cycle and writes one compact event stream, `probe-events.jsonl`
(`rvw.probe-events/1`). `rvw probes convert` writes each consumer tool's existing format from
that stream. Scala 2.13.14, SpinalHDL 1.15.0. No core names in this library.

## Use it in a core

```scala
import spinalprobes.Probe

// In a component or a plugin's build(), during elaboration:
Probe.branch("bp", commitFire && isBranch, commitPc, taken, target,
  predictedTaken = Some(predictedTaken), semantics = "final-prediction")
Probe.stage("D", decode.isValid, decodeId, pc = Some(decodePc))
Probe.retire("wb", commitFire, commitId)
Probe.flush("kill", killFire, killedId)
Probe.stall("issue", "operand_wait", issueBlockedByOperand)
Probe.cacheAccess("dcache", "read", dcacheRspFire, address, hit = Some(hit), data = Some(word))
Probe.tlb("dtlb", "fill", fillFire, va = Some(va), pa = Some(pa), asid = Some(asid), entry = Some(way),
  size = Some(pageBytes), pteAddress = Some(pteAddr), pte = Some(pte))
Probe.pageWalk("ptw", "request", ptwReqFire, ptwAddr)
Probe.csrWrite("csr", csrWriteFire, csrAddress, csrValue)
Probe.interruptTaken("irq", irqEntry, mcauseValue, epc)
Probe.traceIngress("te", retireFire, itype, iaddr, iretire, ilastsize, priv)
Probe.counter("rob_full", robFull)                       // Bool or unsigned amount per cycle
Probe.counter("dcache_miss", missFire, hpm = Some(4))    // bound to mhpmevent selector 4
Probe.faultSite("rob_head", robHead)                     // a register rvw fault may force
Probe.custom("lsq", lsqEvent, "addr" -> addr, "size" -> size)
```

Probes are off by default. Every call returns at once and adds no hardware. The adapter
enables them only for a simulation model, the same way the RVFI and Konata probes stay
optional:

```scala
val report = Probe.enabled(key.probes) { SpinalConfig(...).generateVerilog(new Top) }
val sites  = Probe.of(report.toplevel)        // or Probe.of(dut) in the simulation
val probes = riscvsim.ProbeCollector.open(sites, job, ctx.rvfiHeader)
cd.onSamplings { ...; probes.foreach(_.sample(ctl.cycle)) }
probes.foreach(_.close(cycles))
```

C1 `run --probes` selects a separate model (`ModelKey.probes`, name suffix `_probes`). The
probe wires change the generated Verilog, so the RTL hash differs from a plain model.
Adapters set `supportsProbes = true`; the generic command line refuses `--probes` otherwise.

Each call copies its signals into new wires `rvwprobe__KIND__NAME__FIELD` in the calling
component's top scope, also when it is called inside a `when`. The wires are simulation
public. `rvw probes list --db` finds them in a design database built with probes enabled.

Rules for exact events:

- `valid` is a one-cycle event, except `stall` and `stage` (a level sampled each cycle) and
  `counter` (summed each cycle).
- Probe branches at the commit point. `rvw probes convert --to bp-events` aligns events 1:1
  with C2 retirements and refuses extra (speculative) or missing events.
- Stage IDs must be unique for the run. Assign a counter once per instruction and carry it
  down the pipeline. Do not reuse a PC or ROB index.
- Use `measured` stall evidence only for an explicit reason signal.

## Event inventory

The consumers below read events from a core. Before this layer no core adapter wrote most of
them. The table gives the format each tool reads and the probe that now feeds it.

| Consumer | Format it reads | Probe | Converter (`--to`) |
|----------|-----------------|-------|--------------------|
| `rvw csim compare-rtl` | `rvw.bp-events/1` JSONL (order, pc, kind, taken, target, predicted_*) | `branch` | `bp-events` |
| `rvw perf`, SpinalKonata reports | Kanata 0004 (I/L/S/E/R) | `stage`, `retire`, `flush` | `kanata` |
| `rvw perf` stall causes (#49) | Kanata `#rvw 1 stall scope cause evidence` | `stall` | `kanata` |
| `rvw perf` predictor effects | Kanata `#rvw 1 prediction ...` (direction) | `branch` with `predictedTaken` and `id` (the stage probes' instruction ID) | `kanata` |
| RiscvSim `CacheEventObserver` | JSONL cycle, hart, event, physical_address, bytes, mask | `cacheAccess` | `cache` |
| `rvw regress mmu report --protocol-config` | `rvw.mmu-observations/1` tlb_fill, tlb_hit, tlb_invalidate | `tlb` | `mmu` |
| MMU observation capture | `rvw.mmu-observations/1` walk_request, walk_response | `pageWalk` | `mmu` |
| `rvw regress mmu report` ordered walks | C2 `mmu_walks` per-access records | `pageWalk` responses + `walkResult` | `mmu-walks` |
| `rvw arch ooo-calibrate` | RTL event counts `{c1_sha256, trace_sha256, counts}` | `counter` | `counts` |
| HPM monitors (`SpinalChecks.HpmControlChecks`) | `rvw.hpm-bindings/1` selector, counter, total | `counter(..., hpm)` | `hpm` |
| `rvw debug etrace`, `etrace-check` | encoder ingress CSV (`itype_0 ... ilastsize_0`) | `traceIngress` | `etrace-ingress` |
| `rvw cosim` interrupt evidence | C2 trap events with `intr` | `interruptTaken` | `interrupts` (independent check) |
| `rvw cosim` per-slot CSR state | C2/2 `csr_snapshot` | `csrWrite` | no (needs `RvfiProbe csrSlots` per-slot state) |
| CSR write port check | C2 CSR instructions and operands | `csrWrite` | `csr-writes` (independent check) |
| Data bus check | C2 loads and stores | `bus` | `bus` (independent check) |
| `rvw fault plan --sites` | site list `{sites: [{path, width}]}`, C1 `--fault` | `faultSite` | `fault-sites` |
| N-Trace checks | vendor packet capture | none | no |

`rvw probes list` prints this matrix for one design: which consumers its probes enable and
which events are still missing.

## Build and test

```sh
source ../spinal-boom/env.sh
../scripts/with-lock.sh sbt nice -n 10 sbt -batch -Dsbt.offline=true test
cd ../RiscvSim && ../scripts/with-lock.sh sbt nice -n 10 sbt -batch -Dsbt.offline=true 'testOnly riscvsim.ProbeCollectorSpec'
```

The library test elaborates a small component with probes off (no `rvwprobe` text in the
Verilog) and on (named wires, registered sites). `ProbeSafetySpec` is the synthesis-safety
test: a seeded three-stage pipeline (register file, TLB tag, cache tag, branch unit, CSR) that
calls every probe kind gives Verilog byte-identical to the same design without the calls when
probes are disabled, and different Verilog with every kind's wires when they are enabled.

The example cores repeat the check on real designs: `rvwvex.ProbeSafety` (VexRiscv, with and
without `ProbePlugin`) and `rvwvexii.ProbeSafety` (VexiiRiscv `rv32im` and `rv32imasu`, with
and without `ProbeTapPlugin`). Each prints both Verilog SHA-256 values and exits 1 when they
differ. Measured on 2026-11-13: identical for all three (`1ba7bb07…`, `af58b6d9…`,
`eee00998…`). The RiscvSim test runs Verilator and checks
the event rows, the counter totals and the end record.

## Decisions

- New top-level library, not inside SpinalKonata. SpinalKonata writes Kanata only and keeps a
  BOOM subproject. Probes feed a dozen consumers; Kanata is one converter among them. The
  library depends on spinalhdl-core and -sim only, so a core can add it to its main build.
- One stream, converters in Python. The harness writes one compact file per run. Each
  consumer format is written by `rvw probes convert`, where it has fast unit tests and can
  check alignment against C2.
- Probe wires are copies in the calling component's top scope. Their names stay stable for
  the design database, and a call inside a `when` stays unconditional.
- Disabled probes add nothing. Enabling is per elaboration (`Probe.enabled`), not a global
  setting, so a synthesis build in the same JVM stays clean.

## Limits

- Events are producer claims from sampled signals. A probe at the wrong point gives wrong
  events; the converters refuse what they can detect (count or PC differences against C2).
- Single hart. The converters write hart 0.
- Counter totals are JSON numbers; values above 2^53 lose precision.
- `csrWrite` events do not fill a C2 `csr_snapshot` (see the table).
- The library does not add probes to any core. A core or its adapter calls the API.

## Cache probe comparison

The optional cached configurations tap existing cache signals. They emit
`access`, `fill`, `evict`, `flush` and, for a write-back cache, `writeback`.
The write-through VexRiscv cache has no dirty writeback event.
An instruction access is recorded at retirement. Its miss bit associates a
refill with the first retirement in that line. It does not count speculative
fetch lookups. Data access semantics are in each example's `CacheProbes.scala`.

Use the run's `probe-events.jsonl`, `rvfi.jsonl` and ELF together:

```sh
rvw probes convert RUN/probe-events.jsonl --to cache-check \
  --c2 RUN/rvfi.jsonl --elf ELF --geometry dcache=128x1 \
  --geometry icache=128x1 --out cache-check.json
rvw csim compare-rtl examples/vexriscv/rvw/csim/caches.json \
  --cache dcache --trace RUN/rvfi.jsonl --events RUN/probe-events.jsonl \
  --trace-out accesses.csim --json
```

For VexiiRiscv use its study and `32x2` geometry for both caches.
`compare-cache` provides the same cache comparison. Reports give per-access
hit agreement and signed miss-rate error. Incomplete streams and missing or
misaligned accesses are inconclusive. The aligned access stream can feed
replacement and prefetch studies with `rvw csim run` or `sweep`. Model results
do not establish RTL correctness or speed.

For reused ROB indices, call `Probe.stageAt` at entry with `first = true`.
Use it again at later stages with distinct probe names and the same ID.
`Probe.flushYounger` flushes a ROB tail in entry order, including its anchor
when requested. The Kanata converter reports orphan events, unknown anchors
and stale live-ID replacements. Check those fields beside C2 retirement counts.
See the NaxRiscv example for a native out-of-order binding.

## Measured cached examples

Both examples have an extra `rv32im_cached` configuration. Their defaults
remain cacheless. No core source changes are needed. With probes enabled,
each cached core passed 49 selected aligned RV32UI/UM programs and matched
all 49 complete Spike traces at seed 7 and memory latency 0.

Four programs per core feed the cache checker and performance reports. All
eight cache checks were consistent. The cache sweep produced 769 data
accesses and 513 misses on each core. Each data-cache model agreed on all
769 accesses. VexiiRiscv also checked 512 writeback bursts. Its instruction
cache restarted early 12 times; the checker verified the exact returned
word and data before accepting each hit. A hit on an unreturned word still
fails. The VexRiscv data cache writes through and has no dirty writeback.
The VexiiRiscv data-cache flush cleans dirty lines and retains tags. Its
model omits that final clean and writes back 449 lines, 63 fewer than RTL.
The report keeps that aggregate gap beside per-access agreement.

Physical `lookup` events and retired refill attribution are separate. Use
`refill_beat` events for caches that restart before a full line arrives. A
retired attribution stream without physical lookups cannot establish
residency consistency. The old line-only and retirement-only record stays
in each example's `measured.json`. Current physical checks and performance
measurements are in `perf-measured.json`.

`rvw perf` preserves explicit sampling bounds. It keeps inferred spans
separate from measured stalls. The VexiiRiscv commit-port count differs
from its completion-based C1 count. The report retains that difference.
Both three-program timing calibrations report inconclusive accuracy.
These checks are selected simulation evidence. They are not cache proofs
or timing qualification.

See the [VexRiscv results](../examples/vexriscv/rvw/csim/README.md),
[VexiiRiscv results](../examples/vexiiriscv/rvw/csim/README.md), and
[retirement boundaries](../examples/vexiiriscv/rvw/csim/RETIREMENT.md).
The [native negative test](../examples/vexriscv/rvw/tests/test_probe_misplaced.py)
moves a branch probe to decode in a temporary adapter. Validation returns
1 and names `branch/misplaced_decode_branch`.
