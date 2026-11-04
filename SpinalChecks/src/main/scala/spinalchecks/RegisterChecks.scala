package spinalchecks

import spinal.core._

/** Device register model. Masks are disjoint. Hardware set has final priority. */
case class RegisterModel(version: Int, width: Int, reset: BigInt,
                         writeMask: BigInt, w1cMask: BigInt, readClearMask: BigInt) {
  require(version == 1 && width > 0)
  require(Seq(reset, writeMask, w1cMask, readClearMask).forall(x => x >= 0 && x.bitLength <= width))
  require((writeMask & w1cMask) == 0)
}
object RegisterChecks {
  /** Bind accepted bus transactions, byte enables expanded to bit enables, and independent hardware events.
    * Order: read clear, masked write/W1C, hardware clear, hardware set.
    */
  def bind(name: String, m: RegisterModel, observed: Bits, read: Bool, write: Bool,
           data: Bits, strobes: Bits, hwSet: Bits, hwClear: Bits,
           response: Bits = null, responseValid: Bool = null, latency: Int = 0): Unit = {
    require(latency >= 0)
    require((response == null) == (responseValid == null))
    val w = m.width
    require(Seq(observed, data, strobes, hwSet, hwClear).forall(_.getWidth == w))
    val expected = Reg(Bits(w bits)).init(m.reset)
    val afterRead = expected & ~(Mux(read, B(m.readClearMask, w bits), B(0, w bits)))
    val mask = B(m.writeMask, w bits) & strobes
    val written = ((afterRead & ~mask) | (data & mask)) & ~(data & strobes & B(m.w1cMask, w bits))
    expected := (Mux(write, written, afterRead) & ~hwClear) | hwSet
    if (response != null) {
      require(response.getWidth == w)
      var due = read
      var value = expected
      for (_ <- 0 until latency) {
        due = RegNext(due).init(False)
        value = RegNext(value).init(0)
      }
      DeclaredChecks.rule("register.response", name, "accepted read, pre-side-effect data and fixed response latency")(
        (responseValid =/= due) || (due && response =/= value))
    }
    DeclaredChecks.rule("register.state", name, "v1 independent device transactions; read-clear, masks, W1C, set priority")(
      observed =/= expected)
  }
}
