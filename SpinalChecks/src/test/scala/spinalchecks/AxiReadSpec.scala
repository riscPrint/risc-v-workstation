package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinal.lib.bus.amba4.axi._

class AxiReadSpec extends AnyFunSuite {
  class Top(options: Boolean) extends Component {
    val p = Axi4Config(32, 32, idWidth = 2, readIssuingCapability = 4, combinedIssuingCapability = 4)
    val bus = in(Axi4ReadOnly(if (!options) p else p.copy(useId = false, useLen = false,
      useLast = false, useSize = false, useResp = false, useLock = false)))
  }
  lazy val compiled = {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/axi-read"), ChecksConfig(mode = Mode.Monitor))
    SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName("axi-read").withVerilator.compile(new Top(false))
  }
  def run(fault: String): Set[String] = {
    var hits = Set.empty[String]
    compiled.doSim { dut =>
      dut.bus.flatten.foreach {
        case b: Bool => b #= false
        case b: Bits => b #= 0
        case u: UInt => u #= 0
        case _ =>
      }
      val ar = dut.bus.ar; val r = dut.bus.r
      ar.ready #= true; r.ready #= true
      ar.size #= 2; ar.burst #= 1
      dut.clockDomain.forkStimulus(10); dut.clockDomain.waitSampling(4)
      def step(): Unit = dut.clockDomain.waitFallingEdge()
      step(); ar.valid #= true; ar.id #= 0; ar.len #= 1
      step(); ar.id #= 1; ar.len #= 0
      step(); ar.valid #= false
      r.valid #= true; r.id #= (if (fault == "orphan") 2 else 1); r.last #= true
      if (fault == "exokay") r.resp #= 1
      if (fault == "slverr") r.resp #= 2
      if (fault == "decerr") r.resp #= 3
      step(); r.valid #= false; r.resp #= 0
      step(); r.valid #= true; r.id #= 0; r.last #= (fault == "early")
      step(); r.last #= true
      step(); r.valid #= false
      dut.clockDomain.waitSampling(3)
      hits = ChecksSim.firings(dut).map(_.check.kind).toSet
    }
    hits
  }
  test("AXI4 responses can reorder IDs but keep each ID's burst length") { assert(run("clean").isEmpty) }
  test("SLVERR and DECERR are legal response errors") {
    assert(run("slverr").isEmpty); assert(run("decerr").isEmpty)
  }
  test("omitted ID, length, last, size, lock and response fields use their declared semantics") {
    val (cfg, _) = SpinalChecks.install(SpinalConfig(targetDirectory = "generated/axi-options"), ChecksConfig(mode = Mode.Monitor))
    SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName("axi-options").withVerilator
      .compile(new Top(true)).doSim { dut =>
        SimTimeout(2000)
        dut.bus.flatten.foreach {
          case b: Bool => b #= false
          case b: Bits => b #= 0
          case u: UInt => u #= 0
          case _ =>
        }
        val ar = dut.bus.ar; val r = dut.bus.r
        ar.ready #= true; ar.burst #= 1
        dut.clockDomain.forkStimulus(10); dut.clockDomain.waitSampling(4)
        dut.clockDomain.waitFallingEdge(); ar.valid #= true
        dut.clockDomain.waitFallingEdge(); ar.valid #= false; r.valid #= true
        dut.clockDomain.waitFallingEdge(2); r.ready #= true
        dut.clockDomain.waitFallingEdge(); r.valid #= false
        dut.clockDomain.waitSampling(3)
        assert(ChecksSim.firings(dut).isEmpty)
      }
  }
  test("AXI4 orphan ID, early last and EXOKAY without exclusive each fire") {
    for (f <- Seq("orphan", "early", "exokay")) assert(run(f).contains("axi4.read_match"), f)
  }
}
