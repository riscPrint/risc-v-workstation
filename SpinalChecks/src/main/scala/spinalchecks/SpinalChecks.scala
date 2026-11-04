package spinalchecks

import java.nio.file.{Files, Paths}

import spinal.core._
import spinal.core.internals._
import spinal.core.sim._
import spinal.lib._
import spinal.lib.bus.tilelink
import spinal.lib.fsm.StateMachine

import scala.collection.mutable
import scala.language.existentials
import scala.collection.mutable.ArrayBuffer

/** Entry points. Typical use:
  * {{{
  *   val (cfg, checks) = SpinalChecks.install(SpinalConfig(targetDirectory = "gen"), ChecksConfig())
  *   cfg.generateVerilog(new MyTop)          // or SimConfig.withConfig(cfg).compile(new MyTop)
  *   // gen/MyTop.checks.json lists every check; checks.records holds them in this JVM
  * }}}
  */
object SpinalChecks {
  /** A copy of `config` that inserts the checks while elaborating, and the result they are recorded in. */
  def install(config: SpinalConfig, checks: ChecksConfig = ChecksConfig()): (SpinalConfig, ChecksResult) = {
    val result = new ChecksResult(checks)
    val c = config.copy(phasesInserters = config.phasesInserters.clone())
    c.phasesInserters += { phases =>
      // After reflection naming and enum collection (names are known), before the IO/hierarchy checks,
      // clock-domain pulling and width inference (the checks go through them like user logic).
      val at = phases.indexWhere(_.isInstanceOf[PhaseCheckIoBundle])
      require(at >= 0, "SpinalChecks: PhaseCheckIoBundle not found (unsupported Spinal version?)")
      phases.insert(at, new PhaseInsertChecks(checks, result))
      val named = phases.indexWhere(_.isInstanceOf[PhaseAllocateNames])
      if (named >= 0) phases.insert(named + 1, new PhaseChecksReport(checks, result))
    }
    (c, result)
  }

  /** Spinal records creation stacks (source locations) only for `debugComponents`. Elaborate once up to
    * naming to learn every component class, and return `config` with all of them as debug components.
    * The generator runs twice, so it must be deterministic. */
  def withLocations[T <: Component](config: SpinalConfig)(gen: => T): SpinalConfig = {
    val scratch = Files.createTempDirectory("spinalchecks-locations-")
    try {
      val inserters = config.phasesInserters.clone()
      inserters += { phases =>
        // Stop before naming: a discarded backend pass would rename shared SpinalEnum singletons.
        val naming = phases.indexWhere(_.isInstanceOf[PhaseNameNodesByReflection])
        require(naming >= 0, "SpinalChecks: PhaseNameNodesByReflection not found")
        phases.dropRightInPlace(phases.size - naming)
      }
      val first = config.copy(targetDirectory = scratch.toString, phasesInserters = inserters).generateVerilog(gen)
      val classes = mutable.HashSet.empty[Class[_]] ++ config.debugComponents
      def collect(c: Component): Unit = { classes += c.getClass; c.children.foreach(collect) }
      collect(first.toplevel)
      config.copy(debugComponents = classes)
    } finally {
      import scala.jdk.CollectionConverters._
      val files = Files.walk(scratch)
      try files.iterator().asScala.toVector.sortBy(_.getNameCount).reverse.foreach(Files.delete)
      finally files.close()
    }
  }

  /** The checks of an elaborated toplevel (also works on a simulation's `dut`). */
  def result(top: Component): ChecksResult = top.getTag(classOf[ChecksTag]).map(_.result)
    .getOrElse(throw new IllegalStateException(s"${top.definitionName} was not elaborated with SpinalChecks"))

  /** Instance path below the toplevel from the components' current names. Spinal names a component
    * that has no name (one created inside a loop body) only at name allocation, after the checks are
    * inserted; until then its segment is its class name with a lower-case first letter. Never an empty
    * segment. The report calls it after name allocation, so its paths are the final Verilog names;
    * check ids use `instanceIds`, which are distinct per instance before naming. */
  private[spinalchecks] def instancePath(c: Component): String =
    if (c.parent == null) "" else {
      val p = instancePath(c.parent)
      val n = segment(c)
      if (p.isEmpty) n else p + "." + n
    }

  /** The identity path of every component below `top` (the toplevel is ""), fixed before any check id
    * is formed. Spinal allocates the final instance names only after the checks are inserted, against
    * names this phase cannot see yet (definition names, case-insensitively), so loop-built siblings
    * that all read `stage` here may become `stage_2` and `stage_3`. Here each parent's children get
    * distinct segments: named children keep their names (a repeated name gets `_1`, `_2`, ...), then
    * unnamed ones take their `segment` with the first free suffix, in child order. An id is therefore
    * unique per instance; the report's `path` is the final Verilog name. */
  private[spinalchecks] def instanceIds(top: Component): Map[Component, String] = {
    val out = mutable.LinkedHashMap[Component, String](top -> "")
    def walk(c: Component): Unit = {
      val taken = mutable.HashSet[String]()
      val seg = mutable.LinkedHashMap[Component, String]()
      val (named, unnamed) = c.children.toSeq.partition(k => !k.isUnnamed && k.getName() != null && k.getName().nonEmpty)
      for (k <- named ++ unnamed) seg(k) = unique(segment(k), taken)
      for (k <- c.children) { out(k) = qualify(out(c), seg(k)); walk(k) }
    }
    walk(top)
    out.toMap
  }

