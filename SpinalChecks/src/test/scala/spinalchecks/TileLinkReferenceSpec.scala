package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib._
import spinal.lib.bus.tilelink._
import spinalchecks.sim.TileLinkReference

class TileLinkReferenceSpec extends AnyFunSuite {
  class Memory extends Component {
    val bus = slave(Bus(BusParameter.simple(32, 32, 4, 2)))
    val mem = Mem(Bits(32 bits), 16)
    mem.initBigInt(Seq.fill(16)(BigInt(0)))
    val pending = RegInit(False)
    bus.a.ready := !pending || bus.d.ready
    val write = Opcode.A.isPut(bus.a.opcode)
    when(bus.d.fire) { pending := False }
    when(bus.a.fire) { pending := True }
    val index = bus.a.address(5 downto 2)
    mem.write(index, bus.a.data, bus.a.fire && write, bus.a.mask)
    bus.d.valid := pending
    bus.d.opcode := RegNextWhen(write.mux(Opcode.D.ACCESS_ACK(), Opcode.D.ACCESS_ACK_DATA()), bus.a.fire)
    bus.d.source := RegNextWhen(bus.a.source, bus.a.fire)
    bus.d.size := RegNextWhen(bus.a.size, bus.a.fire)
    bus.d.data := RegNextWhen(mem.readAsync(index), bus.a.fire)
    bus.d.param := 0; bus.d.sink := 0; bus.d.denied := False; bus.d.corrupt := False
  }
  test("Spinal driver, randomized response backpressure and independent reference memory agree") {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/tl-reference"), ChecksConfig(mode = Mode.Monitor))
    SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName("tl-reference").withVerilator
      .compile(new Memory).doSim(seed = 19) { dut =>
        SimTimeout(10000)
        dut.clockDomain.forkStimulus(10)
        val ref = new TileLinkReference(dut.bus, dut.clockDomain, (0 until 64).map(i => BigInt(i) -> 0.toByte).toMap)
        dut.clockDomain.waitSampling(4)
        ref.master.driver.d.factor = 0.3f
        ref.put(0, 0, Array[Byte](10, 20, 30, 40), Array(true, false, true, false))
        dut.clockDomain.waitSamplingWhere(ref.scoreboard.responses == 1)
        ref.get(1, 0, 2)
        dut.clockDomain.waitSamplingWhere(ref.scoreboard.responses == 2)
        ref.scoreboard.assertComplete()
        assert(ChecksSim.firings(dut).isEmpty)
      }
  }
}
