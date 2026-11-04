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
  test("native code coverage keeps physical instance counters") {
    val dir = java.nio.file.Files.createTempDirectory("coverage-flags").toFile
    val cfg = RiscvSimConfig(ModelKey("fixture", coverage = true), dir, new java.io.File(dir, "cache"),
      spinal.core.SpinalConfig())
    assert(!RiscvSimConfig.perInstanceSupported("Verilator 5.049"))
    assert(RiscvSimConfig.perInstanceSupported("Verilator 5.052"))
    assert(!RiscvSimConfig.perInstanceSupported("unknown"))
    assert(cfg._simulatorFlags.contains("--coverage-per-instance") == RiscvSimConfig.perInstanceCoverage)
  }
}
