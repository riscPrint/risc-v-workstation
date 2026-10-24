package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._

/** Index/enum checks on registers without a reset value are armed by writes (review 2026-10-21). */
class ArmingSpec extends AnyFunSuite {

  /** From the review (/tmp/review-design-sol/ReviewChecksProbe.scala): `idx` has no reset value, is
    * written 0 every cycle and 3 (out of range for a 3-element Vec) for one cycle; `idx2` the same,
    * written only in `when` scopes. `cold` has no reset
    * value and is written only when `io.wcold` is high, which the test never does. */
  class Arming extends Component {
    val io = new Bundle {
      val start, wcold = in Bool()
      val y, z, y2 = out UInt(8 bits)
    }
    val idx = Reg(UInt(2 bits))
    idx := 0
    when(io.start) { idx := 3 }
    val table = Vec(U(10, 8 bits), U(20, 8 bits), U(30, 8 bits))
    io.y := table(idx)

    // written only in nested scopes: 3 for one cycle, then back to 0
    val idx2 = Reg(UInt(2 bits))
    when(io.start) { idx2 := 3 } otherwise { when(idx2 === 3) { idx2 := 0 } }
    io.y2 := table(idx2)

    val cold = Reg(UInt(2 bits)).simPublic()
    when(io.wcold) { cold := 1 }
    val table2 = Vec(U(1, 8 bits), U(2, 8 bits), U(3, 8 bits))
    io.z := table2(cold)
  }

  def run(name: String)(body: Arming => Unit): Set[String] = {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = s"generated/arming_$name"),
      ChecksConfig(mode = Mode.Monitor))
    var fired = Set.empty[String]
    SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName(s"arming_$name").withVerilator
      .compile(new Arming).doSim(seed = 42) { dut =>
        dut.io.start #= false
        dut.io.wcold #= false
        dut.cold #= 3 // an illegal power-up value; never written
        dut.clockDomain.forkStimulus(10)
        body(dut)
        dut.clockDomain.waitSampling(8)
        fired = ChecksSim.firings(dut).map(_.check.id).toSet
      }
    fired
  }

  test("the first written illegal value fires; an unwritten register's power-up value does not") {
    val fired = run("first") { dut =>
      dut.clockDomain.waitSampling(8)
      dut.clockDomain.waitFallingEdge()
      dut.io.start #= true
      dut.clockDomain.waitSampling()
      dut.clockDomain.waitFallingEdge()
      dut.io.start #= false
    }
    assert(fired == Set("vec.index:idx_of3", "vec.index:idx2_of3"), fired)
  }

  test("nothing fires while only legal values are written") {
    val fired = run("quiet") { dut => dut.clockDomain.waitSampling(20) }
    assert(fired.isEmpty, fired)
  }
}
