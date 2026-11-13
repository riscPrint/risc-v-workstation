package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite

class EnvironmentTraceSpec extends AnyFunSuite {
  test("environment capability selects C2/2 without requiring FP state") {
    val path = Files.createTempFile("environment", ".jsonl")
    val writer = new RvfiTraceWriter(path.toFile, ujson.Obj("xlen" -> 32,
      "capabilities" -> ujson.Arr("environment"), "environment" -> "retirement-ordered/1"))
    try {
      writer.environment(1, 0, "pins", ujson.Obj("levels" -> "0x8"))
      writer.trap(2, BigInt("80000003",16), 0, true, Some(0))
      writer.write(RvfiRecord(0, 3, 0x13, false, false, true, 3, 1,
        0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, false))
    } finally writer.close()
    try {
      val rows = Files.readAllLines(path)
      assert(ujson.read(rows.get(0))("schema").str == "rvw.rvfi/2")
      assert(ujson.read(rows.get(1))("cycle").num == 1)
      assert(ujson.read(rows.get(1))("before_order").num == 0)
      assert(ujson.read(rows.get(2))("before_order").num == 0)
      assert(ujson.read(rows.get(3))("order").num == 0)
    } finally Files.deleteIfExists(path)
  }
}
