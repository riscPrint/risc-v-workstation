package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib.bus.tilelink._

class TileLinkCoherentSpec extends AnyFunSuite {
  class Top extends Component {
    val bus = in(Bus(BusParameter.simple(32, 32, 4, 2).copy(withBCE = true, sinkWidth = 2)))
  }
  lazy val compiled = {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/tl-coherent"), ChecksConfig(mode = Mode.Monitor))
    SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName("tl-coherent").withVerilator.compile(new Top)
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
      val a = dut.bus.a; val d = dut.bus.d; val c = dut.bus.c; val e = dut.bus.e
      a.opcode #= Opcode.A.ACQUIRE_BLOCK; a.size #= 2; a.param #= 1; a.mask #= 15; a.ready #= true
      c.opcode #= Opcode.C.RELEASE; c.size #= 2; c.ready #= true
      dut.bus.b.opcode #= Opcode.B.PROBE_BLOCK
      d.opcode #= Opcode.D.GRANT; d.size #= 2; d.ready #= true
      e.ready #= true
      dut.clockDomain.forkStimulus(10); dut.clockDomain.waitSampling(4)
      def step(): Unit = dut.clockDomain.waitFallingEdge()
      step(); a.valid #= true
      step(); a.valid #= false; d.valid #= true
      step(); d.valid #= false
      if (fault == "sinkreuse") {
        a.valid #= true; a.source #= 1
        step(); a.valid #= false; d.valid #= true; d.source #= 1
        step(); d.valid #= false
      }
      e.valid #= true; e.sink #= (if (fault == "orphanack") 1 else 0)
      step(); e.valid #= false
      if (fault != "orphanrelease") c.valid #= true
      step(); c.valid #= false; d.valid #= true; d.opcode #= Opcode.D.RELEASE_ACK; d.source #= 0
      if (fault == "badreleaseparam") d.param #= 1
      step(); d.valid #= false
      dut.clockDomain.waitSampling(3)
      hits = ChecksSim.firings(dut).map(_.check.kind).toSet
    }
    hits
  }
  test("Grant/GrantAck and Release/ReleaseAck bookkeeping is separate") { assert(run("clean").isEmpty) }
  test("ReleaseAck reserved parameter must be zero") {
    assert(run("badreleaseparam").contains("tilelink.response_legal"))
  }
  test("sink reuse and orphan GrantAck or ReleaseAck fire") {
    assert(run("sinkreuse").contains("tilelink.sink_busy"))
    assert(run("orphanack").contains("tilelink.sink_match"))
    assert(run("orphanrelease").contains("tilelink.release_match"))
  }
}
