package rvwsmp
import spinal.core._
import spinal.lib.bus.tilelink

/** Project-selected line projection. It observes handshakes and never drives DUT ready. */
object CachedLineTap {
  def apply(bus: tilelink.Bus): tilelink.Bus = {
    val tap = tilelink.Bus(bus.p.copy(sourceWidth=bus.p.sourceWidth max 1,sinkWidth=bus.p.sinkWidth max 1))
    tap.a.valid := bus.a.valid; tap.a.ready := bus.a.ready
    tap.b.valid := bus.b.valid; tap.b.ready := bus.b.ready
    tap.c.valid := bus.c.valid; tap.c.ready := bus.c.ready
    tap.d.valid := bus.d.valid; tap.d.ready := bus.d.ready
    tap.e.valid := bus.e.valid; tap.e.ready := bus.e.ready
    def copyPayload(to: Bundle, from: Bundle): Unit = {
      val fields = from.elements.toMap
      to.elements.filterNot(p => Set("source","sink")(p._1)).foreach { case (name,field) =>
        field.assignFromBits(fields(name).asBits)
      }
    }
    copyPayload(tap.a.payload,bus.a.payload); copyPayload(tap.b.payload,bus.b.payload)
    copyPayload(tap.c.payload,bus.c.payload); copyPayload(tap.d.payload,bus.d.payload)
    tap.a.source := bus.a.source.resized
    tap.b.source := bus.b.source.resized
    tap.c.source := bus.c.source.resized
    tap.d.source := bus.d.source.resized
    tap.d.sink := bus.d.sink.resized
    tap.e.sink := bus.e.sink.resized
    val reads = Vec.fill(1 << bus.a.source.getWidth)(RegInit(False))
    val releases = Vec.fill(1 << bus.c.source.getWidth)(RegInit(False))
    val sinks = Vec.fill(1 << bus.d.sink.getWidth)(RegInit(False))
    def selected(address: UInt) = address(31 downto 6) === U(0x80080000L >> 6,26 bits)
    when(bus.a.fire) { reads(bus.a.source) := selected(bus.a.address) }
    when(bus.c.fire && (bus.c.opcode === tilelink.Opcode.C.RELEASE || bus.c.opcode === tilelink.Opcode.C.RELEASE_DATA)) {
      releases(bus.c.source) := selected(bus.c.address)
    }
    val replySelected = (bus.d.opcode === tilelink.Opcode.D.RELEASE_ACK).mux(releases(bus.d.source),reads(bus.d.source))
    when(bus.d.fire && (bus.d.opcode === tilelink.Opcode.D.GRANT || bus.d.opcode === tilelink.Opcode.D.GRANT_DATA)) {
      sinks(bus.d.sink) := replySelected
    }
    tap.a.valid.allowOverride(); tap.b.valid.allowOverride(); tap.c.valid.allowOverride()
    tap.d.valid.allowOverride(); tap.e.valid.allowOverride()
    tap.a.valid := bus.a.valid && selected(bus.a.address)
    tap.b.valid := bus.b.valid && selected(bus.b.address)
    tap.c.valid := bus.c.valid && selected(bus.c.address)
    tap.d.valid := bus.d.valid && replySelected
    tap.e.valid := bus.e.valid && sinks(bus.e.sink)
    tap
  }
}