  /** `base`, or `base_1`, `base_2`, ... : the first not in `taken` (which it is added to). */
  private[spinalchecks] def unique(base: String, taken: mutable.Set[String]): String = {
    var n = base; var i = 0
    while (taken.contains(n)) { i += 1; n = s"${base}_$i" }
    taken += n
    n
  }

  private def segment(c: Component): String = {
    val n = if (c.isUnnamed) null else c.getName()
    if (n != null && n.nonEmpty) n
    else {
      val k = c.getClass.getSimpleName.stripSuffix("$").replaceAll("[^A-Za-z0-9_]", "_")
      if (k.isEmpty || !k.head.isLetter) "anon" else s"${k.head.toLower}${k.tail}"
    }
  }

  private[spinalchecks] def qualify(path: String, name: String) = if (path.isEmpty) name else path + "." + name
}

/** Inserts the generated checks into every component of the elaborated design. */
class PhaseInsertChecks(cfg: ChecksConfig, result: ChecksResult) extends PhaseNetlist {
  import SpinalChecks.{qualify, unique}

  private def isPow2(n: Int) = n > 0 && (n & (n - 1)) == 0

  /** A signal with a driver (or an input): only those can be referenced by a check without creating
    * a "no driver" error for a signal Spinal would otherwise have pruned. */
  private def driven(bt: BaseType): Boolean = bt.isInput || bt.isInOut || !bt.dlcIsEmpty

  private def hasResetValue(bt: BaseType): Boolean = {
    var r = false
    bt.foreachStatements { case _: InitAssignmentStatement => r = true; case _ => }
    r
  }
  private def unresetNote(bt: Any): String = bt match {
    case b: BaseType if b.isReg && !hasResetValue(b) => ", armed once the register is first written (no reset value)"
    case _ => ""
  }

  private def sanitize(s: String) = {
    val t = s.replaceAll("[^A-Za-z0-9_]", "_")
    if (t.isEmpty) "anon" else t
  }

