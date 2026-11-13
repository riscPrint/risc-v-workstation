package spinalprobes

import spinal.core._
import spinal.core.sim._
import scala.collection.mutable.ArrayBuffer

/** One probe instance: a sampled `valid` and named value fields.
  * `kind` selects the event type (see `Probe`), `meta` holds static strings (stage name,
  * stall cause, cache event, ...). Signals exist only when probes are enabled. */
final case class ProbeSite(index: Int, kind: String, name: String, valid: Bool,
    fields: Seq[(String, BaseType)], meta: Map[String, String]) {
  def field(n: String): Option[BaseType] = fields.collectFirst { case (`n`, d) => d }
}

/** The probes registered under one toplevel component. */
final class ProbeSet {
  private val buffer = ArrayBuffer.empty[ProbeSite]
  def sites: Seq[ProbeSite] = synchronized(buffer.toList)
  private[spinalprobes] def add(make: Int => ProbeSite): ProbeSite = synchronized {
    val s = make(buffer.size); buffer += s; s
  }
}

/** Simulation-only instrumentation. Off by default: every call returns at once and adds no
  * hardware. Enable it around the elaboration of a simulation model only:
  * {{{
  *   val report = Probe.enabled(job.probes) { SpinalConfig().generateVerilog(new Top) }
  *   val sites = Probe.of(report.toplevel)
  * }}}
  * Each call copies its signals into new named wires `rvwprobe__KIND__NAME__FIELD` in the
  * calling component's top scope (not inside the caller's `when`) and marks them public for
  * the simulator. Probe signals must be readable from the calling component.
  * `valid` is a one-cycle event (or a level sampled each cycle for stall, stage and counter).
  */
object Probe {
  @volatile private var on = false
  private val registry = new java.util.WeakHashMap[Component, ProbeSet]()
  val Prefix = "rvwprobe"

  def isEnabled: Boolean = on
  /** Run `body` (an elaboration) with probes enabled or disabled, then restore the old state. */
  def enabled[T](enable: Boolean)(body: => T): T = {
    val old = on
    on = enable
    try body finally on = old
  }
  /** The probes of an elaborated toplevel component (empty when probes were disabled). */
  def of(top: Component): Seq[ProbeSite] = registry.synchronized(Option(registry.get(top))).map(_.sites).getOrElse(Nil)

  private def toplevel(c: Component): Component = if (c.parent == null) c else toplevel(c.parent)
  private val token = "[^A-Za-z0-9]+".r
  def clean(s: String): String = {
    val t = token.replaceAllIn(s, "_").stripPrefix("_").stripSuffix("_")
    require(t.nonEmpty, s"probe name '$s' has no letters or digits")
    t
  }

  /** Register a probe. Returns None when probes are disabled. Used by every typed call below,
    * and by core code for event kinds this object does not name. */
  def site(kind: String, name: String, valid: Bool, fields: Seq[(String, Data)],
      meta: Map[String, String] = Map.empty): Option[ProbeSite] = {
    if (!on) return None
    require(kind.matches("[a-z][a-z0-9]*"), s"probe kind '$kind' must be lower-case letters and digits")
    require(meta.forall { case (k, v) => !k.contains('\t') && !v.contains('\t') && !v.contains('\n') })
    val names = fields.map(_._1)
    require(names.distinct.size == names.size, s"probe $kind/$name has duplicate field names")
    val c = Component.current
    require(c != null, "Probe calls must run during elaboration, inside a component")
    val set = registry.synchronized(registry.computeIfAbsent(toplevel(c), _ => new ProbeSet))
    val base = s"${Prefix}__${kind}__${clean(name)}"
    Some(set.add { index =>
      // ScopeStatement.on returns Unit in older SpinalHDL versions (for example NaxRiscv's pin).
      var site: ProbeSite = null
      c.dslBody.on {
        val v = Bool().setName(s"${base}__valid")
        v := valid
        v.simPublic()
        val copies = fields.map { case (n, d) =>
          val w: BaseType = d match {
            case b: Bool => val x = Bool(); x := b; x
            case other => val x = Bits(other.getBitsWidth bits); x := other.asBits; x
          }
          w.setName(s"${base}__${clean(n)}")
          w.simPublic()
          clean(n) -> w
        }
        site = ProbeSite(index, kind, name, v, copies, meta)
      }
      site
    })
  }

  private def opt(name: String, d: Option[Data]): Seq[(String, Data)] = d.map(name -> _).toSeq

