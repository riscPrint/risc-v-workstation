package riscvsim

import spinal.lib.bus.tilelink.Param
import spinal.lib.bus.tilelink.sim.MemoryAgent

/** A manager-side DMA port for Spinal's coherent simulation memory fabric.
  * It shares the manager's cache-line lock with CPU bus transactions. Coherent
  * accesses wait for actual B/C snoops under that lock before sampling memory.
  * Noncoherent accesses bypass snoops and require project cache maintenance. */
final class TileLinkDmaTransport(agent: MemoryAgent, physicalBase: Long) extends DmaTransport {
  override def supportsCoherence = true
  private def transaction[T](address: Int, count: Int, coherent: Boolean, write: Boolean)(body: Long => T): T = {
    require(address >= 0 && count > 0 && physicalBase >= 0 && physicalBase <= Long.MaxValue - address)
    val physical = physicalBase + address
    val blockSize = SpinalCompat.intMember(agent, "blockSize").getOrElse(
      throw new UnsupportedOperationException("MemoryAgent.blockSize is missing in this SpinalHDL version"))
    require(physical <= Long.MaxValue - count && blockSize > 0)
    val block = physical - physical % blockSize
    require(physical + count <= block + blockSize, "split DMA access at cache-line boundary")
    agent.reserve(block)
    try {
      if (coherent) agent.handleCoherency(block, false, null,
        if (write) Param.Cap.toN else Param.Cap.toB, false)
      body(physical)
    } finally agent.release(block)
  }
  def read(address: Int, count: Int, coherent: Boolean, accepted: () => Unit): Vector[Byte] =
    transaction(address,count,coherent,false) { physical =>
      val bytes = agent.mem.readBytes(physical,count).toVector
      accepted(); bytes
    }
  def write(address: Int, data: Seq[Byte], mask: BigInt, coherent: Boolean, accepted: () => Unit): Unit = {
    require(data.nonEmpty && mask >= 0 && mask < (BigInt(1) << data.size), "DMA byte mask")
    transaction(address,data.size,coherent,true) { physical =>
      data.indices.filter(mask.testBit).foreach(i => agent.mem.write(physical+i,Array(data(i))))
      accepted()
    }
  }
}
