package riscvsim

import java.io.File
import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._

class RtlIdentitySpec extends AnyFunSuite {
  test("the JSON options envelope is only valid for identity") {
    intercept[Cli.UsageError] { Cli.parse(Seq("--options", "{}")) }
    assert(Cli.parse(Seq("--options", "{}"), identity = true)("options") == "{}")
    intercept[Cli.UsageError] { Cli.fromJson(ujson.Obj("options" -> "{}")) }
  }

  class Monitor(path: String) extends BlackBox {
    val io = new Bundle { val value = out Bool() }
    setDefinitionName("IdentityMonitor")
    addRTLPath(path)
  }
  class Top(path: String) extends Component {
    val value = out Bool()
    value := new Monitor(path).io.value
  }

  test("the single emitted file includes blackbox bytes and binds monitor changes") {
    val work = Files.createTempDirectory("riscvsim-rtl-identity").toFile
    val monitor = new File(work, "monitor.v")
    try {
      def emit(value: Int, name: String): Array[Byte] = {
        Files.writeString(monitor.toPath, s"module IdentityMonitor(output io_value); assign io_value = 1'b$value; endmodule\n")
        val report = RiscvSimConfig.elaborate(ModelKey(name), work, SpinalConfig())(new Top(monitor.getPath))
        assert(report.generatedSourcesPaths.size == 1)
        assert(report.blackboxesSourcesPaths.isEmpty)
        Files.readAllBytes(new File(report.generatedSourcesPaths.head).toPath)
      }
      val first = emit(0, "first")
      val second = emit(1, "second")
      assert(new String(first).contains("assign io_value = 1'b0"))
      assert(new String(second).contains("assign io_value = 1'b1"))
      assert(ElfFile.sha256(first) != ElfFile.sha256(second))
    } finally org.apache.commons.io.FileUtils.deleteDirectory(work)
  }

  test("external RTL include and memory data dependencies refuse identity") {
    val work = Files.createTempDirectory("riscvsim-rtl-dependencies").toFile
    val monitor = new File(work, "monitor.v")
    try {
      for ((text, i) <- Seq("`include \"external.v\"", "$readmemh(\"data.hex\", data);").zipWithIndex) {
        Files.writeString(monitor.toPath, s"module IdentityMonitor(output io_value); $text\nendmodule\n")
        intercept[IllegalArgumentException] {
          RiscvSimConfig.elaborate(ModelKey(s"refuse$i"), work, SpinalConfig())(new Top(monitor.getPath))
        }
      }
    } finally org.apache.commons.io.FileUtils.deleteDirectory(work)
  }
}
