package spinalblocks

import java.nio.file.Path

import spinal.core._
import spinal.core.internals._

import scala.collection.mutable

/** Walks an elaborated (and generated) Spinal design and builds one block diagram per Verilog module.
  * See docs/FORMAT.md for the output. */
class Extractor(sourceRoots: Seq[Path]) {
  import Model._
  import Extractor._

  private val locate = new Locator(sourceRoots)

  def extract(top: Component): Design = {
    val all = mutable.ArrayBuffer[Component]()
    def walk(c: Component): Unit = { all += c; c.children.foreach(walk) }
    walk(top)
    clockSignals = clockDomainSignals(all.toSeq)
    val counts = all.groupBy(moduleName).map { case (k, v) => k -> v.size }
    val modules = mutable.LinkedHashMap[String, Module]()
    for (c <- all if !modules.contains(moduleName(c)))
      modules(moduleName(c)) = new ModuleExtractor(c).run(counts(moduleName(c)))
    Design(moduleName(top), modules.values.toSeq)
  }

  private def moduleName(c: Component): String =
    if (c.definitionName != null) c.definitionName else c.getClass.getSimpleName

  private def typeName(bt: BaseType): String = bt match {
    case e: SpinalEnumCraft[_] => e.spinalEnum.getName("enum")
    case _: Bool               => "Bool"
    case _: UInt               => "UInt"
    case _: SInt               => "SInt"
    case _: Bits               => "Bits"
    case other                 => other.getClass.getSimpleName
  }

  private def width(bt: BaseType): Int = try bt.getBitsWidth catch { case _: Throwable => 0 }

  private var clockSignals = Set.empty[BaseType]
  private def isClock(bt: BaseType): Boolean =
    clockSignals.contains(bt) || bt.getTags().exists(_.isInstanceOf[ClockDomainBoolTag])

  /** Clock, reset and clock-enable signals of every clock domain, and the ports they were pulled through. */
  private def clockDomainSignals(all: Seq[Component]): Set[BaseType] = {
    val cds = mutable.LinkedHashSet[ClockDomain]()
    for (c <- all) c.dslBody.walkDeclarations {
      case bt: BaseType if bt.isReg && bt.clockDomain != null => cds += bt.clockDomain
      case _ =>
    }
    val roots: Seq[Data] = cds.toSeq.flatMap(cd => Seq(cd.clock, cd.reset, cd.softReset, cd.clockEnable)).filter(_ != null)
    val pulled = for (c <- all; r <- roots; p <- c.pulledDataCache.get(r)) yield p
    (roots ++ pulled).collect { case bt: BaseType => bt }.toSet
  }

  /** Spinal-generated names: `_zz_*`, `when_<File>_l<n>` and other REMOVABLE names. */
  private def isGenerated(n: Nameable with ContextUser): Boolean = n match {
    case bt: BaseType =>
      val p = SpinalBlocksAccess.anonymSignalPrefix(bt)
      val name = bt.getName()
      bt.isUnnamed || name.startsWith("_" + p) || name.startsWith(p + "_") || GeneratedName.matches(name) ||
        SpinalBlocksAccess.namePriority(bt) == Nameable.REMOVABLE
    case other => other.isUnnamed
  }

  private def assignments(bt: BaseType): Seq[AssignmentStatement] = {
    val ret = mutable.ArrayBuffer[AssignmentStatement]()
    bt.foreachStatements(ret += _)
    ret.toSeq
  }

  private def stripCasts(e: Expression): Expression = e match {
    case c: Cast   => stripCasts(c.input)
    case r: Resize => stripCasts(r.input)
    case other     => other
  }

  private def isLiteral(e: Expression): Boolean = stripCasts(e).isInstanceOf[Literal]


  /** Leaves read by an expression tree. `control` marks mux selects. */
  private def reads(e: Expression, control: Boolean, out: (Read, Boolean) => Unit): Unit = e match {
    case bt: BaseType           => out(SigRead(bt), control)
    case p: MemPortStatement    => out(MemRead(p.mem), control) // its address/enable feed the memory node
    case m: Multiplexer         => reads(m.select, true, out); m.inputs.foreach(reads(_, control, out))
    case m: BinaryMultiplexer   => reads(m.cond, true, out); reads(m.whenTrue, control, out); reads(m.whenFalse, control, out)
    case other                  => other.foreachDrivingExpression(reads(_, control, out))
  }

