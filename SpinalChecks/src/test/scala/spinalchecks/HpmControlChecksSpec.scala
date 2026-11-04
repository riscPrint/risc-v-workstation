package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._

class HpmControlChecksSpec extends AnyFunSuite {
  class Ref extends Component {
    val selector, selectorData = in Bits(4 bits)
    val selectorWrite, inhibit, permitted, counterWrite, clear, enabled, pending, irq = in Bool()
    val count, events = in UInt(4 bits)
    HpmControlChecks.selector("selector", selector, selectorWrite, selectorData, 3)
    HpmControlChecks.interrupt("overflow", 4, count, events, inhibit, permitted, counterWrite, clear, enabled, pending, irq)
  }
  test("hpm independent observations: legal traffic and injected faults") {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/HpmControl"), ChecksConfig(mode = Mode.Monitor))
    val sim = SimConfig.withConfig(cfg).withVerilator.workspacePath("simWorkspace").workspaceName("HpmControl").compile(new Ref)
    for (fault <- Seq("none", "hpm.selector", "hpm.overflow_pending", "hpm.counter_interrupt")) sim.doSim(seed = 1) { d =>
      d.selector #= 0; d.selectorData #= 15; d.selectorWrite #= false; d.inhibit #= false; d.permitted #= true
      d.counterWrite #= false; d.clear #= false; d.enabled #= true; d.pending #= false; d.irq #= false
      d.count #= 0; d.events #= 0
      d.clockDomain.forkStimulus(10); d.clockDomain.waitSampling(5); d.clockDomain.waitFallingEdge()
      def tick(): Unit = { d.clockDomain.waitSampling(); d.clockDomain.waitFallingEdge() }
      d.selectorWrite #= true; tick(); d.selectorWrite #= false; d.selector #= 3
      // Independent oracle operands wrap 15 + 1. Each suppression blocks overflow.
      d.count #= 15; d.events #= 1; d.inhibit #= true; tick(); tick()
      d.inhibit #= false; d.permitted #= false; tick(); tick()
      d.permitted #= true; d.counterWrite #= true; tick(); tick()
      d.counterWrite #= false; d.clear #= true; tick(); tick()
      d.clear #= false; tick()
      d.count #= 0; d.events #= 0; d.pending #= true; d.irq #= true; tick(); tick()
      d.enabled #= false; d.irq #= false; tick()
      // Clear an already pending overflow, then exercise another overflow.
      d.clear #= true; tick(); d.pending #= false; tick()
      d.clear #= false; d.count #= 15; d.events #= 1; tick()
      d.count #= 0; d.events #= 0; d.pending #= true; tick()
      fault match {
        case "hpm.selector" => d.selector #= 15
        case "hpm.overflow_pending" => d.pending #= false
        case "hpm.counter_interrupt" => d.irq #= true
        case _ =>
      }
      tick()
      for (_ <- 0 until 4) tick()
      val fired = ChecksSim.firings(d).map(_.check.kind).toSet
      assert(fired == (if (fault == "none") Set.empty[String] else Set(fault)), fired)
    }
  }
}
