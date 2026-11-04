package spinalchecks.sim

import spinal.core.ClockDomain
import spinal.core.sim._
import spinal.lib.bus.tilelink._
import spinal.lib.bus.tilelink.sim._
import scala.collection.mutable

/** A serialized, noncoherent Get/Put memory model. Reads snapshot memory at accepted A completion.
  * Initialize every byte that a test reads. Concurrent overlapping accesses need a separate
  * ordering model. The model permits responses to reorder across independent sources. */
class TileLinkMemoryScoreboard(initial: Map[BigInt, Byte]) extends MonitorSubscriber {
  private val memory = mutable.Map.empty[BigInt, Byte] ++ initial
  private case class Pending(size: Int, data: Option[Array[Byte]], denied: Boolean)
  private val pending = mutable.Map.empty[Int, Pending]
  private val denials = mutable.Set.empty[Int]
  var requests = 0L
  var responses = 0L
  def expectDenied(source: Int): Unit = { require(!pending.contains(source)); denials += source }
  override def onA(a: TransactionA): Unit = {
    require(!pending.contains(a.source), s"source ${a.source} is already pending")
    val denied = denials.remove(a.source)
    val data = a.opcode match {
      case Opcode.A.GET =>
        Some(Array.tabulate(a.bytes)(i => memory.getOrElse(a.address + i,
          throw new IllegalArgumentException(s"reference byte ${a.address + i} has no initial value"))))
      case Opcode.A.PUT_FULL_DATA | Opcode.A.PUT_PARTIAL_DATA =>
        require(a.data.length == a.bytes && a.mask.length == a.bytes)
        if (!denied) for (i <- 0 until a.bytes if a.mask(i)) memory(a.address + i) = a.data(i)
        None
      case other => throw new IllegalArgumentException(s"noncoherent scoreboard does not support $other")
    }
    pending(a.source) = Pending(a.size, data, denied)
    requests += 1
  }
  override def onD(d: TransactionD): Unit = {
    val expected = pending.getOrElse(d.source, throw new IllegalArgumentException(s"unmatched source ${d.source}"))
    require(d.size == expected.size, "response size mismatch")
    require(d.denied == expected.denied, "unexpected denial status")
    require(d.opcode == (if (expected.data.isDefined) Opcode.D.ACCESS_ACK_DATA else Opcode.D.ACCESS_ACK),
      "response opcode mismatch")
    if (!d.denied) expected.data.foreach { bytes =>
      require(!d.corrupt, "unexpected corrupt response")
      require(d.data != null && java.util.Arrays.equals(bytes, d.data), "reference memory data mismatch")
    }
    pending.remove(d.source)
    responses += 1
  }
  def assertComplete(): Unit = {
    require(requests > 0, "no reference transactions observed")
    require(pending.isEmpty && denials.isEmpty && requests == responses, "reference transactions remain outstanding")
  }
}

/** Reuse Spinal's beat drivers and monitor. The scoreboard is independent of the subordinate. */
class TileLinkReference(bus: Bus, cd: ClockDomain, initial: Map[BigInt, Byte]) {
  require(!bus.p.withBCE, "coherent traffic needs its own model")
  val master = new MasterDriver(bus, cd)
  val monitor = new Monitor(bus, cd)
  val scoreboard = new TileLinkMemoryScoreboard(initial)
  monitor.add(scoreboard)
  def get(source: Int, address: BigInt, size: Int): Unit = {
    val a = TransactionA(); a.opcode = Opcode.A.GET
    a.source = source; a.address = address; a.size = size; a.param = 0; a.debugId = 0
    // Spinal's TransactionA.write sets mask only for data-bearing opcodes.
    // A Get still needs all accessed byte lanes asserted.
    master.driver.a.single { payload =>
      a.write(payload)
      if (bus.p.withDataA) {
        val lanes = scala.math.min(1 << size, bus.p.dataBytes)
        payload.mask #= ((BigInt(1) << lanes) - 1) << (address.toInt & (bus.p.dataBytes - 1))
      }
    }
  }
  def put(source: Int, address: BigInt, bytes: Array[Byte], mask: Array[Boolean]): Unit = {
    require(bytes.nonEmpty && (bytes.length & (bytes.length - 1)) == 0 && bytes.length == mask.length)
    val a = TransactionA(); a.opcode = Opcode.A.PUT_PARTIAL_DATA
    a.source = source; a.address = address; a.size = Integer.numberOfTrailingZeros(bytes.length); a.param = 0; a.debugId = 0
    a.data = bytes.clone(); a.mask = mask.clone()
    master.scheduleA(a)
  }
}
