package riscvsim
import spinal.core._
import org.scalatest.funsuite.AnyFunSuite
import java.nio.file.Files
class RtlCoverageSpec extends AnyFunSuite {
  class UnitTop extends Component {
    val io = new Bundle { val value = in UInt(2 bits); val result = out UInt(2 bits) }
    io.result := RegNext(io.value) init(0)
    val internalEvent = Bool().setName("internal_event")
    internalEvent := io.value === 1
    RtlCoverage.tag(internalEvent, RtlCoverage.Bin("internal", "event", "structural", Seq(BigInt(1)),
      RtlCoverage.Source("Fixture.scala", 8), "Bool"))
    Seq("event", "occupancy", "state", "transition", "arbitration").foreach { kind =>
      RtlCoverage.tag(io.result, RtlCoverage.Bin(kind, kind, "speculative", Seq(BigInt(1)),
        RtlCoverage.Source("Fixture.scala", 7), "UInt[2]",
        if (kind == "transition") Seq(BigInt(0)) else Nil))
    }
  }
  test("export all tag kinds with stable exact paths and source links") {
    val report = SpinalConfig(targetDirectory = Files.createTempDirectory("rtl-tags").toString).generateVerilog(new UnitTop)
    val p = RtlCoverage.plan(report, "fixture", report.toplevel.clockDomain.clock, report.toplevel.clockDomain.reset)
    assert(p("bins").arr.size == 6)
    assert(p("bins").arr.forall(_("id").str.startsWith("TOP:")))
    assert(p("signals")("TOP.io_result")("scala")("line").num == 7)
    assert(p == RtlCoverage.plan(report, "fixture", report.toplevel.clockDomain.clock, report.toplevel.clockDomain.reset))
    Files.writeString(java.nio.file.Paths.get("/tmp/cov2-tags-plan.json"), ujson.write(p))
  }
  test("deduplicated child modules retain separate bin IDs") {
    class Pair extends Component {
      val io = new Bundle { val input = in UInt(2 bits); val result = out UInt(2 bits) }
      val a = new UnitTop
      val b = new UnitTop
      a.io.value := io.input
      b.io.value := io.input
      io.result := a.io.result ^ b.io.result
    }
    val report = SpinalConfig(targetDirectory = Files.createTempDirectory("rtl-tag-pair").toString).generateVerilog(new Pair)
    val p = RtlCoverage.plan(report, "pair", report.toplevel.clockDomain.clock, report.toplevel.clockDomain.reset)
    val ids = p("bins").arr.map(_("id").str)
    assert(ids.size == 12 && ids.distinct.size == 12)
    assert(ids.contains("TOP.a:internal") && ids.contains("TOP.b:internal"))
  }
}
