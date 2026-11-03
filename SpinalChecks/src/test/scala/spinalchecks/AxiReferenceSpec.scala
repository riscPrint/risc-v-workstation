package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib._
import spinal.lib.bus.amba4.axi._
import spinal.lib.bus.amba4.axi.sim._
import spinalchecks.sim.AxiReference

class AxiReferenceSpec extends AnyFunSuite {
  class Bridge extends Component {
    val p = Axi4Config(32, 32, idWidth = 2, readIssuingCapability = 4,
      writeIssuingCapability = 4, combinedIssuingCapability = 8)
    val up = slave(Axi4(p))
    val down = master(Axi4(p))
    down << up
  }
  test("AXI master and subordinate with delays preserve an independent DMA memory model") {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/axi-reference"), ChecksConfig(mode = Mode.Monitor))
    SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName("axi-reference").withVerilator
      .compile(new Bridge).doSim(seed = 29) { dut =>
        SimTimeout(20000)
        dut.clockDomain.forkStimulus(10)
        val memory = AxiMemorySim(dut.down, dut.clockDomain, AxiMemorySimConfig(
          maxOutstandingReads = 4, maxOutstandingWrites = 4, readResponseDelay = 3,
          writeResponseDelay = 4, interruptProbability = 40, interruptMaxDelay = 3))
        memory.start()
        val ref = new AxiReference(dut.up, dut.clockDomain)
        dut.clockDomain.waitSampling(5)
        val data = (0 until 32).map(i => (i * 7).toByte).toList
        ref.write(0x100, data, id = 1, len = 3)
        ref.copy(0x100, 0x200, 32, id = 2, len = 3)
        assert(ref.checkRead(0x200, 32, id = 3, len = 3) == data)
        assert(ref.reads == 2 && ref.writes == 2)
        assert(ChecksSim.firings(dut).isEmpty)
        memory.stop()
      }
  }
}
