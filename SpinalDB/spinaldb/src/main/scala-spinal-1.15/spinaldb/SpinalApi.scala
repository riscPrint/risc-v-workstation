package spinaldb

import spinal.core._
import spinal.core.internals._

/** SpinalHDL members that older versions lack, for SpinalHDL 1.15 and later. The source axis
  * (`scripts/sbt/SpinalAxis.scala`) compiles this file or `scala-spinal-legacy/`. */
object SpinalApi {
  type AsyncWritePort = MemReadAsyncWrite
  type BitsRepeat = Operator.Bits.Repeat
  type BoolRepeat = Operator.Bool.Repeat
  type UIntRepeat = Operator.UInt.Repeat
  type SIntRepeat = Operator.SInt.Repeat
  type VerilogValue = VerilogValues
  object VerilogValue { def unapply(v: VerilogValues): Option[String] = Some(v.v) }
  val phaseDeviceDefault: AnyRef = PhaseDeviceDefault
  val configRecords: Seq[Class[_]] = Seq(classOf[ObfuscateConfig])
  def preventBlackbox(m: Mem[_]): Boolean = m.preventMemToBlackboxTranslation
}
