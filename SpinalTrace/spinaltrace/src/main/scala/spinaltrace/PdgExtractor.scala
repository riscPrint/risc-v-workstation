package spinaltrace

import java.io.File

import spinal.core._
import spinal.core.internals._
import spinalwaves.HglNaming

import scala.collection.mutable
import scala.collection.mutable.ArrayBuffer

import PdgModel._

/** Options of the PDG extraction. */
case class ExtractOptions(
    /** Extra source roots used to turn bare stack-trace file names into absolute paths. */
    sourceRoots: Seq[File] = Nil,
    /** Memories with more words than this are tracked as one coarse symbol instead of per word. */
    maxMemWords: Int = 4096,
    /** Keep spinal.lib frames as statement locations (default: report the user's call site). */
    includeLibraryFrames: Boolean = false,
    /** VCD scopes above the toplevel's signals; default `TOP <toplevel definition name>`. */
    extraScopes: Option[Seq[String]] = None
)

/** Walks the final Spinal netlist (after name allocation) and builds a ChiselTrace-format PDG.
  *
  * Conventions (see docs/PDG_FORMAT.md):
  *  - one symbol per Spinal BaseType = `HglNaming.rtlPath(bt)` (also the VCD path below the extra
  *    scopes), so assignments in a parent to a child IO and reads in the child meet on the same symbol;
  *  - one CFG statement per Spinal statement; `when` -> boolean fork on the (named) condition signal;
  *    `switch` -> case fork on the value signal (SpinalTrace CFG extension);
  *  - dynamic selects/indexes go through `defnode_probe_*` vertices (Index edges) and edge/vertex
  *    conditions on the select signal's value, exactly like ChiselTrace's inserted probes, except that
  *    the probe *value* is read from the existing (named) Spinal signal.
  */
class PdgExtractor(report: SpinalReport[_ <: Component], opts: ExtractOptions = ExtractOptions()) {
  private val top        = report.toplevel
  private val locs       = new Locations(opts.sourceRoots, opts.includeLibraryFrames)
  private val pruned     = identitySet(report.prunedSignals)
  private val warnings   = mutable.LinkedHashSet[String]()
  private val generated: BaseType => Boolean = Netlist.isGenerated

  private case class Dep(symbol: String, isIndex: Boolean, cond: Condition)
  private class Stmt(val vertex: Int, val deps: Seq[Dep], val provides: Seq[String], val clocked: Boolean)

  private val vertices   = ArrayBuffer[Vertex]()
  private val stmts      = ArrayBuffer[Stmt]()
  private val predicates = ArrayBuffer[Predicate]()
  private val predIndex  = mutable.HashMap[String, Int]()
  private var uniq       = 0

  private def identitySet[T <: AnyRef](xs: Iterable[T]): java.util.Set[T] = {
    val s = java.util.Collections.newSetFromMap(new java.util.IdentityHashMap[T, java.lang.Boolean]())
    xs.foreach(s.add)
    s
  }

  private def fresh(prefix: String): String = { uniq += 1; s"$$$prefix$uniq" }

  private def warn(msg: String): Unit = warnings += msg

  // ------------------------------------------------------------------ naming helpers
  private def sym(bt: BaseType): String = HglNaming.rtlPath(bt)

  private def memSym(m: Mem[_]): String = (HglNaming.instancePath(m.component) :+ m.getName()).mkString(".")

  /** Name of `bt` as seen from component `from` (child signals get the child instance path). */
  private def rel(bt: BaseType, from: Component): String = {
    val p = HglNaming.instancePath(bt.component)
    val f = HglNaming.instancePath(from)
    if (p.startsWith(f)) (p.drop(f.length) :+ bt.getName()).mkString(".") else sym(bt)
  }

  private def relatedSignal(bt: BaseType): Option[(String, String)] =
    if (generated(bt)) None else Some(HglNaming.hglPath(bt))

  // ------------------------------------------------------------------ clock-domain plumbing
  /** Clock-domain signals. Spinal's ClockDomain signals may live outside the netlist; the real ports
    * that carry them have an `ExternalDriverTag(driver)` and children get them through plain wiring. */
  private val cdSignals: java.util.Set[BaseType] = identitySet[BaseType](Nil)
  /** Netlist signal (preferably a toplevel port) standing for a clock-domain signal. */
  private val cdPort = new java.util.IdentityHashMap[BaseType, BaseType]()

