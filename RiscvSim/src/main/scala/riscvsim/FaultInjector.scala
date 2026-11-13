package riscvsim

import java.io.File

import scala.collection.mutable

import spinal.core._
import spinal.core.sim._
import spinal.core.internals.{PhaseContext, PhaseNetlist}

/** One fault of a C1 fault file (`rvw.fault/1`). */
case class Fault(id: String, kind: String, site: String, bit: Int, cycle: Long, duration: Option[Long]) {
  def lastCycle: Option[Long] = kind match {
    case "flip" => Some(cycle)
    case _ => duration.map(d => cycle + d - 1)
  }
}

/** A parsed `--fault` file. The file bytes stay in the job for replay. */
case class FaultFile(file: File, faults: Seq[Fault])

object FaultFile {
  val schema = "rvw.fault/1"
  val kinds = Set("stuck0", "stuck1", "flip")

  def load(file: File): FaultFile = {
    val doc = ujson.read(java.nio.file.Files.readString(file.toPath))
    if (doc.obj.get("schema").exists(_.str != schema)) throw new Cli.UsageError(s"--fault: schema must be $schema")
    val faults = doc("faults").arr.toSeq.map { v =>
      val o = v.obj
      def num(k: String): Long = o.get(k).map(x => x.num).filter(n => n >= 0 && n % 1 == 0).map(_.toLong)
        .getOrElse(throw new Cli.UsageError(s"--fault: '$k' must be a non-negative integer"))
      val kind = o("kind").str
      if (!kinds(kind)) throw new Cli.UsageError(s"--fault: unknown kind '$kind'")
      val duration = o.get("duration").filterNot(_.isNull).map(_ => num("duration"))
      if (duration.exists(_ <= 0)) throw new Cli.UsageError("--fault: duration must be positive")
      Fault(o.get("id").map(_.str).getOrElse(o("site").str + ":" + num("bit")), kind, o("site").str,
        num("bit").toInt, num("cycle"), duration)
    }
    if (faults.isEmpty) throw new Cli.UsageError("--fault: the file lists no faults")
    FaultFile(file, faults)
  }

  /** Design database register path: instance names below the toplevel, then the signal name. */
  def path(bt: BaseType): String = {
    def inst(c: Component): Seq[String] = if (c == null || c.parent == null) Nil else inst(c.parent) :+ c.getName()
    (inst(bt.component) :+ bt.getName()).mkString(".")
  }

  /** Elaboration phase for fault models: every register becomes visible and writable in Verilator. */
  class PublicRegisters extends PhaseNetlist {
    override def impl(pc: PhaseContext): Unit = pc.walkDeclarations {
      case bt: BaseType if bt.isReg => bt.simPublic()
      case _ =>
    }
  }
}

/**
 * Applies the faults of one run through Verilator public access and records what happened.
 * `stuck0`/`stuck1` set the bit after every clock edge from `cycle` for `duration` cycles (or to
 * the end); `flip` inverts it once at `cycle`. Each fault is confirmed by reading the register back
 * one time unit after the write. Cycles are `SimControl.cycle` values.
 */
class FaultInjector(file: FaultFile) {
  private class State(val fault: Fault) {
    var target: Option[BaseType] = None
    var reason: Option[String] = None
    var before: Option[BigInt] = None
    var after: Option[BigInt] = None
    var appliedCycle: Option[Long] = None
    var writes = 0L
    var lastWrite: Option[Long] = None
  }
  private val states = file.faults.map(new State(_))
  @volatile private var attached = false

