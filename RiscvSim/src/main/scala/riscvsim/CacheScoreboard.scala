package riscvsim

import scala.collection.mutable

/** Byte-addressed stimulus oracle. Never initialize this from DUT observations. */
final class MemoryImage(val size: Int) {
  require(size > 0)
  private val bytes = Array.fill[Byte](size)(0)
  private def range(address: Int, count: Int): Unit =
    require(address >= 0 && count > 0 && address.toLong + count <= size, "memory range")
  def read(address: Int, count: Int): Vector[Byte] = {
    range(address, count); bytes.slice(address, address + count).toVector
  }
  def write(address: Int, data: Seq[Byte], mask: BigInt): Unit = {
    range(address, data.size)
    require(mask >= 0 && mask < (BigInt(1) << data.size), "byte mask")
    data.indices.filter(mask.testBit).foreach(i => bytes(address + i) = data(i))
  }
}

/** Passive cache content checker. Project adapters map accepted bus events into this API.
  * The oracle receives expected program/device writes independently of DUT read data.
  * Replacement policy is project-defined; the default checks only set/way capacity. */
final class CacheScoreboard(val oracle: MemoryImage, val lineBytes: Int, sets: Int, ways: Int, replacement: String = "any") {
  require(lineBytes > 0 && (lineBytes & (lineBytes - 1)) == 0 && sets > 0 && ways > 0)
  require(Set("any", "lru", "fifo")(replacement), "replacement policy")
  private val order = mutable.ArrayBuffer.empty[Int]
  private def touch(address: Int): Unit = if (replacement == "lru") {
    order -= address; order += address
  }
  private val resident = mutable.Map.empty[Int, Vector[Byte]]
  private val dirty = mutable.Set.empty[Int]
  private def base(a: Int): Int = { require(a >= 0); a - a % lineBytes }
  private def set(a: Int): Int = (a / lineBytes) % sets
  def contains(address: Int): Boolean = resident.contains(base(address))
  def fill(address: Int, observed: Seq[Byte], denied: Boolean = false): Unit = {
    require(address == base(address) && observed.size == lineBytes)
    if (denied) require(!resident.contains(address), "denied fill installed a line")
    else {
      require(!resident.contains(address), "duplicate fill")
      require(resident.keys.count(a => set(a) == set(address)) < ways, "replacement needs eviction")
      require(observed == oracle.read(address, lineBytes), "fill data mismatch")
      resident(address) = observed.toVector
      order += address
    }
  }
  /** Actual accepted cache write; oracle must already contain the independent expected write. */
  def store(address: Int, data: Seq[Byte], mask: BigInt): Unit = {
    val b = base(address)
    require(mask >= 0 && mask < (BigInt(1) << data.size) && data.nonEmpty)
    require(address.toLong + data.size <= b.toLong + lineBytes, "split store before checking")
    val old = resident.getOrElse(b, throw new IllegalArgumentException("store miss needs fill"))
    val updated = old.toArray
    data.indices.filter(mask.testBit).foreach(i => updated(address - b + i) = data(i))
    require(updated.toVector == oracle.read(b, lineBytes), "stored data mismatch")
    resident(b) = updated.toVector
    if (mask != 0) { dirty += b; touch(b) }
  }
  def read(address: Int, observed: Seq[Byte]): Unit = {
    val b = base(address)
    require(observed.nonEmpty && address.toLong + observed.size <= b.toLong + lineBytes)
    val data = resident.getOrElse(b, throw new IllegalArgumentException("read miss needs fill"))
    require(observed == data.slice(address - b, address - b + observed.size), "cache read mismatch")
    require(observed == oracle.read(address, observed.size), "stale data")
    touch(b)
  }
  /** Accepted dirty transfer that retains the cache line after a downgrade. */
  def writeback(address: Int, observed: Seq[Byte]): Unit = {
    require(address == base(address) && resident.contains(address), "writeback needs a resident line")
    require(observed == resident(address) && observed == oracle.read(address, lineBytes), "writeback mismatch")
    dirty -= address
  }
  /** replacementEviction distinguishes a demand replacement from maintenance. */
  def evict(address: Int, writeback: Option[Seq[Byte]], replacementEviction: Boolean = false): Unit = {
    require(address == base(address) && resident.contains(address))
    if (replacementEviction && replacement != "any")
      require(order.find(a => set(a) == set(address)).contains(address), "wrong replacement victim")
    require(!dirty(address) || writeback.nonEmpty, "dirty eviction lost writeback")
    writeback.foreach { data =>
      require(data == resident(address) && data == oracle.read(address, lineBytes), "writeback mismatch")
    }
    resident.remove(address); dirty -= address; order -= address
  }
  /** Call only after observed invalidation/maintenance completion. */
  def invalidate(address: Int): Unit = {
    val b = base(address)
    require(!dirty(b), "dirty invalidation needs writeback")
    resident.remove(b); order -= b
  }
}
