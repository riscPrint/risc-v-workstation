package spinalchecks

import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba4.axi._

/** Independent AW/W queues, followed by an ordered response queue for each ID. */
private[spinalchecks] object AxiWriteChecks {
  private class Queue(width: Int, depth: Int) extends Area {
    val push, pop = Bool()
    val input = Bits(width bits)
    val count = Reg(UInt(log2Up(depth + 1) bits)).init(0)
    val head, tail = Reg(UInt(log2Up(depth) bits)).init(0)
    val storage = Vec.fill(depth)(Reg(Bits(width bits)).init(0))
    val valid = count =/= 0 || push
    val output = (count === 0).mux(input, storage(head))
    val overflow = push && !pop && count === depth
    when(push) { storage(tail) := input; tail := tail + 1 }
    when(pop) { head := head + 1 }
    when(push =/= pop) { when(push) { count := count + 1 } otherwise { count := count - 1 } }
  }
  def apply(aw: Stream[Axi4Aw], w: Stream[Axi4W], b: Stream[Axi4B], emit: ProtocolChecks.Emit): Unit = {
    val c = aw.payload.config
    val limit = c.writeIssuingCapability
    require(limit > 0 && limit <= 32, "AXI write checks need writeIssuingCapability in 1..32")
    require(!c.useId || c.idWidth <= 4, "AXI write checks support at most 16 IDs")
    require(c.useLast || !c.useLen, "AXI write bursts need WLAST")
    val ids = if (c.useId) 1 << c.idWidth else 1
    val idWidth = scala.math.max(1, if (c.useId) c.idWidth else 1)
    val depth = 1 << log2Up(scala.math.max(2, limit))
    val ai = if (c.useId) aw.id.resize(idWidth) else U(0, idWidth bits)
    val bi = if (c.useId) b.id.resize(idWidth) else U(0, idWidth bits)
    val len = if (c.useLen) aw.len else U(0, 8 bits)
    val lock = if (c.useLock) aw.lock === 1 else False
    val addresses = new Queue(idWidth + 9, depth)
    addresses.push := aw.fire
    addresses.input := ai.asBits ## len.asBits ## lock.asBits
    val beatCount = Reg(UInt(9 bits)).init(0)
    val last = if (c.useLast) w.last else True
    when(w.fire) { beatCount := beatCount + 1; when(last) { beatCount := 0 } }
    val writes = new Queue(9, depth)
    writes.push := w.fire && last
    writes.input := beatCount.asBits
    val pair = addresses.valid && writes.valid
    addresses.pop := pair; writes.pop := pair
    val pairedId = addresses.output.takeHigh(idWidth).asUInt
    val pairedLen = addresses.output(8 downto 1).asUInt
    val pairedLock = addresses.output(0)
    val pending = (0 until ids).map { i =>
      val q = new Queue(1, depth)
      q.push := pair && pairedId === i
      q.input := pairedLock.asBits
      q.pop := b.fire && bi === i
      q
    }
    val known = Vec(pending.map(_.count =/= 0))(bi.resize(log2Up(ids)))
    val exclusive = Vec(pending.map(_.output(0)))(bi.resize(log2Up(ids)))
    emit("axi4.write_match", "_b", b.valid.isInput,
      "B ID follows AW and complete W burst; EXOKAY needs an exclusive request",
      b.valid && (!known || (if (c.useResp) b.resp === 1 && !exclusive else False)))
    emit("axi4.write_beats", "_w", w.valid.isInput, "W burst matches AWLEN in address order",
      (pair && writes.output.asUInt =/= pairedLen.resize(9)) || (w.valid && beatCount > 255))
    emit("axi4.write_capacity", "_aw", aw.valid.isInput,
      s"declared write monitor queue bound $depth",
      addresses.overflow || writes.overflow || pending.map(_.overflow).reduce(_ || _))
  }
}
