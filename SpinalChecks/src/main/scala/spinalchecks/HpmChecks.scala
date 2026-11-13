package spinalchecks

import spinal.core._

case class HpmModel(version: Int, width: Int, reset: BigInt, eventMeaning: String) {
  require(version == 1 && width > 0 && reset >= 0 && reset.bitLength <= width && eventMeaning.trim.nonEmpty)
}
object HpmChecks {
  /** eventCount comes from an independent event observation. Inhibit/filter suppress increments.
    * A software write wins over an increment. Wraparound is modular at the declared width.
    */
  def bind(name: String, model: HpmModel, observed: UInt, eventCount: UInt, inhibit: Bool,
           permitted: Bool, write: Bool, data: UInt, writeMask: UInt = null): Unit = {
    track(name, model, observed, eventCount, inhibit, permitted, write, data, writeMask)
    ()
  }
  /** Return independent expected state for a separate read-response binding. */
  def track(name: String, model: HpmModel, observed: UInt, eventCount: UInt, inhibit: Bool,
            permitted: Bool, write: Bool, data: UInt, writeMask: UInt = null): UInt = {
    require(observed.getWidth == model.width && data.getWidth == model.width)
    val expected = Reg(UInt(model.width bits)).init(model.reset)
    val mask = if (writeMask == null) U((BigInt(1) << model.width) - 1, model.width bits) else writeMask
    require(mask.getWidth == model.width)
    val incremented = UInt(model.width bits)
    incremented := expected
    when(!inhibit && permitted) { incremented := (expected + eventCount.resized).resized }
    expected := Mux(write, (incremented & ~mask) | (data & mask), incremented)
    DeclaredChecks.rule("hpm.count", name, "v1 independent events: " + model.eventMeaning, trigger = True)(observed =/= expected)
    expected
  }
  /** Requests include denied attempts. Counter-enable bits are independent project observations.
    * Machine access bypasses counter enables; supervisor access needs mcounteren;
    * user access needs both mcounteren and scounteren when S mode exists.
    */
  def bindAccess(name: String, read: Bool, write: Bool, privilege: UInt,
                 machineEnable: Bool, supervisorEnable: Bool, hasSupervisor: Boolean,
                 machineAlias: Bool, denied: Bool): Bool = {
    val userAllowed = machineEnable && (if (hasSupervisor) supervisorEnable else True)
    val allowed = (!write || machineAlias) && (privilege === 3 || (!machineAlias &&
      ((privilege === 1 && machineEnable) || (privilege === 0 && userAllowed))))
    DeclaredChecks.rule("hpm.access", name, "Zihpm privilege, read-only alias and counter enables", trigger = read || write)(
      (read || write) && (denied === allowed))
    allowed
  }

  /** Check an RV32 read response against a full independent expected counter. */
  def bindHalfRead(name: String, expected: UInt, high: Bool, response: Bits, valid: Bool): Unit = {
    require(expected.getWidth == 64 && response.getWidth == 32)
    DeclaredChecks.rule("hpm.read", name, "RV32 selected counter half", trigger = valid)(
      valid && response =/= Mux(high, expected(63 downto 32).asBits, expected(31 downto 0).asBits))
  }

}