  /** A resolved branch or jump. Probe at the commit point so that every event belongs to a
    * retired instruction. `semantics` is `first-prediction` or `final-prediction`.
    * `covers` lists the branch kinds the probe fires for (cond, jump, ijump, call, icall, ret).
    * `id` is the instruction ID of the stage/retire probes; with it, the Kanata converter writes
    * prediction records. */
  def branch(name: String, valid: Bool, pc: Data, taken: Bool, target: Data,
      predictedTaken: Option[Bool] = None, predictedTarget: Option[Data] = None,
      semantics: String = "final-prediction", covers: Seq[String] = Seq("cond", "jump", "ijump", "call", "icall", "ret"),
      id: Option[Data] = None): Unit =
    site("branch", name, valid, Seq("pc" -> pc, "taken" -> taken, "target" -> target) ++
      opt("predicted_taken", predictedTaken) ++ opt("predicted_target", predictedTarget) ++ opt("id", id),
      Map("semantics" -> semantics, "covers" -> covers.mkString(",")))

  /** A cache event. `event` is a project word such as access, fill, evict or invalidate.
    * `hit` gives the lookup result of an access. `data`/`mask` give bytes for the cache observer. */
  def cacheAccess(cache: String, event: String, valid: Bool, address: Data, hit: Option[Bool] = None,
      write: Option[Bool] = None, data: Option[Data] = None, mask: Option[Data] = None, way: Option[Data] = None, semantics: String = "lookup"): Unit =
    site("cache", s"${cache}_$event", valid, Seq("address" -> address) ++ opt("hit", hit) ++ opt("write", write) ++
      opt("data", data) ++ opt("mask", mask) ++ opt("way", way), Map("cache" -> cache, "event" -> event, "semantics" -> semantics))

  /** A TLB event: `fill`, `hit`, `miss` or `invalidate` (va/asid absent means all). */
  def tlb(tlb: String, event: String, valid: Bool, va: Option[Data] = None, pa: Option[Data] = None,
      asid: Option[Data] = None, entry: Option[Data] = None, size: Option[Data] = None,
      global: Option[Bool] = None, pteAddress: Option[Data] = None, pte: Option[Data] = None): Unit = {
    require(Set("fill", "hit", "miss", "invalidate")(event), "tlb event must be fill, hit, miss or invalidate")
    site("tlb", s"${tlb}_$event", valid, opt("va", va) ++ opt("pa", pa) ++ opt("asid", asid) ++
      opt("entry", entry) ++ opt("size", size) ++ opt("global", global) ++ opt("pte_address", pteAddress) ++ opt("pte", pte),
      Map("tlb" -> tlb, "event" -> event))
  }

  /** One page-table walker memory step: `request` (address) or `response` (address, data). */
  def pageWalk(walker: String, event: String, valid: Bool, address: Data, data: Option[Data] = None,
      level: Option[Data] = None, fault: Option[Bool] = None): Unit = {
    require(event == "request" || event == "response", "pageWalk event must be request or response")
    site("walk", s"${walker}_$event", valid, Seq("address" -> address) ++ opt("data", data) ++
      opt("level", level) ++ opt("fault", fault), Map("walker" -> walker, "event" -> event))
  }

  /** The end of one page-table walk of `walker`: translated `va`, `access` (0 load, 1 store,
    * 2 fetch), `root` table address, `status` (0 success, 1 page fault, 2 access fault) and `pa`
    * (read on success). The walker's `response` events since its previous result are the walk's
    * PTE reads. `mode` is the translation mode word (sv32, sv39, sv48, sv57). Probe only
    * walks whose access is architectural: a squashed speculative walk would be an extra record. */
  def walkResult(walker: String, mode: String, valid: Bool, va: Data, access: Data, root: Data,
      status: Data, pa: Data): Unit = {
    require(Set("sv32", "sv39", "sv48", "sv57")(mode), "walk mode must be sv32, sv39, sv48 or sv57")
    site("walk", s"${walker}_result", valid, Seq("va" -> va, "access" -> access, "root" -> root,
      "status" -> status, "pa" -> pa), Map("walker" -> walker, "event" -> "result", "mode" -> mode))
  }

  /** The instruction `id` is in stage `stage` this cycle (occupancy). IDs must be unique among
    * live instructions. Use stageAt with first for reused ROB indices. */
  def stage(stage: String, valid: Bool, id: Data, pc: Option[Data] = None, lane: String = "0"): Unit =
    site("stage", stage, valid, Seq("id" -> id) ++ opt("pc", pc), Map("stage" -> stage, "lane" -> lane))
  /** Stage occupancy for a core that reuses IDs (for example ROB indices). `first` marks the stage
    * where an instruction enters the pipeline: only a `first` stage starts an instruction, so a late
    * event for a reused ID cannot start a false one. `name` keeps several lanes of one stage apart. */
  def stageAt(name: String, stage: String, valid: Bool, id: Data, pc: Option[Data] = None,
      lane: String = "0", first: Boolean = false): Unit =
    site("stage", name, valid, Seq("id" -> id) ++ opt("pc", pc),
      Map("stage" -> stage, "lane" -> lane) ++ (if (first) Map("first" -> "true") else Map.empty))
  /** An LSU attempt rejected by an explicit control predicate. The collector supplies the cycle.
    * IDs use the stage/retire namespace. Squashed attempts need not retire. */
  def lsuRetry(name: String, valid: Bool, id: Data, cause: String): Unit = {
    require(Set("memory_order_violation", "store_forward_miss", "cache_miss_retry", "tlb_miss")(cause),
      "unknown LSU retry cause")
    site("lsuretry", name, valid, Seq("id" -> id), Map("cause" -> cause))
  }

