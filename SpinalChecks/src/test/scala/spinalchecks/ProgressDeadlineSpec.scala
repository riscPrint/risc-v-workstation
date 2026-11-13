package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._

class ProgressDeadlineSpec extends AnyFunSuite {
  class Top extends Component { val progress = in Bool() }

  for (limit <- Seq(1, 3)) test(s"watchdog fires on idle sample $limit and restarts after progress") {
    val (cfg, result) = SpinalChecks.install(SpinalConfig(
      targetDirectory = s"generated/progress_deadline_$limit",
      defaultConfigForClockDomains = ClockDomainConfig(resetKind = SYNC)),
      ChecksConfig(mode = Mode.Monitor, progress = Seq(ProgressSpec("deadline", "progress", limit))))
    SimConfig.withConfig(cfg).withVerilator.workspacePath("simWorkspace")
      .workspaceName(s"progress_deadline_$limit").compile(new Top).doSim { dut =>
        dut.progress #= true
        dut.clockDomain.forkStimulus(10)
        dut.clockDomain.waitSampling(5)
        dut.clockDomain.waitFallingEdge()
        val check = result.inserted.find(_.kind == Kind.Progress).get
        for (_ <- 0 until 2) {
          val before = check.count.toInt
          dut.progress #= false
          for (idle <- 1 to limit) {
            dut.clockDomain.waitSampling()
            dut.clockDomain.waitFallingEdge()
            assert(check.count.toInt == before + (if (idle == limit) 1 else 0), s"idle sample $idle")
          }
          dut.progress #= true
          dut.clockDomain.waitSampling()
          dut.clockDomain.waitFallingEdge()
          assert(check.count.toInt == before + 1)
        }
      }
  }
}
