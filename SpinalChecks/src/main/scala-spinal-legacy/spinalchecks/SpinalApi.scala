package spinalchecks

import spinal.core._
import spinal.core.internals._
import spinal.idslplugin.Location
import spinal.lib.bus.amba4.axi.sim.Axi4Master

/** SpinalHDL members that older versions (for example NaxRiscv's pinned c3626570) lack or name
  * differently. `AsyncWritePort` is never instantiated, so its match never succeeds. */
object SpinalApi {
  trait AsyncWritePort extends MemPortStatement with WidthProvider with Expression {
    def address: Expression with WidthProvider
    def address_=(e: Expression with WidthProvider): Unit
    def writeEnable: Expression
    def writeEnable_=(e: Expression): Unit
    def clockDomain: ClockDomain
  }
  /** `report` takes no source location in this version. */
  def report(message: Seq[Any], loc: Location): Unit = spinal.core.report(message)
  /** The burst length parameter is named `len` in this version. */
  def axiWrite(m: Axi4Master, address: BigInt, bytes: List[Byte], id: Int, len: Int): Unit =
    m.write(address, bytes, id = id, len = len)
}