  private val clockish: java.util.Set[BaseType] = {
    val s = identitySet[BaseType](Nil)
    def addCd(cd: ClockDomain): Unit = if (cd != null) {
      Seq(cd.clock, cd.reset, cd.softReset, cd.clockEnable).foreach(b => if (b != null) { cdSignals.add(b); s.add(b) })
    }
    val all = ArrayBuffer[BaseType]()
    top.walkComponents { c =>
      addCd(c.clockDomain)
      c.dslBody.walkStatements {
        case bt: BaseType =>
          all += bt
          if (bt.isReg) addCd(bt.clockDomain)
        case st: Statement => st.foreachClockDomain(addCd)
      }
    }
    all.foreach { bt =>
      bt.getTag(classOf[ExternalDriverTag]).foreach { t =>
        t.driver match {
          case d: BaseType if cdSignals.contains(d) =>
            s.add(bt)
            if (!cdPort.containsKey(d) || (bt.component eq top)) cdPort.put(d, bt)
          case _ =>
        }
      }
      if (bt.hasTag(classOf[ClockDomainBoolTag])) s.add(bt)
    }
    cdSignals.forEach(d => if (d.component != null && !cdPort.containsKey(d)) cdPort.put(d, d))
    // Close over plain wiring: anything assigned straight from a clock-domain signal is plumbing.
    var changed = true
    while (changed) {
      changed = false
      top.walkComponents(_.dslBody.walkStatements {
        case a: DataAssignmentStatement =>
          (a.target, a.source) match {
            // Only wiring counts as plumbing: child ports and anonymous wires, never registers or
            // user-named signals (e.g. `RegNext(reset)` stays traceable).
            case (t: BaseType, src: BaseType) if s.contains(src) && !s.contains(t) && !t.isReg &&
                ((t.isInput && (t.component ne top)) || generated(t)) => s.add(t); changed = true
            case _                                                                 =>
          }
        case _ =>
      })
    }
    s
  }

  // ------------------------------------------------------------------ statements
  private case class Ctx(comp: Component, condSym: Option[String], vcond: Condition,
                         vcondIndex: Seq[(Expression, Condition)], instSym: Option[String]) {
    val modulePath: Seq[String] = HglNaming.instancePath(comp)
  }

  private def addStmt(v: Vertex, deps: Seq[Dep], provides: Seq[String], clocked: Boolean): Int = {
    vertices += v
    stmts += new Stmt(vertices.length - 1, deps, provides, clocked)
    vertices.length - 1
  }

  private def predicate(bt: BaseType, loc: Location): Int =
    predIndex.getOrElseUpdate(sym(bt), { predicates += Predicate(sym(bt), loc); predicates.length - 1 })

  /** Expression walk result. */
  private class ExprInfo {
    val data   = ArrayBuffer[Dep]()
    val index  = ArrayBuffer[(Expression, Condition)]()
    var delay  = 0
    var vcond  = Condition.empty
    var leaves = ArrayBuffer[String]()
  }

  private def single(name: String, v: BigInt) = Condition(Seq(name), Seq(v))

  private def walkExpr(e: Expression, c: Condition, info: ExprInfo, from: Component): Unit = e match {
    case bt: BaseType =>
      if (!clockish.contains(bt)) { info.data += Dep(sym(bt), isIndex = false, c); info.leaves += rel(bt, from) }
    case _: Literal => // constants have no provider
    case m: BinaryMultiplexer =>
      m.cond match {
        case l: Literal => walkExpr(if (l.getValue() != 0) m.whenTrue else m.whenFalse, c, info, from)
        case sel: BaseType =>
          info.index += ((sel, c))
          walkExpr(m.whenTrue, c ++ single(sym(sel), 1), info, from)
          walkExpr(m.whenFalse, c ++ single(sym(sel), 0), info, from)
        case other =>
          warn(s"mux select is an anonymous expression (${other.getClass.getSimpleName}); both inputs are reported as dependencies")
          info.index += ((other, c)); walkExpr(m.whenTrue, c, info, from); walkExpr(m.whenFalse, c, info, from)
      }
    case m: Multiplexer =>
      m.select match {
        case l: Literal =>
          val i = l.getValue().toInt
          if (i < m.inputs.length) walkExpr(m.inputs(i), c, info, from)
        case sel: BaseType =>
          info.index += ((sel, c))
          m.inputs.zipWithIndex.foreach { case (in, i) => walkExpr(in, c ++ single(sym(sel), i), info, from) }
        case other =>
          warn(s"mux select is an anonymous expression (${other.getClass.getSimpleName}); all inputs are reported as dependencies")
          info.index += ((other, c)); m.inputs.foreach(walkExpr(_, c, info, from))
      }
    case a: BitVectorBitAccessFloating =>
      walkExpr(a.source, c, info, from); info.index += ((a.bitId, c))
    case a: BitVectorRangedAccessFloating =>
      walkExpr(a.source, c, info, from); info.index += ((a.offset, c))
    case r: MemReadAsync =>
      memRead(r.mem, r.address, r.getWidth, c, info)
    case r: MemReadSync =>
      memRead(r.mem, r.address, r.getWidth, c, info); info.delay = 1
      enableCond(r.readEnable, info)
    case r: MemReadWrite =>
      memRead(r.mem, r.address, r.getWidth, c, info); info.delay = 1
      enableCond(r.chipSelect, info)
    case r: MemReadAsyncWrite =>
      memRead(r.mem, r.address, r.getWidth, c, info)
    case other =>
      other.foreachExpression(walkExpr(_, c, info, from))
  }

