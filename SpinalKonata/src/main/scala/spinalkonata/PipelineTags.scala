package spinalkonata

import spinal.core._
import spinal.core.sim._
import scala.collection.mutable.ArrayBuffer

/** Simulation-only tags attached at elaboration. Valid means an event pulse/handshake,
  * not pipeline occupancy. IDs must be stable and unique for the complete run.
  * Stall valid is a blocked level sampled once per cycle.
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
  def stall(valid: Bool, scope: String, cause: String, evidence: String = "measured"): Unit = {
    valid.setWeakName(s"konata_stall_${readers.size}").simPublic()
    readers += (() => if (valid.toBoolean) Seq(Stall(scope, cause, evidence)) else Seq.empty)
  }
  def replay(valid: Bool, id: UInt, cause: String, evidence: String = "measured"): Unit =
    event(valid, id)(i => Seq(Replay(i, cause, evidence)))
  def commit(valid: Bool, id: UInt, predicatedOff: Bool): Unit = {
    predicatedOff.setWeakName(s"konata_predicated_${readers.size}").simPublic()
    event(valid, id)(i => Seq(Commit(i, predicatedOff.toBoolean)))
  }
  def dependency(valid: Bool, consumer: UInt, producer: UInt): Unit = {
    producer.setWeakName(s"konata_producer_${readers.size}").simPublic()
    event(valid, consumer)(i => Seq(Dependency(i, producer.toLong)))
  }
  def flush(valid: Bool, id: UInt): Unit = event(valid, id)(i => Seq(Flush(i)))
  /** Observed branch direction outcome. Optional signals are unknown (`?`) when absent.
    * Register it before the instruction's terminal tag (commit, retire or flush).
    */
  def direction(valid: Bool, id: UInt, predictor: String, predictedTaken: Bool, actualTaken: Bool,
      recovery: Option[UInt] = None, wrongPath: Option[UInt] = None, warmup: Option[Bool] = None,
      alias: Option[Bool] = None, context: () => Option[String] = () => None): Unit = {
    def taken(b: Bool) = if (b.toBoolean) "taken" else "not_taken"
    outcome(valid, id, predictor, "direction", Seq(predictedTaken, actualTaken), recovery, wrongPath, warmup, alias,
      context)(() => (taken(predictedTaken), taken(actualTaken)))
  }
  /** Observed target or return-address outcome (`kind` is "target" or "return"). */
  def target(valid: Bool, id: UInt, predictor: String, kind: String, predicted: UInt, actual: UInt,
      recovery: Option[UInt] = None, wrongPath: Option[UInt] = None, warmup: Option[Bool] = None,
      alias: Option[Bool] = None, context: () => Option[String] = () => None): Unit = {
    require(kind == "target" || kind == "return", "target kind must be target or return")
    outcome(valid, id, predictor, kind, Seq(predicted, actual), recovery, wrongPath, warmup, alias,
      context)(() => ("0x" + predicted.toBigInt.toString(16), "0x" + actual.toBigInt.toString(16)))
  }
  private def outcome(valid: Bool, id: UInt, predictor: String, kind: String, values: Seq[Data],
      recovery: Option[UInt], wrongPath: Option[UInt], warmup: Option[Bool], alias: Option[Bool],
      context: () => Option[String])(read: () => (String, String)): Unit = {
    val n = readers.size
    (values ++ recovery ++ wrongPath ++ warmup ++ alias).zipWithIndex.foreach { case (d, k) =>
      d.setWeakName(s"konata_prediction_${n}_$k").simPublic()
    }
    event(valid, id) { i =>
      val (p, a) = read()
      Seq(PredictionOutcome(i, predictor, kind, p, a, recovery.map(_.toLong), wrongPath.map(_.toLong),
        warmup.map(_.toBoolean), alias.map(_.toBoolean), context()))
    }
  }
  def sample(writer: KanataWriter, cycle: Long): Unit = {
    readers.foreach(reader => reader().foreach(writer.record(cycle, _)))
    writer.seal(cycle)
  }
}
