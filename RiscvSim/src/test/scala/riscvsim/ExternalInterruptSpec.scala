package riscvsim

import java.nio.file.Files
import org.scalatest.funsuite.AnyFunSuite

class ExternalInterruptSpec extends AnyFunSuite {
  test("external evidence is declared and ordered at the emitted retirement boundary") {
    val path = Files.createTempFile("external-irq", ".jsonl")
    val writer = new RvfiTraceWriter(path.toFile, ujson.Obj("xlen" -> 64,
      "external_interrupts" -> ujson.Obj("schema" -> "rvw.external-interrupts/1")))
    writer.externalInterrupt(1, "pins", ujson.Obj("levels" -> "0x800"))
    writer.externalInterrupt(1, "taken", ujson.Obj("cause" -> "0x800000000000000b"))
    writer.end(2, "pass")
    writer.close()
    val rows = Files.readAllLines(path).toArray.map(x => ujson.read(x.toString))
    assert(rows(1)("seq").num == 0)
    assert(rows(2)("seq").num == 1)
    assert(rows(2)("before_order").num == 0)
  }

  test("undeclared external evidence is refused") {
    val path = Files.createTempFile("external-irq-bad", ".jsonl")
    val writer = new RvfiTraceWriter(path.toFile, ujson.Obj("xlen" -> 64))
    try intercept[IllegalArgumentException] {
      writer.externalInterrupt(1, "pins", ujson.Obj("levels" -> "0x0"))
    } finally writer.close()
  }
}
