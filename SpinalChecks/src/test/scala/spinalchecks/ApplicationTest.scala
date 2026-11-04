package spinalchecks

import spinal.core._
import spinal.core.sim._
import org.scalatest.funsuite.AnyFunSuite

abstract class ApplicationRef extends Component {
  val corrupt = in Bool()
  val read, write, inhibit, permitted = in Bool()
  val data = in Bits(4 bits)
  val strobes, hwSet, hwClear = in Bits(4 bits)
  val privilege = in UInt(2 bits)
}
trait ApplicationTest { self: AnyFunSuite =>
  def exercise[T <: ApplicationRef](name: String, kinds: Set[String])(gen: => T): Unit = {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = s"generated/$name"), ChecksConfig(mode = Mode.Monitor))
    val sim = SimConfig.withConfig(cfg).withVerilator.workspacePath("simWorkspace").workspaceName(name).compile(gen)
    for (broken <- Seq(false, true)) sim.doSim(seed = 1) { d =>
      d.corrupt #= false; d.read #= false; d.write #= false; d.inhibit #= false; d.permitted #= true
      d.data #= 0; d.strobes #= 15; d.hwSet #= 0; d.hwClear #= 0; d.privilege #= 3
      d.clockDomain.forkStimulus(10)
      d.clockDomain.waitSampling(5)
      for (i <- 0 until 32) {
        d.clockDomain.waitFallingEdge()
        d.corrupt #= (broken && i >= 20)
        d.read #= (i % 3 != 1); d.write #= (i % 3 == 0)
        d.inhibit #= (i % 4 == 0); d.permitted #= (i % 5 != 0)
        d.data #= (i % 16); d.strobes #= (if (i % 2 == 0) 15 else 3)
        d.hwSet #= (if (i % 7 == 0) 8 else 0); d.hwClear #= (if (i % 6 == 0) 8 else 0)
        d.privilege #= (i % 4)
        d.clockDomain.waitSampling()
      }
      d.clockDomain.waitFallingEdge()
      val fired = ChecksSim.firings(d).map(_.check.kind).toSet
      assert(fired == (if (broken) kinds else Set.empty[String]), fired)
    }
  }
}
