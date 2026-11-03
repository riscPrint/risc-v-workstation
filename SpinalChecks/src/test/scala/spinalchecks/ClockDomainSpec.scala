package spinalchecks

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import java.nio.file.Files

class ClockDomainSpec extends AnyFunSuite {
  object State extends SpinalEnum(binarySequential) { val a, b, c = newElement() }
  class Top extends Component {
    val io = new Bundle {
      val otherClock, otherReset = in Bool()
      val bad = in Bool()
      val state, primary, value = out Bits(2 bits)
    }
    val primaryState = Reg(State()).init(State.a)
    primaryState := State.b
    io.primary := primaryState.asBits
    val other = ClockDomain(io.otherClock, io.otherReset,
      config = ClockDomainConfig(resetKind = ASYNC))
    val area = new ClockingArea(other) {
      val state = Reg(State()).init(State.a)
      state := State.b
      when(io.bad) { state.assignFromBits(B(3, 2 bits)) }
      io.state := state.asBits
      val index = Reg(UInt(2 bits)).init(0)
      when(io.bad) { index := 3 }
      io.value := Vec(B(0, 2 bits), B(1, 2 bits), B(2, 2 bits))(index)
    }
  }
  class MixedStream extends Top {
    val stream = spinal.lib.Stream(Bits(2 bits))
    stream.valid := True
    stream.payload := area.state.asBits
    stream.ready := True
  }
  test("refuse streams with ambiguous domains in a component") {
    val (config, _) = SpinalChecks.install(
      SpinalConfig(targetDirectory = Files.createTempDirectory("checks-mixed-").toString))
    val error = intercept[Throwable] { config.generateVerilog(new MixedStream) }
    assert(error.toString.contains("clock domain"))
  }
  test("enum checks and monitor state use the register clock and reset") {
    val dir = Files.createTempDirectory("checks-domains-")
    val (config, result) = SpinalChecks.install(
      SpinalConfig(targetDirectory = dir.toString).includeFormal,
      ChecksConfig(mode = Mode.Both))
    val top = config.generateVerilog(new Top).toplevel
    val check = result.records.find(r =>
      r.kind == Kind.EnumLegal && (r.signals("state").head eq top.area.state)).get
    assert(check.clockDomain eq top.other)
    val primary = result.records.find(r =>
      r.kind == Kind.EnumLegal && (r.signals("state").head eq top.primaryState)).get
    assert(primary.clockDomain eq top.clockDomain.get)
    val index = result.records.find(_.kind == Kind.VecIndex).get
    assert(index.clockDomain eq top.other)
    assert(check.fired.clockDomain eq top.other)
    assert(check.count.clockDomain eq top.other)
    assert(check.firstCycle.clockDomain eq top.other)
    val rtl = Files.readString(dir.resolve("Top.v"))
    val blocks = """(?s)always @\(([^)]*)\)(.*?)(?=\n  always|\nendmodule)""".r
    val properties = blocks.findAllMatchIn(rtl).filter(_.group(2).contains("assert(")).toSeq
    assert(properties.size >= 2)
    assert(properties.forall(!_.group(1).contains("Reset")))
    assert(properties.forall(!_.group(1).contains("reset")))
    val json = Report.json(result)
    assert(json.contains("\"clock_domain\""))
    assert(json.contains("\"clock\": \"io_otherClock\""))
    assert(json.contains("\"reset_kind\": \"ASYNC\""))
  }
}
