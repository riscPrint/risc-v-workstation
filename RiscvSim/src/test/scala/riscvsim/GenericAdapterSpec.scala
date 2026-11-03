package riscvsim

import java.io.File
import java.nio.{ByteBuffer, ByteOrder}
import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite

class GenericAdapterSpec extends AnyFunSuite {
  class Adapter(val xlen: Int) extends CoreAdapter {
    type Model = Unit
    var compiled = 0
    var executed = 0
    def core = s"test-rv$xlen"
    def configs = Seq("test")
    def isa(config: String) = s"rv${xlen}i"
    def sourceDir = new File(".")
    def compile(key: ModelKey, work: File, cache: File): Unit = { compiled += 1 }
    def run(model: Unit, job: RunJob, ctx: RunContext): RunOutcome = {
      executed += 1
      RunOutcome(Status.Fail, 1, 1, Some(7))
    }
  }
  for (xlen <- Seq(32, 64)) {
    test(s"RV$xlen store lanes update only the addressed bytes and masks") {
      val width = new Adapter(xlen).busBytes
      for (base <- Seq(0x1000L, 0x1003L); size <- Seq(1, 2, 4, 8) if size <= width;
           offset <- 0 until 16 if (base + offset) % size == 0) {
        val t = new ToHost(base, width)
        val m = new MemWords(base, 2, width)
        val addr = base + offset
        val data = BigInt(if (width == 4) "44332211" else "8877665544332211", 16)
        val bytes = Array.fill(16)(0)
        val masks = Array.fill(2)(0)
        // Independent oracle: bus byte i has value 0x11 * (i + 1).
        for (i <- 0 until size if offset + i < 16) {
          bytes(offset + i) = 0x11 * (((addr + i) % width).toInt + 1)
          masks((offset + i) / 8) |= 1 << ((offset + i) % 8)
        }
        def word(start: Int): BigInt = (0 until 8).map(i => BigInt(bytes(start + i)) << (8 * i)).sum
        t.onStore(addr, Integer.numberOfTrailingZeros(size), data)
        m.onStore(addr, Integer.numberOfTrailingZeros(size), data)
        assert(t.value == word(0))
        assert(m.words.toSeq == Seq(word(0), word(8)))
        assert(m.masks.toSeq == masks.toSeq)
        assert(m.complete == masks.forall(_ == 255))
      }
      val split = new MemWords(0x2000, 1, width)
      for (off <- 0 until 8 by width) split.onStore(0x2000 + off, Integer.numberOfTrailingZeros(width), 1)
      assert(split.complete && split.masks.toSeq == Seq(255))
      val pass = new ToHost(0x2000, width)
      assert(pass.onStore(0x2000, Integer.numberOfTrailingZeros(width), 1).contains(ToHost.Pass))
      assert(pass.onStore(0x3000, 0, 7).isEmpty)
    }
    for (elfXlen <- Seq(32, 64)) test(s"RV$xlen driver checks ELF$elfXlen before compile and execution") {
      val dir = Files.createTempDirectory("xlen-check").toFile
      try {
        val file = new File(dir, "input.elf")
        val header = ByteBuffer.allocate(64).order(ByteOrder.LITTLE_ENDIAN)
        header.put(Array[Byte](0x7f, 'E'.toByte, 'L'.toByte, 'F'.toByte,
          (if (elfXlen == 32) 1 else 2).toByte, 1))
        header.putShort(0x12, 243.toShort)
        Files.write(file.toPath, header.array())
        val adapter = new Adapter(xlen)
        val job = RunJob(file, new File(dir, "out"), "test", 1, false, 100, None,
          false, false, false, None, None, false, false)
        val result = new Driver(adapter).runOne(job)
        assert(ujson.read(new File(job.out, "result.json"))("status") == result("status"))
        if (xlen == elfXlen) {
          assert(result("status").str == "fail")
          assert(adapter.compiled == 1 && adapter.executed == 1)
        } else {
          assert(result("status").str == "error")
          assert(result("message").str.contains(s"ELF XLEN $elfXlen does not match adapter XLEN $xlen"))
          assert(result("cycles").num == 0 && result("instret").num == 0)
          assert(adapter.compiled == 0 && adapter.executed == 0)
        }
      } finally org.apache.commons.io.FileUtils.deleteDirectory(dir)
    }
  }
}
