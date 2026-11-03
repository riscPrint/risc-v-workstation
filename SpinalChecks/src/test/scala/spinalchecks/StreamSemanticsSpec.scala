package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib._

class StreamSemanticsSpec extends AnyFunSuite {
  class Top extends Component {
    val offer = slave(Stream(Bits(8 bits)))
    val go = in Bool()
    offer.ready := go
  }
  test("a declared Decoupled offer can change and drop; strict streams still fire") {
    for (decoupled <- Seq(false, true)) {
      val config = ChecksConfig(mode = Mode.Monitor, mayDropValid =
        if (decoupled) Seq(StreamSemantics("offer", "producer reselects before acceptance")) else Nil)
      val (cfg, checks) = SpinalChecks.install(SpinalConfig(targetDirectory = s"generated/drop-$decoupled"), config)
      val compiled = SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName(s"drop-$decoupled")
        .withVerilator.compile(new Top)
      compiled.doSim { dut =>
        dut.offer.valid #= false; dut.offer.payload #= 0; dut.go #= false
        dut.clockDomain.forkStimulus(10); dut.clockDomain.waitSampling(4)
        dut.clockDomain.waitFallingEdge(); dut.offer.valid #= true; dut.offer.payload #= 1
        dut.clockDomain.waitFallingEdge(); dut.offer.payload #= 2
        dut.clockDomain.waitFallingEdge(); dut.offer.valid #= false
        dut.clockDomain.waitSampling(3)
        val hits = ChecksSim.firings(dut).map(_.check.kind).toSet
        assert(hits == (if (decoupled) Set.empty[String] else Set(Kind.StreamValidHold, Kind.StreamPayloadStable)))
      }
      if (decoupled) assert(checks.records.forall(r => r.status == "waived" && r.reason.contains("reselects")))
    }
  }
  test("settings require a reason") {
    intercept[IllegalArgumentException](StreamSemantics("*", " "))
  }
}
