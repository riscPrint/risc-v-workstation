package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib._

class LocalRulesSpec extends AnyFunSuite {
  class Ref extends Component {
    val use = in Bool()
    val idx = in UInt(2 bits)
    val bits = in Bits(3 bits)
    val value = out UInt(8 bits)
    val bit = out Bool()
    val flow = slave(Flow(Bits(3 bits)))
    value := 0
    bit := False
    when(use) {
      value := Vec(U(1, 8 bits), U(2, 8 bits), U(3, 8 bits))(idx)
      bit := bits(idx)
    }
    DeclaredChecks.flowValues("input", flow, Seq(BigInt(1), BigInt(2)))
  }
  test("direct conditional selects and Flow payload intent: legal, unused, illegal") {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/local_rules"),
      ChecksConfig(mode = Mode.Monitor))
    val sim = SimConfig.withConfig(cfg).withVerilator.workspacePath("simWorkspace").workspaceName("local_rules").compile(new Ref)
    for ((use, idx, valid, payload, expected) <- Seq(
      (true, 2, true, 1, Set.empty[String]),
      (false, 3, false, 7, Set.empty[String]),
      (true, 3, true, 7, Set("vec.index", "bits.index", "flow.payload_legal")))) {
      sim.doSim { d =>
        d.use #= use; d.idx #= idx; d.bits #= 5
        d.flow.valid #= valid; d.flow.payload #= payload
        d.clockDomain.forkStimulus(10)
        d.clockDomain.waitSampling(8)
        d.clockDomain.waitFallingEdge()
        assert(ChecksSim.firings(d).map(_.check.kind).toSet == expected)
      }
    }
  }
  class Indirect(style: Int = 0) extends Component {
    val use = in Bool()
    val idx = in UInt(2 bits)
    val bits = in Bits(3 bits)
    val bit = out Bool()
    val value = out UInt(8 bits)
    val selected = bits(idx)
    val selectedValue = Vec(U(1,8 bits), U(2,8 bits), U(3,8 bits))(idx)
    if (style == 0) {
      bit := Mux(use, selected, False)
      value := Mux(use, selectedValue, U(0,8 bits))
    } else if (style == 1) {
      bit := False; value := 0
      switch(use.asUInt) { is(U(1,1 bits)) { bit := selected; value := selectedValue } }
    } else {
      val mem = Mem(Bits(8 bits), 3)
      mem.initBigInt(Seq(BigInt(1),BigInt(2),BigInt(3)))
      val data = mem.readAsync(idx)
      bit := Mux(use, selected, False)
      value := Mux(use, data.asUInt, U(0,8 bits))
    }
  }
  for (style <- 0 to 2) test(s"intermediate use gating: expression mux, switch or async memory style=$style") {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/indirect"), ChecksConfig(mode = Mode.Monitor))
    val sim = SimConfig.withConfig(cfg).withVerilator.workspacePath("simWorkspace").workspaceName(s"indirect_$style").compile(new Indirect(style))
    for ((use, idx, expected) <- Seq((false,3,Set.empty[String]), (true,2,Set.empty[String]),
      (true,3,if (style == 2) Set("bits.index", "mem.index") else Set("bits.index", "vec.index")))) sim.doSim { d =>
      d.use #= use; d.idx #= idx; d.bits #= 5
      d.clockDomain.forkStimulus(10); d.clockDomain.waitSampling(8); d.clockDomain.waitFallingEdge()
      assert(ChecksSim.firings(d).map(_.check.kind).toSet == expected)
    }
  }
  class Domains extends Component {
    val bad = in Bool()
    val a = ClockDomain.external("a")
    val b = ClockDomain.external("b")
    val first = new ClockingArea(a) { DeclaredChecks.rule("domain.test", "a", "first domain")(bad) }
    val second = new ClockingArea(b) { DeclaredChecks.rule("domain.test", "b", "second domain")(bad) }
  }
  test("declared checks and monitor cycles use each binding clock domain") {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/domains"), ChecksConfig(mode = Mode.Monitor))
    SimConfig.withConfig(cfg).withVerilator.workspacePath("simWorkspace").workspaceName("domains").compile(new Domains).doSim { d =>
      d.bad #= false
      d.a.forkStimulus(10); d.b.forkStimulus(30)
      d.b.waitSampling(5)
      d.b.waitFallingEdge()
      assert(ChecksSim.firings(d).isEmpty)
      d.bad #= true
      d.b.waitSampling(6)
      d.b.waitFallingEdge()
      val fs = ChecksSim.firings(d).map(f => f.check.objName -> f).toMap
      assert(fs.keySet == Set("a", "b"))
      assert(fs("a").count >= 2 * fs("b").count)
      assert(fs("a").firstCycle > 2 * fs("b").firstCycle)
    }
  }

}