  private def enableCond(en: Expression, info: ExprInfo): Unit = en match {
    case l: Literal if l.getValue() != 0 =>
    case bt: BaseType                      => info.vcond = info.vcond ++ single(sym(bt), 1); info.index += ((bt, Condition.empty))
    case null                              =>
    case other =>
      warn(s"memory port enable is an anonymous expression (${other.getClass.getSimpleName}); read assumed always enabled")
  }

  /** Per-word symbols of a memory, or None when it is tracked coarsely. */
  private def memWords(m: Mem[_]): Option[Seq[String]] =
    if (m.wordCount <= opts.maxMemWords) Some((0 until m.wordCount).map(i => s"${memSym(m)}.$i")) else None

  private def memRead(m: Mem[_], address: Expression, width: Int, c: Condition, info: ExprInfo): Unit = {
    info.leaves += m.getName()
    val words = if (width == m.width) memWords(m) else {
      warn(s"mixed-width access to memory ${memSym(m)} is tracked coarsely"); None
    }
    (words, address) match {
      case (None, a) =>
        info.data += Dep(memSym(m), isIndex = false, c); info.index += ((a, c))
      case (Some(ws), l: Literal) =>
        val i = l.getValue().toInt
        if (i < ws.length) info.data += Dep(ws(i), isIndex = false, c)
      case (Some(ws), bt: BaseType) =>
        info.index += ((bt, c))
        ws.zipWithIndex.foreach { case (w, i) => info.data += Dep(w, isIndex = false, c ++ single(sym(bt), i)) }
      case (Some(ws), other) =>
        warn(s"memory ${memSym(m)} is read with an anonymous address expression; every word is a dependency")
        info.index += ((other, c)); ws.foreach(w => info.data += Dep(w, isIndex = false, c))
    }
  }

  /** Probe vertices for index/select expressions (ChiselTrace's `defnode_probe_*`), placed in the CFG
    * right before their user. Returns the Index dependencies of the user. */
  private def probes(index: Seq[(Expression, Condition)], loc: Location, ctx: Ctx, out: ArrayBuffer[CfgNode]): Seq[Dep] = {
    val seen = mutable.HashSet[(String, Condition)]()
    index.flatMap { case (e, c) =>
      val info = new ExprInfo
      walkExpr(e, Condition.empty, info, ctx.comp)
      val label = e match {
        case bt: BaseType => rel(bt, ctx.comp)
        case _            => info.leaves.distinct.mkString("_")
      }
      if (info.data.isEmpty || !seen.add((label, c))) Nil
      else {
        val s = fresh("probe")
        val v = addStmt(
          Vertex(loc, s"defnode_probe_$label", VertexKind.DataDefinition, clocked = false, ctx.modulePath,
            assignsTo = Some(s), isChiselStatement = false),
          info.data.map(_.copy(cond = Condition.empty)).toSeq ++ ctx.instSym.map(Dep(_, isIndex = false, Condition.empty)),
          Seq(s), clocked = false)
        out += CfgStatement(v)
        Seq(Dep(s, isIndex = true, c))
      }
    }
  }

  private def commonDeps(ctx: Ctx): Seq[Dep] =
    ctx.condSym.map(Dep(_, isIndex = false, Condition.empty)).toSeq ++
      ctx.instSym.map(Dep(_, isIndex = false, Condition.empty))

  private def vcondOpt(c: Condition): Option[Condition] = if (c.isEmpty) None else Some(c)

  /** Comb signal declared and fully assigned once on the same line: a Chisel `node` (`defnode_`). */
  private def isNodeLike(bt: BaseType): Boolean =
    !bt.isReg && !bt.isInput && !bt.isOutput && (Netlist.assignments(bt) match {
      case Seq(a: DataAssignmentStatement) =>
        (a.target eq bt) && (a.parentScope eq bt.parentScope) && locs.ofAssignment(a).line == locs.of(bt).line
      case _ => false
    })

  private def hasInit(bt: BaseType): Boolean = Netlist.assignments(bt).exists(a =>
    a.isInstanceOf[InitAssignmentStatement] || a.isInstanceOf[InitialAssignmentStatement])

