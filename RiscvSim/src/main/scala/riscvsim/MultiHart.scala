package riscvsim

import java.io.{File, PrintWriter}
import scala.collection.mutable

/** Opt-in C2/2 writer. File order is capture order, never a memory-model oracle. */
final class MultiHartTrace(file: File, header: ujson.Obj, hartIds: Seq[Int]) extends AutoCloseable {
  require(hartIds.nonEmpty && hartIds.distinct.size == hartIds.size && hartIds.forall(_ >= 0))
  require(!header.value.contains("schema") && !header.value.contains("harts"))
  private val epoch = mutable.Map.from(hartIds.map(_ -> -1))
  private val nextOrder = mutable.Map.from(hartIds.map(_ -> BigInt(0)))
  private val done = mutable.Map.empty[Int, Status]
  private var cycle = -1L
  private var seq = 0L
  private val eventIds = mutable.Set.empty[String]
  private val out = { file.getAbsoluteFile.getParentFile.mkdirs(); new PrintWriter(file, "UTF-8") }
  out.println(ujson.write(ujson.Obj.from(header.value.toSeq ++ Seq(
    "schema" -> ujson.Str("rvw.rvfi/2"), "capabilities" -> ujson.Arr("multihart"), "harts" -> ujson.Arr.from(hartIds)))))
  private def emit(c: Long, fields: ujson.Obj): Unit = {
    require(c >= 0 && c <= 9007199254740991L && c >= cycle, "capture cycle range/order")
    cycle = c
    fields("cycle") = ujson.Num(c.toDouble)
    // Sequence is a string: JSON doubles cannot represent every Long.
    fields("capture_seq") = seq.toString
    seq += 1
    out.println(ujson.write(fields))
  }
  private def active(h: Int): Unit = {
    require(epoch.contains(h), s"unknown hart $h")
    require(epoch(h) >= 0 && !done.contains(h), s"hart $h is not active")
  }
  def reset(h: Int, c: Long): Unit = {
    require(epoch.contains(h) && !done.contains(h))
    require(c >= 0 && c <= 9007199254740991L && c >= cycle)
    epoch(h) += 1
    nextOrder(h) = 0
    emit(c, ujson.Obj("event" -> "reset", "hart" -> h, "epoch" -> epoch(h)))
  }
  def retire(h: Int, r: RvfiRecord): Unit = {
    active(h)
    require(r.order >= 0 && r.order < (BigInt(1) << 64))
    require(r.order == nextOrder(h), s"hart $h retirement order gap")
    val fields = ujson.read(r.toJson).obj
    fields("hart") = ujson.Num(h)
    fields("epoch") = ujson.Num(epoch(h))
    // Keep full precision for RVFI's 64-bit order field.
    fields("order") = ujson.Str(r.order.toString)
    emit(r.cycle, ujson.Obj.from(fields))
    nextOrder(h) += 1
  }
  /** Captures an accepted external action. Payload must include address, data, mask and source. */
  def memory(c: Long, id: String, action: String, payload: ujson.Obj): Unit = {
    require(id.nonEmpty && !eventIds(id) && Set("read", "write", "atomic", "irq", "maintenance").contains(action))
    require(Seq("address", "data", "mask", "source").forall(payload.value.contains))
    require(!Seq("event", "cycle", "capture_seq", "id", "action").exists(payload.value.contains))
    emit(c, ujson.Obj.from(payload.value.toSeq ++ Seq("event" -> ujson.Str("external"),
      "id" -> ujson.Str(id), "action" -> ujson.Str(action))))
    eventIds += id
  }
  def complete(h: Int, c: Long, status: Status): Unit = {
    active(h)
    emit(c, ujson.Obj("event" -> "hart_end", "hart" -> h, "epoch" -> epoch(h), "status" -> status.name))
    done(h) = status
  }
  /** No completion or partial success must become a passing C1 outcome. */
  def outcome(c: Long, instret: Long): RunOutcome = {
    val status = if (done.values.exists(_ == Status.Error)) Status.Error
      else if (done.size != hartIds.size) Status.Timeout
      else Seq(Status.RvfiError, Status.Assert, Status.Timeout, Status.Fail)
        .find(s => done.values.exists(_ == s)).getOrElse(Status.Pass)
    RunOutcome(status, c, instret, details = ujson.Obj("multihart" -> ujson.Obj(
      "trace_schema" -> "rvw.rvfi/2", "harts" -> ujson.Arr.from(hartIds.map(h => ujson.Obj(
        "hart" -> h, "epoch" -> epoch(h), "status" -> ujson.Str(done.get(h).map(_.name).getOrElse("incomplete"))))))))
  }
  def close(): Unit = { out.close(); require(!out.checkError(), "trace write failed") }
}
