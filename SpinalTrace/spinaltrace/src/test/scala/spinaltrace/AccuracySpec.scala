package spinaltrace
import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.internals._
import spinaltrace.examples._

class AccuracySpec extends AnyFunSuite {
  private def extract(gen: => Component, maxWords: Int = 4096): PdgModel.Pdg = {
    val dir = Files.createTempDirectory("trace-accuracy").toFile
    val report = SpinalTrace.elaborate(SpinalConfig(targetDirectory = dir.getPath))(gen)
    PdgExtractor.extract(report, ExtractOptions(maxMemWords = maxWords))
  }
  test("two clocks, clock enables and soft resets have explicit limits") {
    assert(extract(new TwoClockDomains).meta.warnings.exists(_.contains("clock domains")))
    val enabled = extract(new EnabledState)
    assert(enabled.meta.warnings.exists(_.contains("clock enable")))
    assert(enabled.meta.warnings.exists(_.contains("soft reset")))
  }
  test("masked, mixed-width and coarse memories cannot claim exact attribution") {
    assert(extract(new MaskedMemory).meta.warnings.exists(_.contains("write masks")))
    // Spinal's Verilog backend refuses this valid mixed-width netlist before extraction.
    intercept[SpinalExit] { extract(new MixedMemory) }
    val dir = Files.createTempDirectory("trace-mixed").toFile
    val report = SpinalTrace.elaborate(SpinalConfig(targetDirectory = dir.getPath))(new MaskedMemory)
    report.toplevel.dslBody.walkStatements {
      case w: MemWrite => w.data = report.toplevel.io.mask
      case _ =>
    }
    assert(PdgExtractor.extract(report).meta.warnings.exists(_.contains("mixed-width write")))
    assert(extract(new LargeMemory).meta.warnings.exists(_.contains("8192 words")))
    assert(extract(new MaskedMemory, 2).meta.warnings.exists(_.contains("one symbol")))
  }
  test("asynchronous writes cannot claim exact read-side attribution") {
    if (!classOf[Mem[Bits]].getMethods.exists(_.getName == "readAsyncWrite"))
      cancel("The selected SpinalHDL has no Mem.readAsyncWrite API.")
    assert(extract(new AsyncWriteMemory).meta.warnings.exists(_.contains("read side")))
  }
  test("more than 16 partial providers and statements on one line remain visible") {
    assert(extract(new ManyPartialWrites).vertices.count(_.assignRange.contains("dyn")) >= 20)
    val pdg = extract(new SameLine)
    assert(pdg.vertices.groupBy(v => (v.loc.file, v.loc.line)).values.exists(_.count(v => v.kind == "Connection" || v.kind == "DataDefinition") >= 2))
    assert(PdgModel.toJson(pdg)("spinaltrace")("formatVersion").num == 2)
  }
  test("unsupported raw switch keys produce an incomplete extraction") {
    val dir = Files.createTempDirectory("trace-key").toFile
    val report = SpinalTrace.elaborate(SpinalConfig(targetDirectory = dir.getPath))(new ExpressionSwitch)
    val raw = Netlist.assignments(report.toplevel.keyExpr).head.asInstanceOf[DataAssignmentStatement].source
    report.toplevel.dslBody.walkStatements {
      case sw: SwitchStatement => sw.elements.head.keys(0) = raw
      case _ =>
    }
    val pdg = PdgExtractor.extract(report)
    assert(pdg.meta.warnings.exists(_.contains("unsupported switch key")))
    assert(PdgModel.toJson(pdg)("accuracy")("status").str == "incomplete")
    report.toplevel.dslBody.walkStatements {
      case sw: SwitchStatement => sw.value = raw
      case _ =>
    }
    assert(PdgExtractor.extract(report).meta.warnings.exists(_.contains("all cases treated as active")))
  }

}