  /** Reads of a statement: its data inputs and the when/switch conditions it sits under. */
  private def statementReads(s: LeafStatement, out: (Read, Boolean) => Unit): Unit = {
    s.foreachDrivingExpression(reads(_, false, out))
    if (s.parentScope != null) s.walkParentTreeStatementsUntilRootScope {
      case w: WhenStatement   => reads(w.cond, true, out)
      case sw: SwitchStatement =>
        reads(sw.value, true, out)
        sw.elements.foreach(_.keys.foreach(reads(_, true, out)))
      case _ =>
    }
  }

  private class ModuleExtractor(c: Component) {
    private val ownIo = c.getAllIo
    private val childOf = mutable.HashMap[BaseType, Component]()
    for (k <- c.children; io <- k.getAllIo) childOf(io) = k

    private val instIds = mutable.LinkedHashMap[Component, String]()
    private val ids = mutable.HashSet[String]()
    private def uniqueId(base: String): String = {
      var id = base; var i = 1
      while (ids.contains(id)) { i += 1; id = s"$base~$i" }
      ids += id; id
    }

    /** Named areas of this component enclosing `n`, outermost first. */
    private def areaChain(n: OwnableRef): List[Area] = owners(n).collect {
      case a: Area if a.component == c && a.isNamed && a.getName().nonEmpty => a
    }

    /** Outermost data (Bundle/Vec) owner, used to group loose signals of one bundle into one node. */
    private def outerData(n: OwnableRef): Option[Data] = owners(n).collect {
      case d: Data if !d.isInstanceOf[BaseType] && d.isNamed && d.component == c && !holdsIo(d) => d
    }.headOption
    // `io_push_fire` is named after an IO stream but is internal logic: don't group it under `io`.
    private val holdsIoCache = mutable.HashMap[Data, Boolean]()
    private def holdsIo(d: Data): Boolean = holdsIoCache.getOrElseUpdate(d, d.flatten.exists(ownIo.contains))

    // ---- classify the signals declared in this component ----
    private val declared = mutable.ArrayBuffer[DeclarationStatement]()
    c.dslBody.walkDeclarations(d => declared += d)
    private val signals = declared.collect { case bt: BaseType => bt }
    private val mems = declared.collect { case m: Mem[_] => m }

    private def isWire(bt: BaseType): Boolean = assignments(bt) match {
      case Seq(a: DataAssignmentStatement) =>
        (a.target eq bt) && (a.parentScope eq a.rootScopeStatement) && stripCasts(a.source).isInstanceOf[BaseType]
      case _ => false
    }
    private def isConstant(bt: BaseType): Boolean = {
      val as = assignments(bt)
      as.nonEmpty && as.forall(a => a.isInstanceOf[DataAssignmentStatement] && isLiteral(a.source))
    }

    /** Signals that are folded into nets instead of becoming nodes. Returns Some(viaName) if named. */
    private val transparent = mutable.HashMap[BaseType, Option[String]]()
    for (bt <- signals if !ownIo.contains(bt) && !bt.isReg) {
      if (isGenerated(bt)) transparent(bt) = None
      else if (isConstant(bt)) transparent(bt) = None
      else if (areaChain(bt).isEmpty && isWire(bt)) transparent(bt) = Some(bt.getName())
    }
    // Output ports that are not registers: their logic is drawn as the wires into the port.
    for (bt <- signals if ownIo.contains(bt) && bt.isOutput && !bt.isReg) transparent(bt) = Some(bt.getName())
    // Child inputs read back in this component: look through to what drives them.
    for ((bt, _) <- childOf if bt.isInput) transparent(bt) = Some(bt.getName())

    // ---- logic nodes ----
    private final class NodeB(val id: String, val name: String, val area: Option[Area], val className: Option[String],
                              val loc: Option[Loc]) {
      var parent: Option[NodeB] = None
      val sigs = mutable.ArrayBuffer[BaseType]()
      val memList = mutable.ArrayBuffer[Mem[_]]()
      var hasChildren = false
      var ownerArea = false // the leaf holding a compound area's own signals
    }
    private val nodes = mutable.LinkedHashMap[String, NodeB]()
    private val areaNodes = mutable.HashMap[Area, NodeB]()

