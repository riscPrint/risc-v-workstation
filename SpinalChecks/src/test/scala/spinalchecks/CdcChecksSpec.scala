package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib._

class CdcChecksSpec extends AnyFunSuite {
  /** A 3-bit counter crosses through BufferCC as Gray (legal) or binary (fault). A one-bit level
    * crosses from a 4x faster clock; `fast` toggles it every cycle (fault). */
  class Ref(gray: Boolean) extends Component {
    val clkA, clkB = in Bool()
    val fast = in Bool()
    val out3 = out Bits(3 bits)
    val out1 = out Bool()
    val cdA = ClockDomain(clkA, config = ClockDomainConfig(resetKind = BOOT), frequency = FixedFrequency(400 MHz))
    val cdB = ClockDomain(clkB, config = ClockDomainConfig(resetKind = BOOT), frequency = FixedFrequency(100 MHz))
    val a = new ClockingArea(cdA) {
      val count = Reg(UInt(3 bits)).init(0)
      count := count + 1
      val code = RegNext(if (gray) (count ^ (count |>> 1)).asBits else count.asBits).init(0)
      val slow = Reg(UInt(4 bits)).init(0)
      slow := slow + 1
      val level = RegNext(Mux(fast, count(0), slow.msb)).init(False)
    }
    val b = new ClockingArea(cdB) {
      out3 := BufferCC(a.code, B(0, 3 bits))
      out1 := BufferCC(a.level, False)
    }
  }

  test("clock-domain checks: gray and pulse width, legal and faults") {
    for ((gray, short) <- Seq((true, false), (false, false), (true, true))) {
      val (cfg, result) = SpinalChecks.install(
        CdcChecks.install(SpinalConfig(targetDirectory = "generated/Cdc")), ChecksConfig(mode = Mode.Monitor))
      val sim = SimConfig.withConfig(cfg).withVerilator.workspacePath("simWorkspace")
        .workspaceName(s"Cdc_${gray}_$short").compile(new Ref(gray))
      assert(CdcChecks.found.map(_.kind).toSet == Set("cdc.gray", "cdc.pulse_width"))
      assert(result.records.map(_.kind).toSet.contains("cdc.gray"))
      sim.doSim(seed = 1) { d =>
        d.fast #= short
        d.cdA.forkStimulus(10)
        d.cdB.forkStimulus(40)
        d.cdA.waitSampling(100)
        val fired = ChecksSim.firings(d).map(_.check.kind).toSet
        val expected = Set[String]() ++ (if (gray) Nil else Seq("cdc.gray")) ++ (if (short) Seq("cdc.pulse_width") else Nil)
        assert(fired == expected, s"gray=$gray short=$short fired=$fired")
      }
    }
  }
}
