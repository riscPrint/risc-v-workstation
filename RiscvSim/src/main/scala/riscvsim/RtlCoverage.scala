package riscvsim

import spinal.core._
import java.io.File
import java.nio.file.Files
import scala.collection.mutable

/** Adapter-owned event universe. Each annotation declares its source and domain. */
object RtlCoverage {
  case class Source(file: String, line: Int) {
    require(file.nonEmpty && line > 0)
    def json: ujson.Value = ujson.Obj("file" -> file, "line" -> line)
  }
  case class Bin(id: String, kind: String, domain: String, values: Seq[BigInt],
      source: Source, typeName: String, from: Seq[BigInt] = Nil) extends SpinalTag {
    require(id.nonEmpty && Set("event", "occupancy", "state", "transition", "arbitration")(kind))
    require(Set("committed", "speculative", "structural")(domain))
    require(values.nonEmpty && typeName.nonEmpty)
    require((kind == "transition") == from.nonEmpty)
  }
  def tag[T <: BaseType](signal: T, bin: Bin): T = {
    signal.dontSimplifyIt()
    signal.setAsVital()
    signal.addTag(bin)
    signal.addAttribute("keep")
    signal
  }
  /** Call after emission. Paths and bin IDs identify physical instances. */
  def plan[T <: Component](report: SpinalReport[T], design: String,
      clock: BaseType, reset: BaseType, resetActive: Int = 1): ujson.Value = {
    require(design.nonEmpty && Set(0, 1)(resetActive))
    // ClockDomain may name external wires. Use the ports pulled into this top.
    val localClock = report.toplevel.pulledDataCache.get(clock).map(_.asInstanceOf[BaseType]).getOrElse(clock)
    val localReset = report.toplevel.pulledDataCache.get(reset).map(_.asInstanceOf[BaseType]).getOrElse(reset)
    val paths = new java.util.IdentityHashMap[BaseType, String]()
    val signals = ujson.Obj()
    val bins = mutable.ArrayBuffer[ujson.Value]()
    def walk(c: Component, path: String): Unit = {
      c.dslBody.walkDeclarations {
        case b: BaseType if b.isNamed =>
          val full = path + "." + b.getName()
          paths.put(b, full)
          val tags = b.getTags().collect { case t: Bin => t }.toSeq
          if (tags.nonEmpty || (b eq localClock) || (b eq localReset)) {
            require(!report.prunedSignals.contains(b), s"tagged signal was pruned: $full")
            val sources = tags.map(_.source).distinct
            val types = tags.map(_.typeName).distinct
            require(sources.size <= 1 && types.size <= 1, s"conflicting metadata: $full")
            signals(full) = ujson.Obj("width" -> b.getBitsWidth,
              "type" -> ujson.Str(types.headOption.getOrElse("Bool")),
              "scala" -> sources.headOption.map(_.json).getOrElse(ujson.Null))
            tags.foreach { t =>
              require((t.values ++ t.from).forall(v => v >= 0 && v < (BigInt(1) << b.getBitsWidth)))
              require(b.getBitsWidth <= 52, "event JSON domains support at most 52 bits")
              def pred(v: Seq[BigInt]) = ujson.Obj(full -> ujson.Arr.from(v.map(n => ujson.Num(n.toDouble))))
              val bin = ujson.Obj("id" -> (path + ":" + t.id), "kind" -> t.kind,
                "domain" -> t.domain, "when" -> pred(t.values))
              if (t.kind == "transition") bin("from") = pred(t.from)
              bins += bin
            }
          }
        case _ =>
      }
      c.children.toSeq.sortBy(_.getName()).foreach(ch => walk(ch, path + "." + ch.getName()))
    }
    walk(report.toplevel, "TOP")
    require(paths.containsKey(localClock) && paths.containsKey(localReset), "controls must belong to report")
    require(clock.getBitsWidth == 1 && reset.getBitsWidth == 1)
    require(bins.map(_("id").str).distinct.size == bins.size, "duplicate instance bin ID")
    ujson.Obj("schema" -> "rvw.rtl-plan/1", "design" -> design,
      "clock" -> ujson.Obj("signal" -> paths.get(localClock), "edge" -> "rising", "sampling" -> "pre-edge"),
      "reset" -> ujson.Obj("signal" -> paths.get(localReset), "active" -> resetActive, "rule" -> "disable-clear"),
      "signals" -> signals, "bins" -> ujson.Arr.from(bins))
  }
  def write(plan: ujson.Value, file: File): Unit = Files.writeString(file.toPath, ujson.write(plan, indent = 2))
}
