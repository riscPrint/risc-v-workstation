package riscvsim

import java.io.{File, PrintWriter}

import spinal.core._
import spinal.core.sim._

/**
 * Samples a core's trace encoder ingress port, declared in project data
 * (`rvw.trace-ingress-binding/1`), into `te_ingress.csv` (the upstream E-Trace reference
 * encoder's ingress columns). Each source is one kind of ingress row: a `valid` top-level port
 * and, for every column, a top-level port name or an integer constant. Sources are written in
 * binding order within a cycle. Unbound columns are 0.
 */
case class IngressSource(valid: String, fields: Map[String, Either[String, BigInt]])
case class IngressBinding(file: File, sources: Seq[IngressSource])

object IngressBinding {
  val schema = "rvw.trace-ingress-binding/1"
  val columns = Seq("itype_0", "cause", "tval", "priv", "iaddr_0", "context", "ctype", "iretire_0", "ilastsize_0")
  /** Columns the reference encoder reads as hexadecimal. */
  val hexColumns = Set("tval", "iaddr_0")

  def load(file: File): IngressBinding = {
    val doc = ujson.read(java.nio.file.Files.readString(file.toPath)).obj
    if (!doc.get("schema").exists(_.str == schema)) throw new Cli.UsageError(s"--trace-ingress: schema must be $schema")
    val sources = doc("sources").arr.toSeq.map { s =>
      val o = s.obj
      val fields = o("fields").obj.map { case (k, v) =>
        if (!columns.contains(k)) throw new Cli.UsageError(s"--trace-ingress: unknown column '$k'")
        k -> (v match {
          case ujson.Str(name) => Left(name)
          case ujson.Num(n) => Right(BigInt(n.toLong))
          case other => throw new Cli.UsageError(s"--trace-ingress: '$k' must be a port name or an integer: $other")
        })
      }.toMap
      IngressSource(o("valid").str, fields)
    }
    if (sources.isEmpty) throw new Cli.UsageError("--trace-ingress: no sources")
    IngressBinding(file, sources)
  }
}

class TraceIngress(binding: IngressBinding, out: File) {
  @volatile var rows = 0L

  def attach(dut: Component, ctl: SimControl): Unit = {
    def io(name: String): BaseType = dut.getAllIo.find(_.getName() == name)
      .getOrElse(throw new IllegalArgumentException(s"trace ingress binding: no top-level port '$name'"))
    val sources = binding.sources.map { s =>
      (io(s.valid), IngressBinding.columns.map(c => c -> s.fields.get(c).map(_.left.map(io))))
    }
    val writer = new PrintWriter(new File(out, TraceIngress.file))
    writer.println(IngressBinding.columns.mkString(","))
    dut.clockDomain.onSamplings {
      for ((valid, fields) <- sources if FaultInjector.raw(valid) == 1) {
        val values = fields.map { case (column, source) =>
          val v = source.map(_.fold((bt: BaseType) => FaultInjector.raw(bt), (n: BigInt) => n)).getOrElse(BigInt(0))
          if (IngressBinding.hexColumns(column)) v.toString(16) else v.toString
        }
        writer.println(values.mkString(","))
        rows += 1
      }
      if (ctl.isEnded) writer.flush()
    }
    TraceIngress.writers.put(out.getAbsolutePath, writer)
  }
}

object TraceIngress {
  val file = "te_ingress.csv"
  private val writers = new java.util.concurrent.ConcurrentHashMap[String, PrintWriter]()
  private val active = new java.util.concurrent.ConcurrentHashMap[String, TraceIngress]()
  def forRun(job: RunJob): Option[TraceIngress] =
    job.traceIngress.map(b => active.computeIfAbsent(job.out.getAbsolutePath, _ => new TraceIngress(b, job.out)))
  /** Closes the CSV and returns C1 details for the run. */
  def finish(job: RunJob): Option[ujson.Obj] = job.traceIngress.map { b =>
    Option(writers.remove(job.out.getAbsolutePath)).foreach(_.close())
    val t = Option(active.remove(job.out.getAbsolutePath))
    ujson.Obj("binding" -> b.file.getPath, "attached" -> t.nonEmpty, "rows" -> RvwJson.num(t.map(_.rows).getOrElse(0L)))
  }
}