  private def emitAssign(a: AssignmentStatement, ctx: Ctx, out: ArrayBuffer[CfgNode]): Unit = {
    val bt = a.finalTarget
    if (pruned.contains(bt) || clockish.contains(bt)) return
    a.source match {
      case src: BaseType if clockish.contains(src) => return
      case _                                       =>
    }
    val isInit = a.isInstanceOf[InitAssignmentStatement] || a.isInstanceOf[InitialAssignmentStatement]
    val (range, targetIndex) = a.target match {
      case t: BitAssignmentFixed       => (Some(t.bitId.toString), Nil)
      case t: RangedAssignmentFixed    => (Some(s"${t.hi}:${t.lo}"), Nil)
      case t: BitAssignmentFloating    => (Some("dyn"), Seq((t.bitId: Expression, Condition.empty)))
      case t: RangedAssignmentFloating => (Some("dyn"), Seq((t.offset: Expression, Condition.empty)))
      case _                           => (None, Nil)
    }
    val loc  = locs.ofAssignment(a)
    val info = new ExprInfo
    walkExpr(a.source, Condition.empty, info, ctx.comp)
    val idxDeps = probes(info.index.toSeq ++ targetIndex ++ ctx.vcondIndex, loc, ctx, out)
    val r       = rel(bt, ctx.comp)
    val (name, kind) =
      if (isInit) (s"defreg_$r", VertexKind.DataDefinition)
      else if (isNodeLike(bt)) (s"defnode_$r", VertexKind.DataDefinition)
      else (s"connect_$r", VertexKind.Connection)
    val clocked = bt.isReg || isInit
    val v = addStmt(
      Vertex(loc, name, kind, clocked, ctx.modulePath, relatedSignal(bt), Some(sym(bt)), !generated(bt),
        vcondOpt(ctx.vcond ++ info.vcond), info.delay, range),
      info.data.toSeq ++ idxDeps ++ commonDeps(ctx), Seq(sym(bt)), clocked)
    out += CfgStatement(v)
  }

  private def emitDecl(bt: BaseType, ctx: Ctx, out: ArrayBuffer[CfgNode]): Unit = {
    if (pruned.contains(bt) || clockish.contains(bt)) return
    val loc     = locs.of(bt)
    val r       = rel(bt, ctx.comp)
    val isTop   = bt.component eq top
    if (bt.isInput || bt.isOutput) {
      val dirName = if (bt.isInput) "input" else "output"
      if (isTop && bt.isInput) {
        out += CfgStatement(addStmt(Vertex(loc, s"input_$r", VertexKind.IO, clocked = false, ctx.modulePath,
          relatedSignal(bt), Some(sym(bt)), isChiselStatement = true), Nil, Seq(sym(bt)), clocked = false))
      } else if (isTop) {
        out += CfgStatement(addStmt(Vertex(loc, s"output_$r", VertexKind.IO, clocked = false, ctx.modulePath,
          isChiselStatement = true), Seq(Dep(sym(bt), isIndex = false, Condition.empty)), Nil, clocked = false))
      } else {
        // Child IO: declaration only, the parent-side assignment provides the value (ChiselTrace makes
        // non-main IO statements Definitions for the same reason).
        out += CfgStatement(addStmt(Vertex(loc, s"${dirName}_$r", VertexKind.Definition, clocked = false, ctx.modulePath,
          isChiselStatement = true), commonDeps(ctx), Seq(sym(bt)), clocked = false))
      }
    } else if (bt.isReg) {
      if (!hasInit(bt))
        out += CfgStatement(addStmt(Vertex(loc, s"defreg_$r", VertexKind.Definition, clocked = true, ctx.modulePath,
          isChiselStatement = !generated(bt)), commonDeps(ctx), Seq(sym(bt)), clocked = true))
    } else if (!isNodeLike(bt)) {
      out += CfgStatement(addStmt(Vertex(loc, s"defwire_$r", VertexKind.Definition, clocked = false, ctx.modulePath,
        isChiselStatement = !generated(bt)), commonDeps(ctx), Seq(sym(bt)), clocked = false))
    }
  }

  private def condLabel(bt: BaseType, from: Component): String =
    Netlist.soleDriver(bt, generated) match {
      case Some(drv) =>
        val info = new ExprInfo
        walkExpr(drv, Condition.empty, info, from)
        val l = info.leaves.distinct
        if (l.isEmpty) rel(bt, from) else l.mkString(", ")
      case None => rel(bt, from)
    }

