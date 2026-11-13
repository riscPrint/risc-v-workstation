package riscvsim

import java.io.{BufferedWriter, File, FileWriter}
import spinal.core._
import spinal.core.sim._
import spinalprobes.ProbeSite

/** Samples enabled probes once per cycle and writes one compact `rvw.probe-events/1` stream.
  *
  *  - line 1: header with schema, identity (copied from the C2 header) and the probe table;
  *  - then one JSON array per event: `[cycle, probe, value...]` in the probe's field order;
  *  - last line: `{"end": true, "cycles": N, "counters": {...}, "events": {...}}`.
  *
  * Counter probes add their increment each cycle and appear only in the end record.
  * Fault sites are listed in the header and never sampled. Call `sample` from the
  * adapter's `onSamplings`, with the same cycle number that the C2 writer uses. */
final class ProbeCollector(sites: Seq[ProbeSite], file: File, identity: ujson.Obj = ujson.Obj()) {
  private val out = new BufferedWriter(new FileWriter(file))
  private val sampled = sites.filter(s => s.kind != "counter" && s.kind != "fault").toArray
  private val counters = sites.filter(_.kind == "counter").toArray
  private val totals = Array.fill(counters.length)(BigInt(0))
  private val events = Array.fill(sites.length)(0L)
  private var last = -1L
  private var closed = false

  out.write(ujson.write(ujson.Obj("schema" -> ProbeCollector.Schema, "identity" -> identity,
    "probes" -> ujson.Arr.from(sites.map(ProbeCollector.describe)))))
  out.write('\n')

  private def value(d: BaseType): BigInt = d match {
    case b: Bool => if (b.toBoolean) 1 else 0
    case v: BitVector => v.toBigInt
  }

  def sample(cycle: Long): Unit = {
    require(!closed && cycle > last, "probe cycles must increase")
    last = cycle
    var i = 0
    while (i < sampled.length) {
      val s = sampled(i)
      if (s.valid.toBoolean) {
        val sb = new StringBuilder
        sb.append('[').append(cycle).append(',').append(s.index)
        s.fields.foreach { case (_, d) => sb.append(',').append(value(d).toString) }
        sb.append("]\n")
        out.write(sb.toString)
        events(s.index) += 1
      }
      i += 1
    }
    i = 0
    while (i < counters.length) {
      val s = counters(i)
      if (s.valid.toBoolean) { totals(i) += value(s.fields.head._2); events(s.index) += 1 }
      i += 1
    }
  }

  /** Close a stream without the end record (the run did not finish). No-op after close. */
  def abandon(): Unit = if (!closed) { closed = true; out.close() }

  /** Write the end record. `cycles` is the total cycle count of the run. */
  def close(cycles: Long): Unit = if (!closed) {
    closed = true
    out.write(ujson.write(ujson.Obj("end" -> true, "cycles" -> RvwJson.num(cycles),
      "counters" -> ujson.Obj.from(counters.indices.map(i => counters(i).name -> ujson.Num(totals(i).toDouble))),
      "events" -> ujson.Obj.from(sites.filter(_.kind != "fault").map(s => s.index.toString -> RvwJson.num(events(s.index)))))))
    out.write('\n')
    out.close()
  }
}

object ProbeCollector {
  val Schema = "rvw.probe-events/1"
  val FileName = "probe-events.jsonl"
  /** The collector for one run, or None when the job did not ask for probes.
    * A run with `--probes` and no registered probe is an error, not an empty claim. */
  def open(sites: Seq[ProbeSite], job: RunJob, header: ujson.Obj): Option[ProbeCollector] =
    if (!job.probes) None
    else {
      require(sites.nonEmpty, "--probes was given but the design registered no probes")
      Some(new ProbeCollector(sites, new File(job.out, FileName), identity(header)))
    }
  def describe(s: ProbeSite): ujson.Obj = ujson.Obj("id" -> s.index, "kind" -> s.kind, "name" -> s.name,
    "fields" -> ujson.Arr.from(s.fields.map { case (n, d) => ujson.Arr(n, d.getBitsWidth) }),
    "meta" -> ujson.Obj.from((s.meta ++ faultPath(s)).toSeq.sortBy(_._1).map { case (k, v) => k -> ujson.Str(v) }))
  /** A fault site's register path, as `--fault` resolves it (`FaultFile.path`). */
  private def faultPath(s: ProbeSite): Map[String, String] = s.fields.collectFirst {
    case ("value", bt: BaseType) if s.kind == "fault" => "path" -> FaultFile.path(bt)
  }.toMap
  /** Identity fields copied from a C2 header so converters can bind the two streams. */
  def identity(c2Header: ujson.Obj): ujson.Obj =
    ujson.Obj.from(Seq("core", "config", "elf", "elf_sha256", "rtl_sha256", "seed").flatMap(k => c2Header.value.get(k).map(k -> _)))
}
