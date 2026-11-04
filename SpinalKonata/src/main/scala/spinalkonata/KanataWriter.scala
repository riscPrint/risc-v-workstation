package spinalkonata

import java.io.{BufferedWriter, File, FileWriter, PrintWriter}
import scala.collection.mutable

sealed trait Event
final case class Fetch(id: Long, simId: Long, thread: String = "0") extends Event
final case class Label(id: Long, text: String, kind: Int = 0) extends Event
final case class Enter(id: Long, stage: String, lane: String = "0") extends Event
final case class Leave(id: Long, stage: String, lane: String = "0") extends Event
final case class Retire(id: Long) extends Event
final case class Flush(id: Long) extends Event
/** One sampled cycle. Scope names the blocked resource/thread, not an instruction. */
final case class Stall(scope: String, cause: String, evidence: String = "measured") extends Event
final case class Replay(id: Long, cause: String, evidence: String = "measured") extends Event
/** Physical completion with an observed predication flag. Retire alone keeps unknown semantics. */
final case class Commit(id: Long, predicatedOff: Boolean) extends Event
/** Observed outcomes only. None means unknown, never an inferred zero.
  * Recovery counts cycles to resumed correct-path fetch. Work counts admitted wrong-path instructions.
  * Project bindings supply predictor identity, warmup, alias and context observations.
  */
final case class PredictionOutcome(id: Long, predictor: String, kind: String,
    predicted: String, actual: String, recoveryCycles: Option[Long] = None,
    wrongPathInstructions: Option[Long] = None, warmup: Option[Boolean] = None,
    alias: Option[Boolean] = None, context: Option[String] = None) extends Event
object StallCause {
  val OperandWait = "operand_wait"
  val Structural = "structural"
  val LoadMiss = "load_miss"
  val RobFull = "rob_full"
  val LsqFull = "lsq_full"
}
final case class Dependency(consumer: Long, producer: Long) extends Event

/** Buffered event writer. Schedule future events freely, then seal each sampled cycle.
  * No ISA, pipeline names, ROB indices, or simulator assumptions live here.
  * Open instructions at close remain open (a bounded trace is not a flush).
  */
final class KanataWriter(out: File, startCycle: Long = 0) extends AutoCloseable {
  require(startCycle >= 0)
  Option(out.getAbsoluteFile.getParentFile).foreach(_.mkdirs())
  private val writer = new PrintWriter(new BufferedWriter(new FileWriter(out), 1 << 20))
  writer.print(s"Kanata\t0004\nC=\t$startCycle\n")
  private val pending = mutable.TreeMap.empty[Long, mutable.ArrayBuffer[Event]]
  private val seen = mutable.HashSet.empty[Long]
  private val predictions = mutable.HashSet.empty[(Long, String, String)]
  private val alive = mutable.HashSet.empty[Long]
  private val lanes = mutable.HashMap.empty[(Long, String), String]
  private var sealedThrough = startCycle - 1
  private var cursor = startCycle
  private var retired = 0L
  private var closed = false

