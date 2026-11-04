package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinalchecks.coherence.{PermissionMonitor, PermissionRelation}

/** The fixture has permission outputs, not TL-C channels. */
class CoherenceModelFixtureSpec extends AnyFunSuite {
  class CheckedFixture extends AtomicFixture {
    val monitors = (0 until 2).map(w => new PermissionMonitor(io.permissions(w), io.permissions(2+w)))
    monitors.foreach(_.failed.simPublic())
  }

  test("generated relation rejects a conflicting grant in simulation") {
    PermissionRelation.check(0, PermissionRelation.encode(2, 0))
    intercept[IllegalArgumentException] {
      PermissionRelation.check(PermissionRelation.encode(2, 0), PermissionRelation.encode(2, 2))
    }
  }

  test("generated SpinalChecks monitor runs on two harts and catches ownership fault") {
    val work = Files.createTempDirectory("coherence-model-fixture").toFile
    try {
      val compiled = SimConfig.withVerilator.workspacePath(work.getPath).compile(new CheckedFixture)
      for (fault <- Seq(0, 4)) {
        var detected = false
        def run(): Unit = compiled.doSim { dut =>
          dut.io.enable #= 0; dut.io.evict #= false; dut.io.fault #= fault
          dut.io.instructions.foreach(_ #= 0x13)
          dut.clockDomain.forkStimulus(10)
          dut.clockDomain.waitSampling(5)
          val retired = Array(0, 0)
          val previous = Array(0, 0)
          // addi x3,x0,7; sw x3,0(x0); lw x4,0(x0)
          val program = Seq(0x00700193L, 0x00302023L, 0x00002203L)
          for (_ <- 0 until 80) {
            dut.clockDomain.waitFallingEdge()
            for (h <- 0 until 2) {
              dut.io.instructions(h) #= program.lift(retired(h)).getOrElse(0x13L)
            }
            dut.io.enable #= (if (retired(0) < 3) 1 else 0) + (if (retired(1) < 3) 2 else 0)
            sleep(1)
            for (h <- 0 until 2 if dut.harts(h).io.retired.toBoolean) retired(h) += 1
            dut.clockDomain.waitRisingEdge(); sleep(1)
            for (w <- 0 until 2) {
              val state = PermissionRelation.encode(dut.io.permissions(w).toInt, dut.io.permissions(2+w).toInt)
              val softwareFailed = !PermissionRelation.states(state) || !PermissionRelation.edges((previous(w), state))
              val rtlFailed = dut.monitors(w).failed.toBoolean
              assert(rtlFailed == softwareFailed, "hardware and simulation monitors disagree")
              detected ||= rtlFailed
              previous(w) = state
            }
          }
          assert(retired.forall(_ == 3), "two-hart fixture did not complete")
          assert(!detected, "unexpected ownership failure")
        }
        if (fault == 0) run()
        else {
          val error = intercept[spinal.sim.SimFailure](run())
          assert(error.getMessage.contains("HDL assertion failure"))
          assert(detected, "generated software projection did not see the RTL fault")
        }
      }
    } finally org.apache.commons.io.FileUtils.deleteDirectory(work)
  }
}