  private def emitWhen(w: WhenStatement, ctx: Ctx, out: ArrayBuffer[CfgNode]): Unit = {
    Netlist.vecWriteIndex(w.cond, generated) match {
      case Some((addr: BaseType, i)) if w.whenFalse.isEmpty =>
        // Dynamic Vec write: the element statements carry a vertex condition on the address value.
        val c = ctx.copy(vcond = ctx.vcond ++ single(sym(addr), i), vcondIndex = ctx.vcondIndex :+ ((addr, Condition.empty)))
        out ++= walkScope(w.whenTrue, c)
        return
      case _ =>
    }
    val loc = locs.of(w)
    w.cond match {
      case l: Literal =>
        out ++= walkScope(if (l.getValue() != 0) w.whenTrue else w.whenFalse, ctx)
      case cond: BaseType =>
        val info = new ExprInfo
        walkExpr(cond, Condition.empty, info, ctx.comp)
        val s   = fresh("cond")
        val pre = ArrayBuffer[CfgNode]()
        val v = addStmt(Vertex(loc, s"cond_on_[${condLabel(cond, ctx.comp)}]", VertexKind.ControlFlow, clocked = false,
          ctx.modulePath, relatedSignal(cond), None, isChiselStatement = true, vcondOpt(ctx.vcond)),
          info.data.toSeq ++ commonDeps(ctx), Seq(s), clocked = false)
        val inner = ctx.copy(condSym = Some(s))
        out += CfgFork(v, predicate(cond, loc), walkScope(w.whenTrue, inner).toSeq, walkScope(w.whenFalse, inner).toSeq)
      case other =>
        warn(s"when condition at ${loc.file}:${loc.line} is an anonymous ${other.getClass.getSimpleName}; " +
          "both branches are treated as active")
        out ++= walkScope(w.whenTrue, ctx); out ++= walkScope(w.whenFalse, ctx)
    }
  }

  private def bitsOf(v: BigInt, width: Int): String = {
    val m = if (v < 0) v + (BigInt(1) << width) else v
    val s = m.toString(2)
    if (s.length >= width) s.takeRight(width) else "0" * (width - s.length) + s
  }

  private def caseKey(k: Expression, width: Int, loc: Location): Option[(CaseKey, String)] = k match {
    case l: EnumLiteral[_]     => Some((PatternKey(bitsOf(l.getValue(), width)), l.senum.getName()))
    case l: Literal            => Some((PatternKey(bitsOf(l.getValue(), width)), l.getValue().toString))
    case kb: SwitchStatementKeyBool if kb.key != null =>
      val ml = kb.key
      val p = (0 until ml.width).reverse.map { b =>
        if (!ml.careAbout.testBit(b)) '-' else if (ml.value.testBit(b)) '1' else '0'
      }.mkString
      Some((PatternKey(p), p))
    case bt: BaseType => Some((SignalKey(sym(bt)), bt.getName()))
    case other =>
      warn(s"unsupported switch key ${other.getClass.getSimpleName} at ${loc.file}:${loc.line}; that case is never taken")
      None
  }

  private def emitSwitch(sw: SwitchStatement, ctx: Ctx, out: ArrayBuffer[CfgNode]): Unit = {
    val loc = locs.of(sw)
    sw.value match {
      case value: BaseType =>
        val width = value.getBitsWidth
        val info  = new ExprInfo
        walkExpr(value, Condition.empty, info, ctx.comp)
        val label = condLabel(value, ctx.comp)
        val s     = fresh("switch")
        val v = addStmt(Vertex(loc, s"switch_on_[$label]", VertexKind.ControlFlow, clocked = false, ctx.modulePath,
          relatedSignal(value), None, isChiselStatement = true, vcondOpt(ctx.vcond)),
          info.data.toSeq ++ commonDeps(ctx), Seq(s), clocked = false)
        val cases = sw.elements.map { el =>
          val elLoc = locs.of(el)
          val keys  = el.keys.flatMap(k => caseKey(k, width, elLoc))
          val keyDeps = el.keys.collect { case bt: BaseType => Dep(sym(bt), isIndex = false, Condition.empty) }
          val cs = fresh("case")
          val body = ArrayBuffer[CfgNode]()
          body += CfgStatement(addStmt(Vertex(elLoc, s"case_on_[$label is ${keys.map(_._2).mkString(", ")}]",
            VertexKind.ControlFlow, clocked = false, ctx.modulePath, isChiselStatement = true),
            Seq(Dep(s, isIndex = false, Condition.empty)) ++ keyDeps ++ ctx.instSym.map(Dep(_, isIndex = false, Condition.empty)),
            Seq(cs), clocked = false))
          body ++= walkScope(el.scopeStatement, ctx.copy(condSym = Some(cs)))
          (keys.map(_._1).toSeq, body.toSeq)
        }
        val default = if (sw.defaultScope == null) Nil else {
          val cs   = fresh("case")
          val dLoc = sw.defaultScope.head match { case null => loc; case st => locs.of(st) }
          val body = ArrayBuffer[CfgNode]()
          body += CfgStatement(addStmt(Vertex(dLoc, s"case_on_[$label default]", VertexKind.ControlFlow, clocked = false,
            ctx.modulePath, isChiselStatement = true),
            Seq(Dep(s, isIndex = false, Condition.empty)) ++ ctx.instSym.map(Dep(_, isIndex = false, Condition.empty)),
            Seq(cs), clocked = false))
          body ++= walkScope(sw.defaultScope, ctx.copy(condSym = Some(cs)))
          body.toSeq
        }
        out += CfgSwitch(v, predicate(value, loc), cases.toSeq, default)
      case other =>
        warn(s"switch value at ${loc.file}:${loc.line} is an anonymous ${other.getClass.getSimpleName}; all cases treated as active")
        sw.elements.foreach(el => out ++= walkScope(el.scopeStatement, ctx))
        if (sw.defaultScope != null) out ++= walkScope(sw.defaultScope, ctx)
    }
  }