  /** The instruction `id` commits this cycle. */
  def retire(name: String, valid: Bool, id: Data): Unit = site("retire", name, valid, Seq("id" -> id))
  /** The instruction `id` is squashed this cycle. */
  def flush(name: String, valid: Bool, id: Data): Unit = site("flush", name, valid, Seq("id" -> id))
  /** A recovery squashes every live instruction younger than `id` (in pipeline entry order), and
    * `id` itself when `inclusive` is set. For cores that flush a whole ROB tail in one cycle. */
  def flushYounger(name: String, valid: Bool, id: Data, inclusive: Bool): Unit =
    site("flush", name, valid, Seq("id" -> id, "inclusive" -> inclusive), Map("range" -> "younger"))
  /** `scope` is blocked by `cause` this cycle. Causes: operand_wait, structural, load_miss,
    * rob_full, lsq_full or a project word. Use `measured` only for an explicit reason signal. */
  def stall(scope: String, cause: String, valid: Bool, evidence: String = "measured"): Unit = {
    require(evidence == "measured" || evidence == "inferred", "evidence must be measured or inferred")
    site("stall", s"${scope}_$cause", valid, Nil, Map("scope" -> scope, "cause" -> cause, "evidence" -> evidence))
  }

  /** An observed data producer for an instruction. This does not assert a stall cause. */
  def dependency(name: String, valid: Bool, id: Data, producer: Data): Unit =
    site("dependency", name, valid, Seq("id" -> id, "producer" -> producer))

  /** One accepted request on a memory bus at the core's load/store or fetch port (before any
    * cache): `address`, optional `write`, `data`, byte-lane `mask` and log2 `size` in bytes. */
  def bus(bus: String, valid: Bool, address: Data, write: Option[Bool] = None, data: Option[Data] = None,
      mask: Option[Data] = None, size: Option[Data] = None): Unit =
    site("bus", bus, valid, Seq("address" -> address) ++ opt("write", write) ++ opt("data", data) ++
      opt("mask", mask) ++ opt("size", size), Map("bus" -> bus))

  /** A CSR write that takes effect this cycle. */
  def csrWrite(name: String, valid: Bool, address: Data, value: Data): Unit =
    site("csr", name, valid, Seq("address" -> address, "value" -> value))
  /** A trap entry caused by an interrupt. */
  def interruptTaken(name: String, valid: Bool, cause: Data, pc: Data, tval: Option[Data] = None): Unit =
    site("interrupt", name, valid, Seq("cause" -> cause, "pc" -> pc) ++ opt("tval", tval))
  /** One E-Trace encoder ingress row (single retirement group). Fields follow the upstream
    * encoder input: itype, cause, tval, priv, iaddr, iretire, ilastsize. */
  def traceIngress(name: String, valid: Bool, itype: Data, iaddr: Data, iretire: Data, ilastsize: Data,
      priv: Data, cause: Option[Data] = None, tval: Option[Data] = None): Unit =
    site("trace", name, valid, Seq("itype" -> itype, "iaddr" -> iaddr, "iretire" -> iretire,
      "ilastsize" -> ilastsize, "priv" -> priv) ++ opt("cause", cause) ++ opt("tval", tval))
  /** An event counter: adds `inc` (a Bool or an unsigned amount) each cycle. `hpm` binds it to
    * an mhpmevent selector value. The sampler writes totals, not one row per cycle. */
  def counter(name: String, inc: Data, hpm: Option[Int] = None): Unit = {
    val valid = inc match { case b: Bool => b; case other => other.asBits.orR }
    site("counter", name, valid, Seq("inc" -> inc), hpm.map(h => Map("hpm" -> h.toString)).getOrElse(Map.empty))
  }
  /** A register the fault tool may force (`rvw fault`). No events are sampled. */
  def faultSite(name: String, register: BaseType): Unit = if (on) {
    register.simPublic()
    val c = Component.current
    val set = registry.synchronized(registry.computeIfAbsent(toplevel(c), _ => new ProbeSet))
    set.add(i => ProbeSite(i, "fault", name, null, Seq("value" -> register), Map.empty))
  }
  /** A project event with any fields. */
  def custom(name: String, valid: Bool, fields: (String, Data)*): Unit = site("custom", name, valid, fields)
}