    private def areaNode(a: Area, chain: List[Area]): NodeB = areaNodes.getOrElseUpdate(a, {
      val parent = chain.takeWhile(_ ne a).lastOption.map(p => areaNode(p, chain))
      val nm = Option(a.getPartialName()).filter(_.nonEmpty).getOrElse(a.getName())
      val n = new NodeB(uniqueId("area:" + a.getName()), nm, Some(a), areaClass(a), locate(a))
      n.parent = parent
      parent.foreach(_.hasChildren = true)
      nodes(n.id) = n
      n
    })

    private val looseNodes = mutable.HashMap[AnyRef, NodeB]()
    private val ownerOf = mutable.HashMap[AnyRef, NodeB]() // BaseType or Mem -> node

    /** Groups of loose signals drawn as one node. Bundles stay together; anonymous registers are grouped by
      * the line that created them (`package_l97`); loop copies of a named signal (`x_0`, `x_1`) by name stem. */
    private case class LooseKey(kind: String, name: String, loc: Option[Loc])
    private def stem(name: String): String =
      name.split('_').map(p => if (p.nonEmpty && p.forall(_.isDigit)) "*" else p).mkString("_").stripSuffix("_*")
    private lazy val looseKeys: Map[BaseType, AnyRef] = {
      val loose = signals.toSeq.filter(bt => !transparent.contains(bt) && !ownIo.contains(bt) && areaChain(bt).isEmpty)
      val base: Seq[(BaseType, AnyRef)] = loose.map { bt =>
        val key: AnyRef = outerData(bt).getOrElse {
          if (isGenerated(bt)) {
            val l = locate.creation(bt)
            LooseKey("gen", l.map(l => l.file.split('/').last.stripSuffix(".scala") + "_l" + l.line).getOrElse(stem(bt.getName())), l)
          } else LooseKey("stem", stem(bt.getName()), None)
        }
        bt -> key
      }
      // A name stem only groups when several signals share it; otherwise the signal keeps its own node.
      val stemCount = base.collect { case (_, k: LooseKey) if k.kind == "stem" => k }.groupBy(identity).map { case (k, v) => k -> v.size }
      base.map {
        case (bt, k: LooseKey) if k.kind == "stem" && stemCount(k) < 2 => bt -> (bt: AnyRef)
        case other => other
      }.toMap
    }

    private def place(item: Nameable with OwnableRef with ScalaLocated, isMem: Boolean): NodeB = {
      val chain = areaChain(item)
      chain.lastOption match {
        case Some(a) => areaNode(a, chain)
        case None =>
          val key: AnyRef = item match {
            case bt: BaseType if !isMem => looseKeys.getOrElse(bt, bt)
            case _                      => item
          }
          looseNodes.getOrElseUpdate(key, {
            val (nm, loc) = key match {
              case k: LooseKey => (k.name, k.loc.orElse(locate(item)))
              case n: Nameable with ScalaLocated => (n.getName(), locate(n))
              case n: Nameable => (n.getName(), locate(item))
              case _ => (item.getName(), locate(item))
            }
            val n = new NodeB(uniqueId((if (isMem) "mem:" else "sig:") + nm), nm, None, None, loc)
            nodes(n.id) = n
            n
          })
      }
    }

    for (bt <- signals if !transparent.contains(bt) && (!ownIo.contains(bt) || (bt.isOutput && bt.isReg))) {
      val n = if (ownIo.contains(bt)) {
        // A registered output port: its register gets its own node next to the port.
        val n = new NodeB(uniqueId("sig:" + bt.getName()), bt.getName(), None, None, locate(bt))
        nodes(n.id) = n; n
      } else place(bt, isMem = false)
      n.sigs += bt; ownerOf(bt) = n
    }
    for (m <- mems) { val n = place(m, isMem = true); n.memList += m; ownerOf(m) = n }

    // Instances may sit inside areas too.
    private val instParent = mutable.HashMap[Component, Option[NodeB]]()
    for (k <- c.children) {
      instIds(k) = uniqueId("inst:" + k.getName())
      val chain = areaChain(k)
      instParent(k) = chain.lastOption.map { a => val n = areaNode(a, chain); n.hasChildren = true; n }
    }

