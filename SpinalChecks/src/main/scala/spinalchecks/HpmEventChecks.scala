package spinalchecks

import spinal.core._

/** Project-declared additive event bits with Sscofpmf mode inhibit positions.
  * Events are independent counts, not DUT selector outputs. A control write
  * affects counting after the edge. Machine mode is never virtualized.
  */
object HpmEventChecks {
  def bind(name: String, observedControl: Bits, controlWrite: Bool, controlData: Bits,
           events: Seq[UInt], privilege: UInt, virtualized: Bool,
           observedCount: UInt, countWrite: Bool, countData: UInt, inhibit: Bool): Unit = {
    require(events.nonEmpty && events.size <= 56)
    require(observedControl.getWidth == 64 && controlData.getWidth == 64)
    require(privilege.getWidth == 2 && events.forall(_.getWidth <= observedCount.getWidth))
    val eventMask = (BigInt(1) << events.size) - 1
    val modeMask = (BigInt(31) << 58)
    val expectedControl = Reg(Bits(64 bits)).init(0)
    when(controlWrite) { expectedControl := controlData & B(eventMask | modeMask,64 bits) }
    DeclaredChecks.rule("hpm.event_control", name, "project additive event bits and Sscofpmf MINH/SINH/UINH/VSINH/VUINH")(
      (observedControl & B(eventMask | modeMask,64 bits)) =/= expectedControl)
    val permitted = Bool()
    permitted := False
    switch(privilege) {
      is(U(3)) { permitted := !virtualized && !expectedControl(62) }
      is(U(1)) { permitted := !Mux(virtualized, expectedControl(59), expectedControl(61)) }
      is(U(0)) { permitted := !Mux(virtualized, expectedControl(58), expectedControl(60)) }
    }
    val count = events.zipWithIndex.map { case (event, bit) =>
      Mux(expectedControl(bit), event.resize(observedCount.getWidth), U(0,observedCount.getWidth bits))
    }.reduce((a,b) => (a+b).resized)
    HpmChecks.bind(name, HpmModel(1,observedCount.getWidth,0,"declared additive selected events with lower-mode filters"),
      observedCount,count,inhibit,permitted,countWrite,countData)
  }
}
