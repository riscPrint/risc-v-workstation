package riscvsim

import java.io.File
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._

class FlipTop extends Component {
  val r = Reg(UInt(8 bits)) init 0
  r := r
}

/** An adapter that ticks after waitSampling in its own thread races the injector's thread on the
  * same edge. A one-cycle flip must still land on its own cycle. Needs Verilator. */
class FaultInjectorNativeSpec extends AnyFunSuite {
  test("a one-cycle flip lands on its cycle when the adapter ticks in another thread") {
    val work = java.nio.file.Files.createTempDirectory("rvw-flip").toFile
    val compiled = SimConfig.withConfig(SpinalConfig(defaultConfigForClockDomains = ClockDomainConfig(resetKind = SYNC)))
      .withVerilator.workspacePath(work.getPath).compile {
      val top = new FlipTop
      top.r.simPublic()
      top
    }
    val job = Cli.job(Map("elf" -> "test", "out" -> new File(work, "run").getPath, "max-cycles" -> "100"),
      ToyAdapter, new File("."))
    for (at <- Seq(5L, 10L, 11L)) {
      val injector = new FaultInjector(FaultFile(new File(work, "faults.json"),
        Seq(Fault("f0", "flip", "r", 3, at, Some(1)))))
      compiled.doSim { dut =>
        val ctl = new SimControl(job)
        dut.clockDomain.forkStimulus(10)
        // Change ordering at the requested edge: the prior sample sees the new
        // adapter count, but this sample sees the old count. The old injector
        // skips the requested cycle when the order changes back on the next edge.
        fork {
          for (sample <- 1 to 20) {
            dut.clockDomain.waitSampling()
            if (sample == at) sleep(1)
            ctl.tick()
          }
        }
        injector.attach(dut, ctl)
        for (_ <- 0 until 20) dut.clockDomain.waitSampling()
      }
      val d = injector.details(20)
      assert(d("applied").bool, d.toString)
      assert(d("applied_cycle").num == at, d.toString)
    }
  }
}