    // Compound areas with own signals: move the signals into a leaf child.
    for (n <- nodes.values.toList if n.hasChildren && (n.sigs.nonEmpty || n.memList.nonEmpty)) {
      val leaf = new NodeB(uniqueId(n.id + "/logic"), n.name + " logic", None, None, n.loc)
      leaf.parent = Some(n)
      leaf.sigs ++= n.sigs; leaf.memList ++= n.memList
      (n.sigs ++ n.memList).foreach(ownerOf(_) = leaf)
      n.sigs.clear(); n.memList.clear()
      leaf.ownerArea = true
      nodes(leaf.id) = leaf
    }

    // ---- nets ----
    private def endpointOf(r: Read): Option[(Endpoint, String, Int, Boolean)] = r match {
      case MemRead(m) => ownerOf.get(m).map(n => (NodeEp(n.id), m.getName(), m.width, false))
      case SigRead(bt) =>
        if (ownIo.contains(bt)) {
          if (bt.isInput || bt.isInOut) Some((PortEp(bt.getName()), bt.getName(), width(bt), isClock(bt)))
          else ownerOf.get(bt).map(n => (NodeEp(n.id), bt.getName(), width(bt), isClock(bt)))
        } else childOf.get(bt) match {
          case Some(k) if bt.isOutput || bt.isInOut =>
            Some((InstEp(instIds(k), bt.getName()), k.getName() + "." + bt.getName(), width(bt), isClock(bt)))
          case _ => ownerOf.get(bt).map(n => (NodeEp(n.id), bt.getName(), width(bt), isClock(bt)))
        }
    }

    private case class Src(ep: Endpoint, name: String, width: Int, clock: Boolean)

    /** Sources (non-transparent drivers) of a transparent signal, with control flag and via names. */
    private val memo = mutable.HashMap[BaseType, Map[Src, (Boolean, Set[String])]]()
    private val visiting = mutable.HashSet[BaseType]()

    private def sourcesOf(bt: BaseType): Map[Src, (Boolean, Set[String])] = memo.getOrElse(bt, {
      if (!visiting.add(bt)) return Map.empty
      val acc = mutable.HashMap[Src, (Boolean, Set[String])]()
      assignments(bt).foreach(a => statementReads(a, (r, ctl) => collect(r, ctl, acc)))
      visiting -= bt
      val res = acc.toMap
      memo(bt) = res
      res
    })

    private def merge(acc: mutable.HashMap[Src, (Boolean, Set[String])], s: Src, ctl: Boolean, via: Set[String]): Unit =
      acc.get(s) match {
        case Some((c0, v0)) => acc(s) = (c0 && ctl, v0 ++ via)
        case None           => acc(s) = (ctl, via)
      }

    private def collect(r: Read, ctl: Boolean, acc: mutable.HashMap[Src, (Boolean, Set[String])]): Unit = r match {
      case SigRead(bt) if transparent.contains(bt) =>
        val via = transparent(bt).toSet
        for ((s, (c2, v2)) <- sourcesOf(bt)) merge(acc, s, ctl || c2, v2 ++ via)
      case _ =>
        endpointOf(r).foreach { case (ep, nm, w, clk) => merge(acc, Src(ep, nm, w, clk), ctl, Set.empty) }
    }

    private val netMap = mutable.LinkedHashMap[Src, NetB]()
    private final class NetB(val src: Src) {
      val to = mutable.LinkedHashMap[Endpoint, Boolean]() // sink -> control only
      val via = mutable.LinkedHashSet[String]()
    }

    private def connect(sink: Endpoint, srcs: Iterable[(Src, (Boolean, Set[String]))]): Unit =
      for ((s, (ctl, via)) <- srcs if s.ep != sink) {
        val n = netMap.getOrElseUpdate(s, new NetB(s))
        n.to(sink) = n.to.get(sink).map(_ && ctl).getOrElse(ctl)
        n.via ++= via
      }

    private def readsOfStatements(stmts: Iterable[LeafStatement]): Map[Src, (Boolean, Set[String])] = {
      val acc = mutable.HashMap[Src, (Boolean, Set[String])]()
      stmts.foreach(s => statementReads(s, (r, ctl) => collect(r, ctl, acc)))
      acc.toMap
    }

