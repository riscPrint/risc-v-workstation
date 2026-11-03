package riscvsim

import org.scalatest.funsuite.AnyFunSuite

class CoverageVersionSpec extends AnyFunSuite {
  test("FSM coverage needs a checked native tool version") {
    assert(!RiscvSimConfig.fsmSupported("Verilator 5.049 devel"))
    assert(!RiscvSimConfig.fsmSupported("Verilator 5.050"))
    assert(RiscvSimConfig.fsmSupported("Verilator 5.052 2026-09-05"))
    assert(RiscvSimConfig.fsmSupported("Verilator 6.000"))
    assert(!RiscvSimConfig.fsmSupported("unknown"))
  }
}
