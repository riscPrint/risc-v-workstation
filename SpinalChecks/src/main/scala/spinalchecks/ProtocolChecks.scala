package spinalchecks

import spinal.core._
import spinal.lib._
import spinal.lib.bus.tilelink._
import spinal.lib.bus.amba4.axi._

/** Bus rules reserve a source on acceptance, never on valid alone. */
private[spinalchecks] object ProtocolChecks {
  type Emit = (String, String, Boolean, String, Bool) => Unit
  def tileLink(bus: Bus, emit: Emit): Unit = {
    val p = bus.p
    val a = bus.a
    val d = bus.d
    require(p.sourceWidth <= 8, "TileLink bookkeeping supports at most 256 source IDs")
    def last(s: Stream[_ <: BusFragment]): Bool = {
      val b = s.payload
      val beat = Reg(UInt(scala.math.max(1, p.beatWidth) bits)).init(0)
      val end = !b.withBeats || beat === b.sizeToBeatMinusOne().resized
      when(s.fire) { beat := beat + 1; when(end) { beat := 0 } }
      end
    }
    val aLast = last(a)
    val dLast = last(d)
    val dBeat = RegInit(False)
    when(d.fire) { dBeat := !dLast }
    val dFirst = !dBeat
    val aBeat = RegInit(False)
    when(a.fire) { aBeat := !aLast }
    val aFirst = !aBeat
    val n = 1 << p.sourceWidth
    val busy = Vec.fill(n)(RegInit(False))
    val size = Vec.fill(n)(Reg(UInt(p.sizeWidth bits)).init(0))
    val data = Vec.fill(n)(RegInit(False))
    val acquire = Vec.fill(n)(RegInit(False))
    val responding = Opcode.D.fromA(d.opcode)
    val same = a.source === d.source
    val fresh = a.valid && aFirst && same
    val expectedData = fresh.mux((a.opcode === Opcode.A.GET || a.opcode === Opcode.A.ACQUIRE_BLOCK), data(d.source))
    val expectedAcquire = fresh.mux(Opcode.A.isAcquire(a.opcode), acquire(d.source))
    val expectedSize = fresh.mux(a.size, size(d.source))
    val grant = d.opcode === Opcode.D.GRANT || d.opcode === Opcode.D.GRANT_DATA
    val badResponse = d.valid && dFirst && responding && (
      !(busy(d.source) || fresh) ||
      d.size =/= expectedSize ||
      (!expectedAcquire && Opcode.D.isData(d.opcode) =/= expectedData) ||
      (expectedAcquire && !expectedData && Opcode.D.isData(d.opcode)) || grant =/= expectedAcquire ||
      (fresh && d.ready && !a.ready))
    emit("tilelink.response_match", "_d", d.valid.isInput,
      "A/D source, opcode and size; same-cycle responses allowed", badResponse)
    emit("tilelink.source_busy", "_a", a.valid.isInput, "source cannot be reused before first accepted D beat",
      a.fire && aFirst && busy(a.source))
    when(a.fire && aFirst) {
      busy(a.source) := True
      size(a.source) := a.size
      data(a.source) := (a.opcode === Opcode.A.GET || a.opcode === Opcode.A.ACQUIRE_BLOCK)
      acquire(a.source) := Opcode.A.isAcquire(a.opcode)
    }
    when(d.fire && dFirst && responding) { busy(d.source) := False }
    if (p.withBCE) {
      val c = bus.c
      val cLast = last(c)
      val cBeat = RegInit(False)
      when(c.fire) { cBeat := !cLast }
      val release = Opcode.C.isRelease(c.opcode)
      val releaseAck = d.opcode === Opcode.D.RELEASE_ACK
      val releases = Vec.fill(n)(RegInit(False))
      val releaseSizes = Vec.fill(n)(Reg(UInt(p.sizeWidth bits)).init(0))
      val freshRelease = c.valid && !cBeat && release && c.source === d.source
      emit("tilelink.release_busy", "_c", c.valid.isInput, "Release source cannot be reused before ReleaseAck",
        c.fire && !cBeat && release && releases(c.source))
      emit("tilelink.release_match", "_d", d.valid.isInput, "ReleaseAck source and size match C Release",
        d.valid && dFirst && releaseAck && (!(releases(d.source) || freshRelease) ||
          d.size =/= freshRelease.mux(c.size, releaseSizes(d.source)) ||
          (freshRelease && d.ready && !c.ready)))
      when(c.fire && !cBeat && release) { releases(c.source) := True; releaseSizes(c.source) := c.size }
      when(d.fire && dFirst && releaseAck) { releases(d.source) := False }

      require(p.sinkWidth <= 8, "TileLink bookkeeping supports at most 256 sink IDs")
      val sinks = Vec.fill(1 << p.sinkWidth)(RegInit(False))
      val alloc = d.fire && dFirst && grant
      emit("tilelink.sink_busy", "_d", d.valid.isInput, "Grant sink must be free", alloc && sinks(d.sink))
      emit("tilelink.sink_match", "_e", bus.e.valid.isInput, "GrantAck matches an accepted Grant",
        bus.e.valid && !(sinks(bus.e.sink) || (alloc && bus.e.sink === d.sink)))
      when(alloc) { sinks(d.sink) := True }
      when(bus.e.fire) { sinks(bus.e.sink) := False }
    }
    val op = a.opcode
    val legalParam = (Opcode.A.isGetPut(op) && a.param === 0) ||
      (Bool(p.withBCE) && Opcode.A.isAcquire(op) && a.param.asUInt <= 2 &&
        (op =/= Opcode.A.ACQUIRE_PERM || a.param =/= 0))
    val alignMask = ((U(1, p.addressWidth + 1 bits) |<< a.size) - 1).resize(p.addressWidth)
    val badMask = if (p.withDataA) {
      val masks = (0 to p.sizeMax).map(sz => B((BigInt(1) << scala.math.min(1 << sz, p.dataBytes)) - 1, p.dataBytes bits))
      val base = masks.read(a.size.resize(log2Up(p.sizeMax + 1)))
      val access = if (p.dataBytes == 1) base else (base |<< a.address(log2Up(p.dataBytes) - 1 downto 0)).resized
      ((op === Opcode.A.GET || op === Opcode.A.PUT_FULL_DATA) && a.mask =/= access) ||
        (op === Opcode.A.PUT_PARTIAL_DATA && (a.mask & ~access) =/= 0) ||
        (op === Opcode.A.GET && a.corrupt)
    } else False
    emit("tilelink.request_legal", "_a", a.valid.isInput, "Spinal TileLink A opcode, parameter, size and alignment",
      a.valid && (!legalParam || badMask || a.size > p.sizeMax || (a.address & alignMask) =/= 0))
    emit("tilelink.response_legal", "_d", d.valid.isInput, "Spinal TileLink D opcode and parameter",
      d.valid && (!(responding || d.opcode === Opcode.D.RELEASE_ACK) ||
        (grant && d.param.asUInt > 1) || (!grant && d.param =/= 0) ||
        (Bool(!p.withBCE) && (grant || d.opcode === Opcode.D.RELEASE_ACK)) ||
        (d.opcode === Opcode.D.RELEASE_ACK && d.denied) ||
        (if (p.withDataD) ((!Opcode.D.isData(d.opcode) && d.corrupt) ||
          (Opcode.D.isData(d.opcode) && d.denied && !d.corrupt)) else False)))
  }
  def axiAddress(ax: Axi4Ax, emit: Bool => Unit): Unit = {
    val c = ax.config
    require(!c.withAxi3, "AXI3 checks are not supported")
    val len = if (c.useLen) ax.len.resize(9) else U(0, 9 bits)
    val size = if (c.useSize) ax.size else U(log2Up(c.bytePerWord), 3 bits)
    val burst = if (c.useBurst) ax.burst else B(1, 2 bits)
    val aligned = ax.addr & ~((U(1, c.addressWidth bits) |<< size) - 1)
    val end = aligned.resize(c.addressWidth + 1) + ((len + 1).resize(c.addressWidth + 1) |<< size) - 1
    val boundary = if (c.addressWidth >= 12) (end >> 12) =/= (ax.addr.resize(c.addressWidth + 1) >> 12) else False
    val wrapLen = Seq(1, 3, 7, 15).map(len === _).reduce(_ || _)
    val wrapAlign = ax.addr =/= aligned
    val exclusive = if (c.useLock) ax.lock === 1 else False
    val exclusiveBytes = (len + 1).resize(c.addressWidth + 1) |<< size
    val exclusiveAligned = (ax.addr.resize(c.addressWidth + 1) & (exclusiveBytes - 1)) === 0
    val exclusiveLen = Seq(0, 1, 3, 7, 15).map(len === _).reduce(_ || _)
    val exclusiveCache = if (c.useCache) ax.cache(1) else False
    emit(size > log2Up(c.bytePerWord) || burst === 3 ||
      (burst === 1 && boundary) || (burst === 0 && len > 15) ||
      (burst === 2 && (!wrapLen || wrapAlign)) ||
      (exclusive && (!exclusiveLen || exclusiveBytes > 128 || !exclusiveAligned || exclusiveCache)))
  }
}
