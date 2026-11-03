package spinalchecks

import spinal.core._

/** Versioned project data. Unsupported CSR semantics need a different model. */
case class CsrModel(version: Int, width: Int, reset: BigInt, writeMask: BigInt,
                    minPrivilege: Int, allowed: Seq[BigInt] = Nil) {
  require(version == 1 && width > 0 && minPrivilege >= 0 && minPrivilege <= 3)
  require((Seq(reset, writeMask) ++ allowed).forall(x => x >= 0 && x.bitLength <= width))
}
object CsrChecks {
  /** Inputs describe accepted CSR accesses. Hardware set wins over clear and software writes.
    * `observed` is the DUT state, never the source of expected state.
    */
  def bind(name: String, model: CsrModel, observed: Bits, read: Bool, write: Bool,
           data: Bits, privilege: UInt, denied: Bool, hwSet: Bits, hwClear: Bits): Unit = {
    val w = model.width
    require(Seq(observed, data, hwSet, hwClear).forall(_.getWidth == w))
    val expected = Reg(Bits(w bits)).init(model.reset)
    val mask = B(model.writeMask, w bits)
    val accessDenied = privilege < model.minPrivilege
    val candidate = (expected & ~mask) | (data & mask)
    val legal = if (model.allowed.isEmpty) True else model.allowed.map(x => candidate === B(x, w bits)).reduce(_ || _)
    val next = Bits(w bits)
    next := expected
    when(write && !accessDenied && legal) { next := candidate }
    expected := (next & ~hwClear) | hwSet
    DeclaredChecks.rule("csr.state", name, "v1 independent reset, masked writes, reject-illegal WARL, hardware set priority")(
      observed =/= expected)
    DeclaredChecks.rule("csr.access", name, "v1 declared minimum privilege")(
      (read || write) && (denied =/= accessDenied))
  }
}
