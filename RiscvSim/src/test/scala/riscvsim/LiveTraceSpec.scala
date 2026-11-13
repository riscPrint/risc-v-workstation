package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite

class LiveTraceSpec extends AnyFunSuite {
  test("live trace flushes the header and events before close") {
    val path = Files.createTempFile("rvfi-live", ".jsonl")
    val writer = new RvfiTraceWriter(path.toFile, ujson.Obj("xlen" -> 64), flushEachRecord = true)
    def lines = Files.readAllLines(path).size()
    try {
      assert(lines == 1)
      val record = RvfiRecord(order = 0, cycle = 1, insn = 0x13, trap = false,
        halt = false, intr = false, mode = 3, ixl = 2, rs1 = 0, rs1Rdata = 0,
        rs2 = 0, rs2Rdata = 0, rd = 0, rdWdata = 0, pc = 0, pcNext = 4,
        memAddr = 0, memRmask = 0, memWmask = 0, memRdata = 0, memWdata = 0,
        memFault = false)
      writer.write(record)
      assert(lines == 2)
      writer.irq(1, 0)
      assert(lines == 3)
      writer.trap(2, 11, 0, false)
      assert(lines == 4)
      writer.end(3, "pass")
      assert(lines == 5)
    } finally {
      writer.close()
      Files.deleteIfExists(path)
    }
  }
  test("custom transport observes flushed C2 and cannot resume") {
    val path = Files.createTempFile("rvfi-dpi", ".jsonl")
    val seen = scala.collection.mutable.ArrayBuffer.empty[String]
    val observe: String => Unit = line => {
      assert(Files.readAllLines(path).get(seen.size) == line)
      seen += line
    }
    val writer = new RvfiTraceWriter(path.toFile, ujson.Obj("xlen" -> 32),
      observe = Some(observe))
    try {
      assert(seen.size == 1)
      writer.irq(1, 0)
      writer.end(2, "pass")
      assert(seen.size == 3)
    } finally {
      writer.close()
      Files.deleteIfExists(path)
    }
    intercept[IllegalArgumentException] {
      new RvfiTraceWriter(path.toFile, ujson.Obj("xlen" -> 32),
        resume = Some(ujson.Obj()), observe = Some(observe))
    }
  }

}
