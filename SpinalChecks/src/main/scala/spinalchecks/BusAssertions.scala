package spinalchecks

import spinal.core._
import spinal.lib.bus.amba4.axi._
import spinal.lib.bus.tilelink

/** Explicit native binds for composers that already own the bus instances.
  * Reuse the same transaction checks as the extraction phase. Missing AXI
  * issuing limits are returned as gaps instead of silently inventing limits.
  */
object BusAssertions {
  private val emit: ProtocolChecks.Emit = (kind, _, _, detail, fail) => {
    val cd = ClockDomain.current
    val active = if(cd.hasResetSignal || cd.hasSoftResetSignal) !cd.isResetActive else True
    when(active) { assert(!fail, kind + ": " + detail) }
  }
  def apply(bus: Axi4): Seq[String] = {
    val withAxi3 = SpinalCompat.axi3(bus.config)
    val gaps = scala.collection.mutable.ArrayBuffer.empty[String]
    if(!withAxi3) ProtocolChecks.axiAddress(bus.aw.payload, fail => when(bus.aw.valid) { emit("axi4.address_legal", "aw", false, "address options and burst bounds", fail) })
    if(!withAxi3) ProtocolChecks.axiAddress(bus.ar.payload, fail => when(bus.ar.valid) { emit("axi4.address_legal", "ar", false, "address options and burst bounds", fail) })
    val idsSupported = !bus.config.useId || bus.config.idWidth <= 4
    if(withAxi3) gaps += "AXI3 transaction checks are unsupported"
    if(!withAxi3 && idsSupported && bus.config.readIssuingCapability > 0 && bus.config.readIssuingCapability <= 32) AxiReadChecks(bus.ar, bus.r, emit)
    else gaps += "read tracking needs issuing capability in 1..32 and at most 16 IDs"
    if(!withAxi3 && idsSupported && bus.config.writeIssuingCapability > 0 && bus.config.writeIssuingCapability <= 32 && (bus.config.useLast || !bus.config.useLen)) AxiWriteChecks(bus.aw, bus.w, bus.b, emit)
    else gaps += "write tracking needs issuing capability in 1..32, at most 16 IDs and WLAST for bursts"
    gaps.toSeq
  }
  def apply(bus: tilelink.Bus): Seq[String] = {
    if(bus.p.sourceWidth > 8 || (bus.p.withBCE && bus.p.sinkWidth > 8))
      Seq("TileLink tracking supports at most 256 source and sink IDs")
    else { ProtocolChecks.tileLink(bus, emit); Seq.empty }
  }
}
