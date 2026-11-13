package riscvsim

import java.io.File
import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite

class HartImagesSpec extends AnyFunSuite {
  private def elf(bias: Long) = new ElfFile(new BootImageSpec().image(), bias)
  test("N harts load shared memory with distinct entries and BSS") {
    val inputs = new HartImages(Seq(2 -> elf(0x1000), 4 -> elf(0x2000), 9 -> elf(0x3000)), 64)
    val memory = scala.collection.mutable.Map.empty[Long, Byte]
    inputs.load((a, d) => d.indices.foreach(i => memory(a + i) = d(i)))
    assert(memory(0x1100) == 42 && memory(0x2107) == 0 && memory(0x3100) == 42)
    assert(inputs.identity.arr.map(_("entry").str).distinct.size == 3)
  }
  test("identical segments load once; conflicting segments fail before loading") {
    val a = elf(0x1000)
    val shared = new HartImages(Seq(0 -> a, 1 -> a), 64)
    var calls = 0
    shared.load((_, _) => calls += 1)
    assert(calls == 2)
    intercept[IllegalArgumentException](new HartImages(Seq(0 -> a, 1 -> elf(0x1004)), 64))
    intercept[IllegalArgumentException](new HartImages(Seq(0 -> a, 0 -> a), 64))
    intercept[IllegalArgumentException](new HartImages(Seq(0 -> a, 1 -> a), 32))
  }
  test("manifest pins content and exact adapter hart set") {
    val a = elf(0)
    val p = Files.createTempFile("hart-inputs", ".json")
    val rows = ujson.Arr.from(Seq(0, 3).map(h => ujson.Obj(
      "hart" -> h, "elf" -> a.file.getPath, "elf_sha256" -> a.sha256)))
    Files.writeString(p, ujson.write(ujson.Obj("schema" -> "rvw.hart-images/1", "harts" -> rows)))
    try {
      assert(HartImages.capture(p.toFile, Seq(0, 3), 64).harts.size == 2)
      intercept[IllegalArgumentException](HartImages.capture(p.toFile, Seq(0, 1), 64))
      Files.write(a.file.toPath, Array[Byte](0))
      intercept[IllegalArgumentException](HartImages.capture(p.toFile, Seq(0, 3), 64))
    } finally Files.delete(p)
  }
  test("driver captures inputs before compile and includes manifest in replay") {
    val dir = Files.createTempDirectory("hart-driver").toFile
    val a = elf(0)
    val manifest = new File(dir, "harts.json")
    Files.writeString(manifest.toPath, ujson.write(ujson.Obj("schema" -> "rvw.hart-images/1",
      "harts" -> ujson.Arr.from(Seq(0, 1).map(h => ujson.Obj(
        "hart" -> h, "elf" -> a.file.getPath, "elf_sha256" -> a.sha256))))))
    val adapter = new CoreAdapter {
      type Model = Unit
      override def hartIds(config: String) = Seq(0, 1)
      def core = "hart-driver"
      def configs = Seq("test")
      def isa(config: String) = "rv64i"
      def xlen = 64
      def sourceDir = dir
      def compile(key: ModelKey, work: File, cache: File): Unit = {
        Files.write(a.file.toPath, Array[Byte](0)); ()
      }
      def run(model: Unit, job: RunJob, ctx: RunContext): RunOutcome = {
        var seen = false
        ctx.loadMemory((address, data) => if (address == 0x100 && data.head == 42) seen = true)
        assert(seen && ctx.hartImages.get.harts.size == 2)
        RunOutcome(Status.Timeout, 1, 0)
      }
    }
    try {
      val job = Cli.job(Map("elf" -> a.file.getPath, "out" -> new File(dir, "out").getPath,
        "hart-images" -> manifest.getPath, "seed" -> "7"), adapter, dir)
      val driver = new Driver(adapter)
      val result = driver.runJobs(Seq(job), 1).head
      assert(result("status").str == "timeout")
      assert(result("details")("hart_images").arr.size == 2)
      assert(driver.replay(job).contains("--hart-images"))
    } finally org.apache.commons.io.FileUtils.deleteDirectory(dir)
  }
}
