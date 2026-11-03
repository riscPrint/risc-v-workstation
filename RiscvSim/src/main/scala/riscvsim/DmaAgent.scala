package riscvsim

/** Adapter hooks must wait for accepted snoop/maintenance completion before returning. */
trait DmaSnoop {
  def beforeRead(address: Int, count: Int): Unit
  def beforeWrite(address: Int, count: Int): Unit
}

/** DMA agent for a byte-addressed simulation memory model.
  * backing is device-visible storage; expected is the independent stimulus oracle.
  * CPU dirty data need not be in backing until a snoop or explicit clean completes. */
final class DmaAgent(backing: MemoryImage, expected: MemoryImage, snoop: Option[DmaSnoop],
                     capture: ujson.Obj => Unit) {
  require((backing ne expected) && backing.size == expected.size)
  private var serial = 0L
  private def event(action: String, address: Int, data: Seq[Byte], mask: BigInt, coherent: Boolean): Unit = {
    capture(ujson.Obj("id" -> s"dma-$serial", "action" -> action, "source" -> "dma",
      "address" -> Hex(BigInt(address)), "data" -> Hex(data.zipWithIndex.map { case (b, i) => BigInt(b & 255) << (i * 8) }.sum),
      "mask" -> Hex(mask), "coherent" -> coherent))
    serial += 1
  }
  private def hooks(coherent: Boolean): Option[DmaSnoop] = {
    require(!coherent || snoop.nonEmpty, "coherent DMA needs a snoop adapter")
    if (coherent) snoop else None
  }
  def read(address: Int, count: Int, coherent: Boolean): Vector[Byte] = {
    // Validate ranges before invoking an adapter or changing memory.
    val wanted = expected.read(address, count)
    hooks(coherent).foreach(_.beforeRead(address, count))
    val data = backing.read(address, count)
    require(data == wanted, "DMA saw stale or corrupt data; clean cache before noncoherent read")
    event("read", address, data, (BigInt(1) << count) - 1, coherent)
    data
  }
  def write(address: Int, data: Seq[Byte], mask: BigInt, coherent: Boolean): Unit = {
    expected.read(address, data.size)
    require(mask >= 0 && mask < (BigInt(1) << data.size))
    hooks(coherent).foreach(_.beforeWrite(address, data.size))
    // Both writes originate from external test stimulus, never from observed DUT data.
    backing.write(address, data, mask); expected.write(address, data, mask)
    event("write", address, data, mask, coherent)
  }
}
