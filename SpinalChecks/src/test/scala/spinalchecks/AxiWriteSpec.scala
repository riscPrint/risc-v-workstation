package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib.bus.amba4.axi._

class AxiWriteSpec extends AnyFunSuite {
  class Top extends Component {
    val bus = in(Axi4WriteOnly(Axi4Config(32, 32, idWidth = 2,
      writeIssuingCapability = 4, combinedIssuingCapability = 4)))
  }
  lazy val compiled = {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/axi-write"), ChecksConfig(mode = Mode.Monitor))
    SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName("axi-write").withVerilator.compile(new Top)
  }
  def run(fault: String): Set[String] = {
    var hits = Set.empty[String]
    compiled.doSim { dut =>
      dut.bus.flatten.foreach {
        case b: Bool => b #= false
        case b: Bits => b #= 0
        case u: UInt => u #= 0
        case _ =>
      }
      val aw = dut.bus.aw; val w = dut.bus.w; val b = dut.bus.b
      aw.ready #= true; w.ready #= true; b.ready #= true
      aw.size #= 2; aw.burst #= 1; w.strb #= 15
      dut.clockDomain.forkStimulus(10); dut.clockDomain.waitSampling(4)
      def step(): Unit = dut.clockDomain.waitFallingEdge()
      step(); w.valid #= true; w.last #= false; w.data #= 42
      step(); w.last #= true
      step(); w.valid #= false; aw.valid #= true; aw.id #= 0; aw.len #= (if (fault == "length") 0 else 1)
      if (fault == "samecycle") { b.valid #= true; b.id #= 0 }
      step(); b.valid #= false; aw.id #= 1; aw.len #= 0; w.valid #= true; w.last #= true
      step(); aw.valid #= false; w.valid #= false
      if (fault == "reset") {
        dut.clockDomain.assertReset(); dut.clockDomain.waitRisingEdge(3)
        dut.clockDomain.deassertReset(); step()
      }
      b.valid #= true; b.id #= (if (fault == "orphan") 2 else 1)
      if (fault == "exokay") b.resp #= 1
      step(); b.id #= 0; b.resp #= 0
      step(); b.valid #= false
      dut.clockDomain.waitSampling(3)
      hits = ChecksSim.firings(dut).map(_.check.kind).toSet
    }
    hits
  }
  test("AXI4 accepts W before AW and reorders B across IDs") { assert(run("clean").isEmpty) }
  test("BVALID needs AW and final W accepted on earlier edges") {
    assert(run("samecycle").contains("axi4.write_match"))
  }
  test("AXI4 W length mismatch fires") { assert(run("length").contains("axi4.write_beats")) }
  test("AXI4 orphan, EXOKAY and response after reset fire") {
    for (f <- Seq("orphan", "exokay", "reset")) assert(run(f).contains("axi4.write_match"), f)
  }
}
