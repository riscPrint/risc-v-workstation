package spinalchecks.sim

import spinal.core._

/** Small project binding fixture. Mutations are deliberate test faults. */
class CsrSeed(mutant: String = "none") extends Component {
  require(Set("none", "wrong_mask", "missing_trap", "wrong_reset", "writable_ro").contains(mutant))
  val io = new Bundle {
    val valid, write = in Bool()
    val privilege = in UInt(2 bits)
    val address = in UInt(12 bits)
    val data = in Bits(32 bits)
    val trap = out Bool()
    val state, readData = out Bits(32 bits)
  }
  val state = Reg(Bits(32 bits)).init(if (mutant == "wrong_reset") 0 else 5)
  val selected = io.address === U(0x340, 12 bits)
  val readOnly = io.address === U(0xf11, 12 bits)
  val denied = io.privilege =/= 3 || (!selected && !readOnly) || (readOnly && io.write)
  io.trap := (if (mutant == "missing_trap") False else denied)
  io.readData := Mux(readOnly, B(0, 32 bits), state)
  io.state := state
  when(io.valid && io.write && ((!denied && selected) ||
      (if (mutant == "writable_ro") readOnly else False))) {
    if (mutant == "wrong_mask") state := io.data
    else state := (state & B(BigInt("fffffff0", 16), 32 bits)) | (io.data & B(15, 32 bits))
  }
}
