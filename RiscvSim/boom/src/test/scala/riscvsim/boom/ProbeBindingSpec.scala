package riscvsim.boom

import org.scalatest.funsuite.AnyFunSuite

/** Cheap mapping checks. Native capture remains a separate smoke run. */
class ProbeBindingSpec extends AnyFunSuite {
  test("small uses one retirement slot for ordered state capture") {
    assert(BoomAdapter.tile("small").core.decodeWidth == 1)
  }
  test("the adapter opts in to optional collection") {
    assert(BoomAdapter.supportsProbes)
    assert(BoomAdapter.irqInputMask == BigInt(0xA88))
  }
}
