package spinalchecks

import spinal.core._
import spinal.core.internals._
import spinal.idslplugin.Location
import spinal.lib.bus.amba4.axi.sim.Axi4Master

/** SpinalHDL 1.15 members (the release axis, and sources that have them). */
object SpinalApi {
  type AsyncWritePort = MemReadAsyncWrite
  def report(message: Seq[Any], loc: Location): Unit = spinal.core.report(message)(loc)
  def axiWrite(m: Axi4Master, address: BigInt, bytes: List[Byte], id: Int, len: Int): Unit =
    m.write(address, bytes, id = id, maxLen = len)
}