  private def safe(s: String): String = s.replace('\t', ' ').replace('\r', ' ').replace('\n', ' ')
  def record(at: Long, event: Event): Unit = {
    require(!closed, "writer closed")
    require(at > sealedThrough && at >= startCycle, s"event at sealed cycle $at")
    pending.getOrElseUpdate(at, mutable.ArrayBuffer.empty) += event
  }
  private def live(id: Long): Unit = require(alive(id), s"unknown or ended instruction $id")
  private def line(s: String): Unit = writer.println(s)
  private def finish(id: Long, flush: Boolean): Unit = {
    live(id)
    lanes.keys.filter(_._1 == id).toList.sorted.foreach { key =>
      line(s"E\t$id\t${safe(key._2)}\t${safe(lanes.remove(key).get)}")
    }
    line(s"R\t$id\t${if (flush) 0 else retired}\t${if (flush) 1 else 0}")
    if (!flush) retired += 1
    alive -= id
  }
  private def token(value: String): String = {
    require(value.nonEmpty && !value.exists(c => c == '\t' || c == '\r' || c == '\n'), "invalid event token")
    value
  }
  private def evidence(value: String): String = {
    require(Set("measured", "inferred")(value), "invalid evidence kind")
    value
  }
  private def write(event: Event): Unit = event match {
    case Fetch(id, sim, thread) =>
      require(!seen(id), s"duplicate instruction $id")
      seen += id; alive += id
      line(s"I\t$id\t$sim\t${safe(thread)}")
    case Label(id, text, kind) =>
      live(id); require(kind >= 0 && kind <= 2)
      line(s"L\t$id\t$kind\t${safe(text)}")
    case Enter(id, stage, lane) =>
      live(id); require(stage.nonEmpty)
      lanes.remove((id, lane)).foreach(old => line(s"E\t$id\t${safe(lane)}\t${safe(old)}"))
      lanes((id, lane)) = stage
      line(s"S\t$id\t${safe(lane)}\t${safe(stage)}")
    case Leave(id, stage, lane) =>
      live(id); require(lanes.get((id, lane)).contains(stage), s"stage $stage is not active")
      lanes.remove((id, lane))
      line(s"E\t$id\t${safe(lane)}\t${safe(stage)}")
    case Stall(scope, cause, basis) =>
      line(s"#rvw\t1\tstall\t${token(scope)}\t${token(cause)}\t${evidence(basis)}")
    case Replay(id, cause, basis) =>
      live(id)
      line(s"#rvw\t1\treplay\t$id\t${token(cause)}\t${evidence(basis)}")
    case PredictionOutcome(id, predictor, kind, predicted, actual, recovery, work, warmup, alias, context) =>
      live(id)
      require(token(predictor) != "?", "unknown predictor identity")
      require(Set("direction", "target", "return")(kind), "invalid prediction kind")
      def address(value: String): BigInt = {
        require(value.matches("(0x[0-9a-fA-F]+|[0-9]+)"), "invalid prediction address")
        val result = if (value.startsWith("0x")) BigInt(value.drop(2), 16) else BigInt(value)
        require(result >= 0, "negative prediction address"); result
      }
      if (kind == "direction") {
        require(Seq(predicted, actual).forall(Set("taken", "not_taken")), "invalid direction")
      } else { address(predicted); address(actual) }
      require(predictions.add((id, predictor, kind)), "duplicate prediction outcome")
      def count(value: Option[Long]): String = value.map { n => require(n >= 0); n.toString }.getOrElse("?")
      val fields = Seq("#rvw", "1", "prediction", id.toString, predictor, kind,
        token(predicted), token(actual), count(recovery), count(work),
        warmup.map(_.toString).getOrElse("?"), alias.map(_.toString).getOrElse("?"),
        context.map(token).getOrElse("?"))
      line(fields.mkString("\t"))
    case Commit(id, off) =>
      live(id)
      line(s"#rvw\t1\tcommit\t$id\t${if (off) "predicated_off" else "architectural"}")
      finish(id, flush = false)
    case Retire(id) => finish(id, flush = false)
    case Flush(id) => finish(id, flush = true)
    case Dependency(consumer, producer) =>
      live(consumer); require(seen(producer), s"unknown producer $producer")
      line(s"W\t$consumer\t$producer\t0")
  }
  /** Flush through this cycle, including quiet cycles so observation length is explicit. */
  def seal(at: Long): Unit = {
    require(!closed && at >= sealedThrough && at >= startCycle)
    pending.keys.takeWhile(_ <= at).toList.foreach { t =>
      if (t != cursor) line(s"C\t${t - cursor}")
      cursor = t
      pending.remove(t).get.foreach(write)
    }
    if (at != cursor) line(s"C\t${at - cursor}")
    cursor = at
    sealedThrough = at
  }
  override def close(): Unit = if (!closed) {
    try {
      if (pending.nonEmpty) seal(pending.lastKey)
      writer.flush()
      require(!writer.checkError(), s"failed to write ${out.getPath}")
    } finally { writer.close(); closed = true }
  }
}
