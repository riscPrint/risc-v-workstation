package riscvsim

import scala.collection.mutable

/** Expected instruction bytes come from test stimulus, never from fetch data.
  * A project observer calls synchronize only after its publication protocol and
  * local FENCE.I complete. fetch checks consumed bytes, not speculative replies. */
final class InstructionVisibility(expected: MemoryImage, harts: Set[Int]) {
  require(harts.nonEmpty)
  private val published = mutable.Map.empty[String, (Int, Vector[Byte])]
  private val visible = mutable.Map.empty[(Int, String), Vector[Byte]]
  private val checked = mutable.Set.empty[(Int, String)]
  def publish(id: String, address: Int, bytes: Seq[Byte]): Unit = {
    require(id.nonEmpty && !published.contains(id), "duplicate publication")
    require(bytes.nonEmpty && expected.read(address, bytes.size) == bytes, "publication differs from stimulus")
    published(id) = (address, bytes.toVector)
  }
  def synchronize(hart: Int, id: String, dataVisible: Boolean, localFenceComplete: Boolean): Unit = {
    require(harts(hart) && published.contains(id), "unknown hart or publication")
    require(dataVisible && localFenceComplete, "publication needs data synchronization and local FENCE.I")
    val (address, bytes) = published(id)
    require(expected.read(address,bytes.size) == bytes, "publication superseded before synchronization")
    val obsolete = visible.keys.filter { case (h,p) =>
      val (other,data) = published(p)
      h == hart && address.toLong < other.toLong + data.size && other.toLong < address.toLong + bytes.size
    }.toSeq
    obsolete.foreach(visible.remove)
    visible((hart, id)) = bytes
  }
  def fetch(hart: Int, id: String, address: Int, bytes: Seq[Byte]): Unit = {
    require(harts(hart) && published.contains(id), "unknown hart or publication")
    val wanted = visible.getOrElse((hart,id), throw new IllegalArgumentException("unsynchronized instruction observation"))
    require(address == published(id)._1 && bytes == wanted, "stale or corrupt synchronized instruction bytes")
    checked += ((hart,id))
  }
  def finish(required: Set[(Int, String)]): Unit = {
    require(required.nonEmpty && required.subsetOf(checked.toSet), "missing synchronized instruction observations")
  }
}
