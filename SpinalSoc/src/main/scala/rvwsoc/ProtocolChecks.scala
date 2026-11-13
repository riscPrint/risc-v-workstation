package rvwsoc

import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba4.axi._
import spinal.lib.bus.amba4.axilite._
import spinal.lib.bus.tilelink

/** Native sampled channel-safety binds. Transaction scoreboards are separate. */
object ProtocolChecks {
  private def stable(valid: Bool, ready: Bool, payload: Bits): Unit = {
    val stalled = RegNext(valid && !ready) init(False)
    val previous = RegNext(payload)
    when(stalled) {
      assert(valid, "SoC channel must retain valid under backpressure")
      assert(payload === previous, "SoC channel payload must remain stable under backpressure")
    }
  }
  private def stream[T <: Data](bus: Stream[T]): Unit = stable(bus.valid, bus.ready, bus.payload.asBits)
  def apply(bus: Axi4): Unit = {
    stream(bus.aw); stream(bus.w); stream(bus.b); stream(bus.ar); stream(bus.r)
    spinalchecks.BusAssertions(bus).foreach(gap => SpinalWarning("SoC AXI protocol gap: " + gap))
  }
  def apply(bus: AxiLite4): Unit = {
    stream(bus.aw); stream(bus.w); stream(bus.b); stream(bus.ar); stream(bus.r)
  }
  def apply(bus: tilelink.Bus): Unit = {
    stream(bus.a); stream(bus.d)
    if(bus.p.withBCE) { stream(bus.b); stream(bus.c); stream(bus.e) }
    spinalchecks.BusAssertions(bus).foreach(gap => SpinalWarning("SoC TileLink protocol gap: " + gap))
  }
  def apply(bus: SimpleCpuBus): Unit = {
    stable(bus.valid, bus.ready, bus.address.asBits ## bus.write.asBits ## bus.wdata ## bus.mask)
  }
}
