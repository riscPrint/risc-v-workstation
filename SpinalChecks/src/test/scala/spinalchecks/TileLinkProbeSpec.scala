package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib.bus.tilelink._

class TileLinkProbeSpec extends AnyFunSuite {
  class Top extends Component {
    val bus = in(Bus(BusParameter.simple(32, 32, 16, 2).copy(withBCE = true, sinkWidth = 2)))
  }
  lazy val compiled = {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/tl-probes"), ChecksConfig(mode = Mode.Monitor))
    SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName("tl-probes").withVerilator.compile(new Top)
  }
  def run(scenario: String): Set[String] = {
    var hits = Set.empty[String]
    compiled.doSim { dut =>
      dut.bus.flatten.foreach {
        case x: Bool => x #= false
        case x: Bits => x #= 0
        case x: UInt => x #= 0
        case _ =>
      }
      val b = dut.bus.b; val c = dut.bus.c
      dut.bus.a.opcode #= Opcode.A.GET; dut.bus.a.ready #= true
      dut.bus.d.opcode #= Opcode.D.ACCESS_ACK; dut.bus.d.ready #= true
      dut.bus.e.ready #= true
      b.opcode #= Opcode.B.PROBE_BLOCK; b.param #= 2; b.size #= 2; b.address #= 0x100; b.ready #= true
      c.opcode #= Opcode.C.PROBE_ACK; c.param #= 1; c.size #= 2; c.address #= 0x100; c.ready #= true
      dut.clockDomain.forkStimulus(10); dut.clockDomain.waitSampling(4)
      def step(): Unit = dut.clockDomain.waitFallingEdge()
      step()
      if (scenario != "orphan") b.valid #= true
      if (scenario == "badbparam") b.param #= 3
      if (scenario == "permissiondata") b.opcode #= Opcode.B.PROBE_PERM
      if (scenario == "zero") c.valid #= true
      step(); b.valid #= false; c.valid #= false
      if (scenario == "twoaddresses" || scenario == "duplicate") {
        b.valid #= true
        if (scenario == "twoaddresses") b.address #= 0x200
        step(); b.valid #= false
      }
      if (scenario != "zero") {
        c.valid #= true
        if (scenario == "twoaddresses") c.address #= 0x200
        if (scenario == "wrongaddress") c.address #= 0x300
        if (scenario == "wrongsize") c.size #= 3
        if (scenario == "badcap") c.param #= 0
        if (scenario == "badcparam") c.param #= 7
        if (scenario == "permissiondata") c.opcode #= Opcode.C.PROBE_ACK_DATA
      }
      step(); c.valid #= false
      if (scenario == "twoaddresses") {
        c.address #= 0x100; c.valid #= true
        step(); c.valid #= false
      }
      dut.clockDomain.waitSampling(3)
      hits = ChecksSim.firings(dut).map(_.check.kind).toSet
    }
    hits
  }
  test("matched, zero-latency and same-source different-address probes are legal") {
    for (s <- Seq("clean", "zero", "twoaddresses")) assert(run(s).isEmpty, s)
  }
  test("orphan, address, size, permission and ProbePerm data errors fire") {
    for (s <- Seq("orphan", "wrongaddress", "wrongsize", "badcap", "permissiondata"))
      assert(run(s).contains("tilelink.probe_match"), s)
  }
  test("duplicate probe key and invalid parameters fire") {
    assert(run("duplicate").contains("tilelink.probe_busy"))
    assert(run("badbparam").contains("tilelink.probe_legal"))
    assert(run("badcparam").contains("tilelink.c_legal"))
  }
}
