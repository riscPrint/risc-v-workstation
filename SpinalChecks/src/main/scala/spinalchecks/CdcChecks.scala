package spinalchecks

import spinal.core._
import spinal.core.internals._

import scala.collection.mutable

/** Checks that Spinal can emit from its own clock-domain information.
  *
  * For each register tagged `crossClockDomain` (the first stage of `BufferCC` and of user
  * synchronizers) whose data comes, through plain copies, from a register in another clock domain:
  *
  *  - `cdc.gray`: a multi-bit source changes at most one bit per source clock.
  *  - `cdc.pulse_width`: a one-bit source holds each value for at least `settle` destination
  *    periods, when both clock domains have a `FixedFrequency`.
  *
  * The checks are `DeclaredRule`s in the source register's component and clock domain, so
  * `SpinalChecks.install` turns them into assertions or monitors with ids, waivers and the report.
  * Use:
  * {{{
  *   val (cfg, checks) = SpinalChecks.install(CdcChecks.install(SpinalConfig()), ChecksConfig())
  * }}}
  * These are digital sampled checks. They do not model metastability or analog timing. */
object CdcChecks {
  case class Found(destination: BaseType, source: BaseType, kind: String, detail: String)

  /** Records of the last elaboration that used `install` (one per inserted check). */
  val found = mutable.ArrayBuffer[Found]()

  def install(config: SpinalConfig, settle: Double = 1.5): SpinalConfig = {
    require(settle > 0)
    val c = config.copy(phasesInserters = config.phasesInserters.clone())
    c.phasesInserters += { phases =>
      // Before PhaseInsertChecks (which SpinalChecks.install puts at the same place later), so the
      // declared rules are turned into checks.
      val at = phases.indexWhere(_.isInstanceOf[PhaseCheckIoBundle])
      require(at >= 0, "CdcChecks: PhaseCheckIoBundle not found (unsupported Spinal version?)")
      phases.insert(at, new PhaseCdcChecks(settle))
    }
    c
  }

  /** The register that drives `bt` through single plain assignments (wires and ports), or null. */
  def sourceRegister(bt: BaseType, hops: Int = 16): BaseType = {
    val sources = mutable.ArrayBuffer[Expression]()
    bt.foreachStatements {
      case _: InitAssignmentStatement =>
      case a: AssignmentStatement if a.target == bt => sources += a.source
      case _ => sources += null
    }
    if (sources.size != 1) return null
    sources.head match {
      case s: BaseType if s.isReg => s
      case s: BaseType if hops > 0 => sourceRegister(s, hops - 1)
      case _ => null
    }
  }

  private def hz(cd: ClockDomain): Option[BigDecimal] = cd.frequency match {
    case f: ClockDomain.FixedFrequency => Some(f.getValue.toBigDecimal)
    case _ => None
  }

  private def sanitize(s: String) = s.replaceAll("[^A-Za-z0-9_]", "_")

  private[spinalchecks] def insert(dst: BaseType, src: BaseType, settle: Double): Unit = {
    val name = sanitize(s"${src.getName()}_to_${dst.getName()}")
    val width = src.getBitsWidth
    if (width > 1) {
      found += Found(dst, src, "cdc.gray", s"$width bits")
      val v = src.asBits
      val prev = RegNext(v).setName(s"cdc_${name}_prev")
      val valid = RegNext(True).init(False).setName(s"cdc_${name}_valid")
      val diff = (v ^ prev).setName(s"cdc_${name}_diff")
      DeclaredChecks.rule("cdc.gray", name,
        s"at most one of $width bits changes per source clock before ${dst.getName()}")(
        valid && (diff & (diff.asUInt - 1).asBits) =/= 0)
    } else (hz(src.clockDomain), hz(dst.clockDomain)) match {
      case (Some(fs), Some(fd)) =>
        val hold = math.ceil((fs / fd).toDouble * settle).toInt.max(1)
        if (hold > 1) {
          found += Found(dst, src, "cdc.pulse_width", s"$hold source cycles")
          val v = src.asBits.asBool
          val prev = RegNext(v).setName(s"cdc_${name}_prev")
          val valid = RegNext(True).init(False).setName(s"cdc_${name}_valid")
          val held = Reg(UInt(log2Up(hold + 1) bits)).init(hold).setName(s"cdc_${name}_held")
          val changed = valid && v =/= prev
          when(changed) { held := 1 }.elsewhen(held =/= hold) { held := held + 1 }
          DeclaredChecks.rule("cdc.pulse_width", name,
            s"each value is held $hold source cycles ($settle destination periods) before ${dst.getName()}")(
            changed && held < hold)
        }
      case _ =>
    }
  }
}

class PhaseCdcChecks(settle: Double) extends PhaseNetlist {
  override def impl(pc: PhaseContext): Unit = {
    CdcChecks.found.clear()
    val pairs = mutable.LinkedHashMap[BaseType, BaseType]()
    pc.walkComponents { c =>
      c.dslBody.walkDeclarations {
        case bt: BaseType if bt.isReg && bt.hasTag(crossClockDomain) =>
          val src = CdcChecks.sourceRegister(bt)
          if (src != null && src.clockDomain != null && bt.clockDomain != null &&
              src.clockDomain.clock != bt.clockDomain.clock) pairs(bt) = src
        case _ =>
      }
    }
    for ((dst, src) <- pairs) {
      val comp = src.component
      comp.rework { src.clockDomain.on { CdcChecks.insert(dst, src, settle) } }
    }
  }
}
