package spinalchecks

import spinal.core._
import spinal.core.internals._
import spinal.lib.bus.amba4.axi.Axi4Config
import spinal.lib.bus.tilelink.Opcode

/** Calls that differ between the SpinalHDL versions the library is built against (see
  * `scripts/sbt/SpinalAxis.scala`). Members missing from older SpinalHDL versions live in the
  * per-API `SpinalApi` objects (`src/main/scala-spinal-<api>/`). */
object SpinalCompat {
  /** `Axi4Config.withAxi3`; false in older SpinalHDL versions, which have no AXI3 mode. */
  def axi3(c: Axi4Config): Boolean =
    c.getClass.getMethods.find(m => m.getName == "withAxi3" && m.getParameterCount == 0).exists(_.invoke(c) == true)

  /** `Regex.matches` (Scala 2.13 only): the whole string matches. */
  def matches(r: scala.util.matching.Regex, s: String): Boolean = r.pattern.matcher(s).matches()

  /** `Opcode.D.isData` (missing in older SpinalHDL): the D opcodes that carry data. */
  def isDataD(opcode: SpinalEnumCraft[Opcode.D.type]): Bool =
    opcode === Opcode.D.ACCESS_ACK_DATA || opcode === Opcode.D.GRANT_DATA

  /** `spinal.core.internals.Literal(bt)` (missing in older SpinalHDL): the value of a
    * combinational signal with one literal assignment in its own scope; throws otherwise. */
  def literal(bt: BaseType): BigInt = bt match {
    case b if b.isComb && b.dlcHasOnlyOne && b.dlcHead.parentScope == b.parentScope => b.dlcHead match {
      case das: DataAssignmentStatement if das.target == b => das.source match {
        case lit: Literal if !lit.hasPoison() => lit.getValue()
        case _ => throw new IllegalArgumentException("not a literal")
      }
      case _ => throw new IllegalArgumentException("not a literal")
    }
    case _ => throw new IllegalArgumentException("not a literal")
  }
}
