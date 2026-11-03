package spinalchecks

import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba4.axi._

/** AXI4 read ordering within each ID. A declared issuing limit bounds the monitor storage. */
private[spinalchecks] object AxiReadChecks {
  def apply(ar: Stream[Axi4Ar], r: Stream[Axi4R], emit: ProtocolChecks.Emit): Unit = {
    val c = ar.payload.config
    val limit = c.readIssuingCapability
    require(limit > 0 && limit <= 32, "AXI read checks need readIssuingCapability in 1..32")
    require(!c.useId || c.idWidth <= 4, "AXI read checks support at most 16 IDs")
    val ids = if (c.useId) 1 << c.idWidth else 1
    val depth = 1 << log2Up(scala.math.max(2, limit))
    val ptrWidth = log2Up(depth)
    val ai = if (c.useId) ar.id else U(0, 0 bits)
    val ri = if (c.useId) r.id else U(0, 0 bits)
    val heads = Vec.fill(ids)(Reg(UInt(ptrWidth bits)).init(0))
    val tails = Vec.fill(ids)(Reg(UInt(ptrWidth bits)).init(0))
    val counts = Vec.fill(ids)(Reg(UInt(log2Up(limit + 1) bits)).init(0))
    val beats = Vec.fill(ids)(Reg(UInt(9 bits)).init(0))
    val lens = Vec.fill(ids * depth)(Reg(UInt(8 bits)).init(0))
    val locks = Vec.fill(ids * depth)(RegInit(False))
    val push = ar.fire
    val aIndex = (ai.resize(log2Up(ids * depth)) |<< ptrWidth) | tails(ai).resized
    val rIndex = (ri.resize(log2Up(ids * depth)) |<< ptrWidth) | heads(ri).resized
    val fresh = counts(ri) === 0 && ar.valid && ai === ri
    val aLen = if (c.useLen) ar.len else U(0, 8 bits)
    val aLock = if (c.useLock) ar.lock === 1 else False
    val len = fresh.mux(aLen, lens(rIndex))
    val lock = fresh.mux(aLock, locks(rIndex))
    val last = if (c.useLast) r.last else beats(ri) === len.resize(9)
    val pop = r.fire && last
    val present = counts(ri) =/= 0 || fresh
    emit("axi4.read_match", "_r", r.valid.isInput,
      "read ID, ordered per-ID burst length and exclusive response",
      r.valid && (!present || last =/= (beats(ri) === len.resize(9)) ||
        (if (c.useResp) r.resp === 1 && !lock else False) ||
        (fresh && r.ready && !ar.ready)))
    val total = Reg(UInt(log2Up(limit + 1) bits)).init(0)
    emit("axi4.read_capacity", "_ar", ar.valid.isInput, s"declared read issuing limit $limit",
      push && !pop && total === limit)
    when(push =/= pop) { when(push) { total := total + 1 } otherwise { total := total - 1 } }
    when(push) {
      lens(aIndex) := aLen; locks(aIndex) := aLock; tails(ai) := tails(ai) + 1
    }
    when(pop) { heads(ri) := heads(ri) + 1 }
    for (i <- 0 until ids) {
      val inc = push && ai === i
      val dec = pop && ri === i
      when(inc =/= dec) { when(inc) { counts(i) := counts(i) + 1 } otherwise { counts(i) := counts(i) - 1 } }
      when(r.fire && ri === i) { beats(i) := beats(i) + 1; when(last) { beats(i) := 0 } }
    }
  }
}
