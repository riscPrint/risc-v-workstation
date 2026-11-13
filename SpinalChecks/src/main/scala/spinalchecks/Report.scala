package spinalchecks

import spinal.core._

/** Minimal JSON writer (the library has no dependencies besides Spinal). */
object Json {
  sealed trait V
  case class Str(s: String) extends V
  case class Num(n: BigDecimal) extends V
  case class Bool_(b: Boolean) extends V
  case object Null extends V
  case class Arr(items: Seq[V]) extends V
  case class Obj(fields: Seq[(String, V)]) extends V

  implicit def str(s: String): V = if (s == null) Null else Str(s)
  implicit def int(i: Int): V = Num(i)
  implicit def long(l: Long): V = Num(l)
  implicit def big(b: BigInt): V = Num(BigDecimal(b))
  implicit def bool(b: Boolean): V = Bool_(b)
  implicit def opt[T](o: Option[T])(implicit f: T => V): V = o.map(f).getOrElse(Null)
  def obj(fields: (String, V)*): Obj = Obj(fields)
  def arr(items: Seq[V]): Arr = Arr(items)

  def quote(s: String): String = {
    val b = new StringBuilder("\"")
    s.foreach {
      case '"' => b ++= "\\\""
      case '\\' => b ++= "\\\\"
      case '\n' => b ++= "\\n"
      case '\r' => b ++= "\\r"
      case '\t' => b ++= "\\t"
      case c if c < 0x20 => b ++= f"\\u${c.toInt}%04x"
      case c => b += c
    }
    b += '"'
    b.toString
  }

  def write(v: V, indent: Int = 0): String = {
    val pad = "  " * (indent + 1)
    val end = "  " * indent
    v match {
      case null => "null"
      case Str(s) => quote(s)
      case Num(n) => n.bigDecimal.toPlainString
      case Bool_(b) => b.toString
      case Null => "null"
      case Arr(items) if items.isEmpty => "[]"
      case Arr(items) if items.forall(i => i.isInstanceOf[Str] || i.isInstanceOf[Num]) =>
        items.map(write(_)).mkString("[", ", ", "]")
      case Arr(items) => items.map(i => pad + write(i, indent + 1)).mkString("[\n", ",\n", s"\n$end]")
      case Obj(fields) if fields.isEmpty => "{}"
      case Obj(fields) => fields.map { case (k, x) => s"$pad${quote(k)}: ${write(x, indent + 1)}" }.mkString("{\n", ",\n", s"\n$end}")
    }
  }
}

object Report {
  import Json._

  /** Verilog-level hierarchical name (`inst.inst.signal`, relative to the toplevel). */
  def vname(path: String, bt: BaseType): String = SpinalChecks.qualify(path, bt.getName())

  /** Signals Spinal removed while simplifying the design have no Verilog name. */
  private def alive(bt: BaseType): Boolean = bt.parentScope != null && bt.component != null

  def json(r: ChecksResult): String = {
    val byKind = r.records.toSeq.map(_.kind).distinct.sorted.flatMap { k =>
      val rs = r.records.filter(_.kind == k)
      if (rs.isEmpty) None else Some(k -> (obj(rs.groupBy(_.status).toSeq.sortBy(_._1).map { case (s, v) => s -> (v.size: V) }: _*): V))
    }
    def loc(l: Option[SourceLoc]): V = l.map(x => obj("file" -> x.file, "line" -> x.line, "class" -> x.className): V).getOrElse(Null)
    // Paths from the final component names (the report is written after name allocation): `c.path`
    // was taken at insertion, before Spinal named components created inside loops.
    val checks = r.records.map { c =>
      val path = SpinalChecks.instancePath(c.component)
      obj(
        "id" -> c.id, "kind" -> c.kind, "status" -> c.status, "reason" -> c.reason,
        "path" -> path, "module" -> c.module, "component_class" -> c.component.getClass.getName,
        "object" -> c.objName, "env" -> c.env, "detail" -> c.detail,
        "source" -> loc(c.location),
        "clock_domain" -> Option(c.clockDomain).map { cd =>
          def signal(bt: Bool): V = Option(bt).flatMap { original =>
            c.component.pulledDataCache.get(original).collect {
              case b: BaseType if alive(b) => b
            }.orElse(Option(original).filter(alive))
          }.map(b => vname(SpinalChecks.instancePath(b.component), b): V).getOrElse(Null)
          obj("clock" -> signal(cd.clock), "edge" -> cd.config.clockEdge.getClass.getSimpleName.stripSuffix("$"),
              "reset" -> signal(cd.reset), "reset_kind" -> cd.config.resetKind.getClass.getSimpleName.stripSuffix("$"),
              "reset_active" -> cd.config.resetActiveLevel.getClass.getSimpleName.stripSuffix("$"),
              "clock_enable" -> signal(cd.clockEnable)): V
        }.getOrElse(Null),
        "trigger_signal" -> Option(c.trigger).map(b => vname(path, b)),
        "fail_signal" -> Option(c.failName).map(n => SpinalChecks.qualify(path, n)),
        "signals" -> obj(c.signals.toSeq.map { case (role, bts) => role -> (arr(bts.filter(alive).map(b => vname(path, b): V)): V) }: _*)
      ): V
    }
    val channels = r.channels.map { ch =>
      val path = SpinalChecks.instancePath(ch.component)
      obj(
        "kind" -> ch.kind, "path" -> path, "object" -> ch.objName, "source" -> loc(ch.location),
        "valid" -> Option(ch.valid).filter(alive).map(vname(path, _)),
        "ready" -> Option(ch.ready).filter(alive).map(vname(path, _)),
        "payload" -> arr(ch.payload.filter(alive).map(b => vname(path, b): V))
      ): V
    }
    write(obj(
      "schema" -> "rvw.checks/1",
      "toplevel" -> r.top.definitionName,
      "mode" -> r.config.mode.name,
      "formal" -> r.formal,
      "counts" -> obj(
        "total" -> r.records.size,
        "inserted" -> r.records.count(_.status == "inserted"),
        "waived" -> r.records.count(_.status == "waived"),
        "disabled" -> r.records.count(_.status == "disabled"),
        "by_kind" -> obj(byKind: _*)),
      "notes" -> arr(r.notes.map(n => n: V).toSeq),
      "checks" -> arr(checks.toSeq),
      "channels" -> arr(channels.toSeq),
      "buses" -> arr(r.buses.map { b =>
        obj("path" -> SpinalChecks.instancePath(b.component), "object" -> b.bus.getName(),
          "class_name" -> b.protocol,
          "signals" -> arr(b.bus.flatten.filter(alive).map(x => x.getName(): V).toList),
          "options" -> obj(b.options.toSeq.sortBy(_._1).map { case (k, v) => k -> (v: V) }: _*)) : V
      }.toSeq)
    )) + "\n"
  }
}