  private def emitMemWrite(m: Mem[_], address: Expression, data: Expression, enables: Seq[Expression],
                           loc: Location, ctx: Ctx, out: ArrayBuffer[CfgNode]): Unit = {
    val info = new ExprInfo
    walkExpr(data, Condition.empty, info, ctx.comp)
    var vcond = ctx.vcond
    val index = ArrayBuffer[(Expression, Condition)]()
    var never = false
    enables.foreach {
      case null                                =>
      case l: Literal                          => if (l.getValue() == 0) never = true
      case bt: BaseType                        => vcond = vcond ++ single(sym(bt), 1); index += ((bt, Condition.empty))
      case other =>
        warn(s"memory ${memSym(m)} write enable is an anonymous ${other.getClass.getSimpleName}; write assumed enabled")
    }
    if (never) return
    def emit(word: String, wordName: String, c: Condition, extraIndex: Seq[(Expression, Condition)]): Unit = {
      val idx = probes(index.toSeq ++ extraIndex ++ ctx.vcondIndex, loc, ctx, out)
      out += CfgStatement(addStmt(Vertex(loc, s"connect_$wordName", VertexKind.Connection, clocked = true, ctx.modulePath,
        None, Some(word), isChiselStatement = true, vcondOpt(c)), info.data.toSeq ++ idx ++ commonDeps(ctx), Seq(word),
        clocked = true))
    }
    (memWords(m), address) match {
      case (None, a) => emit(memSym(m), m.getName(), vcond, Seq((a, Condition.empty)))
      case (Some(ws), l: Literal) =>
        val i = l.getValue().toInt
        if (i < ws.length) emit(ws(i), s"${m.getName()}.$i", vcond, Nil)
      case (Some(ws), bt: BaseType) =>
        ws.zipWithIndex.foreach { case (w, i) =>
          emit(w, s"${m.getName()}.$i", vcond ++ single(sym(bt), i), Seq((bt, Condition.empty)))
        }
      case (Some(ws), other) =>
        warn(s"memory ${memSym(m)} is written with an anonymous address expression; every word is a provider")
        ws.zipWithIndex.foreach { case (w, i) => emit(w, s"${m.getName()}.$i", vcond, Seq((other, Condition.empty))) }
    }
  }

