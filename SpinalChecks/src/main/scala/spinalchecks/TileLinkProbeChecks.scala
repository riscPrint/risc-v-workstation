package spinalchecks

import spinal.core._
import spinal.lib._
import spinal.lib.bus.tilelink._

/** Probe keys are (source, address), rather than source alone. */
private[spinalchecks] object TileLinkProbeChecks {
  def apply(bus: Bus, firstC: Bool, emit: ProtocolChecks.Emit, slots: Int = 16): Unit = {
    require(bus.p.withBCE && slots > 0)
    val b = bus.b
    val c = bus.c
    val live = Vec.fill(slots)(RegInit(False))
    val source = Vec.fill(slots)(Reg(UInt(bus.p.sourceWidth bits)).init(0))
    val address = Vec.fill(slots)(Reg(UInt(bus.p.addressWidth bits)).init(0))
    val size = Vec.fill(slots)(Reg(UInt(bus.p.sizeWidth bits)).init(0))
    val cap = Vec.fill(slots)(Reg(Bits(3 bits)).init(0))
    val permissionOnly = Vec.fill(slots)(RegInit(False))
    val probeAck = Opcode.C.isProbe(c.opcode)
    val cMatch = Vec((0 until slots).map(i => live(i) && source(i) === c.source && address(i) === c.address))
    val bMatch = Vec((0 until slots).map(i => live(i) && source(i) === b.source && address(i) === b.address))
    val found = cMatch.asBits.orR
    val ci = OHToUInt(cMatch.asBits)
    val same = b.source === c.source && b.address === c.address
    val fresh = b.valid && same
    val retire = c.fire && firstC && probeAck && found
    val free = Vec((0 until slots).map(i => !live(i) || (retire && cMatch(i))))
    val freeOH = OHMasking.first(free.asBits)
    val fi = OHToUInt(freeOH)
    val zero = c.fire && firstC && probeAck && !found && fresh
    val expectedSize = found.mux(size(ci), b.size)
    val expectedCap = found.mux(cap(ci), b.param).asUInt
    val expectedPerm = found.mux(permissionOnly(ci), b.opcode === Opcode.B.PROBE_PERM)
    val resultCap = UInt(2 bits)
    resultCap := 2
    switch(c.param) {
      is(B(0, 3 bits), B(4, 3 bits)) { resultCap := 1 }
      is(B(3, 3 bits)) { resultCap := 0 }
    }
    emit("tilelink.probe_match", "_c", c.valid.isInput,
      "ProbeAck matches Probe source, address, size and permission cap",
      c.valid && firstC && probeAck && (!(found || fresh) || c.size =/= expectedSize ||
        resultCap.resize(3) < expectedCap || (expectedPerm && Opcode.C.withData(c.opcode)) ||
        (!found && fresh && c.ready && !b.ready)))
    val duplicate = (0 until slots).map(i => bMatch(i) && !(retire && cMatch(i))).reduce(_ || _)
    emit("tilelink.probe_busy", "_b", b.valid.isInput,
      "Probe source/address pair cannot be reused before first accepted ProbeAck",
      b.fire && duplicate)
    emit("tilelink.probe_capacity", "_b", b.valid.isInput,
      s"Probe tracker capacity is $slots pending source/address pairs; instrumentation limit",
      b.fire && !zero && !free.asBits.orR)
    val bMask = ((U(1, bus.p.addressWidth + 1 bits) |<< b.size) - 1).resize(bus.p.addressWidth)
    emit("tilelink.probe_legal", "_b", b.valid.isInput,
      "Probe cap, size and address alignment",
      b.valid && (b.param.asUInt > 2 || b.size > bus.p.sizeMax || b.size < log2Up(bus.p.dataBytes) || (b.address & bMask) =/= 0))
    emit("tilelink.c_legal", "_c", c.valid.isInput,
      "C permission parameter, size, address alignment and no-data corruption",
      c.valid && ((probeAck && c.param.asUInt > 5) || (Opcode.C.isRelease(c.opcode) && c.param.asUInt > 2) ||
        c.size > bus.p.sizeMax || c.size < log2Up(bus.p.dataBytes) || (c.address & (((U(1, bus.p.addressWidth + 1 bits) |<< c.size) - 1).resize(bus.p.addressWidth))) =/= 0 ||
        (Opcode.C.withoutData(c.opcode) && c.corrupt)))
    when(retire) { live(ci) := False }
    when(b.fire && !zero && free.asBits.orR) {
      live(fi) := True
      source(fi) := b.source
      address(fi) := b.address
      size(fi) := b.size
      cap(fi) := b.param
      permissionOnly(fi) := b.opcode === Opcode.B.PROBE_PERM
    }
  }
}
