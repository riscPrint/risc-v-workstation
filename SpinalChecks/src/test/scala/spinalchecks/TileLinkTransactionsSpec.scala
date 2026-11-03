package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib.bus.tilelink._

class TileLinkTransactionsSpec extends AnyFunSuite {
  class Top extends Component {
    val bus = in(Bus(BusParameter.simple(32, 32, 16, 2)))
  }
  lazy val compiled = {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/tltxn"), ChecksConfig(mode = Mode.Monitor))
    SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName("tltxn").withVerilator.compile(new Top)
  }
  def run(scenario: String): Set[String] = {
    var hits = Set.empty[String]
    compiled.doSim { dut =>
      val a = dut.bus.a; val d = dut.bus.d
      a.valid #= false; a.ready #= true
      d.valid #= false; d.ready #= true
      a.opcode #= Opcode.A.GET; a.param #= 0; a.size #= 2
      a.source #= 0; a.address #= 0x100; a.mask #= 15; a.data #= 0; a.corrupt #= false
      d.opcode #= Opcode.D.ACCESS_ACK_DATA; d.param #= 0; d.size #= 2
      d.source #= 0; d.sink #= 0; d.denied #= false; d.data #= 0; d.corrupt #= false
      dut.clockDomain.forkStimulus(10); dut.clockDomain.waitSampling(4)
      def step(): Unit = dut.clockDomain.waitFallingEdge()
      step()
      if (scenario != "orphan") a.valid #= true
      if (scenario == "badmask") a.mask #= 0
      if (scenario == "corruptget") a.corrupt #= true
      if (scenario == "zero") d.valid #= true
      step(); a.valid #= false; d.valid #= false
      scenario match {
        case "reuse" => a.valid #= true
        case "badparam" => a.valid #= true; a.source #= 1; a.param #= 7
        case "reorder" => a.valid #= true; a.source #= 1
        case _ =>
      }
      step(); a.valid #= false
      if (scenario != "zero") {
        d.valid #= true
        if (scenario == "wrongsize") d.size #= 3
        if (scenario == "wrongopcode") d.opcode #= Opcode.D.ACCESS_ACK
        if (scenario == "reorder") d.source #= 1
      }
      step(); d.valid #= false
      if (scenario == "reorder") { step(); d.valid #= true; d.source #= 0; step(); d.valid #= false }
      dut.clockDomain.waitSampling(3)
      hits = ChecksSim.firings(dut).map(_.check.kind).toSet
    }
    hits
  }
  test("matched, zero-latency and reordered sources are legal") {
    for (s <- Seq("clean", "zero", "reorder")) assert(run(s).isEmpty, s)
  }
  test("orphan, response size and opcode mismatch fire") {
    for (s <- Seq("orphan", "wrongsize", "wrongopcode")) assert(run(s).contains("tilelink.response_match"), s)
  }
  test("source reuse fires") { assert(run("reuse").contains("tilelink.source_busy")) }
  test("invalid Get mask and corrupt Get fire") {
    assert(run("badmask").contains("tilelink.request_legal"))
    assert(run("corruptget").contains("tilelink.request_legal"))
  }
  test("illegal parameter fires") { assert(run("badparam").contains("tilelink.request_legal")) }
}