  /** Resolves the sites in `dut` and forks the injection thread. Call inside the simulation. */
  def attach(dut: Component, ctl: SimControl): Unit = {
    attached = true
    val registers = mutable.HashMap[String, BaseType]()
    dut.walkComponents(c => c.dslBody.walkStatements {
      case bt: BaseType if bt.isReg && bt.hasTag(SimPublic) => registers(FaultFile.path(bt)) = bt
      case _ =>
    })
    for (s <- states) registers.get(s.fault.site) match {
      case None => s.reason = Some("site is not a public register of the simulation model")
      case Some(_: SpinalEnumCraft[_]) => s.reason = Some("enumeration registers are not supported")
      case Some(bt) if s.fault.bit >= bt.getBitsWidth =>
        s.reason = Some(s"bit ${s.fault.bit} outside the ${bt.getBitsWidth}-bit register")
      case Some(bt) => s.target = Some(bt)
    }
    val live = states.filter(_.target.nonEmpty)
    if (live.isEmpty) return
    val cd = dut.clockDomain
    // Count clock samples here. The adapter's tick() runs in another thread on the
    // same edge, so reading ctl.cycle could see either side of the increment and
    // skip a cycle. The contract is one tick() per sample, starting at zero.
    var samples = ctl.cycle
    var diverged = false
    fork {
      while (!diverged && live.exists(s => s.fault.lastCycle.forall(l => s.lastWrite.forall(_ < l)))) {
        cd.waitSampling()
        samples += 1
        val cycle = samples
        diverged = ctl.cycle != samples && ctl.cycle != samples - 1
        if (diverged) {
          for (s <- live if s.writes == 0) {
            s.lastWrite = Some(cycle)
            s.reason = Some(s"adapter cycle ${ctl.cycle} diverges from clock sample $samples; injection cycle is ambiguous")
          }
        }
        val first = mutable.ArrayBuffer[State]()
        for (s <- live if !diverged; bt <- s.target) {
          val f = s.fault
          val active = cycle >= f.cycle && f.lastCycle.forall(cycle <= _) && !(f.kind == "flip" && s.writes > 0)
          if (active) {
            val value = FaultInjector.raw(bt)
            val mask = BigInt(1) << f.bit
            val next = f.kind match {
              case "stuck0" => value & ~mask
              case "stuck1" => value | mask
              case _ => value ^ mask
            }
            setBigInt(bt, next)
            if (s.writes == 0) { s.before = Some(value); s.appliedCycle = Some(cycle); first += s }
            s.writes += 1
            s.lastWrite = Some(cycle)
          } else if (f.lastCycle.exists(cycle > _) && s.lastWrite.isEmpty) {
            s.lastWrite = Some(cycle)
            s.reason = Some(s"fault window ended before cycle $cycle, the first cycle the injector saw")
          }
        }
        if (first.nonEmpty) {
          sleep(1)
          for (s <- first; bt <- s.target) s.after = Some(FaultInjector.raw(bt))
        }
      }
    }
  }

  /** C1 `details.fault` for this run. */
  def details(endCycle: Long): ujson.Value = {
    val items = states.map { s =>
      val f = s.fault
      val confirmed = for (a <- s.after; b <- s.before) yield f.kind match {
        case "stuck0" => !a.testBit(f.bit)
        case "stuck1" => a.testBit(f.bit)
        case _ => a.testBit(f.bit) != b.testBit(f.bit)
      }
      val o = ujson.Obj("id" -> f.id, "kind" -> f.kind, "site" -> f.site, "bit" -> f.bit, "cycle" -> RvwJson.num(f.cycle))
      if (confirmed.contains(true)) {
        o("applied") = true
        o("applied_cycle") = RvwJson.num(s.appliedCycle.get)
        o("before") = Hex(s.before.get)
        o("after") = Hex(s.after.get)
        o("writes") = RvwJson.num(s.writes)
      } else {
        o("applied") = false
        o("reason") = s.reason.getOrElse(
          if (!attached) "adapter did not attach the generic fault injector"
          else if (s.before.isEmpty) s"run ended at cycle $endCycle before the fault cycle"
          else "read-back did not show the forced bit")
      }
      o
    }
    if (items.size == 1) items.head
    else {
      val all = items.forall(_("applied").bool)
      val o = ujson.Obj("applied" -> all, "faults" -> ujson.Arr.from(items))
      if (!all) o("reason") = "not every fault was applied"
      o
    }
  }
}

object FaultInjector {
  /** Unsigned register bits. */
  def raw(bt: BaseType): BigInt = bt match {
    case b: Bool => if (b.toBoolean) 1 else 0
    case b: Bits => b.toBigInt
    case u: UInt => u.toBigInt
    case s: SInt => val v = s.toBigInt; if (v < 0) v + (BigInt(1) << s.getBitsWidth) else v
    case other => throw new IllegalArgumentException(s"unsupported register type ${other.getClass.getSimpleName}")
  }

  private val active = new java.util.concurrent.ConcurrentHashMap[String, FaultInjector]()
  private def key(job: RunJob) = job.out.getAbsolutePath

  /** The injector for a run with `--fault`; created on first use. */
  def forJob(job: RunJob): Option[FaultInjector] =
    job.fault.map(f => active.computeIfAbsent(key(job), _ => new FaultInjector(f)))

  /** Removes and returns this run's injector. */
  def finish(job: RunJob): Option[FaultInjector] =
    job.fault.map(f => Option(active.remove(key(job))).getOrElse(new FaultInjector(f)))
}
