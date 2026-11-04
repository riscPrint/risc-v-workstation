package spinalchecks

import spinal.core._

/** Versioned project data. Unsupported CSR semantics need a different model. */
case class CsrModel(version: Int, width: Int, reset: BigInt, writeMask: BigInt,
                    minPrivilege: Int, allowed: Seq[BigInt] = Nil,
                    w1cMask: BigInt = 0, readClearMask: BigInt = 0,
                    legalize: Map[BigInt, BigInt] = Map.empty,
                    wlrl: Boolean = false, readOnly: Boolean = false) {
  require(version == 1 && width > 0 && minPrivilege >= 0 && minPrivilege <= 3)
  require((Seq(reset, writeMask, w1cMask, readClearMask) ++ allowed ++ legalize.keys ++ legalize.values).forall(x => x >= 0 && x.bitLength <= width))
  require((writeMask & w1cMask) == 0, "ordinary and W1C masks overlap")
  require(!readOnly || (writeMask == 0 && w1cMask == 0))
  require(!wlrl || (allowed.nonEmpty && legalize.isEmpty))
  require(legalize.values.forall(x => allowed.isEmpty || allowed.contains(x)))
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
    val candidate = (expected & ~mask) | (data & mask)
    val legalized = Bits(w bits)
    legalized := candidate
    for ((from, to) <- model.legalize.toSeq.sortBy(_._1)) {
      when(candidate === B(from, w bits)) { legalized := B(to, w bits) }
    }
    val legal = if (model.allowed.isEmpty) True else model.allowed.map(x => legalized === B(x, w bits)).reduce(_ || _)
    val accessDenied = privilege < model.minPrivilege || (write && Bool(model.readOnly)) ||
      (write && Bool(model.wlrl) && !legal)
    val next = Bits(w bits)
    next := expected & ~Mux(read && !accessDenied, B(model.readClearMask, w bits), B(0, w bits))
    when(write && !accessDenied && legal) { next := legalized & ~(data & B(model.w1cMask, w bits)) }
    expected := (next & ~hwClear) | hwSet
    DeclaredChecks.rule("csr.state", name, "v1 independent reset, WARL/WLRL, read-only, read-clear, W1C, hardware priority")(
      observed =/= expected)
    DeclaredChecks.rule("csr.access", name, "v1 declared minimum privilege")(
      (read || write) && (denied =/= accessDenied))
  }
}
