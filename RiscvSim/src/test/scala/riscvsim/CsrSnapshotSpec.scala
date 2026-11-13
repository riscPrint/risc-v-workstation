package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite

class CsrSnapshotSpec extends AnyFunSuite {
  def record(order: Int, value: Int): RvfiRecord = RvfiRecord(
    order = order, cycle = 1, insn = 0x13, trap = false, halt = false,
    intr = false, mode = 3, ixl = 2, rs1 = 0, rs1Rdata = 0,
    rs2 = 0, rs2Rdata = 0, rd = 0, rdWdata = 0, pc = order * 4,
    pcNext = order * 4 + 4, memAddr = 0, memRmask = 0, memWmask = 0,
    memRdata = 0, memWdata = 0, memFault = false,
    csrState = Map(0x340 -> BigInt(value)))

  test("each retirement retains its own CSR snapshot in the same cycle") {
    val path = Files.createTempFile("csr-slots", ".jsonl")
    val writer = new RvfiTraceWriter(path.toFile,
      ujson.Obj("xlen" -> 64, "csr_snapshot" -> ujson.Arr("0x340")))
    try {
      writer.write(record(0, 7))
      writer.write(record(1, 9))
    } finally writer.close()
    try {
      val rows = Files.readAllLines(path)
      assert(ujson.read(rows.get(0))("schema").str == "rvw.rvfi/2")
      assert(ujson.read(rows.get(1))("csr_state")("0x340").str == "0x7")
      assert(ujson.read(rows.get(2))("csr_state")("0x340").str == "0x9")
    } finally Files.deleteIfExists(path)
  }

  test("writer refuses a missing or undeclared snapshot") {
    val path = Files.createTempFile("csr-missing", ".jsonl")
    val writer = new RvfiTraceWriter(path.toFile,
      ujson.Obj("xlen" -> 64, "csr_snapshot" -> ujson.Arr("0x340")))
    try {
      intercept[IllegalArgumentException] { writer.write(record(0, 1).copy(csrState = Map.empty)) }
      intercept[IllegalArgumentException] { writer.write(record(0, 1).copy(csrState = Map(0x300 -> BigInt(1)))) }
      assert(writer.records == 0)
    } finally {
      writer.close()
      Files.deleteIfExists(path)
    }
  }
}
