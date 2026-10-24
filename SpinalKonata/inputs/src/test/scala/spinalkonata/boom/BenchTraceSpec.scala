package spinalkonata.boom

import java.nio.{ByteBuffer, ByteOrder}
import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite

class BenchTraceSpec extends AnyFunSuite {
  for (result <- Seq(_root_.boom.sim.BoomSim.Fail(2), _root_.boom.sim.BoomSim.Timeout,
                     _root_.boom.sim.BoomSim.RvfiError(1))) {
    test(s"a real simulator outcome still fails after writing measurements: $result") {
      _root_.boom.sim.BoomSim.outcome = result
      try {
        intercept[IllegalArgumentException] { runFixture() }
      } finally _root_.boom.sim.BoomSim.outcome = _root_.boom.sim.BoomSim.Pass
    }
  }

  private def runFixture(): Unit = {
    val dir = Files.createTempDirectory("bench-failure")
    val elf = dir.resolve("input.elf")
    val bytes = new Array[Byte](64)
    val b = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
    b.put(0, 0x7f.toByte); b.put(1, 'E'.toByte); b.put(2, 'L'.toByte); b.put(3, 'F'.toByte)
    b.put(4, 2.toByte); b.put(5, 1.toByte); b.put(6, 1.toByte)
    b.putShort(0x10, 2.toShort); b.putShort(0x12, 243.toShort); b.putInt(0x14, 1)
    b.putShort(0x34, 64.toShort)
    Files.write(elf, bytes)
    try BenchTrace.main(Array(dir.resolve("out").toString, elf.toString))
    finally {
      val result = ujson.read(Files.readString(dir.resolve("out/input.elf/result.json")))
      assert(result("status").str == "error")
      assert(result("observed_status").str != "pass")
      assert(result("cache_key") == ujson.Null)
      assert(Files.size(dir.resolve("out/input.elf/report.json")) > 0)
    }
  }

  test("batch ELF identity is pinned before compilation and bound to the result") {
    val dir = Files.createTempDirectory("bench-capture")
    val path = dir.resolve("program.elf")
    val bytes = new Array[Byte](64)
    val b = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
    b.put(0, 0x7f.toByte); b.put(1, 'E'.toByte); b.put(2, 'L'.toByte); b.put(3, 'F'.toByte)
    b.put(4, 2.toByte); b.put(5, 1.toByte); b.put(6, 1.toByte)
    b.putShort(0x10, 2.toShort); b.putShort(0x12, 243.toShort); b.putInt(0x14, 1)
    b.putShort(0x34, 64.toShort)
    Files.write(path, bytes)
    val changed = bytes.clone(); changed(0x18) = 4
    _root_.boom.sim.BoomSim.beforeCompile = () => Files.write(path, changed)
    try {
      val stderr = new java.io.ByteArrayOutputStream()
      val outcome = Console.withErr(new java.io.PrintStream(stderr)) {
        scala.util.Try(BenchTrace.main(Array(dir.resolve("out").toString, path.toString)))
      }
      assert(stderr.toString("UTF-8").contains("C1 results are inconclusive and uncached"))
      val report = ujson.read(Files.readString(dir.resolve("out/program.elf/result.json")))
      assert(report("max_cycles").isInstanceOf[ujson.Num])
      assert(ProbeRun.loaded.sameElements(bytes))
      assert(report("elf_sha256").str == riscvsim.ElfFile.sha256(bytes))
      assert(report("inconclusive").str.startsWith("input_not_captured:compiled_model"))
      assert(outcome.isSuccess, outcome.failed.toOption.map(_.toString).getOrElse(""))
      assert(report("status").str == "error")
      assert(report("observed_status").str == "pass")
      assert(report("cache_key") == ujson.Null)
      val perf = ujson.read(Files.readString(dir.resolve("out/program.elf/report.json")))
      assert(perf("measurement_scope").str == "trace_only")
      assert(!perf.obj.contains("cross_check"))
      assert(perf("cache_key") == ujson.Null)
      assert(Files.size(dir.resolve("out/program.elf/report.txt")) > 0)
    } finally _root_.boom.sim.BoomSim.beforeCompile = () => ()
  }
}
