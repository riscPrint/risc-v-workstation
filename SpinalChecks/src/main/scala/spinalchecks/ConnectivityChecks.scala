package spinalchecks

import spinal.core._

object ConnectivityChecks {
  /** Value transfer at fixed latency. Each enabled source sample must reach the destination.
    * Sampling and pipeline history use the caller's domain. This is a temporal assertion,
    * not a structural path proof or a proof that a forbidden influence is absent.
    */
  def bind(name: String, source: Bits, destination: Bits, enable: Bool, latency: Int): Unit = {
    require(latency >= 0 && source.getWidth == destination.getWidth)
    var expected = source
    var valid = enable
    for (_ <- 0 until latency) {
      expected = RegNext(expected)
      valid = RegNext(valid).init(False)
    }
    DeclaredChecks.rule("connectivity.value", name, s"declared value transfer, latency=$latency")(
      valid && destination =/= expected)
  }
}
