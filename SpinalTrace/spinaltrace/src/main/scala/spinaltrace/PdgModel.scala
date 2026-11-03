package spinaltrace

import java.io.{File, PrintWriter}

/** In-memory form of the ChiselTrace `PDGSpec` plus the SpinalTrace extensions (docs/PDG_FORMAT.md). */
object PdgModel {
  object VertexKind {
    val Definition     = "Definition"
    val DataDefinition = "DataDefinition"
    val IO             = "IO"
    val Connection     = "Connection"
    val ControlFlow    = "ControlFlow"
  }
  object EdgeKind {
    val Data        = "Data"
    val Conditional = "Conditional"
    val Declaration = "Declaration"
    val Index       = "Index"
  }

  case class Condition(probeName: Seq[String], probeValue: Seq[BigInt]) {
    def ++(o: Condition): Condition = Condition(probeName ++ o.probeName, probeValue ++ o.probeValue)
    def isEmpty: Boolean = probeName.isEmpty
  }
  object Condition { val empty: Condition = Condition(Nil, Nil) }

  case class Location(file: String, line: Int, char: Int)
  object Location { val unknown: Location = Location("", 0, 0) }

  case class Vertex(
      loc: Location,
      name: String,
      kind: String,
      clocked: Boolean,
      modulePath: Seq[String],
      relatedSignal: Option[(String, String)] = None,
      assignsTo: Option[String] = None,
      isChiselStatement: Boolean = false,
      condition: Option[Condition] = None,
      assignDelay: Int = 0,
      assignRange: Option[String] = None // SpinalTrace extension: partial (bit/range) assignment key
  )

  case class Edge(from: Int, to: Int, kind: String, clocked: Boolean, condition: Option[Condition])

  case class Predicate(name: String, loc: Location)

  /** One key of a switch case: a bit pattern ('0'/'1'/'-', MSB first) or the value of another signal. */
  sealed trait CaseKey
  case class PatternKey(pattern: String) extends CaseKey
  case class SignalKey(signal: String) extends CaseKey

  sealed trait CfgNode
  case class CfgStatement(stmtRef: Int) extends CfgNode
  case class CfgFork(stmtRef: Int, predRef: Int, trueBranch: Seq[CfgNode], falseBranch: Seq[CfgNode]) extends CfgNode
  case class CfgSwitch(stmtRef: Int, predRef: Int, cases: Seq[(Seq[CaseKey], Seq[CfgNode])], default: Seq[CfgNode]) extends CfgNode

  case class ClockDomainInfo(
      clock: String,
      reset: Option[String],
      resetKind: String,
      resetActiveLow: Boolean,
      clockEnable: Option[String],
      softReset: Option[String],
      registers: Int
  )

  case class Meta(
      toplevel: String,
      extraScopes: Seq[String],
      clockDomains: Seq[ClockDomainInfo],
      warnings: Seq[String]
  )

  case class Pdg(vertices: Seq[Vertex], edges: Seq[Edge], predicates: Seq[Predicate], cfg: Seq[CfgNode], meta: Meta)

  // ---------------------------------------------------------------- JSON
  private def condJson(c: Option[Condition]): ujson.Value = c match {
    case Some(c) if !c.isEmpty =>
      ujson.Obj("probeName" -> ujson.Arr(c.probeName.map(ujson.Str(_)): _*),
                "probeValue" -> ujson.Arr(c.probeValue.map(v => ujson.Num(v.toDouble)): _*))
    case _ => ujson.Null
  }

  private def vertexJson(v: Vertex): ujson.Obj = {
    val o = ujson.Obj(
      "file" -> v.loc.file,
      "line" -> v.loc.line,
      "char" -> v.loc.char,
      "name" -> v.name,
      "kind" -> v.kind,
      "clocked" -> v.clocked,
      "modulePath" -> ujson.Arr(v.modulePath.map(ujson.Str(_)): _*),
      "relatedSignal" -> (v.relatedSignal match {
        case Some((s, f)) => ujson.Obj("signalPath" -> s, "fieldPath" -> f)
        case None         => ujson.Null
      }),
      "assignsTo" -> v.assignsTo.map(ujson.Str(_)).getOrElse(ujson.Null),
      "isChiselStatement" -> v.isChiselStatement,
      "condition" -> condJson(v.condition),
      "assignDelay" -> v.assignDelay
    )
    v.assignRange.foreach(r => o("assignRange") = r)
    o
  }

