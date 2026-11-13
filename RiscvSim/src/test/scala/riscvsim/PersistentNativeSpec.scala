package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._

/** Bounded native reset test. This circuit is not an ISA implementation. */
class PersistentResetFixture extends Component {
  val io = new Bundle {
    val data = in UInt(32 bits)
    val value = out UInt(32 bits)
  }
  val state = Reg(UInt(32 bits)) init 0
  state := state + io.data
  io.value := state
}

class PersistentNativeSpec extends AnyFunSuite {
  test("compiled native model isolates DUT, RNG, device and monitor state after failures") {
    val dir = Files.createTempDirectory("persistent-native").toFile
    try {
      val compiled = SimConfig.withVerilator.workspacePath(dir.getPath)
        .compile(new PersistentResetFixture)
      def execute(seed: Int, fail: Boolean): Seq[BigInt] = {
        val random = new scala.util.Random(seed)
        val device = new ToHost(0, 4)
        val monitor = new ProgressMonitor(20, 1, "fixture responds each cycle")
        val samples = scala.collection.mutable.ArrayBuffer.empty[BigInt]
        compiled.doSim(seed = seed) { dut =>
          dut.io.data #= 0
          dut.clockDomain.forkStimulus(10)
          dut.clockDomain.waitSampling(5)
          assert(dut.io.value.toBigInt == 0)
          assert(device.value == 0 && monitor.outstanding == 0)
          for (cycle <- 0 until 8) {
            dut.clockDomain.waitFallingEdge()
            monitor.request("request", cycle)
            dut.io.data #= random.nextInt(1000)
            dut.clockDomain.waitSampling()
            sleep(1)
            samples += dut.io.value.toBigInt
            monitor.complete("request", cycle)
          }
          monitor.finish(8)
          device.onStore(0, 2, if (fail) 7 else 1)
          if (fail) simFailure("injected native failure after device write")
        }
        samples.toSeq
      }
      val reference = execute(317, false)
      for (seed <- Seq(42, 93, 317)) {
        intercept[spinal.sim.SimFailure] { execute(seed, true) }
        assert(execute(317, false) == reference)
      }
      // Repeated requests exercise teardown; this is not an RSS measurement.
      for (_ <- 0 until 8) assert(execute(317, false) == reference)
    } finally org.apache.commons.io.FileUtils.deleteDirectory(dir)
  }
}
