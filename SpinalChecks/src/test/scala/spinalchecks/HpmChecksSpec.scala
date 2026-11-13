package spinalchecks
import spinal.core._
import org.scalatest.funsuite.AnyFunSuite
class HpmChecksSpec extends AnyFunSuite with ApplicationTest {
  class Ref extends ApplicationRef {
    val count = Reg(UInt(4 bits)).init(0)
    when(permitted && !inhibit) { count := count + 1 }
    when(write) { count := data.asUInt }
    HpmChecks.bind("events", HpmModel(1, 4, 0, "one independently driven event each cycle"),
      count ^ Mux(corrupt, U(1, 4 bits), U(0, 4 bits)), U(1, 1 bits), inhibit, permitted, write, data.asUInt)
  }
  test("HPM legal inhibit, filter, writes and wrap; wrong count fires") {
    exercise("hpm_ref", Set("hpm.count"))(new Ref)
  }
  test("reject unsupported or ambiguous project intent") { intercept[IllegalArgumentException](HpmModel(1, 4, 0, "")) }
  class Masked extends ApplicationRef {
    val count = Reg(UInt(4 bits)).init(0)
    val inc = (count + 1).resized
    count := inc
    for(i <- 0 until 4) when(write && strobes(i)) { count(i) := data(i) }
    HpmChecks.bind("halves", HpmModel(1, 4, 0, "one event per cycle with masked software writes"),
      count ^ Mux(corrupt, U(1, 4 bits), U(0, 4 bits)), U(1, 1 bits), False, True,
      write, data.asUInt, strobes.asUInt)
  }
  test("masked counter writes preserve unselected increment and carry bits") {
    exercise("hpm_masked", Set("hpm.count"))(new Masked)
  }
  test("read activation counts only valid responses") {
    import spinal.core.sim._
    class ReadView extends Component {
      val valid = in Bool()
      val count = Reg(UInt(64 bits)).init(0)
      count := count + 1
      HpmChecks.bindHalfRead("read", count, False, count(31 downto 0).asBits, valid)
    }
    val (cfg, result) = SpinalChecks.install(SpinalConfig(targetDirectory="generated/hpm_activation",
      defaultConfigForClockDomains=ClockDomainConfig(resetKind=SYNC)), ChecksConfig(mode=Mode.Monitor))
    SimConfig.withConfig(cfg).workspacePath("simWorkspace").workspaceName("hpm_activation").withVerilator
      .compile(new ReadView).doSim(seed=17) { dut =>
        dut.valid #= false
        dut.clockDomain.forkStimulus(10)
        dut.clockDomain.waitSampling(8)
        dut.clockDomain.waitFallingEdge()
        val check=result.inserted.find(_.kind=="hpm.read").get
        assert(check.activationCount.toLong==0)
        dut.valid #= true
        dut.clockDomain.waitSampling(6)
        dut.clockDomain.waitFallingEdge()
        assert(check.activationCount.toLong>0)
        assert(ChecksSim.firings(dut).isEmpty)
      }
  }
}
