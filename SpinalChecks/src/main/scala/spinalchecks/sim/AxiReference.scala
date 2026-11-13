package spinalchecks.sim

import spinal.core.ClockDomain
import spinal.lib.bus.amba4.axi._
import spinal.lib.bus.amba4.axi.sim._
import scala.collection.mutable

/** Serialized INCR memory traffic. Expected bytes are separate from the subordinate memory.
  * Use protocol reference tests for channel errors and reordering. */
class AxiReference(bus: Axi4, cd: ClockDomain) {
  require(!spinalchecks.SpinalCompat.axi3(bus.config), "AXI reference supports AXI4")
  val master = Axi4Master(bus, cd)
  private val expected = mutable.Map.empty[BigInt, Byte]
  var reads = 0L
  var writes = 0L
  def write(address: BigInt, bytes: List[Byte], id: Int = 0, len: Int = 0): Unit = {
    require(bytes.nonEmpty)
    spinalchecks.SpinalApi.axiWrite(master, address, bytes, id, len)
    bytes.zipWithIndex.foreach { case (b, i) => expected(address + i) = b }
    writes += 1
  }
  def checkRead(address: BigInt, count: Int, id: Int = 0, len: Int = 0): List[Byte] = {
    require(count > 0)
    val want = (0 until count).map(i => expected.getOrElse(address + i,
      throw new IllegalArgumentException(s"no reference byte at ${address + i}"))).toList
    val got = master.read(address, count, id = id, len = len)
    require(got == want, "AXI reference memory data mismatch")
    reads += 1
    got
  }
  def copy(source: BigInt, destination: BigInt, count: Int, id: Int = 0, len: Int = 0): Unit =
    write(destination, checkRead(source, count, id, len), id, len)
}