    def run(instanceCount: Int): Module = {
      // Logic nodes read their signals' and memories' inputs.
      for (n <- nodes.values) {
        val stmts = n.sigs.flatMap(assignments) ++ n.memList.flatMap { m =>
          val b = mutable.ArrayBuffer[LeafStatement](); m.foreachStatements(b += _); b
        }
        connect(NodeEp(n.id), readsOfStatements(stmts).toSeq)
      }
      // Registered output ports: node -> port.
      for (bt <- signals if ownIo.contains(bt) && bt.isOutput && bt.isReg; n <- ownerOf.get(bt))
        connect(PortEp(bt.getName()), Seq(Src(NodeEp(n.id), bt.getName(), width(bt), false) -> (false, Set.empty[String])))
      // Plain output ports and child inputs: whatever drives them.
      for (bt <- signals if ownIo.contains(bt) && bt.isOutput && !bt.isReg)
        connect(PortEp(bt.getName()), readsOfStatements(assignments(bt)).toSeq)
      for (k <- c.children; bt <- ioOrder(k) if bt.isInput || bt.isInOut)
        connect(InstEp(instIds(k), bt.getName()), readsOfStatements(assignments(bt)).toSeq)

      val nets = netMap.values.zipWithIndex.collect { case (n, i) if n.to.nonEmpty =>
        Net(s"n$i", n.src.name, n.src.width, n.via.toSeq.filter(_ != n.src.name), n.to.values.forall(identity),
          n.src.clock, n.src.ep, n.to.keys.toSeq)
      }.toSeq

      val nodeOut = nodes.values.toSeq.map { n =>
        val compound = n.hasChildren
        val regs = n.sigs.count(_.isReg)
        val kind =
          if (n.area.isDefined) "area"
          else if (n.ownerArea) "logic"
          else if (n.memList.nonEmpty && n.sigs.isEmpty) "mem"
          else if (regs == n.sigs.size) "reg" else if (regs == 0) "comb" else "mixed"
        Node(n.id, n.name, kind, n.parent.map(_.id), compound, n.className, n.loc,
          n.sigs.toSeq.map(s => Signal(s.getName(), width(s), typeName(s), s.isReg, locate(s))) ++
            n.memList.toSeq.map(m => Signal(m.getName(), m.width, s"Mem[${m.wordCount}]", reg = false, locate(m))),
          regs, n.sigs.size - regs)
      }

      Module(
        name = moduleName(c),
        className = c.getClass.getName,
        loc = locate.definition(c),
        instanceCount = instanceCount,
        blackbox = c.isInstanceOf[BlackBox],
        ports = ioOrder(c).map(port),
        instances = c.children.toSeq.map(k => Instance(instIds(k), k.getName(), moduleName(k), instParent(k).map(_.id), locate.instantiation(k))),
        nodes = nodeOut,
        nets = nets,
        fsms = new Fsms(c, locate(_), bt => ownerOf.get(bt).map(_.id),
          bt => childOf.get(bt).map(k => s"${k.getName()}.${bt.getName()}").getOrElse(bt.getName()),
          bt => isGenerated(bt)).extract()
      )
    }
  }

  /** Owners of `n` (areas, bundles, components), outermost first. Composite names (`stream_fire`,
    * `Composite` areas of spinal.lib) are followed to the object they are named after. */
  private def owners(n: Any): List[Any] = {
    val out = mutable.ListBuffer[Any]()
    var cur: Any = n
    var depth = 0
    while (cur != null && depth < 64 && (depth == 0 || !cur.isInstanceOf[Component])) {
      val next: Any = cur match {
        case o: Nameable if o.refOwner == null => SpinalBlocksAccess.nameableRef(o)
        case o: OwnableRef                     => o.refOwner
        case _                                 => null
      }
      if (next != null && !next.isInstanceOf[Component]) out.prepend(next)
      cur = next
      depth += 1
    }
    out.toList
  }

  /** Area subclass worth showing (`StateMachine`, `Composite`...), skipping anonymous subclasses. */
  private def areaClass(a: Area): Option[String] = {
    var k: Class[_] = a.getClass
    while (k != null && (k.isAnonymousClass || k.getName.contains("$anon"))) k = k.getSuperclass
    Option(k).map(_.getName).filter(n => n != "java.lang.Object" && n != "spinal.core.Area")
  }

  /** IO of a component in declaration order. */
  private def ioOrder(c: Component): Seq[BaseType] = {
    val io = c.getAllIo
    val out = mutable.ArrayBuffer[BaseType]()
    c.dslBody.walkDeclarations { case bt: BaseType if io.contains(bt) => out += bt; case _ => }
    val seen = out.toSet
    out ++= io.toSeq.filterNot(seen).sortBy(_.getName())
    out.toSeq
  }

