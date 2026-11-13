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
| `rvw perf` predictor effects | Kanata `#rvw 1 prediction ...` | SpinalKonata `PipelineTags.direction` | not yet (needs a live instruction ID on the branch probe) |
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
