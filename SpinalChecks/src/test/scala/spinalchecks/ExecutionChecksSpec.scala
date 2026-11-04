package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._

class ExecutionChecksSpec extends AnyFunSuite {
  class Ref(missingWake: Boolean = false) extends Component {
    val allocate, wake, issue, replay, writeback = in Bool()
    val allocateId, wakeId, issueId, replayId, writebackId = in UInt(2 bits)
    val initialReady, wakeMask = in Bits(2 bits)
    val cancel = in Bits(3 bits)
    ExecutionChecks.bind("pipe", 3, 2, allocate, allocateId, initialReady, if (missingWake) null else wake, wakeId, wakeMask,
      issue, issueId, replay, replayId, writeback, writebackId, cancel)
  }
  test("missing execution bindings refuse elaboration") {
    val error = intercept[Throwable] {
      SpinalConfig(targetDirectory = "generated/execution_missing").generateVerilog(new Ref(missingWake = true))
    }
    assert(error.toString.contains("incomplete execution binding"))
  }
  test("execution rules: legal readiness, wakeup, replay and cancellation; each illegal event fires") {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/execution_intent"), ChecksConfig(mode = Mode.Monitor))
    val sim = SimConfig.withConfig(cfg).withVerilator.workspacePath("simWorkspace").workspaceName("execution_intent").compile(new Ref)
    for (fault <- Seq("none", "allocate", "wakeup", "issue", "operands", "replay", "writeback", "late_writeback", "canceled_issue", "canceled_writeback", "wake_bypass", "duplicate_issue", "range")) sim.doSim(seed = 1) { d =>
      def inputs(event: String = "", id: Int = 0, mask: Int = 0): Unit = {
        d.allocate #= (event == "allocate"); d.wake #= (event == "wake"); d.issue #= (event == "issue")
        d.replay #= (event == "replay"); d.writeback #= (event == "writeback")
        d.allocateId #= id; d.wakeId #= id; d.issueId #= id; d.replayId #= id; d.writebackId #= id
        d.initialReady #= 1; d.wakeMask #= 2; d.cancel #= mask
      }
      inputs(); d.clockDomain.forkStimulus(10); d.clockDomain.waitSampling(5)
      def step(event: String = "", id: Int = 0, mask: Int = 0): Unit = {
        d.clockDomain.waitFallingEdge(); inputs(event, id, mask); d.clockDomain.waitSampling()
      }
      step("allocate"); step("wake"); step("issue"); step("replay"); step("issue"); step("writeback")
      step("allocate", 1); step(mask = 2); step()
      assert(ChecksSim.firings(d).isEmpty)
      fault match {
        case "allocate" => step("allocate"); step("allocate")
        case "wakeup" => step("wake", 2)
        case "issue" => step("issue", 2)
        case "operands" => step("allocate"); step("issue")
        case "replay" => step("allocate"); step("replay")
        case "writeback" => step("allocate"); step("writeback")
        case "late_writeback" => step("allocate"); step("wake"); step("issue"); step(mask = 1); step("writeback")
        case "canceled_issue" => step("allocate"); step("wake"); step("issue", mask = 1)
        case "canceled_writeback" => step("allocate"); step("wake"); step("issue"); step("writeback", mask = 1)
        case "wake_bypass" =>
          step("allocate")
          d.clockDomain.waitFallingEdge(); inputs("issue"); d.wake #= true; d.clockDomain.waitSampling()
        case "duplicate_issue" => step("allocate"); step("wake"); step("issue"); step("issue")
        case "range" => step("allocate", 3)
        case _ => step()
      }
      step(); d.clockDomain.waitFallingEdge()
      val kind = fault match {
        case "none" => Set.empty[String]
        case "late_writeback" => Set("execution.writeback")
        case "canceled_issue" => Set("execution.issue")
        case "canceled_writeback" => Set("execution.writeback")
        case "wake_bypass" => Set("execution.operands")
        case "duplicate_issue" => Set("execution.issue")
        case "range" => Set("execution.allocate")
        case x => Set(s"execution.$x")
      }
      assert(ChecksSim.firings(d).map(_.check.kind).toSet == kind, fault)
    }
  }
}
