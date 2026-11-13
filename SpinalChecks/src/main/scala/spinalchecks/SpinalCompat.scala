package spinalchecks

import spinal.lib.bus.amba4.axi.Axi4Config

/** Calls that differ between the SpinalHDL versions the library is built against (see
  * `scripts/sbt/SpinalAxis.scala`). */
object SpinalCompat {
  /** `Axi4Config.withAxi3`; false in older SpinalHDL versions, which have no AXI3 mode. */
  def axi3(c: Axi4Config): Boolean =
    c.getClass.getMethods.find(m => m.getName == "withAxi3" && m.getParameterCount == 0).exists(_.invoke(c) == true)
}
