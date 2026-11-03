package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib._
import spinal.lib.bus.amba4.axi._

class AxiSpec extends AnyFunSuite {
  class Top extends Component {
    val ar = slave(Stream(new Axi4Ar(Axi4Config(32, 32, useId = false))))
    ar.ready := True
  }
  lazy val compiled = {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/axi"), ChecksConfig(mode = Mode.Monitor))
    SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName("axi").withVerilator.compile(new Top)
  }
  def run(addr: Long, len: Int, burst: Int): Set[String] = {
    var hits = Set.empty[String]
    compiled.doSim { dut =>
      dut.ar.valid #= false
      dut.ar.payload.flatten.foreach(x => x match {
        case b: Bits => b #= 0
        case u: UInt => u #= 0
        case _ =>
      })
      dut.clockDomain.forkStimulus(10); dut.clockDomain.waitSampling(4)
      dut.clockDomain.waitFallingEdge()
      dut.ar.addr #= addr; dut.ar.len #= len; dut.ar.size #= 2; dut.ar.burst #= burst
      dut.ar.valid #= true
      dut.clockDomain.waitFallingEdge(); dut.ar.valid #= false
      dut.clockDomain.waitSampling(3)
      hits = ChecksSim.firings(dut).map(_.check.kind).toSet
    }
    hits
  }
  test("AXI4 incrementing burst inside a page is legal") { assert(run(0x100, 3, 1).isEmpty) }
  test("AXI4 burst crossing a page fires") { assert(run(0xffc, 1, 1) == Set("axi4.address_legal")) }
  test("AXI4 WRAP uses beats minus one") {
    assert(run(0x100, 3, 2).isEmpty)
    assert(run(0x100, 2, 2) == Set("axi4.address_legal"))
  }
}
