package spinalchecks

import spinal.core._

/** Optional project-owned selectors and overflow interrupt policy, separate from count checks. */
object HpmControlChecks {
  def selector(name: String, observed: Bits, writeAccepted: Bool, writeData: Bits,
               legalMask: BigInt, reset: BigInt = 0): Unit = {
    val w = observed.getWidth
    require(writeData.getWidth == w && legalMask >= 0 && legalMask.bitLength <= w)
    require(reset >= 0 && reset.bitLength <= w && (reset & ~legalMask) == 0)
    val expected = Reg(Bits(w bits)).init(reset)
    when(writeAccepted) { expected := writeData & B(legalMask, w bits) }
    DeclaredChecks.rule("hpm.selector", name, "accepted selector writes obey project WARL mask")(
      observed =/= expected)
  }

  /** eventCount and expectedCount must come from independent event observations.
    * Overflow is sticky. Clear wins over overflow. A counter write prevents overflow.
    * This explicit policy is project data, not a claim that all HPM extensions use it.
    */
  def interrupt(name: String, width: Int, expectedCount: UInt, eventCount: UInt,
                inhibit: Bool, permitted: Bool, counterWrite: Bool, clear: Bool,
                enabled: Bool, observedPending: Bool, observedIrq: Bool): Unit = {
    require(width > 0 && expectedCount.getWidth == width && eventCount.getWidth <= width)
    val sum = expectedCount.resize(width + 1) + eventCount.resize(width + 1)
    val pending = Reg(Bool()).init(False)
    when(!inhibit && permitted && !counterWrite && sum.msb) { pending := True }
    when(clear) { pending := False }
    DeclaredChecks.rule("hpm.overflow_pending", name, "independent modular overflow; sticky, clear priority")(
      observedPending =/= pending)
    DeclaredChecks.rule("hpm.counter_interrupt", name, "project overflow interrupt enable and pending")(
      observedIrq =/= (pending && enabled))
  }
}