  private def keyJson(k: CaseKey): ujson.Value = k match {
    case PatternKey(p) => ujson.Obj("pattern" -> p)
    case SignalKey(s)  => ujson.Obj("signal" -> s)
  }

  private def cfgJson(nodes: Seq[CfgNode]): ujson.Arr = ujson.Arr(nodes.map {
    case CfgStatement(r) => ujson.Obj("stmtRef" -> r)
    case CfgFork(r, p, t, f) =>
      val o = ujson.Obj("stmtRef" -> r, "predStmtRef" -> p)
      if (t.nonEmpty) o("trueBranch") = cfgJson(t)
      if (f.nonEmpty) o("falseBranch") = cfgJson(f)
      o
    case CfgSwitch(r, p, cases, d) =>
      val o = ujson.Obj("stmtRef" -> r, "predStmtRef" -> p,
        "cases" -> ujson.Arr(cases.map { case (keys, branch) =>
          ujson.Obj("keys" -> ujson.Arr(keys.map(keyJson): _*), "branch" -> cfgJson(branch))
        }: _*))
      if (d.nonEmpty) o("defaultBranch") = cfgJson(d)
      o
  }: _*)

  def toJson(pdg: Pdg): ujson.Obj = ujson.Obj(
    "accuracy" -> ujson.Obj(
      "status" -> (if (pdg.meta.warnings.nonEmpty || pdg.vertices.exists(_.assignRange.contains("dyn"))) "incomplete"
        else if (pdg.vertices.exists(_.assignRange.nonEmpty)) "approximate" else "exact"),
      "reasons" -> ujson.Arr((pdg.meta.warnings ++
        (if (pdg.vertices.exists(_.assignRange.nonEmpty)) Seq("Partial writes use bounded or conservative providers; signal criteria select the latest provider.") else Nil)).map(ujson.Str(_)): _*)
    ),
    "vertices" -> ujson.Arr(pdg.vertices.map(vertexJson): _*),
    "edges" -> ujson.Arr(pdg.edges.map(e => ujson.Obj(
      "from" -> e.from, "to" -> e.to, "kind" -> e.kind, "clocked" -> e.clocked, "condition" -> condJson(e.condition))): _*),
    "predicates" -> ujson.Arr(pdg.predicates.map(p => ujson.Obj(
      "file" -> p.loc.file, "line" -> p.loc.line, "char" -> p.loc.char, "name" -> p.name,
      "kind" -> VertexKind.DataDefinition, "clocked" -> false, "isChiselStatement" -> false)): _*),
    "cfg" -> cfgJson(pdg.cfg),
    "spinaltrace" -> ujson.Obj(
      "formatVersion" -> 2,
      "toplevel" -> pdg.meta.toplevel,
      "extraScopes" -> ujson.Arr(pdg.meta.extraScopes.map(ujson.Str(_)): _*),
      "clockDomains" -> ujson.Arr(pdg.meta.clockDomains.map(cd => ujson.Obj(
        "clock" -> cd.clock,
        "reset" -> cd.reset.map(ujson.Str(_)).getOrElse(ujson.Null),
        "resetKind" -> cd.resetKind,
        "resetActiveLow" -> cd.resetActiveLow,
        "clockEnable" -> cd.clockEnable.map(ujson.Str(_)).getOrElse(ujson.Null),
        "softReset" -> cd.softReset.map(ujson.Str(_)).getOrElse(ujson.Null),
        "registers" -> cd.registers)): _*),
      "warnings" -> ujson.Arr(pdg.meta.warnings.map(ujson.Str(_)): _*)
    )
  )

  def write(pdg: Pdg, file: File): File = {
    file.getAbsoluteFile.getParentFile.mkdirs()
    val w = new PrintWriter(file, "UTF-8")
    try w.write(ujson.write(toJson(pdg), indent = 1)) finally w.close()
    file
  }
}
