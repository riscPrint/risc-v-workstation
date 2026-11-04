package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._

class ResetChecksSpec extends AnyFunSuite {
  class Ref extends Component {
    val request, reset, edge, known, src, dst, isolated, consume, other = in Bool()
    val earlier, later = in Bool()
    ResetChecks.order("order", earlier, later)
    ResetChecks.bind("reset", request, reset, edge, known, 2)
    ResetChecks.crossing("cross", src, dst, isolated, consume)
    ResetChecks.reconvergence("merge", src, other, isolated, consume)
  }
  test("rdc independent observations: legal traffic and injected faults") {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/Reset"), ChecksConfig(mode = Mode.Monitor))
    val sim = SimConfig.withConfig(cfg).withVerilator.workspacePath("simWorkspace").workspaceName("Reset").compile(new Ref)
    for (fault <- Seq("none", "rdc.assertion", "rdc.release", "rdc.unknown_control", "rdc.isolation", "rdc.reconvergence_protocol", "rdc.release_order")) sim.doSim(seed = 1) { d =>
      d.earlier #= false; d.later #= true
      d.request #= true; d.reset #= true; d.edge #= false; d.known #= true
      d.src #= true; d.dst #= true; d.other #= true; d.isolated #= true; d.consume #= false
      d.clockDomain.forkStimulus(10); d.clockDomain.waitSampling(5); d.clockDomain.waitFallingEdge()
      def tick(): Unit = { d.clockDomain.waitSampling(); d.clockDomain.waitFallingEdge() }
      d.request #= false; d.edge #= true; tick(); tick(); tick(); d.reset #= false; tick()
      fault match {
        case "rdc.release_order" => d.earlier #= true; d.later #= false
        case "rdc.assertion" => d.request #= true
        case "rdc.release" => d.reset #= true; tick(); d.reset #= false; d.edge #= false
        case "rdc.unknown_control" => d.known #= false
        case "rdc.isolation" => d.dst #= false; d.isolated #= false; d.consume #= true
        case "rdc.reconvergence_protocol" => d.other #= false; d.isolated #= false; d.consume #= true
        case _ =>
      }
      tick()
      for (_ <- 0 until 4) tick()
      val fired = ChecksSim.firings(d).map(_.check.kind).toSet
      assert(fired == (if (fault == "none") Set.empty[String] else Set(fault)), fired)
    }
  }
}
