package riscvsim

import scala.collection.mutable
import spinal.lib.bus.tilelink.Opcode
import spinal.lib.bus.tilelink.sim._

/** Complete accepted TileLink messages retain one logical deadline through E.
  * Attach to one library Monitor. Check environment readiness separately.
  * Tick after each sampled clock. Reset during a transaction is not supported. */
final class TileLinkProgressObserver(boundCycles: Long, capacity: Int, fairness: String,
                                     now: () => Long) extends MonitorSubscriber {
  private val progress = new ProgressMonitor(boundCycles, capacity, fairness)
  private val acquire = mutable.Map.empty[Int, String]
  private val probes = mutable.Map.empty[(Int, BigInt), String]
  private val releases = mutable.Map.empty[Int, String]
  private val partialReleases = mutable.Set.empty[Int]
  private val grants = mutable.Map.empty[BigInt, String]
  private val counts = mutable.Map.empty[String, Int].withDefaultValue(0)
  private var serial = 0L
  private var batchCycle = -1L
  private var eventCycle = -1L
  private sealed trait Event
  private case class A(source: Int) extends Event
  private case class B(source: Int, address: BigInt, valid: Boolean) extends Event
  private case class CStart(source: Int) extends Event
  private case class C(source: Int, address: BigInt, probe: Boolean, valid: Boolean) extends Event
  private case class D(source: Int, sink: BigInt, grant: Boolean, release: Boolean, valid: Boolean) extends Event
  private case class E(sink: BigInt) extends Event
  private val queued = mutable.ArrayBuffer.empty[Event]
  private def enqueue(event: Event): Unit = {
    val cycle = now()
    require(cycle >= 0 && cycle >= batchCycle, "TileLink capture cycle order")
    if (queued.nonEmpty && cycle != batchCycle) flush()
    batchCycle = cycle; queued += event
  }
  private def request(kind: String): String = {
    val id = s"tl-$kind-$serial"
    progress.request(id, eventCycle); serial += 1; counts(kind) += 1; id
  }
  private def complete(id: String, kind: String): Unit = {
    progress.complete(id, eventCycle); counts(kind) += 1
  }
  private def applyEvent(event: Event): Unit = event match {
    case A(source) =>
      require(source >= 0 && !acquire.contains(source), "duplicate accepted A source")
      acquire(source) = request("a")
    case B(source, address, valid) =>
      require(valid && source >= 0 && address >= 0 && !probes.contains(source -> address), "invalid or duplicate accepted probe")
      probes(source -> address) = request("b")
    case CStart(source) =>
      require(source >= 0 && !releases.contains(source), "duplicate first release beat")
      releases(source) = request("c_release"); partialReleases += source
    case C(source, address, true, valid) =>
      require(valid)
      val id = probes.getOrElse(source -> address, throw new IllegalArgumentException("ProbeAck without accepted probe"))
      complete(id, "c_probe_ack"); probes.remove(source -> address)
    case C(source, _, false, valid) =>
      require(valid && source >= 0, "invalid release source")
      if (releases.contains(source)) require(partialReleases.remove(source), "duplicate complete release")
      else releases(source) = request("c_release")
      counts("c_release_complete") += 1
    case D(source, _, _, true, valid) =>
      require(valid && !partialReleases(source), "ReleaseAck before complete release")
      val id = releases.getOrElse(source, throw new IllegalArgumentException("ReleaseAck without accepted release"))
      complete(id, "d_release_ack"); releases.remove(source); counts("d") += 1
    case D(source, sink, grant, false, valid) =>
      require(valid)
      val id = acquire.getOrElse(source, throw new IllegalArgumentException("D response without accepted A"))
      if (grant) {
        require(sink >= 0 && !grants.contains(sink), "reused outstanding grant sink")
        // D does not complete/restart A's deadline. E finishes that same request.
        grants(sink) = id; counts("d_grant") += 1
      } else complete(id, "d_response")
      acquire.remove(source); counts("d") += 1
    case E(sink) =>
      val id = grants.getOrElse(sink, throw new IllegalArgumentException("GrantAck without accepted grant"))
      complete(id, "e"); grants.remove(sink)
  }
  private def flush(): Unit = if (queued.nonEmpty) {
    eventCycle = batchCycle
    val events = queued.toVector; queued.clear()
    // Release existing identities first. Then accept new prerequisites. This
    // permits same-cycle response/ack and source/sink reuse without callback races.
    val oldE = events.collect { case e: E if grants.contains(e.sink) => e }
    oldE.foreach(applyEvent)
    val oldC = events.collect { case c: C if c.probe && probes.contains(c.source -> c.address) => c }
    oldC.foreach(applyEvent)
    val oldD = events.collect { case d: D if (if (d.release) releases.contains(d.source) && !partialReleases(d.source) else acquire.contains(d.source)) => d }
    oldD.foreach(applyEvent)
    events.collect { case a: A => a }.foreach(applyEvent)
    events.collect { case b: B => b }.foreach(applyEvent)
    events.collect { case c: CStart => c }.foreach(applyEvent)
    events.collect { case c: C if !oldC.contains(c) => c }.foreach(applyEvent)
    events.collect { case d: D if !oldD.contains(d) => d }.foreach(applyEvent)
    events.collect { case e: E if !oldE.contains(e) => e }.foreach(applyEvent)
  }
  override def onA(a: TransactionA): Unit = enqueue(A(a.source))
  override def onB(b: TransactionB): Unit = enqueue(B(b.source, b.address,
    b.opcode == Opcode.B.PROBE_BLOCK || b.opcode == Opcode.B.PROBE_PERM))
  // Sources with a C transaction in progress; used when TransactionC has no `beat` (older SpinalHDL).
  private val cOpen = scala.collection.mutable.Set.empty[Long]
  private def firstBeat(c: TransactionC): Boolean =
    SpinalCompat.intMember(c, "beat").map(_ == 0).getOrElse(cOpen.add(c.source.toLong))
  override def onBeatC(c: TransactionC): Unit =
    if (firstBeat(c) && (c.opcode == Opcode.C.RELEASE || c.opcode == Opcode.C.RELEASE_DATA)) enqueue(CStart(c.source))
  override def onC(c: TransactionC): Unit = { cOpen -= c.source.toLong; enqueueC(c) }
  private def enqueueC(c: TransactionC): Unit = enqueue(C(c.source, c.address,
    c.opcode == Opcode.C.PROBE_ACK || c.opcode == Opcode.C.PROBE_ACK_DATA,
    Set(Opcode.C.PROBE_ACK, Opcode.C.PROBE_ACK_DATA, Opcode.C.RELEASE, Opcode.C.RELEASE_DATA)(c.opcode)))
  override def onD(d: TransactionD): Unit = enqueue(D(d.source, d.sink,
    d.opcode == Opcode.D.GRANT || d.opcode == Opcode.D.GRANT_DATA, d.opcode == Opcode.D.RELEASE_ACK,
    Set(Opcode.D.GRANT, Opcode.D.GRANT_DATA, Opcode.D.RELEASE_ACK, Opcode.D.ACCESS_ACK, Opcode.D.ACCESS_ACK_DATA)(d.opcode)))
  override def onE(e: TransactionE): Unit = enqueue(E(e.sink))
  def tick(): Unit = { flush(); progress.check(now()) }
  def outstanding: Int = { flush(); progress.outstanding }
  def coverage: Map[String, Int] = { flush(); counts.toMap }
  def finish(required: Set[String]): Unit = {
    flush(); progress.finish(now())
    require(required.nonEmpty && required.forall(k => counts(k) > 0), "missing TileLink progress observations")
  }
}
