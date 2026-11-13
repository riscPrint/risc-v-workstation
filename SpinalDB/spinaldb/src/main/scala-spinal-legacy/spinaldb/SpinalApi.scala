package spinaldb

import spinal.core._
import spinal.core.internals._

/** SpinalHDL members that older versions (for example NaxRiscv's pinned c3626570) lack. The
  * port and operator types are never instantiated, so their matches never succeed. */
object SpinalApi {
  trait AsyncWritePort extends MemPortStatement with WidthProvider with Expression {
    def width: Int
    def address: Expression with WidthProvider
    def data: Expression with WidthProvider
    def mask: Expression with WidthProvider
    def writeEnable: Expression
    def clockDomain: ClockDomain
    def readUnderWrite: ReadUnderWritePolicy
    def duringWrite: DuringWritePolicy
  }
  trait Repeat extends Expression { def count: Int }
  trait BitsRepeat extends Repeat
  trait BoolRepeat extends Repeat
  trait UIntRepeat extends Repeat
  trait SIntRepeat extends Repeat
  final class VerilogValue private ()
  object VerilogValue { def unapply(v: VerilogValue): Option[String] = None }
  val phaseDeviceDefault: AnyRef = new Object
  val configRecords: Seq[Class[_]] = Nil
  def preventBlackbox(m: Mem[_]): Boolean = false
}
