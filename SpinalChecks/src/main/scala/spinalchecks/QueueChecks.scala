package spinalchecks

import spinal.core._

/** One accepted push and pop per cycle. Flush discards all entries and dominates transfers. */
object QueueChecks {
  def fifo(name: String, depth: Int, push: Bool, pop: Bool, flush: Bool,
           pushed: Bits, popped: Bits, occupancy: UInt): Unit = {
    require(depth > 0 && pushed.getWidth == popped.getWidth)
    require(occupancy.getWidth >= log2Up(depth + 1))
    val count = Reg(UInt(log2Up(depth + 1) bits)).init(0)
    val head = Reg(UInt(Math.max(1, log2Up(depth)) bits)).init(0)
    val tail = Reg(UInt(Math.max(1, log2Up(depth)) bits)).init(0)
    val entries = Vec.fill(depth)(Reg(Bits(pushed.getWidth bits)))
    def advance(p: UInt): UInt = Mux(p === depth - 1, U(0, p.getWidth bits), p + 1)
    // No empty bypass. A full FIFO can replace its oldest entry in the same cycle.
    val underflow = pop && count === 0
    val overflow = push && !pop && count === depth
    DeclaredChecks.rule("queue.capacity", name, "accepted transfers; no empty bypass; flush dominates")(
      !flush && (underflow || overflow))
    DeclaredChecks.rule("queue.occupancy", name, "independent accepted push/pop count before this edge")(
      !flush && occupancy =/= count)
    DeclaredChecks.rule("queue.order", name, "independent FIFO data or unique token order; no loss or duplication")(
      !flush && pop && count =/= 0 && popped =/= entries(head))
    when(flush) { count := 0; head := 0; tail := 0 }
      .elsewhen(!underflow && !overflow) {
        when(push) { entries(tail) := pushed; tail := advance(tail) }
        when(pop) { head := advance(head) }
        when(push && !pop) { count := count + 1 }
        when(pop && !push) { count := count - 1 }
      }
  }

  /** Safety only. No fairness or eventual grant is inferred. */
  def arbiter(name: String, requests: Bits, grants: Bits): Unit = {
    require(requests.getWidth > 0 && requests.getWidth == grants.getWidth)
    val g = grants.asUInt
    DeclaredChecks.rule("arbiter.exclusive", name, "at most one grant per cycle")(
      (g & (g - 1)) =/= 0)
    DeclaredChecks.rule("arbiter.requested", name, "every grant needs its corresponding request")(
      (grants & ~requests) =/= 0)
  }
}
