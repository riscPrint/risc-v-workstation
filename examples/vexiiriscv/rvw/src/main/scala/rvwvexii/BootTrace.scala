package rvwvexii

import java.io.File
import scala.collection.mutable
import spinal.core._
import spinal.core.sim._
import riscvsim._

/** Host memory effects for the simulation-only retirement observer. */
final class BootTrace(port: Bundle, out: File, header: ujson.Obj, window: Option[(Long,Long)],
                      restored: Option[ujson.Value], inputs: BootInputs) {
  private case class Memory(physical: Long, read: BigInt, write: BigInt, rmask: Int, wmask: Int, error: Boolean, io: Boolean)
  private val memory = mutable.LongMap.empty[Memory]
  restored.foreach(_.arr.foreach { row => memory(row(0).str.toLong) = Memory(row(1).str.toLong,
    BigInt(row(2).str), BigInt(row(3).str), row(4).num.toInt, row(5).num.toInt, row(6).bool, row(7).bool) })
  private val fields = port.elements.toMap
  private def bit(name: String) = fields(name).asInstanceOf[Bool].toBoolean
  private def number(name: String) = fields(name).asInstanceOf[BitVector].toBigInt
  private val probe = new RvfiProbe(Seq(port))
  private val writer = window.map { case (from,to) =>
    header("window") = ujson.Obj("from_cycle" -> from.toString, "to_cycle" -> to.toString,
      "scope" -> "bounded retirement window; no reset prefix")
    new RvfiTraceWriter(new File(out,"rvfi.jsonl"),header)
  }
  private val events = mutable.ArrayBuffer.empty[(Long, () => Unit)]
  private var records = 0L
  private var lastLevels = Option.empty[BigInt]
  private var inputLevels = Option.empty[BigInt]
  private var closed = false
  private def active(cycle: Long) = window.exists { case (from,to) => cycle >= from && cycle < to }
  def observe(id: Long, physical: Long, read: BigInt, write: BigInt, rmask: Int, wmask: Int, error: Boolean, io: Boolean): Unit =
    memory(id) = Memory(physical,read,write,rmask,wmask,error,io)
  def state: ujson.Value = ujson.Arr.from(memory.toSeq.sortBy(_._1).map { case (id,m) =>
    ujson.Arr(id.toString,m.physical.toString,m.read.toString,m.write.toString,m.rmask,m.wmask,m.error,m.io) })
  private def external(at: Long, event: ujson.Value): Unit = if (!closed && active(at)) {
    val fields = ujson.Obj.from(event.obj.toSeq.filterNot { case (k,_) => Set("event","cycle","seq","before_order","kind")(k) })
    events += at -> (() => writer.foreach(_.externalInterrupt(at,event("kind").str,fields)))
  }
  private def flush(watermark: Long): Unit = {
    val ready = events.filter(_._1 <= watermark).sortBy(_._1).toVector
    events.filterInPlace(_._1 > watermark)
    ready.foreach(_._2())
  }
  /** Call before the sampled edge, after combinational settling. */
  def sample(cycle: Long, levels: BigInt, trap: Option[(BigInt,BigInt,BigInt)]): Unit = {
    if (trap.nonEmpty) require(!bit("overlap"), "reference history has an unordered commit/trap boundary")
    if (!closed && active(cycle)) require(!bit("overlap"), "C2 observer has an unordered commit/trap boundary")
    if (bit("valid")) {
      val id = number("uop_id").toLong
      val effect = memory.remove(id)
      val at = number("record_cycle").toLong
      if ((!closed && active(at)) || (inputs.enabled && (effect.exists(_.io) || bit("counter_input")))) {
        require(!bit("overlap"), "C2 observer has an unordered commit/trap boundary")
        var record = probe.sample(at).head
        require(bit("raw_known"), "C2 raw instruction tag is not observed")
        require(record.rd == 0 || bit("result_known"), "C2 destination write is not observed")
        if (bit("needs_memory")) {
          val m = effect.getOrElse(throw new IllegalStateException("C2 memory effect is not observed"))
          require(!m.error, "C2 normal retirement has a failed memory access")
          record = record.copy(memAddr = if ((m.rmask | m.wmask) == 0) BigInt(0) else record.memAddr,
            memRmask=m.rmask,memWmask=m.wmask,memRdata=m.read,memWdata=m.write,
            extra=Seq("mem_physical_address" -> ujson.Str(Hex(BigInt(m.physical)))))
        }
        effect.filter(_.io).foreach(m => external(at, inputs.mmio(at,record.order,record.pc,record.insn,
          m.physical,record.memAddr,m.read,m.write,m.rmask,m.wmask)))
        if (bit("counter_input")) inputs.counter(at,record.order,record.pc,record.insn,record.rd,record.rdWdata)
        if (!closed && active(at)) {
          val r = record.copy(order=BigInt(records), extra=record.extra :+ ("absolute_order" -> ujson.Str(record.order.toString)))
          events += at -> (() => writer.foreach(_.write(r)))
          records += 1
          flush(at)
        }
      }
    }
    if (!inputLevels.contains(levels) || trap.nonEmpty) {
      val order = number("retired_count")
      inputs.pins(cycle,order,levels).foreach(external(cycle,_))
      trap.foreach { case (epc,cause,tval) => inputs.trap(cycle,order,epc,cause,tval).foreach(external(cycle,_)) }
      inputLevels = Some(levels)
    }
    if (!closed && active(cycle)) {
      if (!lastLevels.contains(levels)) events += cycle -> (() => writer.foreach(_.irq(cycle,levels)))
      lastLevels = Some(levels)
      trap.foreach { case (_,cause,tval) =>
        events += cycle -> (() => writer.foreach(_.trap(cycle,cause,tval,cause.testBit(63))))
      }
    }
    if (trap.nonEmpty) memory.clear()
    if (!closed && window.exists(_._2 <= cycle)) finish(cycle)
  }
  def finish(cycle: Long): Unit = if (!closed) {
    flush(Long.MaxValue)
    window.foreach { case (_,to) => writer.foreach(_.end(math.min(cycle,to),"timeout")) }
    writer.foreach(_.close()); closed = true
  }
  def count: Long = records
}