  private def port(bt: BaseType): Port = {
    val groups = bt.getRefOwnersChain().collect { case d: Data if !d.isInstanceOf[BaseType] && d.isNamed => d.getName() }
    Port(bt.getName(), if (bt.isInput) "in" else if (bt.isOutput) "out" else "inout", width(bt), typeName(bt),
      groups.lastOption.getOrElse(""), groups, locate(bt))
  }
}

private object Extractor {
  /** Names Spinal gives to condition temporaries: `when_Gcd_l21`, `switch_Misc_l245`. */
  val GeneratedName = """(when|switch)_\w+_l\d+(_\d+)?""".r
  /** Something a statement reads: a signal or a memory. */
  sealed trait Read
  final case class SigRead(bt: BaseType) extends Read
  final case class MemRead(mem: Mem[_]) extends Read
}

/** Source locations for ScalaLocated objects (needs elaboration with location tracking). */
private class Locator(sourceRoots: Seq[Path]) {
  private def userFrame(f: StackTraceElement): Boolean = {
    val c = f.getClassName
    f.getFileName != null && f.getLineNumber > 0 && !f.getFileName.endsWith(".java") &&
      !c.startsWith("java.") && !c.startsWith("jdk.") && !c.startsWith("sun.") && !c.startsWith("scala.") &&
      !c.startsWith("spinalblocks.SpinalBlocks") && !c.startsWith("spinalwaves.") && !c.startsWith("spinal.core.")
  }
  private val cache = mutable.HashMap[(String, String, Int), Model.Loc]()

  private def frames(s: ScalaLocated): Seq[StackTraceElement] = {
    val t = s.getScalaTrace()
    if (t == null) Nil else ScalaLocated.filterStackTrace(t.getStackTrace).filter(userFrame).toSeq
  }

  private def toLoc(f: StackTraceElement): Model.Loc =
    cache.getOrElseUpdate((f.getClassName, f.getFileName, f.getLineNumber), {
      val l = spinalwaves.SourceLocator.fromFrame(f, sourceRoots)
      Model.Loc(l.absPath, l.line)
    })

  // Prefer the user's code over spinal.lib internals (a Stream's valid is "declared" in spinal.lib).
  private def pick(fs: Seq[StackTraceElement]): Option[Model.Loc] =
    fs.find(!_.getClassName.startsWith("spinal.lib.")).orElse(fs.headOption).map(toLoc)

  def apply(s: ScalaLocated): Option[Model.Loc] = pick(frames(s))

  private def classNames(c: Component): Set[String] =
    Iterator.iterate[Class[_]](c.getClass)(_.getSuperclass).takeWhile(_ != null).map(_.getName).toSet

  private val dataClass = mutable.HashMap[String, Boolean]()
  private def isDataClass(name: String): Boolean = dataClass.getOrElseUpdate(name,
    try classOf[Data].isAssignableFrom(Class.forName(name, false, getClass.getClassLoader))
    catch { case _: Throwable => false })

  /** Where a signal was created, outside Bundle constructors: `Reg(Vec(new MicroOp))` points at that line,
    * not at the MicroOp field. */
  def creation(s: ScalaLocated): Option[Model.Loc] = {
    val fs = frames(s)
    // Bundle traits (`trait HasFPUCtrlSigs extends Bundle`) run in `$init$`, called by the Bundle's constructor.
    def inBundle(i: Int): Boolean = isDataClass(fs(i).getClassName) ||
      (fs(i).getMethodName == "$init$" && i + 1 < fs.size && isDataClass(fs(i + 1).getClassName))
    pick(fs.indices.filterNot(inBundle).map(fs)).orElse(pick(fs))
  }

  /** Where a component class is written: a frame inside its own constructor. */
  def definition(c: Component): Option[Model.Loc] = {
    // The class itself first: base class constructors (shared `BoomModule`-style parents) run before it.
    val own = c.getClass.getName
    val names = classNames(c)
    frames(c).find(_.getClassName == own)
      .orElse(frames(c).find(f => names.contains(f.getClassName)))
      .map(toLoc).orElse(apply(c))
  }

  /** Where a component is instantiated: the first frame outside its own class. */
  def instantiation(c: Component): Option[Model.Loc] = {
    val names = classNames(c)
    pick(frames(c).filterNot(f => names.contains(f.getClassName) || names.contains(f.getClassName.stripSuffix("$"))))
  }
}
