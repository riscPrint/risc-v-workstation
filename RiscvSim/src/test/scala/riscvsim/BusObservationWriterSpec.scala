package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite

class BusObservationWriterSpec extends AnyFunSuite {
  test("accepted channels keep independent identity, common clock, data and terminal status") {
    val path = Files.createTempFile("bus-observer", ".jsonl")
    val w = new BusObservationWriter(path.toFile, ujson.Obj("elf_sha256" -> "expected"), 8)
    try {
      w.sample("a", 3, "source" -> ujson.Num(1), "data" -> ujson.Str("0x12"))
      w.sample("d", 3, "source" -> ujson.Num(1), "denied" -> ujson.Bool(false))
      intercept[IllegalArgumentException](w.sample("a", 2))
      intercept[IllegalArgumentException](w.sample("z", 4))
      intercept[IllegalArgumentException](w.sample("a", 4, "cycle" -> ujson.Num(5)))
      w.end(5, "timeout")
    } finally w.close()
    try {
      val rows = Files.readAllLines(path).toArray.toSeq.map(s => ujson.read(s.toString))
      assert(rows.head("independent").bool)
      assert(rows.head("bus_bytes").num == 8)
      assert(rows(1)("data").str == "0x12")
      assert(rows(2)("sequence").str == "1")
      assert(rows.last("status").str == "timeout")
    } finally Files.delete(path)
  }
}
