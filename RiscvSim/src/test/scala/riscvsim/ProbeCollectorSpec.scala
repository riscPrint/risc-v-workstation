package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import spinalprobes.Probe

class ProbeDut extends Component {
  val io = new Bundle { val go = in Bool(); val pc = in UInt(32 bits) }
  val n = Reg(UInt(8 bits)) init(0)
  n := n + 1
  Probe.branch("bp", io.go, io.pc, n(0), io.pc + 8, predictedTaken = Some(n(1)))
  Probe.counter("go", io.go)
  Probe.counter("sum", n.resize(4 bits))
  Probe.stall("issue", "operand_wait", !io.go)
}

class ProbeCollectorSpec extends AnyFunSuite {
  test("samples events, sums counters and writes the end record") {
    val dir = Files.createTempDirectory("probes").toFile
    val file = new java.io.File(dir, "probe-events.jsonl")
    val compiled = Probe.enabled(true) {
      SimConfig.workspacePath(dir.getPath).compile(new ProbeDut)
    }
    compiled.doSim { dut =>
      val sites = Probe.of(dut)
      assert(sites.size == 4)
      val c = new ProbeCollector(sites, file, ujson.Obj("elf_sha256" -> "ab"))
      dut.clockDomain.forkStimulus(10)
      dut.io.go #= false
      dut.io.pc #= 0x80000000L
      dut.clockDomain.waitSampling()
      var cycle = 0L
      dut.clockDomain.onSamplings { c.sample(cycle); cycle += 1 }
      for (i <- 0 until 6) { dut.io.go #= (i % 2 == 0); dut.io.pc #= 0x80000000L + 4 * i; dut.clockDomain.waitSampling() }
      dut.clockDomain.waitSampling()
      c.close(cycle)
    }
    val lines = scala.io.Source.fromFile(file).getLines().toVector
    val header = ujson.read(lines.head)
    assert(header("schema").str == "rvw.probe-events/1")
    assert(header("probes").arr.map(_("kind").str) == Seq("branch", "counter", "counter", "stall"))
    assert(header("probes")(0)("fields").arr.map(_(0).str) == Seq("pc", "taken", "target", "predicted_taken"))
    val rows = lines.tail.init.map(ujson.read(_))
    val branches = rows.filter(_(1).num == 0)
    assert(branches.nonEmpty && branches.forall(r => r.arr.size == 6))
    assert(branches.forall(r => r(4).num.toLong == r(2).num.toLong + 8))
    val end = ujson.read(lines.last)
    assert(end("end").bool)
    assert(end("counters")("go").num == branches.size)
    assert(rows.count(_(1).num == 3) + branches.size == end("cycles").num.toLong)
  }

  test("disabled elaboration has no probes") {
    val dir = Files.createTempDirectory("probes-off").toFile
    val report = SpinalConfig(targetDirectory = dir.getPath).generateVerilog(new ProbeDut)
    assert(Probe.of(report.toplevel).isEmpty)
  }
}
