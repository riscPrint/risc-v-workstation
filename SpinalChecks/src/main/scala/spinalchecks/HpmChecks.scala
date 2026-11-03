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
           permitted: Bool, write: Bool, data: UInt): Unit = {
    require(observed.getWidth == model.width && data.getWidth == model.width)
    val expected = Reg(UInt(model.width bits)).init(model.reset)
    when(!inhibit && permitted) { expected := (expected + eventCount.resized).resized }
    when(write) { expected := data }
    DeclaredChecks.rule("hpm.count", name, "v1 independent events: " + model.eventMeaning)(observed =/= expected)
  }
}
