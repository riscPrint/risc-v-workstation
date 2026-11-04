package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._

class IntentChecksSpec extends AnyFunSuite {
  private def config(name: String) = {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = s"generated/$name"), ChecksConfig(mode = Mode.Monitor))
    SimConfig.withConfig(cfg).withVerilator.workspacePath("simWorkspace").workspaceName(name)
  }
  private def fired(d: Component) = ChecksSim.firings(d).map(_.check.kind).toSet

  class QueueRef extends Component {
    val push, pop, flush = in Bool()
    val pushed, popped = in Bits(8 bits)
    val occupancy = in UInt(2 bits)
    QueueChecks.fifo("fifo", 3, push, pop, flush, pushed, popped, occupancy)
  }
  test("queue rules: legal wraparound, simultaneous transfers, flush; each illegal transfer fires") {
    val sim = config("intent_queue").compile(new QueueRef)
    for (fault <- Seq("none", "underflow", "overflow", "occupancy", "order")) sim.doSim(seed = 1) { d =>
      d.push #= false; d.pop #= false; d.flush #= false
      d.pushed #= 0; d.popped #= 0; d.occupancy #= 0
      d.clockDomain.forkStimulus(10); d.clockDomain.waitSampling(5)
      var q = Vector.empty[Int]
      def step(push: Option[Int] = None, pop: Boolean = false, flush: Boolean = false, bad: Boolean = false): Unit = {
        d.clockDomain.waitFallingEdge()
        d.push #= push.nonEmpty; d.pop #= pop; d.flush #= flush
        d.pushed #= push.getOrElse(0)
        d.popped #= (if (bad && fault == "order") 255 else q.headOption.getOrElse(0))
        d.occupancy #= (if (bad && fault == "occupancy") (q.size + 1) % 4 else q.size)
        d.clockDomain.waitSampling()
        if (flush) q = Vector.empty
        else if (!(pop && q.isEmpty) && !(push.nonEmpty && !pop && q.size == 3)) {
          if (pop) q = q.tail
          push.foreach(x => q = q :+ x)
        }
      }
      step(Some(1)); step(Some(2)); step(Some(3))
      if (fault == "overflow") step(Some(4), bad = true)
      for (i <- 4 to 12) step(Some(i), pop = true)
      step(pop = true, bad = fault == "order")
      step(pop = true); step(pop = true)
      if (fault == "underflow") step(pop = true)
      step(Some(20)); step(bad = fault == "occupancy")
      step(Some(21), pop = true, flush = true)
      step(Some(22)); step(pop = true); step()
      d.clockDomain.waitFallingEdge()
      val expected = fault match {
        case "none" => Set.empty[String]
        case "underflow" | "overflow" => Set("queue.capacity")
        case x => Set(s"queue.$x")
      }
      assert(fired(d) == expected, s"$fault: ${fired(d)}")
    }
  }
  class ArbiterRef extends Component {
    val requests, grants = in Bits(3 bits)
    QueueChecks.arbiter("arb", requests, grants)
  }
  test("arbiter rules: legal idle and single grants; illegal multiple or unrequested grants") {
    val sim = config("intent_arbiter").compile(new ArbiterRef)
    for ((req, grant, expected) <- Seq((0,0,Set.empty[String]), (7,4,Set.empty[String]),
      (7,3,Set("arbiter.exclusive")), (1,2,Set("arbiter.requested")))) sim.doSim { d =>
      d.requests #= req; d.grants #= grant
      d.clockDomain.forkStimulus(10); d.clockDomain.waitSampling(8); d.clockDomain.waitFallingEdge()
      assert(fired(d) == expected)
    }
  }
  class StateRef extends Component {
    val state = in UInt(2 bits)
    val initialized, active = in Bool()
    val selected = in Bits(3 bits)
    StateChecks.machine("fsm", state, initialized, Seq(BigInt(0),BigInt(1),BigInt(2)),
      Seq((0,0),(0,1),(1,1),(1,2),(2,2),(2,0)).map { case (a,b) => (BigInt(a),BigInt(b)) })
    StateChecks.branches("branches", active, selected, required = true)
  }
  test("state rules: initialization, encoding, transition, branch exclusion and required case") {
    val sim = config("intent_state").compile(new StateRef)
    for (fault <- Seq("none", "encoding", "transition", "exclusive", "required")) sim.doSim { d =>
      d.state #= 3; d.initialized #= false; d.active #= false; d.selected #= 7
      d.clockDomain.forkStimulus(10); d.clockDomain.waitSampling(5)
      def step(state: Int, initialized: Boolean, active: Boolean = true, branches: Int = 1): Unit = {
        d.clockDomain.waitFallingEdge(); d.state #= state; d.initialized #= initialized
        d.active #= active; d.selected #= branches; d.clockDomain.waitSampling()
      }
      step(0, true); step(1, true); step(2, true); step(0, true)
      assert(fired(d).isEmpty)
      fault match {
        case "encoding" => step(0, false); step(3, true); step(0, false, false)
        case "transition" => step(2, true)
        case "exclusive" => step(0, true, branches = 3)
        case "required" => step(0, true, branches = 0)
        case _ => step(0, true)
      }
      d.clockDomain.waitFallingEdge()
      assert(fired(d) == (if (fault == "none") Set.empty[String] else Set(s"state.$fault")), s"$fault: ${fired(d)}")
    }
  }
  class ValueRef(modular: Boolean) extends Component {
    val active = in Bool()
    val value = in SInt(6 bits)
    val narrowed = in SInt(4 bits)
    ValueChecks.range("range", active, value, -8, 7)
    ValueChecks.narrowing("cast", active, value, narrowed, modular)
  }
  test("value rules: signed boundaries, inactive values, overflow, underflow and truncation") {
    val sim = config("intent_value").compile(new ValueRef(false))
    for ((value, narrow, active, expected) <- Seq(
      (-8,-8,true,Set.empty[String]), (7,7,true,Set.empty[String]),
      (31,0,false,Set.empty[String]), (8,-8,true,Set("value.overflow","value.truncation")),
      (-9,7,true,Set("value.underflow","value.truncation")), (1,2,true,Set("value.truncation")))) sim.doSim { d =>
      d.active #= active; d.value #= value; d.narrowed #= narrow
      d.clockDomain.forkStimulus(10); d.clockDomain.waitSampling(8); d.clockDomain.waitFallingEdge()
      assert(fired(d) == expected)
    }
  }
  test("declared modular arithmetic permits lost high bits but checks the low bits") {
    val sim = config("intent_modular").compile(new ValueRef(true))
    for ((narrow, expected) <- Seq((-8,Set("value.overflow")), (-7,Set("value.overflow","value.truncation")))) sim.doSim { d =>
      d.active #= true; d.value #= 8; d.narrowed #= narrow
      d.clockDomain.forkStimulus(10); d.clockDomain.waitSampling(8); d.clockDomain.waitFallingEdge()
      assert(fired(d) == expected)
    }
  }
}
