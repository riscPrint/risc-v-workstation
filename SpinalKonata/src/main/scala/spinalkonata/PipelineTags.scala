package spinalkonata

import spinal.core._
import spinal.core.sim._
import scala.collection.mutable.ArrayBuffer

/** Simulation-only tags attached at elaboration. Valid means an event pulse/handshake,
  * not pipeline occupancy. IDs must be stable and unique for the complete run.
  * Register fetches before stage events and terminal events for same-cycle ordering.
  * Call sample in clockDomain.onSamplings, using one monotonically increasing cycle.
  */
final class PipelineTags {
  private val readers = ArrayBuffer.empty[() => Seq[Event]]
  def event(valid: Bool, id: UInt)(make: Long => Seq[Event]): Unit = {
    valid.setWeakName(s"konata_event_${readers.size}").simPublic()
    id.setWeakName(s"konata_id_${readers.size}").simPublic()
    readers += (() => if (valid.toBoolean) make(id.toLong) else Seq.empty)
  }
  def fetch(valid: Bool, id: UInt, label: () => String, thread: String = "0"): Unit =
    event(valid, id)(i => Seq(Fetch(i, i, thread), Label(i, label())))
  def enter(valid: Bool, id: UInt, stage: String, lane: String = "0"): Unit =
    event(valid, id)(i => Seq(Enter(i, stage, lane)))
  def retire(valid: Bool, id: UInt): Unit = event(valid, id)(i => Seq(Retire(i)))
  def flush(valid: Bool, id: UInt): Unit = event(valid, id)(i => Seq(Flush(i)))
  def sample(writer: KanataWriter, cycle: Long): Unit = {
    readers.foreach(reader => reader().foreach(writer.record(cycle, _)))
    writer.seal(cycle)
  }
}