  private def walkScope(scope: ScopeStatement, ctx: Ctx): ArrayBuffer[CfgNode] = {
    val out = ArrayBuffer[CfgNode]()
    scope.foreachStatements {
      case w: WhenStatement       => emitWhen(w, ctx, out)
      case sw: SwitchStatement    => emitSwitch(sw, ctx, out)
      case a: AssignmentStatement => emitAssign(a, ctx, out)
      case bt: BaseType           => emitDecl(bt, ctx, out)
      case m: Mem[_] =>
        val loc = locs.of(m)
        memWords(m) match {
          case Some(ws) => ws.zipWithIndex.foreach { case (w, i) =>
            out += CfgStatement(addStmt(Vertex(loc, s"defmem_${m.getName()}.$i", VertexKind.Definition, clocked = true,
              ctx.modulePath, isChiselStatement = true), commonDeps(ctx), Seq(w), clocked = true))
          }
          case None =>
            warn(s"memory ${memSym(m)} has ${m.wordCount} words (> maxMemWords=${opts.maxMemWords}); tracked as one symbol, " +
              "so a read depends on the last write to any address")
            out += CfgStatement(addStmt(Vertex(loc, s"defmem_${m.getName()}", VertexKind.Definition, clocked = true,
              ctx.modulePath, isChiselStatement = true), commonDeps(ctx), Seq(memSym(m)), clocked = true))
        }
      case w: MemWrite =>
        if (w.mask != null) warn(s"memory ${memSym(w.mem)}: write masks are ignored (masked writes count as full-word writes)")
        emitMemWrite(w.mem, w.address, w.data, Seq(w.writeEnable), locs.of(w), ctx, out)
      case rw: MemReadWrite =>
        emitMemWrite(rw.mem, rw.address, rw.data, Seq(rw.chipSelect, rw.writeEnable), locs.of(rw), ctx, out)
      case _: MemReadSync | _: MemReadAsync => // handled where the read data is assigned
      case rw: MemReadAsyncWrite =>
        warn(s"memory ${memSym(rw.mem)}: MemReadAsyncWrite ports are only traced on their read side")
      case as: AssertStatement =>
        val loc  = locs.of(as)
        val info = new ExprInfo
        walkExpr(as.cond, Condition.empty, info, ctx.comp)
        val kind = as.kind match {
          case AssertStatementKind.ASSUME => "assume"
          case AssertStatementKind.COVER  => "cover"
          case _                          => "assert"
        }
        val file = new File(loc.file).getName.stripSuffix(".scala")
        val idx  = probes(info.index.toSeq, loc, ctx, out)
        out += CfgStatement(addStmt(Vertex(loc, s"${kind}_${file}_l${loc.line}", VertexKind.Connection,
          clocked = as.trigger == AssertStatementTrigger.CLOCKED, ctx.modulePath, isChiselStatement = true,
          condition = vcondOpt(ctx.vcond)), info.data.toSeq ++ idx ++ commonDeps(ctx), Nil,
          clocked = as.trigger == AssertStatementTrigger.CLOCKED))
      case other =>
        warn(s"unsupported Spinal statement ${other.getClass.getName} at ${locs.of(other).file}:${locs.of(other).line} (ignored)")
    }
    out
  }

  private def walkComponent(c: Component, instSym: Option[String]): ArrayBuffer[CfgNode] = {
    val ctx = Ctx(c, None, Condition.empty, Nil, instSym)
    val out = walkScope(c.dslBody, ctx)
    c.children.foreach { child =>
      val loc   = locs.of(child)
      val iSym  = fresh("inst")
      val iVert = addStmt(Vertex(loc, s"definstance_${child.getName()}", VertexKind.Definition, clocked = false,
        ctx.modulePath, isChiselStatement = true), commonDeps(ctx), Seq(iSym), clocked = true)
      child match {
        case bb: BlackBox if bb.isBlackBox => out ++= walkBlackBox(bb, Some(iSym))
        case _                             => out ++= walkComponent(child, Some(iSym))
      }
      out += CfgStatement(iVert)
    }
    out
  }

  /** BlackBoxes are opaque: every output depends on every (non clock-domain) input. */
  private def walkBlackBox(bb: BlackBox, instSym: Option[String]): ArrayBuffer[CfgNode] = {
    warn(s"BlackBox ${HglNaming.instancePath(bb).mkString(".")} (${bb.definitionName}) is opaque: each output depends on all inputs")
    val out    = ArrayBuffer[CfgNode]()
    val loc    = locs.of(bb)
    val ios    = bb.getAllIo.toSeq.filterNot(clockish.contains)
    val inputs = ios.filter(_.isInput).map(i => Dep(sym(i), isIndex = false, Condition.empty))
    val path   = HglNaming.instancePath(bb)
    ios.filter(_.isOutput).foreach { o =>
      out += CfgStatement(addStmt(Vertex(loc, s"blackbox_${bb.getName()}.${o.getName()}", VertexKind.Connection,
        clocked = false, path.dropRight(1), relatedSignal(o), Some(sym(o)), isChiselStatement = true),
        inputs ++ instSym.map(Dep(_, isIndex = false, Condition.empty)), Seq(sym(o)), clocked = false))
    }
    out
  }

  // ------------------------------------------------------------------ clock domains / metadata
  private def rootOf(bt: BaseType): BaseType = {
    var cur   = bt
    var guard = 0
    while (cur != null && (cur.component ne top) && cur.isInput && guard < 64) {
      guard += 1
      Netlist.assignments(cur) match {
        case Seq(a: DataAssignmentStatement) =>
          a.source match {
            case src: BaseType => cur = src
            case _             => return cur
          }
        case _ => return cur
      }
    }
    cur
  }

