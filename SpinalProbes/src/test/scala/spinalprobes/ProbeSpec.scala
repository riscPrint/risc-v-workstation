package spinalprobes

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._

class Tiny extends Component {
  val io = new Bundle {
    val a = in UInt(8 bits)
    val go = in Bool()
    val y = out UInt(8 bits)
  }
  val r = Reg(UInt(8 bits)) init(0)
  when(io.go) {
    r := io.a
    // Calls inside a when still create unconditional copies.
    Probe.branch("bp", io.go, io.a, io.a(0), io.a + 4, predictedTaken = Some(io.a(1)))
  }
  Probe.counter("go", io.go, hpm = Some(3))
  Probe.stall("issue", "operand_wait", !io.go)
  Probe.faultSite("r", r)
  io.y := r
}

class ProbeSpec extends AnyFunSuite {
  private def verilog(enable: Boolean): (String, Seq[ProbeSite]) = {
    val dir = Files.createTempDirectory("spinalprobes").toFile
    val report = Probe.enabled(enable) { SpinalConfig(targetDirectory = dir.getPath).generateVerilog(new Tiny) }
    val text = new String(Files.readAllBytes(new java.io.File(dir, "Tiny.v").toPath))
    (text, Probe.of(report.toplevel))
  }

  test("disabled probes add no hardware") {
    val (text, sites) = verilog(enable = false)
    assert(!text.contains("rvwprobe"))
    assert(sites.isEmpty)
    assert(!Probe.isEnabled)
  }

  test("enabled probes create named public wires and register sites") {
    val (text, sites) = verilog(enable = true)
    assert(sites.map(_.kind) == Seq("branch", "counter", "stall", "fault"))
    val bp = sites.head
    assert(bp.fields.map(_._1) == Seq("pc", "taken", "target", "predicted_taken"))
    assert(bp.meta("semantics") == "final-prediction")
    for (n <- Seq("rvwprobe__branch__bp__valid", "rvwprobe__branch__bp__pc", "rvwprobe__counter__go__inc",
        "rvwprobe__stall__issue_operand_wait__valid"))
      assert(text.contains(n), n)
    assert(sites(1).meta("hpm") == "3")
    assert(!Probe.isEnabled)
  }

  test("names are cleaned and kinds checked") {
    assert(Probe.clean("d-cache.fill") == "d_cache_fill")
    assertThrows[IllegalArgumentException](Probe.enabled(true)(Probe.site("Bad", "x", null, Nil)))
  }
}
