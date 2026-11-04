package riscvsim

import spinal.core._
import spinal.core.sim._

/** Round 2 harts with RV32 word atomics and programmable instruction inputs.
  * One shared, serialized memory port. N/B/T permissions are a fixture protocol,
  * not TileLink channels or a cache implementation. */
class AtomicFixture extends Component {
  val io = new Bundle {
    val instructions = in Vec(Bits(32 bits), 2)
    val enable = in Bits(2 bits)
    val fault = in UInt(4 bits)
    val evict = in Bool()
    val memory = out Vec(Bits(32 bits), 2)
    val permissions = out Vec(UInt(2 bits), 4) // N=0, B=1, T=2; hart*2+word
    val transfer = out Bool() // dirty-data transfer before downgrade
  }
  val harts = Seq.fill(2)(new FixtureHart(Seq(0L, 0L), programmable = true))
  val memory = Vec(Reg(Bits(32 bits)) init 0, 2)
  val permissions = Vec(Reg(UInt(2 bits)) init 0, 4)
  val reserved = Vec(Reg(Bool()) init False, 2)
  val reservation = Vec(Reg(UInt(1 bits)) init 0, 2)
  val phase = Reg(UInt(3 bits)) init 0
  phase := phase + 1
  io.memory := memory; io.permissions := permissions
  io.transfer := io.fault =/= 7
  for ((h, id) <- harts.zipWithIndex) {
    val other = 1-id
    h.io.instruction := io.instructions(id)
    h.io.enable := io.enable(id)
    // Each port has a slot every eight cycles. Faults violate the declared fairness.
    h.io.ready := phase === id*2 && !(io.fault === 5 && Bool(id == 0)) && io.fault =/= 6
    val word = h.io.address(2).asUInt
    val old = memory(word)
    val op = h.io.operation
    val sc = h.io.atomic && op === 3
    val lr = h.io.atomic && op === 2
    val success = reserved(id) && reservation(id) === word
    val updated = Bits(32 bits)
    updated := h.io.wdata
    switch(op) {
      is(0) { updated := (old.asUInt + h.io.wdata.asUInt).asBits }
      is(4) { updated := old ^ h.io.wdata }
      is(8) { updated := old | h.io.wdata }
      is(12) { updated := old & h.io.wdata }
      is(16) { updated := Mux(old.asSInt < h.io.wdata.asSInt, old, h.io.wdata) }
      is(20) { updated := Mux(old.asSInt > h.io.wdata.asSInt, old, h.io.wdata) }
      is(24) { updated := Mux(old.asUInt < h.io.wdata.asUInt, old, h.io.wdata) }
      is(28) { updated := Mux(old.asUInt > h.io.wdata.asUInt, old, h.io.wdata) }
    }
    val write = h.io.write && (!sc || success)
    h.io.rdata := Mux(sc, Mux(success, B(0,32 bits), B(1,32 bits)), old)
    when(io.fault === 9 && !h.io.atomic && !h.io.write) { h.io.rdata := B(2,32 bits) }
    when(io.fault === 3 && h.io.atomic && !sc && !lr) { h.io.rdata := old ^ B(1,32 bits) }
    when(h.io.request && h.io.ready) {
      when(lr) { reserved(id) := True; reservation(id) := word }
      when(sc) { reserved(id) := False }
      when(write) {
        val data = Mux(h.io.atomic && !sc, updated, h.io.wdata)
        memory(word) := data
        // Torn AMO: expose only the low half to the independent observer.
        when(io.fault === 2 && h.io.atomic && !sc) { memory(word) := old(31 downto 16) ## data(15 downto 0) }
        when(reservation(other) === word && io.fault =/= 1) { reserved(other) := False }
        permissions(U(id*2,2 bits) + word.resize(2)) := U(2,2 bits)
        when(io.fault =/= 4) { permissions(U(other*2,2 bits) + word.resize(2)) := U(0,2 bits) }
      } otherwise {
        permissions(U(id*2,2 bits) + word.resize(2)) := Mux(permissions(U(id*2,2 bits) + word.resize(2)) === 2, U(2,2 bits), U(1,2 bits))
        when(permissions(U(other*2,2 bits) + word.resize(2)) === 2) {
          permissions(U(other*2,2 bits) + word.resize(2)) := U(1,2 bits)
        }
      }
    }
    h.io.simPublic()
  }
  when(io.evict) { permissions.foreach(_ := 0) }
}