  private def clockDomains(): Seq[ClockDomainInfo] = {
    val byClock = mutable.LinkedHashMap[BaseType, (ClockDomain, Int)]()
    def count(cd: ClockDomain): Unit = if (cd != null && cd.clock != null) {
      val root = Option(cdPort.get(cd.clock)).map(rootOf).getOrElse(cd.clock)
      val key  = byClock.keys.find(k => (k eq root) || path(k) == path(root)).getOrElse(root)
      val prev = byClock.get(key).map(_._2).getOrElse(0)
      byClock(key) = (byClock.get(key).map(_._1).getOrElse(cd), prev + 1)
    }
    top.walkComponents(_.dslBody.walkStatements {
      case bt: BaseType if bt.isReg && !pruned.contains(bt) => count(bt.clockDomain)
      case w: MemWrite                                      => count(w.clockDomain)
      case r: MemReadSync                                   => count(r.clockDomain)
      case _                                                =>
    })
    if (byClock.isEmpty && top.clockDomain != null && top.clockDomain.clock != null) {
      byClock(top.clockDomain.clock) = (top.clockDomain, 0)
    }
    byClock.toSeq.map { case (clk, (cd, n)) =>
      def p(b: BaseType) = Option(b).map(path)
      ClockDomainInfo(path(clk), p(cd.reset), cd.config.resetKind.toString, cd.config.resetActiveLevel == LOW,
        p(cd.clockEnable), p(cd.softReset), n)
    }
  }

  /** VCD path of a (possibly virtual) clock-domain signal. */
  private def path(b: BaseType): String = {
    val port = cdPort.get(b)
    if (port != null) sym(rootOf(port))
    else if (b.component != null) sym(rootOf(b))
    else b.getName()
  }

  // ------------------------------------------------------------------ edges
  private def buildEdges(): Seq[Edge] = {
    val providers = mutable.HashMap[String, ArrayBuffer[Stmt]]()
    stmts.foreach(s => s.provides.foreach(p => providers.getOrElseUpdate(p, ArrayBuffer()) += s))
    val edges = ArrayBuffer[Edge]()
    for (s <- stmts; d <- s.deps) {
      providers.get(d.symbol) match {
        case None =>
          if (!d.symbol.startsWith("$")) warn(s"no provider for ${d.symbol} (used by ${vertices(s.vertex).name})")
        case Some(ps) =>
          val cond = vcondOpt(d.cond)
          for (p <- ps) {
            if (d.isIndex) edges += Edge(s.vertex, p.vertex, EdgeKind.Index, s.clocked, cond)
            else vertices(p.vertex).kind match {
              case VertexKind.DataDefinition =>
                edges += Edge(s.vertex, p.vertex, EdgeKind.Data, s.clocked, cond)
                edges += Edge(s.vertex, p.vertex, EdgeKind.Declaration, clocked = false, cond)
              case VertexKind.Connection | VertexKind.IO =>
                edges += Edge(s.vertex, p.vertex, EdgeKind.Data, s.clocked, cond)
              case VertexKind.ControlFlow =>
                edges += Edge(s.vertex, p.vertex, EdgeKind.Conditional, s.clocked, cond)
              case _ =>
                edges += Edge(s.vertex, p.vertex, EdgeKind.Declaration, clocked = false, cond)
            }
          }
      }
    }
    edges.distinct.toSeq
  }

  def extract(): Pdg = {
    val cfg     = walkComponent(top, None)
    val edges   = buildEdges()
    val domains = clockDomains()
    if (domains.size > 1)
      warn(s"design has ${domains.size} clock domains (${domains.map(_.clock).mkString(", ")}); SpinalTrace (like " +
        "ChiselTrace) steps all registers on one clock, so dependencies through other domains are approximate")
    domains.filter(_.clockEnable.nonEmpty).foreach(d =>
      warn(s"clock domain ${d.clock} has a clock enable (${d.clockEnable.get}); register updates are assumed on every edge"))
    domains.filter(_.softReset.nonEmpty).foreach(d =>
      warn(s"clock domain ${d.clock} has a soft reset (${d.softReset.get}); it is not modelled"))
    val scopes = opts.extraScopes.getOrElse(Seq("TOP", top.definitionName))
    Pdg(vertices.toSeq, edges, predicates.toSeq, cfg.toSeq, Meta(top.definitionName, scopes, domains, warnings.toSeq))
  }
}

object PdgExtractor {
  def extract(report: SpinalReport[_ <: Component], opts: ExtractOptions = ExtractOptions()): Pdg =
    new PdgExtractor(report, opts).extract()

  def extractTo(report: SpinalReport[_ <: Component], file: File, opts: ExtractOptions = ExtractOptions()): File =
    PdgModel.write(extract(report, opts), file)
}
