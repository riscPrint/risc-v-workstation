package spinalblocks

import java.nio.file.{Files, Paths}

import spinal.core._
import spinal.core.internals._
import spinal.lib.fsm.StateMachine

import scala.collection.mutable
import scala.jdk.CollectionConverters._

/** State machines of one component (docs/FORMAT.md, "State machines"):
  *  - every spinal.lib `StateMachine` (states, entry, gotos);
  *  - every other register of a SpinalEnum type whose assignments are enum constants.
  *
  * A transition is an assignment of a state constant to the state register (or to the signal that feeds it,
  * like a StateMachine's `stateNext`). Its source state comes from the enclosing `switch(state)` /
  * `when(state === X)`; the other enclosing conditions become the condition text. */
private[spinalblocks] class Fsms(
    c: Component,
    locate: ScalaLocated => Option[Model.Loc],
    /** Logic node id that owns a signal. */
    nodeOf: BaseType => Option[String],
    /** How a signal is written in condition text (child ports as `inst.port`). */
    signalName: BaseType => String,
    /** Compiler temporaries (`when_Foo_l12`) are printed as their expression. */
    isTemporary: BaseType => Boolean
) {
  import Model._

  def extract(): Seq[Fsm] = {
    val machines = mutable.ArrayBuffer[Fsm]()
    val covered = mutable.HashSet[BaseType]()
    val ids = mutable.HashSet[String]()
    def uniqueId(base: String): String = { var id = base; var i = 1; while (ids(id)) { i += 1; id = s"$base~$i" }; ids += id; id }

    // spinal.lib StateMachines: found through their state register's owners.
    val regs = mutable.ArrayBuffer[SpinalEnumCraft[_]]()
    c.dslBody.walkDeclarations {
      case e: SpinalEnumCraft[_] if e.isReg && e.component == c => regs += e
      case _ =>
    }
    for (r <- regs) stateMachineOf(r) match {
      case Some(sm) if sm.stateReg eq r =>
        covered += r
        machines += fromStateMachine(sm, r, uniqueId("fsm:" + sm.getName()))
      case _ =>
    }
    for (r <- regs if !covered(r)) {
      val f = fromEnumRegister(r, uniqueId("fsm:" + r.getName()))
      if (f.transitions.exists(_.to.isDefined)) machines += f
    }
    // Small UInt/Bits registers used like Chisel's `Enum(n)` states (`rob_state := s_normal`).
    c.dslBody.walkDeclarations {
      case r: BitVector if r.isReg && r.component == c && !r.isInstanceOf[SInt] && width(r) >= 1 && width(r) <= 8 =>
        fromValueRegister(r).foreach(f => machines += f.copy(id = uniqueId(f.id)))
      case _ =>
    }
    machines.toSeq
  }

  private def stateMachineOf(r: BaseType): Option[StateMachine] =
    r.getRefOwnersChain().collect { case sm: StateMachine => sm }.lastOption

  // ---- StateMachine ----

  private def fromStateMachine(sm: StateMachine, reg: SpinalEnumCraft[_], id: String): Fsm = {
    val boot = sm.stateBoot
    val elementName = (s: spinal.lib.fsm.State) => sm.enumOf(s).getName()
    val bootName = if (sm.states.contains(boot)) Some(elementName(boot)) else None
    val raw = transitions(reg, defaultState = bootName)
    // The internal BOOT state only jumps to the entry state: show the entry state as the reset state instead.
    val bootOnlyEnters = bootName.exists(b => raw.filter(_.from.contains(b)).forall(t => t.condition.isEmpty && t.to.isDefined))
    val reset =
      if (bootName.isDefined && bootOnlyEnters) raw.find(t => t.from == bootName).flatMap(_.to).orElse(Option(sm.entryState).map(elementName))
      else bootName
    // Transitions driven by the machine's own start/kill/exit plumbing are how BOOT works, not user transitions.
    val internal = Seq(sm.wantStart, sm.wantKill, sm.wantExit).filter(_ != null).map(_.getName())
    val user = raw.filterNot(t => t.condition.exists(cnd => internal.exists(n => cnd.split("[^A-Za-z0-9_.]+").contains(n))))
    val trans = if (bootOnlyEnters) user.filterNot(t => t.from == bootName || t.to == bootName) else user
    val states = sm.states.toSeq
      .filter(s => !(bootOnlyEnters && (s eq boot)))
      .map(s => FsmState(elementName(s), locate(s)))
    Fsm(id, sm.getName(), nodeOf(reg), reg.getName(), "statemachine", locate(sm), states, reset, trans)
  }

  // ---- plain enum registers ----

  private def fromEnumRegister(reg: SpinalEnumCraft[_], id: String): Fsm = {
    val states = reg.spinalEnum.elements.map(e => FsmState(e.getName(), None)).toSeq
    val reset = assignments(reg).collectFirst {
      case a: InitAssignmentStatement => literalState(a.source)
    }.flatten
    Fsm(id, reg.getName(), nodeOf(reg), reg.getName(), "enum", locate(reg), states, reset, transitions(reg, defaultState = None))
  }

  /** A literal's value; None for don't-care (poisoned) literals. */
  private def value(l: BitVectorLiteral): Option[BigInt] = try Some(l.getValue()) catch { case _: Exception => None }

  private def width(bt: BaseType): Int = try bt.getBitsWidth catch { case _: Throwable => 0 }

  /** A register is a state machine when it only takes constants (or keeps its value), takes at least two
    * different ones, and at least one assignment depends on its current value. Counters and data
    * registers fail this test. */
  private def fromValueRegister(reg: BitVector): Option[Fsm] = {
    names.clear()
    val first = transitions(reg, defaultState = None)
    val targets = first.flatMap(_.to).distinct
    val unresolved = first.count(_.to.isEmpty)
    if (targets.size < 2 || !first.exists(_.from.isDefined) || unresolved * 3 > first.size) return None
    val reset = assignments(reg).collectFirst { case a: InitAssignmentStatement => literalState(a.source) }.flatten
    // Second pass: now that the states are known, default branches and `=/=` tests expand to them.
    val keys = (first.flatMap(t => t.from.toSeq ++ t.to.toSeq) ++ reset.toSeq ++ names.keys.map(v => s"#$v")).distinct
    val trans = transitions(reg, defaultState = None, known = keys)
    val sorted = keys.sortBy(k => if (k.startsWith("#")) BigInt(k.drop(1)) else BigInt(-1))
    def show(k: String) = if (k.startsWith("#")) names.get(BigInt(k.drop(1))).map(_._1).getOrElse(k.drop(1)) else k
    val states = sorted.map(k => FsmState(show(k), if (k.startsWith("#")) names.get(BigInt(k.drop(1))).flatMap(_._2) else None))
    Some(Fsm("fsm:" + reg.getName(), reg.getName(), nodeOf(reg), reg.getName(), "enum", locate(reg), states,
      reset.map(show), trans.map(t => t.copy(from = t.from.map(show), to = t.to.map(show)))))
  }

  /** Names of constant signals seen as states, by value (`val s_normal = U(1, 2 bits)`). */
  private val names = mutable.HashMap[BigInt, (String, Option[Loc])]()

  // ---- transitions ----

  private def assignments(bt: BaseType): Seq[AssignmentStatement] = {
    val out = mutable.ArrayBuffer[AssignmentStatement]()
    bt.foreachStatements(out += _)
    out.toSeq
  }

  private def strip(e: Expression): Expression = e match {
    case c: Cast   => strip(c.input)
    case r: Resize => strip(r.input)
    case other     => other
  }

  /** State key of a constant: an enum element's name, or "#<value>" for numbers (named constant signals
    * are remembered in `names`). */
  private def literalState(e: Expression): Option[String] = strip(e) match {
    case l: EnumLiteral[_]    => Some(l.senum.getName())
    case l: BitVectorLiteral  => value(l).map(v => s"#$v")
    case bt: BaseType if !bt.isReg && !bt.isInput && !bt.isInstanceOf[SpinalEnumCraft[_]] =>
      single(bt).flatMap(x => strip(x) match {
        case l: BitVectorLiteral => value(l).map { v =>
          if (!isTemporary(bt) && !names.contains(v)) names(v) = (bt.getName(), locate(bt))
          s"#$v"
        }
        case _ => None
      })
    case _ => None
  }

  /** The register and the combinational signals of the same type that feed it (StateMachine's stateNext). */
  private def stateSignals(reg: BaseType): Seq[BaseType] = {
    val out = mutable.LinkedHashSet[BaseType](reg)
    def feeds(s: BaseType) = !s.isReg && !s.isInput && s.component == c && !out(s) && s.getClass == reg.getClass &&
      width(s) == width(reg) && literalState(s).isEmpty
    def visit(bt: BaseType, depth: Int): Unit = if (depth < 4) for (a <- assignments(bt) if a.isInstanceOf[DataAssignmentStatement]) {
      val found = mutable.ArrayBuffer[BaseType]()
      a.source.walkDrivingExpressions { case s: BaseType if feeds(s) => found += s; case _ => }
      strip(a.source) match { case s: BaseType if feeds(s) => found += s; case _ => }
      for (s <- found.distinct if !out(s)) { out += s; visit(s, depth + 1) }
    }
    visit(reg, 0)
    out.toSeq
  }

  private def isStateRead(e: Expression, reg: BaseType): Boolean = strip(e) eq reg

  private def transitions(reg: BaseType, defaultState: Option[String], known: Seq[String] = Nil): Seq[FsmTransition] = {
    val all = reg match {
      case e: SpinalEnumCraft[_] => e.spinalEnum.elements.map(_.getName()).toSeq
      case _                     => known
    }
    val signals = stateSignals(reg)
    val out = mutable.LinkedHashMap[(Option[String], Option[String], Option[String]), FsmTransition]()
    for (target <- signals; a <- assignments(target) if a.isInstanceOf[DataAssignmentStatement]) {
      val src = strip(a.source)
      val holds = src.isInstanceOf[BaseType] && signals.contains(src)
      if (!holds) {
        val to = literalState(src)
        // Walk the enclosing whens/switches from the innermost out.
        var from: Option[Seq[String]] = None
        val conds = mutable.ArrayBuffer[String]()
        var impossible = false
        var scope = a.parentScope
        while (scope != null && scope.parentStatement != null) {
          scope.parentStatement match {
            case w: WhenStatement if (scope eq w.whenTrue) && constant(w.cond).contains(false) => impossible = true
            case w: WhenStatement if (scope eq w.whenFalse) && constant(w.cond).contains(true) => impossible = true
            case w: WhenStatement =>
              val positive = scope eq w.whenTrue
              stateTest(w.cond, reg) match {
                // Outer tests of the state in an elsewhen chain are implied by the inner one.
                case Some(_) if from.isDefined =>
                case Some(states) if positive && from.isEmpty => from = Some(states)
                case Some(states) if !positive && from.isEmpty => from = Some(all.filterNot(states.contains))
                case _ => splitStateTest(w.cond, reg) match {
                  // when(state === X && cond): in state X, under cond.
                  case Some((states, rest)) if positive && from.isEmpty =>
                    from = Some(states)
                    conds.prepend(rest)
                  case _ => conds.prepend(if (positive) text(w.cond) else negate(text(w.cond)))
                }
              }
            case sw: SwitchStatement if isStateRead(sw.value, reg) && from.isEmpty =>
              val element = sw.elements.find(_.scopeStatement eq scope)
              from = Some(element match {
                case Some(el) => el.keys.toSeq.flatMap(k => literalState(k))
                case None     => defaultState.map(Seq(_)).getOrElse(all.filterNot(s => sw.elements.exists(_.keys.exists(k => literalState(k).contains(s)))))
              })
            case sw: SwitchStatement =>
              val element = sw.elements.find(_.scopeStatement eq scope)
              conds.prepend(element match {
                case Some(el) => s"${text(sw.value)} is ${el.keys.map(k => text(k)).mkString(", ")}"
                case None     => s"${text(sw.value)} is default"
              })
            case _ =>
          }
          scope = scope.parentStatement.parentScope
        }
        val condition = if (conds.isEmpty) None else if (conds.size == 1) Some(conds.head) else Some(conds.map(paren).mkString(" && "))
        val loc = locate(a)
        val comment = loc.flatMap(commentAt)
        if (!impossible) for (f <- from.filter(_.nonEmpty).map(_.map(Option(_))).getOrElse(Seq(None))) {
          val key = (f, to, condition)
          if (!out.contains(key) && !(f.isDefined && f == to && condition.isEmpty))
            out(key) = FsmTransition(f, to, condition, comment, loc)
        }
      }
    }
    out.values.toSeq
  }

  /** Value of a condition that is constant (StateMachine's wantStart/wantKill are False when unused). */
  private def constant(e: Expression, depth: Int = 0): Option[Boolean] = if (depth > 8) None else strip(e) match {
    case b: BoolLiteral => Some(b.value)
    case bt: BaseType if !bt.isReg && !bt.isInput => single(bt).flatMap(constant(_, depth + 1))
    case n: Operator.Bool.Not => constant(n.source, depth + 1).map(!_)
    case a: Operator.Bool.And => (constant(a.left, depth + 1), constant(a.right, depth + 1)) match {
      case (Some(false), _) | (_, Some(false)) => Some(false)
      case (Some(true), Some(true))            => Some(true)
      case _                                   => None
    }
    case _ => None
  }

  /** `state === X && rest` (either order, looking through temporaries): the states and the rest. */
  private def splitStateTest(e: Expression, reg: BaseType, depth: Int = 0): Option[(Seq[String], String)] =
    if (depth > 6) None else strip(e) match {
      case a: Operator.Bool.And =>
        stateTest(a.left, reg).map(_ -> text(a.right))
          .orElse(stateTest(a.right, reg).map(_ -> text(a.left)))
          .orElse(splitStateTest(a.left, reg, depth + 1).map { case (s, r) => s -> s"${paren(r)} && ${paren(text(a.right))}" })
          .orElse(splitStateTest(a.right, reg, depth + 1).map { case (s, r) => s -> s"${paren(text(a.left))} && ${paren(r)}" })
      case bt: BaseType if isTemporary(bt) => single(bt).flatMap(splitStateTest(_, reg, depth + 1))
      case _ => None
    }

  /** `state === X` / `state =/= X` / `isActive(X)` style tests on the state register. */
  private def stateTest(e: Expression, reg: BaseType): Option[Seq[String]] = strip(e) match {
    case eq: BinaryOperator if eq.opName.endsWith(" === " + eq.opName.split(' ').head) || eq.isInstanceOf[Operator.Enum.Equal] =>
      if (isStateRead(eq.left, reg)) literalState(eq.right).map(Seq(_))
      else if (isStateRead(eq.right, reg)) literalState(eq.left).map(Seq(_))
      else None
    case bt: BaseType if isTemporary(bt) => single(bt).flatMap(stateTest(_, reg))
    case _ => None
  }

  private def single(bt: BaseType): Option[Expression] = assignments(bt) match {
    case Seq(a: DataAssignmentStatement) if a.target eq bt => Some(a.source)
    case _                                                => None
  }

  // ---- condition text ----

  private def negate(s: String): String = if (s.startsWith("!") && !s.contains(' ')) s.drop(1) else s"!${paren(s)}"
  private def paren(s: String): String = if (s.contains(' ') && !(s.startsWith("(") && s.endsWith(")"))) s"($s)" else s

  /** Spinal-ish source text of an expression; compiler temporaries are expanded. */
  def text(e: Expression, depth: Int = 0): String = {
    if (depth > 12) return "…"
    def t(x: Expression) = text(x, depth + 1)
    strip(e) match {
      case l: EnumLiteral[_]  => l.senum.getName()
      case b: BoolLiteral     => if (b.value) "True" else "False"
      case l: BitVectorLiteral => value(l).map(_.toString).getOrElse("x")
      case bt: BaseType if isTemporary(bt) => single(bt).map(x => t(x)).getOrElse(signalName(bt))
      case bt: BaseType       => signalName(bt)
      case a: BitVectorBitAccessFixed    => s"${t(a.source)}(${a.bitId})"
      case a: BitVectorRangedAccessFixed => s"${t(a.source)}(${a.hi} downto ${a.lo})"
      case m: Multiplexer     => s"${t(m.select)} ? …"
      case op: BinaryOperator =>
        val parts = op.opName.split(' ')
        val sym = if (parts.length == 3) parts(1) else op.opName
        s"${paren(t(op.left))} $sym ${paren(t(op.right))}"
      case op: UnaryOperator  =>
        val sym = op.opName.split(' ').headOption.getOrElse("?")
        s"$sym${paren(t(op.source))}"
      case other =>
        val args = mutable.ArrayBuffer[String]()
        other.foreachExpression(x => args += t(x))
        val name = other.opName.takeWhile(_ != ' ')
        if (args.isEmpty) name else s"$name(${args.mkString(", ")})"
    }
  }

  // ---- comments ----

  private val lines = mutable.HashMap[String, Array[String]]()

  /** The `//` comment on a source line, if the file is readable. */
  private def commentAt(loc: Loc): Option[String] = {
    val src = lines.getOrElseUpdate(loc.file, {
      val p = Paths.get(loc.file)
      if (p.isAbsolute && Files.isRegularFile(p)) Files.readAllLines(p).asScala.toArray else Array.empty[String]
    })
    if (loc.line < 1 || loc.line > src.length) return None
    val l = src(loc.line - 1)
    val i = l.indexOf("//")
    if (i < 0) None else Some(l.substring(i + 2).trim).filter(_.nonEmpty)
  }
}