  override def impl(pc: PhaseContext): Unit = {
    result.clear()
    val top = pc.topLevel
    result.top = top
    result.formal = pc.config.formalAsserts
    top.addTag(new ChecksTag(result))

    val comps = ArrayBuffer[Component]()
    def collect(c: Component): Unit = if (!c.isInstanceOf[BlackBox]) { comps += c; c.children.foreach(collect) }
    collect(top)
    // Identities first (round 13): ids and waivers use them, so one exact waiver is one check.
    val paths = SpinalChecks.instanceIds(top)

    // ---- discovery ----
    class Found {
      val streams = mutable.LinkedHashSet[Stream[_ <: Data]]()
      val flows   = mutable.LinkedHashSet[Flow[_ <: Data]]()
      val mems    = ArrayBuffer[Mem[_]]()
      val enums   = ArrayBuffer[SpinalEnumCraft[_]]()
      val signals = ArrayBuffer[BaseType]()
      /** Multiplexers (dynamic Vec reads) with a non-power-of-two input count, grouped by select. */
      val bits = ArrayBuffer[(BitVectorBitAccessFloating, Statement)]()
      val muxes   = mutable.LinkedHashMap[(Expression, Int), ArrayBuffer[(Multiplexer, Statement)]]()
    }
    val found = comps.map { c =>
      val f = new Found
      c.dslBody.walkDeclarations {
        case m: Mem[_] => f.mems += m
        case bt: BaseType =>
          f.signals += bt
          bt match {
            case e: SpinalEnumCraft[_] if e.isReg => f.enums += e
            case _ =>
          }
          var p: Data = bt.parent
          while (p != null) {
            p match {
              case s: Stream[_] => f.streams += s.asInstanceOf[Stream[_ <: Data]]
              case s: Flow[_]   => f.flows += s.asInstanceOf[Flow[_ <: Data]]
              case _ =>
            }
            p = p.parent
          }
        case _ =>
      }
      c.dslBody.walkStatements { st =>
        st.walkExpression {
          case b: BitVectorBitAccessFloating if !isPow2(b.source.getWidth) => f.bits += ((b, st))
          case m: Multiplexer if m.inputs != null && m.select != null && !isPow2(m.inputs.size) =>
            f.muxes.getOrElseUpdate((m.select, m.inputs.size), ArrayBuffer()) += ((m, st))
          case _ =>
        }
      }
      c -> f
    }.toMap

    def objName(d: Nameable, fallback: String): String = if (d.isNamed && d.getName().nonEmpty) d.getName() else fallback
    val streamNames = comps.map { c =>
      val taken = mutable.HashSet[String]()
      c -> found(c).streams.toSeq.map(s =>
        s -> unique(objName(s, objName(s.valid, "stream").stripSuffix("_valid")), taken)).toMap
    }.toMap

    // Deduplicate only a full, direct connection to an enabled, unwaived consumer check.
    // A shared valid does not imply shared backpressure or payload. Keep ambiguous channels.
    def directlyDrivenBy(target: BaseType, source: BaseType, scope: ScopeStatement): Boolean = {
      val stmts = ArrayBuffer[AssignmentStatement]()
      target.foreachStatements(st => stmts += st)
      !target.isReg && stmts.size == 1 && (stmts.head match {
        case d: DataAssignmentStatement =>
          (d.target eq target) && (d.source eq source) && (d.parentScope eq scope)
        case _ => false
      })
    }
    def enabledChecks(c: Component, s: Stream[_ <: Data]): Boolean = {
      val selected = s.valid.isInput || s.valid.isOutput || cfg.internalStreams
      val checked = Seq(Kind.StreamValidHold) ++ (if (s.payload.flatten.nonEmpty) Seq(Kind.StreamPayloadStable) else Nil) ++
        (if (s.parent.isInstanceOf[tilelink.Bus]) s.payload match {
          case bf: tilelink.BusFragment if bf.withData && bf.p.beatWidth > 0 => Seq(Kind.TileLinkBurstStable)
          case _ => Nil
        } else Nil)
      checked.forall(k => cfg.streamReason(qualify(paths(c), streamNames(c)(s)), k).isEmpty) &&
      selected && !(c == top && s.valid.isInput) && driven(s.valid) && driven(s.ready) &&
        s.payload.flatten.forall(driven) &&
        checked.forall(k => cfg.decide(s"$k:${qualify(paths(c), streamNames(c)(s))}").isEmpty)
    }
    def connected(producer: Stream[_ <: Data], consumer: Stream[_ <: Data], scope: ScopeStatement): Boolean = {
      val from = producer.payload.flatten
      val to = consumer.payload.flatten
      producer.parent.isInstanceOf[tilelink.Bus] == consumer.parent.isInstanceOf[tilelink.Bus] &&
        producer.payload.flattenLocalName == consumer.payload.flattenLocalName && from.size == to.size &&
        directlyDrivenBy(consumer.valid, producer.valid, scope) &&
        directlyDrivenBy(producer.ready, consumer.ready, scope) &&
        from.zip(to).forall { case (p, k) => directlyDrivenBy(k, p, scope) }
    }
    // Edges point towards the retained consumer. A parent wrapper can itself be covered by a
    // child slave, so resolve the whole chain before omitting a child master's checks.
    val coveredAt = mutable.LinkedHashMap[Stream[_ <: Data], Stream[_ <: Data]]()
    for (c <- comps if c != top; child <- found(c).streams if child.valid.isInput && child.ready.isOutput) {
      val scope = c.parent.dslBody
      val childPayload = child.payload.flatten
      if (enabledChecks(c, child)) {
        for (parent <- found(c.parent).streams if !parent.valid.isInput && !parent.valid.isOutput) {
          val parentPayload = parent.payload.flatten
          if ((c.clockDomain eq c.parent.clockDomain) &&
              !parent.ready.isInput && !parent.ready.isOutput &&
              parentPayload.forall(p => !p.isInput && !p.isOutput && driven(p)) &&
              childPayload.forall(_.isInput) &&
              connected(parent, child, scope)) {
            coveredAt(parent) = child
          }
        }
      }
    }
    for (c <- comps if c != top; master <- found(c).streams if master.valid.isOutput && master.ready.isInput) {
      val parent = c.parent
      val local = found(parent).streams.filter(s => !s.valid.isInput && !s.ready.isOutput)
        .map(s => (parent, s))
      val slaves = parent.children.filter(found.contains).flatMap(k => found(k).streams
        .filter(s => s.valid.isInput && s.ready.isOutput).map(s => (k, s)))
      if (master.payload.flatten.forall(_.isOutput)) {
        (local.toSeq ++ slaves).find { case (owner, consumer) =>
          (c.clockDomain eq owner.clockDomain) && enabledChecks(owner, consumer) &&
            connected(master, consumer, parent.dslBody)
        }.foreach { case (_, consumer) => coveredAt(master) = consumer }
      }
    }
    def covered(s: Stream[_ <: Data], seen: Set[Stream[_ <: Data]] = Set.empty): Boolean =
      !seen.contains(s) && coveredAt.get(s).exists(next =>
        if (coveredAt.contains(next)) covered(next, seen + s) else true)
    val coveredStreams = coveredAt.keys.filter(s => covered(s)).toSet

    /** Per-component state for inserting checks; its methods must be called inside `c.rework`. */
    class Ctx(c: Component) {
      private val used = mutable.HashMap[String, Int]()
      def uniqueName(base: String): String = {
        val n = used.getOrElse(base, 0); used(base) = n + 1
        if (n == 0) base else s"${base}_$n"
      }
      // Cycle counter for Monitor mode, created on first use in this component.
      private val cycleCounters = mutable.HashMap[ClockDomain, UInt]()
      def cycles: UInt = {
        cycleCounters.getOrElseUpdate(ClockDomain.current, {
          val counter = Reg(UInt(40 bits)).init(0).setName(uniqueName("chk_cycle"))
          counter := counter + 1
          counter
        })
      }

      /** For a register without a reset value: True once it has been written after reset, so the check
        * covers every written value, the first one included, and never the power-up value of a register
        * that was not written (X in hardware; `rvw formal xprop` covers that).
        *
        * A write is any assignment statement of the register executing: a `<name>_write` wire is False
        * by default (placed at the head of the body) and set True in every scope that assigns the
        * register, so it is high exactly in the cycles the register loads a value. A register
        * assigned from another component's scope falls back to "has changed value", combinationally,
        * so the first changed value is checked. */
      def writtenSinceReset(bt: BaseType): Bool = {
        val n = sanitize(bt.getName())
        val scopes = mutable.LinkedHashSet[ScopeStatement]()
        bt.foreachStatements {
          case a: AssignmentStatement if !a.isInstanceOf[InitAssignmentStatement] => scopes += a.parentScope
          case _ =>
        }
        val cd = Option(bt.clockDomain).getOrElse(ClockDomain.current)
        if (scopes.isEmpty) False
        else if (scopes.forall(_.component == c)) {
          // Only the outermost assigning scopes: a nested scope runs only when its parent does.
          def ancestors(s: ScopeStatement): Iterator[ScopeStatement] =
            Iterator.iterate(Option(s.parentStatement).map(_.parentScope).orNull)(x =>
              if (x == null || x.parentStatement == null) null else x.parentStatement.parentScope).takeWhile(_ != null)
          val outer = scopes.filter(s => !ancestors(s).exists(scopes.contains))
          val write: Bool =
            if (outer.contains(c.dslBody)) True // assigned unconditionally: written every cycle
            else {
              val w = c.dslBody.onHead {
                val w = Bool().setName(uniqueName(s"chk_${n}_write"))
                w := False
                w
              }
              outer.foreach(_.on { w := True })
              w
            }
          cd.on {
            val written = RegInit(False).setName(uniqueName(s"chk_${n}_written"))
            written.setWhen(write)
            written
          }
        } else cd.on {
          val bits = bt.asBits
          val prev = RegNext(bits).setName(uniqueName(s"chk_${n}_prev"))
          val prevValid = RegNext(True).init(False).setName(uniqueName(s"chk_${n}_prev_valid"))
          val written = RegInit(False).setName(uniqueName(s"chk_${n}_written"))
          val changed = prevValid && bits =/= prev
          written.setWhen(changed)
          written || changed
        }
      }
      def armed(bt: Expression): Bool = bt match {
        case b: BaseType if b.isReg && !hasResetValue(b) => writtenSinceReset(b)
        case _ => True
      }

      def active(cd: ClockDomain): Bool =
        if (cd != null && (cd.hasResetSignal || cd.hasSoftResetSignal)) !cd.isResetActive else True

      /** Turns a failure condition into hardware according to the mode. */
      def emit(rec: CheckRecord, cond: Bool, message: String = "failed"): Unit = {
        val base = uniqueName(s"chk_${Kind.tag(rec.kind)}_${sanitize(rec.objName)}")
        val fail = Bool().setName(base)
        fail := cond
        rec.fail = fail
        rec.clockDomain = ClockDomain.current
        val loc = rec.location.map(l => new spinal.idslplugin.Location(l.file.stripSuffix(".scala"), l.line, 1)).getOrElse(implicitly[spinal.idslplugin.Location])
        if (cfg.mode != Mode.Monitor) {
          def property(): Unit = {
            if (rec.env && result.formal && cfg.envAsAssume) assume(!fail)(loc)
            else assert(!fail, s"[spinalchecks] ${rec.id} $message" + rec.location.map(l => s" ($l)").getOrElse(""), cfg.severity)(loc)
          }
          val cd = ClockDomain.current
          // Checks sample pre-edge values. Async reset changes state, not the check's sampling event.
          if (result.formal && cd.config.resetKind == ASYNC)
            cd.copy(config = cd.config.copy(resetKind = SYNC)).on { property() }
          else property()
        }
        if (cfg.mode != Mode.Assert) {
          val fired = RegInit(False).setName(base + "_fired")
          fired.setWhen(fail)
          val count = Reg(UInt(16 bits)).init(0).setName(base + "_count")
          when(fail && count =/= count.maxValue) { count := count + 1 }
          val first = Reg(UInt(40 bits)).init(0).setName(base + "_first")
          when(fail && !fired) { first := cycles }
          if (!result.formal) when(fail && count < cfg.monitorReports) {
            report(Seq(s"[spinalchecks] FIRE ${rec.id} at ", REPORT_TIME))(loc)
          }
          Seq(fired, count, first).foreach(s => s.simPublic().addTag(Verilator.public))
          rec.fired = fired; rec.count = count; rec.firstCycle = first
        }
      }
    }
    val ctxs = mutable.HashMap[Component, Ctx]()
    def ctxOf(c: Component) = ctxs.getOrElseUpdate(c, new Ctx(c))

    // ---- insertion ----
    for (c <- comps) {
      val f = found(c)
      val path = paths(c)
      val isTop = c == top
      val foreignRegisters = f.signals.exists(bt => bt.isReg && (bt.clockDomain ne c.clockDomain.get))
      require(!foreignRegisters || f.streams.isEmpty,
        s"SpinalChecks: component ${paths(c)} has streams and registers in another clock domain; " +
        "put each stream in a component with its own clock domain")
      val ambiguousIndex = f.muxes.keys.exists { case (sel, _) => sel match {
        case b: BaseType if b.isReg => false
        case _ => true
      }}
      require(!foreignRegisters || !ambiguousIndex,
        s"SpinalChecks: component ${paths(c)} has a combinational Vec selector and multiple clock domains; " +
        "put the index check in a component with its own clock domain")
      val ctx = ctxOf(c)
      import ctx._
      // Object identities, distinct within the component before any id is formed: two unnamed
      // objects (`stream`, `mem`, `index_of24`) or two equal names get `_1`, `_2`, ... in discovery order.
      val streamName = streamNames(c)
      val memName = { val t = mutable.HashSet[String](); f.mems.map(m => m -> unique(objName(m, "mem"), t)).toMap }
      val enumName = { val t = mutable.HashSet[String](); f.enums.map(e => e -> unique(objName(e, "state"), t)).toMap }
      val muxName = { val t = mutable.HashSet[String](); f.muxes.keys.toSeq.map { case k @ (sel, n) =>
        val selName = sel match { case b: BaseType if b.isNamed && b.getName().nonEmpty => b.getName(); case _ => "index" }
        k -> unique(s"${selName}_of$n", t) }.toMap }

      def newRecord(kind: String, obj: String, env: Boolean, loc: Option[SourceLoc], detail: String): CheckRecord = {
        val id = s"$kind:${qualify(path, obj)}"
        val rec = new CheckRecord(id, kind, c, path, obj, env, loc, detail)
        cfg.decide(id).foreach { case (st, why) => rec.status = st; rec.reason = why }
        result.records += rec
        rec
      }

      val todo = ArrayBuffer[() => Unit]()
      // Scope guards cover direct conditional uses. Unknown scopes stay conservative.
      def useGuard(st: Statement): Bool = {
        def walk(scope: ScopeStatement): Bool = {
          if (scope == null || scope.parentStatement == null) True
          else scope.parentStatement match {
            case w: WhenStatement =>
              val cond = w.cond match {
                case b: Bool => b
                case e => val b = Bool(); b.assignFrom(e); w.cond = b; b
              }
              walk(w.parentScope) && (if (scope eq w.whenTrue) cond else !cond)
            case other => walk(other.parentScope)
          }
        }
        walk(st.parentScope)
      }
      for (d <- c.getTags().collect { case d: DeclaredRule => d }) {
        val rec = newRecord(d.kind, d.name, false, None, d.detail)
        if (rec.inserted) todo += { () => d.cd.on { emit(rec, active(d.cd) && d.fail) } }
      }
      for (((bit, st), i) <- f.bits.zipWithIndex) {
        val rec = newRecord("bits.index", s"select_$i", false, SourceLoc.of(st), "use-gated dynamic bit select")
        if (rec.inserted) todo += { () =>
          val cd = bit.source match {
            case b: BaseType if b.isReg => b.clockDomain
            case _ => st match { case a: AssignmentStatement if a.finalTarget.isReg => a.finalTarget.clockDomain; case _ => ClockDomain.current }
          }
          cd.on {
            val idx = UInt(); idx.assignFrom(bit.bitId); bit.bitId = idx
            emit(rec, active(cd) && useGuard(st) && idx >= U(bit.source.getWidth))
          }
        }
      }


      // Check every port and selected internal stream. Omit producer checks only when a complete
      // direct connection leads to enabled, unwaived consumer checks. Top inputs are assumptions.
      for (s <- f.streams) {
        val v = s.valid
        val r = s.ready
        val name = streamName(s)
        val payload = s.payload.flatten.filter(driven).toSeq
        result.channels += new Channel("stream", c, path, name, v, r, payload, SourceLoc.of(v))
        val (check, env) =
          if (v.isInput) (true, isTop)
          else if (v.isOutput) (true, false)
          else (cfg.internalStreams, false)
        if (check && coveredStreams.contains(s))
          result.notes += s"stream ${qualify(path, name)} is checked at its connected consumer"
        else if (check) {
          if (!driven(v) || !driven(r)) result.notes += s"skipped stream ${qualify(path, name)}: valid or ready has no driver"
          else {
            val loc = SourceLoc.of(v)
            val hold = newRecord(Kind.StreamValidHold, name, env, loc, "")
            hold.signals("valid") = Seq(v); hold.signals("ready") = Seq(r)
            val stable = if (payload.nonEmpty) newRecord(Kind.StreamPayloadStable, name, env, loc,
              s"${payload.size} payload signals") else null
            if (stable != null) { stable.signals("valid") = Seq(v); stable.signals("ready") = Seq(r); stable.signals("payload") = payload }
            Seq(hold, stable).filter(_ != null).filter(_.inserted).foreach { rec =>
              val semantics = cfg.streamReason(qualify(path, name), rec.kind).orElse(
                if (s.parent.isInstanceOf[tilelink.Bus]) Some("TileLink permits pre-acceptance offer changes; burst checks remain active") else None)
              semantics.foreach { reason =>
                rec.status = "waived"; rec.reason = "declared channel semantics: " + reason
              }
            }
            if (hold.inserted || (stable != null && stable.inserted)) todo += { () =>
              val stall = (v && !r)
              val stallPrev = RegNext(stall).init(False).setName(uniqueName(s"chk_${sanitize(name)}_stall_prev"))
              val act = active(ClockDomain.current)
              if (hold.inserted) emit(hold, act && stallPrev && !v)
              if (stable != null && stable.inserted) {
                val now = Cat(payload.map(_.asBits))
                val prev = RegNext(now).setName(uniqueName(s"chk_${sanitize(name)}_payload_prev"))
                emit(stable, act && stallPrev && v && now =/= prev)
              }
            }
          }
        }
      }
      // TileLink channels (Spinal `tilelink.BusFragment` payloads) with multi-beat messages: inside a
      // burst, after its first beat was accepted, every beat must carry the first beat's header (opcode,
      // param, size, source, address, ...) and a stalled beat must keep its payload. Before the first beat
      // is accepted the message may change (rocket-chip's TLArbiter re-arbitrates until ready; its
      // TLMonitor checks the same rule). Added next to the generic stream rules, which may be waived.
      // Only channels of a `tilelink.Bus`: the beat protocol belongs to the bus, and a Stream that merely
      // carries a TileLink message type (e.g. a one-transfer notification) has no bursts.
      for (s <- f.streams if s.parent.isInstanceOf[tilelink.Bus]) s.payload match {
        case bf: tilelink.BusFragment if bf.withData && bf.p.beatWidth > 0 =>
          val v = s.valid
          val r = s.ready
          val name = streamName(s)
          val check = v.isInput || v.isOutput || cfg.internalStreams
          val covered = coveredStreams.contains(s)
          if (check && !covered && driven(v) && driven(r)) {
            val perBeat = Seq[Data](bf.data, bf.corrupt, bf.maskNull).filter(_ != null).flatMap(_.flatten).toSet
            val all = bf.flatten.filter(driven).toSeq
            val header = all.filterNot(perBeat.contains)
            val env = v.isInput && isTop
            val rec = newRecord(Kind.TileLinkBurstStable, name, env, SourceLoc.of(v),
              s"${bf.getClass.getSimpleName}, up to ${bf.p.beatMax} beats, ${header.size} header signals")
            rec.signals("valid") = Seq(v); rec.signals("ready") = Seq(r)
            rec.signals("header") = header; rec.signals("payload") = all
            if (rec.inserted && header.nonEmpty) todo += { () =>
              val n = sanitize(name)
              val p = bf.p
              val beat = Reg(UInt(p.beatWidth bits)).init(0).setName(uniqueName(s"chk_${n}_beat"))
              val beatsMinusOne = (0 to p.sizeMax).map(sz => U(((1 << sz) + p.dataBytes - 1) / p.dataBytes - 1, p.beatWidth bits))
                .read(bf.size.resize(log2Up(p.sizeMax + 1) bits))
              val last = !bf.withBeats || beat === beatsMinusOne
              val fire = v && r
              when(fire) { beat := (beat + 1).resized; when(last) { beat := 0 } }
              val hdr = Cat(header.map(_.asBits))
              val first = RegNextWhen(hdr, fire && beat === 0).setName(uniqueName(s"chk_${n}_burst_header"))
              val now = Cat(all.map(_.asBits))
              val prev = RegNext(now).setName(uniqueName(s"chk_${n}_burst_prev"))
              val stallPrev = RegNext(v && !r).init(False).setName(uniqueName(s"chk_${n}_burst_stall_prev"))
              val inBurst = beat =/= 0
              emit(rec, active(ClockDomain.current) && v && inBurst && (hdr =/= first || (stallPrev && now =/= prev)))
            }
          }
        case _ =>
      }
      val buses = f.streams.toSeq.map(_.parent).distinct
      val busNames = {
        val taken = mutable.HashSet[String]()
        buses.filter(_ != null).map(b => b -> unique(objName(b, "bus"), taken)).toMap
      }
      for (bus <- buses) bus match {
        case b: tilelink.Bus if b.a.valid.component == c =>
          todo += { () => ProtocolChecks.tileLink(b, (kind, suffix, env, detail, fail) => {
            val rec = newRecord(kind, busNames(b) + suffix, env && isTop, SourceLoc.of(b.a.valid), detail)
            if (rec.inserted) emit(rec, active(ClockDomain.current) && fail)
          }) }
        case b: spinal.lib.bus.amba4.axi.Axi4 if b.ar.valid.component == c && b.config.readIssuingCapability > 0 =>
          todo += { () => AxiReadChecks(b.ar, b.r, (kind, suffix, env, detail, fail) => {
            val rec = newRecord(kind, busNames(b) + suffix, env && isTop, SourceLoc.of(b.r.valid), detail)
            if (rec.inserted) emit(rec, active(ClockDomain.current) && fail)
          }) }
        case b: spinal.lib.bus.amba4.axi.Axi4ReadOnly if b.ar.valid.component == c && b.config.readIssuingCapability > 0 =>
          todo += { () => AxiReadChecks(b.ar, b.r, (kind, suffix, env, detail, fail) => {
            val rec = newRecord(kind, busNames(b) + suffix, env && isTop, SourceLoc.of(b.r.valid), detail)
            if (rec.inserted) emit(rec, active(ClockDomain.current) && fail)
          }) }
        case b: spinal.lib.bus.amba4.axi.Axi4 =>
          result.notes += s"AXI4 ${objName(b, "bus")}: read bookkeeping needs a positive readIssuingCapability"
        case b: spinal.lib.bus.amba4.axi.Axi4ReadOnly =>
          result.notes += s"AXI4 ${objName(b, "bus")}: read bookkeeping needs a positive readIssuingCapability"
        case _ =>
      }
      for (bus <- buses) {
        def writeChecks(aw: Stream[spinal.lib.bus.amba4.axi.Axi4Aw],
                        w: Stream[spinal.lib.bus.amba4.axi.Axi4W],
                        b: Stream[spinal.lib.bus.amba4.axi.Axi4B]): Unit = {
          if (aw.payload.config.writeIssuingCapability > 0) todo += { () =>
            AxiWriteChecks(aw, w, b, (kind, suffix, env, detail, fail) => {
              val rec = newRecord(kind, busNames(bus) + suffix, env && isTop, SourceLoc.of(b.valid), detail)
              if (rec.inserted) emit(rec, active(ClockDomain.current) && fail)
            })
          } else result.notes += s"AXI4 ${objName(bus, "bus")}: write bookkeeping needs a positive writeIssuingCapability"
        }
        bus match {
          case b: spinal.lib.bus.amba4.axi.Axi4 if b.aw.valid.component == c => writeChecks(b.aw, b.w, b.b)
          case b: spinal.lib.bus.amba4.axi.Axi4WriteOnly if b.aw.valid.component == c => writeChecks(b.aw, b.w, b.b)
          case _ =>
        }
      }
      for (s <- f.streams) s.payload match {
        case ax: spinal.lib.bus.amba4.axi.Axi4Ax if driven(s.valid) && driven(s.ready) =>
          todo += { () => ProtocolChecks.axiAddress(ax, fail => {
            val rec = newRecord("axi4.address_legal", streamName(s), s.valid.isInput && isTop,
              SourceLoc.of(s.valid), "AXI4 address options, burst length, alignment and 4 KiB boundary")
            if (rec.inserted) emit(rec, active(ClockDomain.current) && s.valid && fail)
          }) }
        case _ =>
      }
      for (fl <- f.flows) {
        val name = objName(fl, objName(fl.valid, "flow").stripSuffix("_valid"))
        result.channels += new Channel("flow", c, path, name, fl.valid, null, fl.payload.flatten.filter(driven).toSeq, SourceLoc.of(fl.valid))
      }

      // Memories whose size is not a power of two: every enabled port's address must be < wordCount.
      for (m <- f.mems if !isPow2(m.wordCount)) {
        val mname = memName(m)
        var portIdx = 0
        m.foreachStatements { port =>
          val i = portIdx; portIdx += 1
          type Setter = Expression => Unit
          val (kindName, addr, en, setAddr, setEn, cd): (String, Expression, Expression, Setter, Setter, ClockDomain) = port match {
            case p: MemWrite => ("write", p.address, p.writeEnable,
              (e: Expression) => p.address = e.asInstanceOf[Expression with WidthProvider], (e: Expression) => p.writeEnable = e, p.clockDomain)
            case p: MemReadSync => ("read", p.address, p.readEnable,
              (e: Expression) => p.address = e.asInstanceOf[Expression with WidthProvider], (e: Expression) => p.readEnable = e, p.clockDomain)
            case p: MemReadWrite => ("readwrite", p.address, p.chipSelect,
              (e: Expression) => p.address = e.asInstanceOf[Expression with WidthProvider], (e: Expression) => p.chipSelect = e, p.clockDomain)
            case p: MemReadAsyncWrite => ("readasyncwrite", p.address, p.writeEnable,
              (e: Expression) => p.address = e.asInstanceOf[Expression with WidthProvider], (e: Expression) => p.writeEnable = e, p.clockDomain)
            case p: MemReadAsync => ("readasync", p.address, null,
              (e: Expression) => p.address = e.asInstanceOf[Expression with WidthProvider], (_: Expression) => (), null)
            case other => (other.getClass.getSimpleName, null, null, null, null, null)
          }
          if (addr != null) {
            val obj = s"${mname}_port${i}_$kindName"
            val rec = newRecord(Kind.MemIndex, obj, false, SourceLoc.of(m), s"wordCount=${m.wordCount} port=$kindName${unresetNote(addr)}")
            if (rec.inserted) todo += { () =>
              // Reference the port's address/enable through named wires, so each expression keeps one user.
              val a: UInt = addr match {
                case u: UInt => u
                case e => val w = UInt().setName(uniqueName(s"chk_${sanitize(obj)}_addr")); w.assignFrom(e); setAddr(w); w
              }
              val e: Bool = en match {
                case null => True
                case b: Bool => b
                case x => val w = Bool().setName(uniqueName(s"chk_${sanitize(obj)}_en")); w.assignFrom(x); setEn(w); w
              }
              rec.signals("address") = Seq(a)
              def body(): Unit = emit(rec, active(ClockDomain.current) && armed(addr) && e && a >= U(m.wordCount))
              if (cd != null) cd.on(body()) else body()
            }
          }
        }
      }

      // Dynamic Vec reads (Spinal multiplexers) over a non-power-of-two number of elements: the index
      // must be below the element count. One check per index signal and size.
      for (((sel, n), uses) <- f.muxes) {
        val selName = sel match { case b: BaseType if b.isNamed && b.getName().nonEmpty => b.getName(); case _ => "index" }
        val obj = muxName((sel, n))
        val (_, st) = uses.head
        val loc = st match {
          case a: AssignmentStatement => SourceLoc.of(a.finalTarget).orElse(SourceLoc.of(a))
          case other => SourceLoc.of(other)
        }
        val rec = newRecord(Kind.VecIndex, obj, false, loc, s"$n elements, ${uses.size} multiplexers${unresetNote(sel)}")
        if (rec.inserted) todo += { () =>
          val idx: UInt = sel match {
            case u: UInt => u
            case e =>
              val w = UInt().setName(uniqueName(s"chk_${sanitize(selName)}_of${n}_index"))
              w.assignFrom(e)
              uses.foreach(_._1.select = w)
              w
          }
          rec.signals("index") = Seq(idx)
          val cd = sel match { case b: BaseType if b.isReg => b.clockDomain; case _ => ClockDomain.current }
          cd.on { emit(rec, active(cd) && armed(sel) && uses.map(x => useGuard(x._2)).reduce(_ || _) && idx >= U(n)) }
        }
      }

      // Enum registers (StateMachine state registers included) must hold a declared value.
      for (e <- f.enums) {
        val enc0 = e.getEncoding
        val enc = if (enc0 == null || enc0.isNative) binarySequential else enc0
        val elements = e.spinalEnum.elements
        val width = enc.getWidth(e.spinalEnum)
        val full = elements.size == (1 << width) && enc != binaryOneHot
        if (!full && elements.nonEmpty) {
          val isFsm = e.refOwner != null && e.refOwner.isInstanceOf[StateMachine]
          val kind = if (isFsm) Kind.FsmStateLegal else Kind.EnumLegal
          val name = enumName(e)
          val loc = if (isFsm) SourceLoc.of(e.refOwner.asInstanceOf[StateMachine]).orElse(SourceLoc.of(e)) else SourceLoc.of(e)
          val rec = newRecord(kind, name, false, loc,
            s"${e.spinalEnum.getClass.getSimpleName.stripSuffix("$")} ${elements.size} states, ${enc.getClass.getSimpleName.stripSuffix("$")} encoding, $width bits${unresetNote(e)}")
          rec.signals("state") = Seq(e)
          if (rec.inserted) todo += { () =>
            e.clockDomain.on {
              val bits = e.asBits
              val legal = elements.map(el => bits === B(enc.getValue(el), width bits)).reduce(_ || _)
              emit(rec, active(e.clockDomain) && armed(e) && !legal)
            }
          }
        }
      }

      if (todo.nonEmpty) c.rework { c.onBody { todo.foreach(_()) } }
    }

    // Progress watchdogs.
    for (p <- cfg.progress) {
      val re = p.signal.r
      val matches = for (c <- comps; bt <- found(c).signals if bt.isNamed && re.matches(qualify(paths(c), bt.getName()))) yield (c, bt)
      require(matches.nonEmpty, s"SpinalChecks progress '${p.name}': no signal matches '${p.signal}'")
      val owners = matches.map(_._1).distinct
      require(owners.size == 1, s"SpinalChecks progress '${p.name}': matches span components ${owners.map(paths).mkString(", ")}")
      val c = owners.head
      val sigs = matches.map(_._2)
      require(!found(c).signals.exists(bt => bt.isReg && (bt.clockDomain ne c.clockDomain.get)),
        s"SpinalChecks progress '${p.name}': component has multiple clock domains; " +
        "put the progress signal in a component with its own clock domain")
      val allBool = sigs.forall(_.isInstanceOf[Bool])
      require(allBool || sigs.size == 1, s"SpinalChecks progress '${p.name}': several matches must all be Bools")
      val id = s"${Kind.Progress}:${qualify(paths(c), p.name)}"
      val rec = new CheckRecord(id, Kind.Progress, c, paths(c), p.name, false, SourceLoc.of(sigs.head),
        s"${sigs.map(_.getName()).mkString(" | ")} within ${p.maxCycles} cycles")
      cfg.decide(id).foreach { case (st, why) => rec.status = st; rec.reason = why }
      rec.signals("progress") = sigs.toSeq
      result.records += rec
      if (rec.inserted) c.rework {
        c.onBody {
          val event: Bool =
            if (allBool) sigs.map(_.asInstanceOf[Bool]).reduce(_ || _)
            else { val b = sigs.head.asBits; b =/= RegNext(b) }
          val idle = Reg(UInt(log2Up(p.maxCycles + 1) bits)).init(0).setName(s"chk_progress_${sanitize(p.name)}_idle")
          when(event) { idle := 0 }.elsewhen(idle =/= p.maxCycles) { idle := idle + 1 }
          val ctx = ctxOf(c)
          ctx.emit(rec, ctx.active(ClockDomain.current) && !event && idle === p.maxCycles,
            s"failed: no progress for ${p.maxCycles} cycles")
        }
      }
    }

    // Every id names one check: a waiver or an enable that names an id exactly must not reach two.
    val repeated = result.records.groupBy(_.id).collect { case (id, rs) if rs.size > 1 => s"$id (${rs.size}x)" }
    if (repeated.nonEmpty)
      throw new IllegalStateException(s"SpinalChecks: duplicate check ids: ${repeated.toSeq.sorted.mkString(", ")}")
  }
}

/** After name allocation: records the final Verilog names and writes the JSON report. */
class PhaseChecksReport(cfg: ChecksConfig, result: ChecksResult) extends PhaseMisc {
  override def impl(pc: PhaseContext): Unit = {
    for (r <- result.records) {
      r.module = r.component.definitionName
      if (r.fail != null) r.failName = r.fail.getName()
    }
    val file = Option(cfg.reportPath).getOrElse(s"${pc.config.targetDirectory}/${pc.topLevel.definitionName}.checks.json")
    Files.createDirectories(Paths.get(file).toAbsolutePath.getParent)
    Files.write(Paths.get(file), Report.json(result).getBytes("UTF-8"))
    result.reportFile = Paths.get(file).toAbsolutePath.toString
    val n = result.records.groupBy(_.status).map { case (k, v) => s"${v.size} $k" }.mkString(", ")
    SpinalInfo(s"SpinalChecks: ${result.records.size} checks ($n) -> $file")
  }
}
